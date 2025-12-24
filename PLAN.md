# Inchive

## Vision
A privacy-first personal AI OS that ingests conversation history (ChatGPT, Claude), creates a "Personal Knowledge Graph," and provides a unified interface for search, chat, and action.

## Phase 1: Ingest & Unify (Current Focus)
- [x] **Unified Schema Definition**: Define Python dataclasses/models for `Conversation`, `Turn`, `Claim`, `Entity`, `Artifact`, `Decision`, `Task`.
    - See `schema.py`: Complete with Node/Edge types, CodeBlock, Link extraction utilities
- [x] **Enhanced Ingestion**: 
    - [x] Refactor `ingest.py` to map raw JSON (Anthropic/OpenAI) into the Unified Schema.
    - [x] Extract metadata (code blocks, links, images) via `extract_code_blocks()` and `extract_links()`.
- [x] **Storage Layer Upgrade**:
    - [x] Move beyond simple SQLite FTS5: See `storage.py` with KnowledgeStore class.
    - [x] Design schema for storing the Knowledge Graph (Nodes & Edges).
    - [x] Add `--kg` flag to `index.py` for building knowledge graph database.

## Phase 2: Personal Memory Index (Embeddings & RAG)
- [x] **Vector Store Integration**:
    - [x] Select local vector DB: `sqlite-vec` with fallback cosine similarity.
    - [x] Add Cloudflare Vectorize support for edge deployment.
    - [x] Implement embedding generation for Turns via `embeddings.py`.
    - [x] Support multiple providers: local (sentence-transformers), Cloudflare Workers AI, OpenAI.
    - [x] Add `--embed` and `--full` flags to `index.py`.
- [ ] **Clustering Engine**:
    - [ ] Topic Clusters (Embeddings + Clustering algo).
    - [ ] Project Clusters (Keyword/NER based).
- [ ] **Memory Layers**:
    - [x] Raw Archive (Exact search via FTS5).
    - [ ] Derived Notes (Summarization pipeline).
    - [ ] Stable Memory (User-approved high-value items).

## Phase 3: The Personal Model (RAG & Agent)
- [ ] **LLM Integration**:
    - [ ] Setup client for Local LLM (Ollama) or Cloud (OpenAI/Claude).
    - [ ] Build "System Prompt" generation based on profile.
- [ ] **RAG Pipeline**:
    - [ ] Retrieval: Vector search + Graph traversal.
    - [ ] Citation system (linking back to source chat).

## Phase 4: UX & Modes
- [ ] **Home Screen**: Dashboard for Active Projects, Open Loops.
- [ ] **Engagement Modes**:
    - [ ] Ask Mode (QA).
    - [ ] Build Mode (Drafting).
    - [ ] "Time Machine" Slider.

---

## Architecture Options

### Option A: Self-Hosted (Open Source)
- **Backend**: Python (Flask)
- **Database**: SQLite (FTS5 + Knowledge Graph)
- **Vectors**: sqlite-vec (local) or Cloudflare Vectorize
- **Embeddings**: sentence-transformers (local) or API-based
- **Cost**: $0

### Option B: Inchive Cloud (Commercial)
- **Edge Compute**: Cloudflare Workers
- **AI**: Workers AI (@cf/baai/bge, @cf/meta/llama-3.1)
- **Vectors**: Cloudflare Vectorize (768D, 5M vectors free)
- **Database**: Cloudflare D1 (SQLite at edge)
- **Storage**: Cloudflare R2 (S3-compatible)
- **Cost**: ~$0.70/user/month at scale

See `docs/SELF_HOST_VS_CLOUD.md` and `docs/CLOUD_ARCHITECTURE.md` for details.

---

## Cloudflare Stack Summary

| Component | Service | Free Tier |
|-----------|---------|-----------|
| Compute | Workers | 100K req/day |
| AI Inference | Workers AI | 10K neurons/day |
| Vector DB | Vectorize | 5M vectors, 30M queries/mo |
| SQL DB | D1 | 5GB, 5M reads/day |
| Object Storage | R2 | 10GB, 10M reads/mo |
| KV Cache | KV | 100K reads/day |

**Estimated margin at 10K users:** 90%+ ($40K/mo revenue, $4K/mo costs)


