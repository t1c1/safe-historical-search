"""
Knowledge Graph Storage Layer

Provides SQLite-based storage for the unified schema with:
- Conversations and Turns (core data)
- Nodes and Edges (Knowledge Graph)
- Full-text search via FTS5
- Efficient querying and traversal
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Generator
from dataclasses import asdict

from schema import (
    Conversation, Turn, Entity, Artifact, Claim, Decision, Task,
    CodeBlock, Link, Node, Edge, NodeType, EdgeType, SourceType,
    extract_code_blocks, extract_links
)


class KnowledgeStore:
    """SQLite-based storage for conversations and knowledge graph."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = self._connect()
        self._ensure_schema()
    
    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn
    
    def _ensure_schema(self):
        """Create all required tables."""
        
        # Core tables
        self.conn.executescript("""
            -- Conversations table
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                source TEXT,
                created_at REAL,
                updated_at REAL,
                account TEXT DEFAULT 'default',
                tags TEXT,  -- JSON array
                metadata TEXT  -- JSON
            );
            
            -- Turns table
            CREATE TABLE IF NOT EXISTS turns (
                id TEXT PRIMARY KEY,
                conv_id TEXT NOT NULL,
                role TEXT,
                content TEXT,
                timestamp REAL,
                model TEXT,
                turn_index INTEGER,
                metadata TEXT,  -- JSON
                FOREIGN KEY (conv_id) REFERENCES conversations(id)
            );
            
            -- Knowledge Graph Nodes
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                label TEXT,
                ref_id TEXT,  -- ID of the referenced object
                ref_table TEXT,  -- Table name of referenced object
                metadata TEXT  -- JSON
            );
            
            -- Knowledge Graph Edges
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                metadata TEXT,  -- JSON
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id)
            );
            
            -- Entities extracted from turns
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT,
                turn_id TEXT,
                metadata TEXT,
                FOREIGN KEY (turn_id) REFERENCES turns(id)
            );
            
            -- Code blocks extracted from turns
            CREATE TABLE IF NOT EXISTS code_blocks (
                id TEXT PRIMARY KEY,
                turn_id TEXT NOT NULL,
                language TEXT,
                content TEXT,
                start_line INTEGER,
                metadata TEXT,
                FOREIGN KEY (turn_id) REFERENCES turns(id)
            );
            
            -- Links extracted from turns
            CREATE TABLE IF NOT EXISTS links (
                id TEXT PRIMARY KEY,
                turn_id TEXT NOT NULL,
                url TEXT,
                text TEXT,
                domain TEXT,
                metadata TEXT,
                FOREIGN KEY (turn_id) REFERENCES turns(id)
            );
            
            -- Claims extracted from turns
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                turn_id TEXT NOT NULL,
                content TEXT,
                confidence REAL DEFAULT 1.0,
                metadata TEXT,
                FOREIGN KEY (turn_id) REFERENCES turns(id)
            );
            
            -- Decisions extracted from turns
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                turn_id TEXT NOT NULL,
                summary TEXT,
                rationale TEXT,
                alternatives TEXT,  -- JSON array
                metadata TEXT,
                FOREIGN KEY (turn_id) REFERENCES turns(id)
            );
            
            -- Tasks extracted from turns
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                turn_id TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'open',
                priority TEXT,
                due_date REAL,
                metadata TEXT,
                FOREIGN KEY (turn_id) REFERENCES turns(id)
            );
            
            -- FTS5 for full-text search on turns
            CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
                content, title, role, source, conv_id, 
                tokenize='porter'
            );
            
            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_turns_conv ON turns(conv_id);
            CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(timestamp);
            CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at);
            CREATE INDEX IF NOT EXISTS idx_conversations_account ON conversations(account);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
            CREATE INDEX IF NOT EXISTS idx_code_blocks_lang ON code_blocks(language);
        """)
        self.conn.commit()
    
    def add_conversation(self, conv: Conversation, account: str = "default") -> None:
        """Add a conversation and all its turns to the store."""
        
        # Insert conversation
        self.conn.execute("""
            INSERT OR REPLACE INTO conversations 
            (id, title, source, created_at, updated_at, account, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conv.id, conv.title, conv.source.value,
            conv.created_at, conv.updated_at, account,
            json.dumps(conv.tags), json.dumps(conv.metadata)
        ))
        
        # Create node for conversation
        self._add_node(conv.id, NodeType.CONVERSATION, conv.title, conv.id, "conversations")
        
        prev_turn_id = None
        for i, turn in enumerate(conv.turns):
            self._add_turn(turn, conv, i, account)
            
            # Create FOLLOWS edge between consecutive turns
            if prev_turn_id:
                self._add_edge(
                    f"{prev_turn_id}->follows->{turn.id}",
                    EdgeType.FOLLOWS, prev_turn_id, turn.id
                )
            prev_turn_id = turn.id
    
    def _add_turn(self, turn: Turn, conv: Conversation, index: int, account: str) -> None:
        """Add a turn and extract metadata."""
        
        # Insert turn
        self.conn.execute("""
            INSERT OR REPLACE INTO turns
            (id, conv_id, role, content, timestamp, model, turn_index, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            turn.id, conv.id, turn.role, turn.content,
            turn.timestamp, turn.model, index, json.dumps(turn.metadata)
        ))
        
        # Add to FTS
        self.conn.execute("""
            INSERT INTO turns_fts (rowid, content, title, role, source, conv_id)
            SELECT rowid, ?, ?, ?, ?, ?
            FROM turns WHERE id = ?
        """, (turn.content, conv.title, turn.role, conv.source.value, conv.id, turn.id))
        
        # Create node for turn
        self._add_node(turn.id, NodeType.TURN, f"{turn.role}: {turn.content[:50]}...", turn.id, "turns")
        
        # Create CONTAINS edge from conversation to turn
        self._add_edge(
            f"{conv.id}->contains->{turn.id}",
            EdgeType.CONTAINS, conv.id, turn.id
        )
        
        # Extract and store code blocks
        code_blocks = extract_code_blocks(turn.content, turn.id)
        for cb in code_blocks:
            self.conn.execute("""
                INSERT OR REPLACE INTO code_blocks
                (id, turn_id, language, content, start_line, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cb.id, turn.id, cb.language, cb.content, cb.start_line, json.dumps(cb.metadata)))
            
            # Create artifact node and edge
            self._add_node(cb.id, NodeType.ARTIFACT, f"Code: {cb.language}", cb.id, "code_blocks")
            self._add_edge(f"{turn.id}->produces->{cb.id}", EdgeType.PRODUCES, turn.id, cb.id)
        
        # Extract and store links
        links = extract_links(turn.content, turn.id)
        for link in links:
            self.conn.execute("""
                INSERT OR REPLACE INTO links
                (id, turn_id, url, text, domain, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (link.id, turn.id, link.url, link.text, link.domain, json.dumps(link.metadata)))
    
    def _add_node(self, node_id: str, node_type: NodeType, label: str, 
                  ref_id: str, ref_table: str, metadata: Dict = None) -> None:
        """Add a node to the knowledge graph."""
        self.conn.execute("""
            INSERT OR REPLACE INTO nodes (id, type, label, ref_id, ref_table, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (node_id, node_type.value, label, ref_id, ref_table, json.dumps(metadata or {})))
    
    def _add_edge(self, edge_id: str, edge_type: EdgeType, 
                  source_id: str, target_id: str, weight: float = 1.0, 
                  metadata: Dict = None) -> None:
        """Add an edge to the knowledge graph."""
        self.conn.execute("""
            INSERT OR REPLACE INTO edges (id, type, source_id, target_id, weight, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (edge_id, edge_type.value, source_id, target_id, weight, json.dumps(metadata or {})))
    
    def search(self, query: str, limit: int = 50, offset: int = 0,
               provider: Optional[str] = None, role: Optional[str] = None,
               date_from: Optional[str] = None, date_to: Optional[str] = None,
               account: Optional[str] = None) -> Tuple[List[Dict], int]:
        """Search turns using FTS5."""
        
        # Build query
        sql = """
            SELECT t.id, t.conv_id, c.title, t.role, t.timestamp, c.source, 
                   c.account, snippet(turns_fts, 0, '<mark>', '</mark>', '...', 12) as snip
            FROM turns_fts
            JOIN turns t ON t.rowid = turns_fts.rowid
            JOIN conversations c ON c.id = t.conv_id
            WHERE turns_fts MATCH ?
        """
        params = [query]
        
        if provider:
            if provider == "claude":
                sql += " AND c.source = 'anthropic'"
            elif provider == "chatgpt":
                sql += " AND c.source = 'openai'"
        
        if role:
            sql += " AND t.role = ?"
            params.append(role)
        
        if date_from:
            sql += " AND t.timestamp >= ?"
            params.append(datetime.fromisoformat(date_from).timestamp())
        
        if date_to:
            sql += " AND t.timestamp <= ?"
            params.append(datetime.fromisoformat(date_to).timestamp())
        
        if account:
            sql += " AND c.account = ?"
            params.append(account)
        
        # Get total count
        count_sql = f"SELECT COUNT(*) FROM ({sql})"
        total = self.conn.execute(count_sql, params).fetchone()[0]
        
        # Get results
        sql += " ORDER BY rank LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        results = []
        for row in self.conn.execute(sql, params):
            results.append(dict(row))
        
        return results, total
    
    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        """Get a full conversation with all turns."""
        row = self.conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        
        if not row:
            return None
        
        turns = []
        for t in self.conn.execute(
            "SELECT * FROM turns WHERE conv_id = ? ORDER BY turn_index", (conv_id,)
        ):
            turns.append(Turn(
                id=t["id"], role=t["role"], content=t["content"],
                timestamp=t["timestamp"], model=t["model"],
                metadata=json.loads(t["metadata"] or "{}")
            ))
        
        return Conversation(
            id=row["id"], title=row["title"],
            source=SourceType(row["source"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
            turns=turns, tags=json.loads(row["tags"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}")
        )
    
    def get_graph_neighbors(self, node_id: str, edge_types: List[EdgeType] = None,
                            direction: str = "both") -> List[Tuple[Edge, Node]]:
        """Get neighboring nodes in the knowledge graph."""
        results = []
        
        type_filter = ""
        if edge_types:
            types = ",".join(f"'{t.value}'" for t in edge_types)
            type_filter = f" AND e.type IN ({types})"
        
        if direction in ("out", "both"):
            sql = f"""
                SELECT e.*, n.*
                FROM edges e
                JOIN nodes n ON n.id = e.target_id
                WHERE e.source_id = ? {type_filter}
            """
            for row in self.conn.execute(sql, (node_id,)):
                edge = Edge(
                    id=row["id"], type=EdgeType(row["type"]),
                    source_id=row["source_id"], target_id=row["target_id"],
                    weight=row["weight"], metadata=json.loads(row[5] or "{}")
                )
                node = Node(
                    id=row[6], type=NodeType(row[7]), label=row[8],
                    data=None, metadata=json.loads(row[11] or "{}")
                )
                results.append((edge, node))
        
        if direction in ("in", "both"):
            sql = f"""
                SELECT e.*, n.*
                FROM edges e
                JOIN nodes n ON n.id = e.source_id
                WHERE e.target_id = ? {type_filter}
            """
            for row in self.conn.execute(sql, (node_id,)):
                edge = Edge(
                    id=row["id"], type=EdgeType(row["type"]),
                    source_id=row["source_id"], target_id=row["target_id"],
                    weight=row["weight"], metadata=json.loads(row[5] or "{}")
                )
                node = Node(
                    id=row[6], type=NodeType(row[7]), label=row[8],
                    data=None, metadata=json.loads(row[11] or "{}")
                )
                results.append((edge, node))
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        for table in ["conversations", "turns", "nodes", "edges", "code_blocks", "links"]:
            count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count
        return stats
    
    def commit(self):
        self.conn.commit()
    
    def close(self):
        self.conn.close()


# Migration helper to convert old indexer format to new storage

def migrate_from_legacy(legacy_db: Path, new_db: Path) -> None:
    """Migrate data from legacy indexer.py format to new KnowledgeStore."""
    import sqlite3
    
    old_conn = sqlite3.connect(str(legacy_db))
    old_conn.row_factory = sqlite3.Row
    
    store = KnowledgeStore(new_db)
    
    # Group docs by conversation
    convs = {}
    for row in old_conn.execute("SELECT * FROM docs ORDER BY conv_id, ts"):
        conv_id = row["conv_id"]
        if conv_id not in convs:
            convs[conv_id] = {
                "id": conv_id,
                "title": row["title"],
                "source": "anthropic" if "anthropic" in row["source"] else "openai",
                "account": row["account"] or "default",
                "turns": []
            }
        convs[conv_id]["turns"].append(row)
    
    # Convert to new format
    for conv_data in convs.values():
        turns = []
        for i, t in enumerate(conv_data["turns"]):
            turns.append(Turn(
                id=t["id"],
                role=t["role"],
                content=t["content"],
                timestamp=t["ts"] or 0.0,
                metadata={}
            ))
        
        source = SourceType.ANTHROPIC if conv_data["source"] == "anthropic" else SourceType.OPENAI
        conv = Conversation(
            id=conv_data["id"],
            title=conv_data["title"],
            source=source,
            created_at=turns[0].timestamp if turns else 0.0,
            updated_at=turns[-1].timestamp if turns else 0.0,
            turns=turns
        )
        store.add_conversation(conv, conv_data["account"])
    
    store.commit()
    store.close()
    old_conn.close()

