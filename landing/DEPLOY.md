# Inchive Cloudflare Deployment

This guide covers deploying both the landing page and semantic search API to Cloudflare Workers.

## Prerequisites
- Node.js installed (v18+)
- `npm install -g wrangler` (v3+)

---

## Landing Page Worker

### 1. Login to Cloudflare
```bash
wrangler login
```

### 2. Create the Database (KV Namespace)
```bash
wrangler kv:namespace create INCHIVE_WAITLIST
```

Copy the output ID and update `wrangler.toml`:
```toml
kv_namespaces = [
  { binding = "INCHIVE_WAITLIST", id = "YOUR_ID_HERE" }
]
```

### 3. Set Admin Password
```bash
wrangler secret put ADMIN_PASSWORD
```

### 4. Deploy
```bash
cd landing
wrangler deploy
```

Your landing page will be live at `https://inchive-landing.<account>.workers.dev`

---

## Semantic Search Worker (Vector Search API)

The search worker provides AI-powered semantic search using:
- **Workers AI** for embedding generation (@cf/baai/bge-base-en-v1.5, 768D)
- **Vectorize** for vector storage and similarity search

### 1. Create Vectorize Index
```bash
wrangler vectorize create inchive-conversations --dimensions=768 --metric=cosine
```

### 2. Set API Secret
```bash
wrangler secret put API_SECRET -c wrangler-search.toml
```

### 3. Deploy Search Worker
```bash
wrangler deploy -c wrangler-search.toml
```

### API Endpoints

**POST /api/search** - Semantic search
```json
{
  "query": "How do I implement OAuth?",
  "limit": 10,
  "filter": { "source": "anthropic" }
}
```

**POST /api/embed** - Generate embeddings
```json
{
  "texts": ["Hello world", "How are you?"]
}
```

**POST /api/upsert** - Index vectors (requires `Authorization: Bearer <API_SECRET>`)
```json
{
  "vectors": [
    { "id": "turn-123", "values": [...], "metadata": { "title": "..." } }
  ]
}
```

**GET /api/stats** - Get index statistics

---

## Pricing (Cloudflare Free Tier)

| Service | Free Tier |
|---------|-----------|
| Workers | 100K requests/day |
| Workers AI | 10K neurons/day |
| Vectorize | 5M vectors, 30M queries/month |
| KV | 100K reads/day, 1K writes/day |


