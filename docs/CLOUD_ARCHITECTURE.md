# Inchive Cloud Architecture

Technical architecture for running Inchive as a commercial cloud service on Cloudflare.

---

## Overview

Inchive Cloud is built entirely on Cloudflare's edge infrastructure for:
- **Global low-latency**: 300+ edge locations
- **Cost efficiency**: Pay-per-use, generous free tiers
- **Privacy**: Data sovereignty options, no third-party dependencies
- **Simplicity**: Single platform for compute, storage, AI

---

## Stack Components

### 1. Edge Compute: Cloudflare Workers

**Purpose:** API endpoints, authentication, business logic

```
workers/
├── api-gateway.js      # Main API router, auth, rate limiting
├── auth.js             # OAuth flows, session management
├── search.js           # FTS + semantic search endpoints
├── ingest.js           # File upload, parsing, indexing
├── chat.js             # RAG-powered chat interface
└── webhooks.js         # Auto-sync from Claude/ChatGPT APIs
```

**Pricing:**
- Free: 100K requests/day
- Paid: $5/mo for 10M requests

### 2. AI Inference: Workers AI

**Purpose:** Embedding generation, LLM for RAG

**Models Used:**
| Model | Purpose | Dimensions |
|-------|---------|------------|
| @cf/baai/bge-base-en-v1.5 | Text embeddings | 768 |
| @cf/meta/llama-3.1-8b-instruct | RAG responses | N/A |
| @cf/openai/whisper | Audio transcription | N/A |

**Pricing:**
- Free: 10K neurons/day
- Paid: $0.011 per 1K neurons

### 3. Vector Database: Vectorize

**Purpose:** Semantic similarity search

**Configuration:**
```toml
[[vectorize]]
binding = "CONVERSATIONS"
index_name = "inchive-prod"
# 768 dimensions (BGE), cosine metric
```

**Schema per vector:**
```json
{
  "id": "turn-uuid",
  "values": [0.123, -0.456, ...],  // 768D
  "metadata": {
    "user_id": "user-123",
    "conv_id": "conv-456",
    "source": "anthropic",
    "role": "assistant",
    "timestamp": 1703520000,
    "title": "Python async patterns"
  }
}
```

**Pricing:**
- Free: 5M vectors, 30M queries/month
- Paid: $0.01/1M queries, $0.05/1M stored vectors

### 4. Relational Database: D1 (SQLite)

**Purpose:** User accounts, metadata, full-text search

**Schema:**
```sql
-- Users
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    created_at INTEGER,
    plan TEXT DEFAULT 'free',
    settings TEXT  -- JSON
);

-- Conversations (metadata only, content in R2)
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    source TEXT,  -- 'anthropic', 'openai'
    title TEXT,
    created_at INTEGER,
    turn_count INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- FTS for keyword search
CREATE VIRTUAL TABLE conversations_fts USING fts5(
    title, content, source
);

-- API keys for programmatic access
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    key_hash TEXT,
    name TEXT,
    last_used INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Pricing:**
- Free: 5GB storage, 5M reads/day
- Paid: $0.75/M reads, $1/M writes

### 5. Object Storage: R2

**Purpose:** Raw conversation archives, user uploads

**Structure:**
```
r2://inchive-data/
├── users/{user_id}/
│   ├── imports/
│   │   ├── anthropic-2024-01-15.json
│   │   └── chatgpt-2024-01-20.json
│   ├── exports/
│   │   └── full-backup-2024-02.zip
│   └── profile.json
└── system/
    └── models/  # Cached model files if needed
```

**Pricing:**
- Free: 10GB storage, 10M reads/month
- Paid: $0.015/GB storage, $0.36/M Class A ops

### 6. Key-Value: KV

**Purpose:** Sessions, caching, feature flags

```javascript
// Session storage
await env.SESSIONS.put(`session:${token}`, JSON.stringify({
  userId: user.id,
  expiresAt: Date.now() + 3600000
}), { expirationTtl: 3600 });

// Query cache
await env.CACHE.put(`search:${hash}`, JSON.stringify(results), {
  expirationTtl: 300  // 5 min cache
});
```

**Pricing:**
- Free: 100K reads/day, 1K writes/day
- Paid: $0.50/M reads, $5/M writes

---

## Request Flow

### 1. Search Query

```
User → Workers (API Gateway)
         │
         ├─→ Auth check (KV session)
         │
         ├─→ Rate limit check (Durable Objects)
         │
         └─→ Search Worker
               │
               ├─→ Generate embedding (Workers AI)
               │
               ├─→ Vector search (Vectorize)
               │
               ├─→ FTS fallback (D1)
               │
               └─→ Merge & rank results
                     │
                     └─→ Return to user
```

### 2. Import Conversation Export

```
User uploads file → Workers (Ingest)
                       │
                       ├─→ Store raw file (R2)
                       │
                       ├─→ Parse conversations
                       │
                       ├─→ For each turn:
                       │     ├─→ Generate embedding (Workers AI)
                       │     ├─→ Store vector (Vectorize)
                       │     └─→ Store metadata (D1)
                       │
                       └─→ Update user stats
                             │
                             └─→ Return import summary
```

### 3. RAG Chat

```
User asks question → Workers (Chat)
                       │
                       ├─→ Generate query embedding
                       │
                       ├─→ Vector search for context
                       │
                       ├─→ Build prompt with retrieved context
                       │
                       ├─→ Stream LLM response (Workers AI)
                       │
                       └─→ Return with citations
```

---

## API Design

### Endpoints

```
POST   /api/v1/auth/login        # OAuth start
GET    /api/v1/auth/callback     # OAuth callback
DELETE /api/v1/auth/logout       # Logout

GET    /api/v1/search            # Semantic + FTS search
POST   /api/v1/search            # Complex queries

GET    /api/v1/conversations     # List conversations
POST   /api/v1/conversations     # Import new
GET    /api/v1/conversations/:id # Get full conversation
DELETE /api/v1/conversations/:id # Delete

POST   /api/v1/chat              # RAG chat
GET    /api/v1/chat/history      # Chat history

POST   /api/v1/import/upload     # Upload export file
GET    /api/v1/import/status/:id # Import progress

GET    /api/v1/analytics         # Usage stats
```

### Authentication

```javascript
// API Key auth
const apiKey = request.headers.get('Authorization')?.replace('Bearer ', '');
const keyHash = await sha256(apiKey);
const key = await env.DB.prepare(
  'SELECT * FROM api_keys WHERE key_hash = ?'
).bind(keyHash).first();

// Session auth (web)
const sessionToken = getCookie(request, 'session');
const session = await env.SESSIONS.get(`session:${sessionToken}`);
```

---

## Cost Estimates

### Per-User Monthly Costs (Pro tier user)

| Resource | Usage | Cost |
|----------|-------|------|
| Workers requests | 10K | $0.005 |
| Workers AI (embeddings) | 5K neurons | $0.05 |
| Workers AI (LLM) | 50K neurons | $0.55 |
| Vectorize storage | 50K vectors | $0.0025 |
| Vectorize queries | 1K | $0.00001 |
| D1 reads | 100K | $0.075 |
| D1 writes | 10K | $0.01 |
| R2 storage | 100MB | $0.0015 |
| **Total** | | **~$0.70/user/mo** |

### At Scale (10K users)

| Tier | Users | Revenue | Costs | Margin |
|------|-------|---------|-------|--------|
| Free | 7,000 | $0 | $2,100 | -$2,100 |
| Pro ($12) | 2,500 | $30,000 | $1,750 | $28,250 |
| Team ($29) | 500 | $14,500 | $350 | $14,150 |
| **Total** | 10,000 | $44,500 | $4,200 | **$40,300** |

---

## Security

### Data Encryption

```javascript
// Encrypt sensitive data before storage
async function encryptForUser(data, userId) {
  const key = await deriveKey(env.MASTER_KEY, userId);
  return await encrypt(data, key);
}

// User-specific encryption key derivation
async function deriveKey(masterKey, userId) {
  const encoder = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    'raw', encoder.encode(masterKey),
    'PBKDF2', false, ['deriveBits', 'deriveKey']
  );
  return await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: encoder.encode(userId), iterations: 100000, hash: 'SHA-256' },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false, ['encrypt', 'decrypt']
  );
}
```

### Data Isolation

- Each user's vectors have `user_id` in metadata
- All queries filter by authenticated user_id
- R2 paths are user-scoped
- D1 queries always include user_id WHERE clause

---

## Deployment

### Wrangler Configuration

```toml
name = "inchive-api"
main = "src/index.js"
compatibility_date = "2024-01-01"

[ai]
binding = "AI"

[[d1_databases]]
binding = "DB"
database_name = "inchive-prod"
database_id = "xxx"

[[vectorize]]
binding = "VECTORS"
index_name = "inchive-prod"

[[r2_buckets]]
binding = "STORAGE"
bucket_name = "inchive-data"

[[kv_namespaces]]
binding = "SESSIONS"
id = "xxx"

[[kv_namespaces]]
binding = "CACHE"
id = "xxx"

[vars]
ENVIRONMENT = "production"

# Secrets (wrangler secret put)
# MASTER_KEY
# OAUTH_CLIENT_SECRET
```

### CI/CD

```yaml
# .github/workflows/deploy.yml
name: Deploy to Cloudflare
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          command: deploy
```

---

## Monitoring

### Cloudflare Analytics

- Request volume and latency
- Error rates by endpoint
- Geographic distribution
- Cache hit rates

### Custom Metrics

```javascript
// Log to Analytics Engine
env.ANALYTICS.writeDataPoint({
  blobs: [request.cf.country, userId],
  doubles: [responseTime, resultCount],
  indexes: [endpoint]
});
```

---

## Migration Path

### From Self-Hosted to Cloud

```python
# Export from local
from storage import KnowledgeStore
store = KnowledgeStore("./index/knowledge.db")

# Stream to cloud API
import requests
for conv in store.get_all_conversations():
    requests.post("https://api.inchive.ai/v1/import", 
                  json=conv.to_dict(),
                  headers={"Authorization": f"Bearer {api_key}"})
```

### From Cloud to Self-Hosted

```bash
# Download your data
curl -H "Authorization: Bearer $KEY" \
  https://api.inchive.ai/v1/export/full \
  -o my-data.zip

# Import to local
unzip my-data.zip -d ./files
python index.py --export ./files --out ./index --full
```

---

*Privacy-first. Open-core. Your data, your choice.*

