import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Tuple, List
from ingest import (
    parse_conversations, parse_projects, parse_users, 
    parse_chatgpt_conversations, parse_chatgpt_user,
    parse_conversations_unified, parse_chatgpt_unified
)
from schema import SourceType
from storage import KnowledgeStore


def ensure_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS docs(
            id TEXT PRIMARY KEY,
            conv_id TEXT,
            title TEXT,
            role TEXT,
            ts REAL,
            date TEXT,
            source TEXT,
            content TEXT,
            account TEXT
        )
        """
    )
    # Migration: add 'account' column if missing on older databases
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(docs)").fetchall()]
        if "account" not in cols:
            conn.execute("ALTER TABLE docs ADD COLUMN account TEXT")
            conn.execute("UPDATE docs SET account = COALESCE(account, 'default')")
            conn.commit()
    except Exception:
        pass
    # Migration: ensure docs_fts has 'account' column, rebuild if needed
    try:
        row = conn.execute("SELECT sql FROM sqlite_schema WHERE type='table' AND name='docs_fts'").fetchone()
        if row and row[0] and ("account" not in row[0]):
            conn.execute("DROP TABLE IF EXISTS docs_fts")
            conn.commit()
    except Exception:
        pass
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
            content, title, role, source, conv_id, ts, date, account, doc_id UNINDEXED, tokenize='porter'
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_date ON docs(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_account ON docs(account)")
    # If FTS was recreated, repopulate from docs when empty
    try:
        fts_count = conn.execute("SELECT COUNT(*) FROM docs_fts").fetchone()[0]
        if fts_count == 0:
            conn.execute(
                """
                INSERT INTO docs_fts(rowid, content, title, role, source, conv_id, ts, date, account, doc_id)
                SELECT rowid, content, title, role, source, conv_id, CAST(ts AS TEXT), date, COALESCE(account, 'default'), id
                FROM docs
                """
            )
    except Exception:
        pass
    conn.commit()
    return conn


def ts_to_date(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return None


def add_doc(conn: sqlite3.Connection, *, id, conv_id, title, role, ts, source, content, account: str) -> None:
    date_str = ts_to_date(ts)
    conn.execute(
        """INSERT OR REPLACE INTO docs(id, conv_id, title, role, ts, date, source, content, account)
            VALUES (?,?,?,?,?,?,?,?,?)""",
        (id, conv_id, title, role, ts or 0.0, date_str, source, content or "", account or "default"),
    )
    conn.execute(
        """INSERT INTO docs_fts(rowid, content, title, role, source, conv_id, ts, date, account, doc_id)
            VALUES ((SELECT rowid FROM docs WHERE id=?),?,?,?,?,?,?,?,?,?)""",
        (id, content or "", title or "", role or "", source or "", conv_id or "", str(ts or 0.0), date_str or "", account or "default", id),
    )


def _parsers_for_export(export_dir: Path) -> Iterable[Tuple[str, Iterable[dict]]]:
    # Look for all conversation files (conversations.json, conversations 2.json, etc.)
    import glob
    conversation_files = list(export_dir.glob("conversations*.json"))
    
    for conv_file in conversation_files:
        # Try to detect format by reading a small sample
        try:
            with open(conv_file, 'r', encoding='utf-8') as f:
                sample = f.read(2048)  # Read first 2KB for better detection
                if '"mapping"' in sample and '"author"' in sample:
                    # Looks like ChatGPT format
                    yield (f"chatgpt.{conv_file.name}", parse_chatgpt_conversations(conv_file))
                else:
                    # Assume Anthropic format
                    yield (f"anthropic.{conv_file.name}", parse_conversations(conv_file))
        except Exception:
            # Fallback to Anthropic format
            yield (f"anthropic.{conv_file.name}", parse_conversations(conv_file))
    
    # Anthropic-specific files
    p = export_dir / "projects.json"
    if p.exists():
        yield ("anthropic.projects.json", parse_projects(p))
    
    # Handle both user file formats
    p = export_dir / "users.json"
    if p.exists():
        yield ("anthropic.users.json", parse_users(p))
    
    p = export_dir / "user.json"  # ChatGPT uses user.json
    if p.exists():
        yield ("chatgpt.user.json", parse_chatgpt_user(p))


def build_index(export_dir: Path, out_dir: Path) -> Path:
    """Build an index database at out_dir/chatgpt.db from the export_dir files.

    Returns the path to the created database.
    """
    return build_index_multi([(export_dir.name or "default", export_dir)], out_dir)


def build_index_multi(sources: List[Tuple[str, Path]], out_dir: Path) -> Path:
    db_path = out_dir / "chatgpt.db"
    conn = ensure_db(db_path)
    total = 0
    with conn:
        for account, export_dir in sources:
            for name, gen in _parsers_for_export(export_dir):
                print(f"Processing {account}:{name}...")
                for doc in gen:
                    add_doc(conn, **{k: doc[k] for k in ("id","conv_id","title","role","ts","source","content")}, account=account)
                    total += 1
                    if total % 1000 == 0:
                        print(f"  Processed {total:,} docs...")
    print(f"Indexed {total:,} docs into {db_path}")
    conn.close()
    return db_path


# New Knowledge Graph indexing functions

def _detect_format(conv_file: Path) -> str:
    """Detect if a conversations file is ChatGPT or Claude format."""
    try:
        with open(conv_file, 'r', encoding='utf-8') as f:
            sample = f.read(2048)
            if '"mapping"' in sample and '"author"' in sample:
                return "chatgpt"
            return "claude"
    except Exception:
        return "claude"


def build_knowledge_graph(sources: List[Tuple[str, Path]], out_dir: Path) -> Path:
    """Build a Knowledge Graph database from export files.
    
    This is the new indexer that uses the unified schema and creates
    a proper knowledge graph with nodes and edges.
    
    Args:
        sources: List of (account_name, export_dir) tuples
        out_dir: Output directory for the database
    
    Returns:
        Path to the created database
    """
    db_path = out_dir / "knowledge.db"
    store = KnowledgeStore(db_path)
    
    total_convs = 0
    total_turns = 0
    
    for account, export_dir in sources:
        # Find conversation files
        conversation_files = list(export_dir.glob("conversations*.json"))
        
        for conv_file in conversation_files:
            fmt = _detect_format(conv_file)
            print(f"Processing {account}:{conv_file.name} ({fmt} format)...")
            
            if fmt == "chatgpt":
                parser = parse_chatgpt_unified(conv_file)
            else:
                parser = parse_conversations_unified(conv_file)
            
            for conv in parser:
                store.add_conversation(conv, account)
                total_convs += 1
                total_turns += len(conv.turns)
                
                if total_convs % 100 == 0:
                    print(f"  Processed {total_convs:,} conversations, {total_turns:,} turns...")
                    store.commit()
        
        # TODO: Handle projects.json and users.json as special node types
    
    store.commit()
    
    stats = store.get_stats()
    print(f"\nKnowledge Graph built at {db_path}")
    print(f"  Conversations: {stats['conversations']:,}")
    print(f"  Turns: {stats['turns']:,}")
    print(f"  Nodes: {stats['nodes']:,}")
    print(f"  Edges: {stats['edges']:,}")
    print(f"  Code blocks: {stats['code_blocks']:,}")
    print(f"  Links: {stats['links']:,}")
    
    store.close()
    return db_path


def build_dual_index(sources: List[Tuple[str, Path]], out_dir: Path) -> Tuple[Path, Path]:
    """Build both legacy and knowledge graph indexes.
    
    This allows gradual migration while keeping the existing search working.
    """
    legacy_path = build_index_multi(sources, out_dir)
    kg_path = build_knowledge_graph(sources, out_dir)
    return legacy_path, kg_path


# Vector embedding indexing

def build_embeddings(
    sources: List[Tuple[str, Path]], 
    out_dir: Path,
    provider: str = "local",
    batch_size: int = 32,
    **provider_kwargs
) -> Path:
    """
    Build vector embeddings for all conversation turns.
    
    Args:
        sources: List of (account_name, export_dir) tuples
        out_dir: Output directory for the vector database
        provider: Embedding provider ("local", "cloudflare", "openai")
        batch_size: Number of texts to embed at once
        **provider_kwargs: Provider-specific arguments
    
    Returns:
        Path to the vector database
    """
    from embeddings import get_embedder
    from vector_store import get_vector_store
    
    # Initialize embedder
    embedder = get_embedder(provider, **provider_kwargs)
    print(f"Using {provider} embedder: {embedder.model_name} ({embedder.dimensions}D)")
    
    # Initialize vector store
    vector_db_path = out_dir / "vectors.db"
    vector_store = get_vector_store(
        "sqlite", 
        db_path=vector_db_path,
        dimensions=embedder.dimensions
    )
    
    total_embedded = 0
    batch_texts = []
    batch_metadata = []
    
    def flush_batch():
        nonlocal total_embedded, batch_texts, batch_metadata
        if not batch_texts:
            return
        
        try:
            embeddings = embedder.embed(batch_texts)
            items = [
                (meta["id"], emb, meta)
                for emb, meta in zip(embeddings, batch_metadata)
            ]
            vector_store.insert_batch(items)
            total_embedded += len(items)
        except Exception as e:
            print(f"  Warning: batch embedding failed: {e}")
        
        batch_texts = []
        batch_metadata = []
    
    for account, export_dir in sources:
        conversation_files = list(export_dir.glob("conversations*.json"))
        
        for conv_file in conversation_files:
            fmt = _detect_format(conv_file)
            print(f"Embedding {account}:{conv_file.name} ({fmt} format)...")
            
            if fmt == "chatgpt":
                parser = parse_chatgpt_unified(conv_file)
            else:
                parser = parse_conversations_unified(conv_file)
            
            for conv in parser:
                for turn in conv.turns:
                    # Skip very short content
                    if len(turn.content.strip()) < 20:
                        continue
                    
                    batch_texts.append(turn.content[:2000])  # Truncate long content
                    batch_metadata.append({
                        "id": turn.id,
                        "conv_id": conv.id,
                        "title": conv.title,
                        "role": turn.role,
                        "timestamp": turn.timestamp,
                        "source": conv.source.value,
                        "account": account
                    })
                    
                    if len(batch_texts) >= batch_size:
                        flush_batch()
                        if total_embedded % 500 == 0:
                            print(f"  Embedded {total_embedded:,} turns...")
    
    # Final flush
    flush_batch()
    
    print(f"\nVector embeddings built at {vector_db_path}")
    print(f"  Total vectors: {vector_store.count():,}")
    
    return vector_db_path


def build_full_index(
    sources: List[Tuple[str, Path]], 
    out_dir: Path,
    embed_provider: str = "local",
    **embed_kwargs
) -> dict:
    """
    Build complete index: legacy FTS + Knowledge Graph + Vector embeddings.
    
    Args:
        sources: List of (account_name, export_dir) tuples
        out_dir: Output directory
        embed_provider: Embedding provider for vectors
        **embed_kwargs: Embedding provider arguments
    
    Returns:
        Dict with paths to all created databases
    """
    print("=" * 60)
    print("Building Full Inchive Index")
    print("=" * 60)
    
    print("\n[1/3] Building Legacy FTS Index...")
    legacy_path = build_index_multi(sources, out_dir)
    
    print("\n[2/3] Building Knowledge Graph...")
    kg_path = build_knowledge_graph(sources, out_dir)
    
    print("\n[3/3] Building Vector Embeddings...")
    vector_path = build_embeddings(sources, out_dir, provider=embed_provider, **embed_kwargs)
    
    print("\n" + "=" * 60)
    print("Index Complete!")
    print("=" * 60)
    print(f"  Legacy FTS:      {legacy_path}")
    print(f"  Knowledge Graph: {kg_path}")
    print(f"  Vector Store:    {vector_path}")
    
    return {
        "legacy": legacy_path,
        "knowledge_graph": kg_path,
        "vectors": vector_path
    }


