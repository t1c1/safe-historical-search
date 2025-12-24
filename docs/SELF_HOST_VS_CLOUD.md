# Inchive: Self-Hosted vs Cloud

Two paths to semantic search over your AI conversation history.

---

## Option 1: DIY Self-Hosted (This Repo)

**Best for:** Privacy maximalists, developers, those with existing infrastructure.

### Quick Start

```bash
git clone https://github.com/t1c1/safe-historical-search.git
cd safe-historical-search

# Copy your exports
cp ~/Downloads/anthropic-data/*.json ./files/
cp ~/Downloads/chatgpt-export/*.json ./files/

# Build full index (FTS + Knowledge Graph + Vectors)
pip install -r requirements.txt
pip install sentence-transformers sqlite-vec  # Optional: for semantic search

python index.py --export ./files --out ./index --full

# Start server
python server.py --db ./index/chatgpt.db
```

### What You Get

| Feature | Implementation |
|---------|---------------|
| Full-text search | SQLite FTS5 (instant) |
| Knowledge Graph | SQLite (nodes/edges) |
| Semantic search | sqlite-vec + sentence-transformers |
| Embeddings | Local: all-MiniLM-L6-v2 (384D) |
| Privacy | 100% local, zero cloud |
| Cost | $0 (your hardware) |

### DIY Infrastructure Options

**Embedding Providers:**
```python
from embeddings import get_embedder

# Local (free, private, 384D)
embedder = get_embedder("local")

# Cloudflare Workers AI ($0.011/1K after free tier, 768D)
embedder = get_embedder("cloudflare", account_id="...", api_token="...")

# OpenAI ($0.02/1M tokens, 1536D)
embedder = get_embedder("openai", api_key="...")
```

**Vector Storage:**
```python
from vector_store import get_vector_store

# Local SQLite (free, private)
store = get_vector_store("sqlite", db_path="./vectors.db", dimensions=384)

# Cloudflare Vectorize (5M vectors free, 31ms latency)
store = get_vector_store("cloudflare", index_name="inchive", ...)
```

### Self-Hosted Costs

| Component | Option | Cost |
|-----------|--------|------|
| Compute | Your laptop/server | $0 |
| Embeddings | sentence-transformers | $0 (local GPU/CPU) |
| Embeddings | Cloudflare Workers AI | Free 10K/day, then $0.011/1K |
| Embeddings | OpenAI | $0.02/1M tokens |
| Vector DB | sqlite-vec | $0 |
| Vector DB | Cloudflare Vectorize | Free 5M vectors |
| Hosting | Cloudflare Workers | Free 100K req/day |

**Total for typical use:** $0/month

### Pros & Cons

**Pros:**
- Complete privacy (data never leaves your machine)
- Zero ongoing cost
- Full customization
- Works offline
- No vendor lock-in

**Cons:**
- Requires technical setup
- You manage updates/maintenance
- No mobile app
- Single-user focus

---

## Option 2: Inchive Cloud (Commercial Service)

**Best for:** Teams, non-technical users, those wanting managed experience.

### What Inchive Cloud Could Offer

```
https://app.inchive.ai
```

| Feature | Description |
|---------|-------------|
| One-click import | Drag-drop your exports, we handle the rest |
| Web + Mobile apps | Search anywhere, sync across devices |
| Team collaboration | Shared knowledge bases with permissions |
| Auto-sync | Connect accounts, auto-import new conversations |
| Advanced RAG | Ask questions, get answers with citations |
| API access | Build integrations, automate workflows |
| Enterprise SSO | SAML, OIDC, team management |

### Cloud Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Inchive Cloud                        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Web App   │  │ Mobile Apps │  │    API      │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│         └────────────────┼────────────────┘             │
│                          │                              │
│  ┌───────────────────────┴───────────────────────┐     │
│  │           Cloudflare Workers (Edge)           │     │
│  │  • Auth  • Rate Limiting  • Caching           │     │
│  └───────────────────────┬───────────────────────┘     │
│                          │                              │
│  ┌───────────────────────┴───────────────────────┐     │
│  │              AI Pipeline                       │     │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────┐       │     │
│  │  │Workers  │  │Vectorize │  │   D1    │       │     │
│  │  │   AI    │  │ (768D)   │  │ (SQLite)│       │     │
│  │  └─────────┘  └──────────┘  └─────────┘       │     │
│  └───────────────────────────────────────────────┘     │
│                                                         │
│  ┌───────────────────────────────────────────────┐     │
│  │              Storage (R2)                      │     │
│  │  • Encrypted conversation archives             │     │
│  │  • User files and exports                      │     │
│  └───────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### Potential Pricing Tiers

| Tier | Price | Includes |
|------|-------|----------|
| **Free** | $0/mo | 1,000 conversations, basic search, web only |
| **Pro** | $12/mo | Unlimited convos, semantic search, mobile, API |
| **Team** | $29/user/mo | Shared workspaces, permissions, priority support |
| **Enterprise** | Custom | SSO, dedicated instance, SLA, on-prem option |

### Cloud vs Self-Hosted Comparison

| Aspect | Self-Hosted | Inchive Cloud |
|--------|-------------|---------------|
| Setup time | 30 min (technical) | 2 min (drag-drop) |
| Privacy | Maximum (local only) | Strong (E2E encrypted) |
| Cost | $0 | $0-29/mo |
| Mobile access | No | Yes |
| Auto-sync | No | Yes (with OAuth) |
| Team features | No | Yes |
| RAG/Chat | DIY | Built-in |
| Maintenance | You | Managed |
| Offline | Yes | Limited |

---

## Hybrid Approach

Use self-hosted for personal/sensitive data, cloud for team collaboration:

```python
# Personal (local)
personal_store = get_vector_store("sqlite", db_path="./personal.db")

# Team (cloud)
team_store = get_vector_store("cloudflare", index_name="team-knowledge")

# Federated search
def search_all(query):
    personal_results = personal_store.search(query)
    team_results = team_store.search(query)
    return merge_and_rank(personal_results, team_results)
```

---

## Market Context

### Similar Products

| Product | Focus | Pricing |
|---------|-------|---------|
| Rewind AI | Screen recording + search | $19/mo |
| Limitless | Wearable + meeting memory | $99 device + $19/mo |
| Notion AI | Workspace search | $10/mo addon |
| Mem.ai | Personal knowledge | $15/mo |
| **Inchive** | AI conversation history | Free / $12/mo |

### Differentiation

1. **Privacy-first**: Open-source core, self-host option always available
2. **Multi-provider**: Claude + ChatGPT + (future) Gemini, Llama, etc.
3. **Knowledge Graph**: Not just search, but relationships and insights
4. **Subsidiarity**: Your data, your control, your choice of deployment

---

## Getting Started

### Self-Hosted (Today)
```bash
git clone https://github.com/t1c1/safe-historical-search.git
./quickstart.sh
```

### Cloud Waitlist
```
https://inchive.ai
```

---

*"Technology at the service of the person."*

