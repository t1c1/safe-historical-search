import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Tuple, List
from ingest import parse_conversations, parse_projects, parse_users, parse_chatgpt_conversations, parse_chatgpt_user


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


