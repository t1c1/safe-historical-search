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
- [ ] **Vector Store Integration**:
    - [ ] Select local vector DB (e.g., ChromaDB, LanceDB, or `sqlite-vec`).
    - [ ] Implement embedding generation for Turns and Conversations.
- [ ] **Clustering Engine**:
    - [ ] Topic Clusters (Embeddings + Clustering algo).
    - [ ] Project Clusters (Keyword/NER based).
- [ ] **Memory Layers**:
    - [ ] Raw Archive (Exact search - already partially done).
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

## Architecture
- **Backend**: Python (Flask) -> migrating to more robust service structure?
- **Database**: SQLite (Metadata/Graph/FTS) + Vector Store (Embeddings).
- **Processing**: Local pipeline for ingestion and embedding.


