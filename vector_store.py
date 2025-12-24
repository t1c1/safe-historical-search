"""
Vector Store Module

Supports multiple backends:
- Local: sqlite-vec (SQLite extension for vector similarity search)
- Cloudflare: Vectorize (globally distributed vector database)

Usage:
    # Local with sqlite-vec
    store = get_vector_store("sqlite", db_path="./index/vectors.db", dimensions=384)
    store.insert("doc1", [0.1, 0.2, ...], {"title": "Hello"})
    results = store.search([0.1, 0.2, ...], limit=10)
    
    # Cloudflare Vectorize
    store = get_vector_store("cloudflare", index_name="inchive", ...)
    results = store.search([0.1, 0.2, ...], limit=10)
"""

import os
import json
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path


@dataclass
class VectorSearchResult:
    """A single vector search result."""
    id: str
    score: float  # Similarity score (higher = more similar)
    metadata: Dict[str, Any]
    vector: Optional[List[float]] = None


class VectorStore(ABC):
    """Abstract base class for vector stores."""
    
    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the vector dimensions."""
        pass
    
    @abstractmethod
    def insert(self, id: str, vector: List[float], metadata: Dict[str, Any] = None) -> None:
        """Insert a vector with optional metadata."""
        pass
    
    @abstractmethod
    def insert_batch(self, items: List[Tuple[str, List[float], Dict[str, Any]]]) -> int:
        """Insert multiple vectors. Returns count inserted."""
        pass
    
    @abstractmethod
    def search(
        self, 
        query_vector: List[float], 
        limit: int = 10,
        filter_metadata: Dict[str, Any] = None
    ) -> List[VectorSearchResult]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        """Delete a vector by ID."""
        pass
    
    @abstractmethod
    def get(self, id: str) -> Optional[VectorSearchResult]:
        """Get a vector by ID."""
        pass
    
    def count(self) -> int:
        """Return total number of vectors."""
        return 0


class SQLiteVectorStore(VectorStore):
    """
    Local vector store using sqlite-vec extension.
    
    sqlite-vec provides efficient vector similarity search directly in SQLite.
    Install: pip install sqlite-vec
    
    Uses cosine similarity for search.
    """
    
    def __init__(self, db_path: Path, dimensions: int):
        self._dimensions = dimensions
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = self._connect()
        self._ensure_schema()
    
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        
        # Try to load sqlite-vec extension
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            self._has_vec = True
        except (ImportError, Exception) as e:
            print(f"Warning: sqlite-vec not available ({e}). Using fallback cosine similarity.")
            self._has_vec = False
        
        return conn
    
    def _ensure_schema(self):
        """Create tables for vector storage."""
        
        if self._has_vec:
            # Use sqlite-vec virtual table for efficient similarity search
            self.conn.executescript(f"""
                CREATE TABLE IF NOT EXISTS vector_metadata (
                    id TEXT PRIMARY KEY,
                    metadata TEXT
                );
                
                CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0(
                    id TEXT PRIMARY KEY,
                    embedding FLOAT[{self._dimensions}]
                );
            """)
        else:
            # Fallback: store vectors as JSON blobs
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS vectors_fallback (
                    id TEXT PRIMARY KEY,
                    embedding TEXT,
                    metadata TEXT
                );
            """)
        
        self.conn.commit()
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    def insert(self, id: str, vector: List[float], metadata: Dict[str, Any] = None) -> None:
        """Insert a single vector."""
        if len(vector) != self._dimensions:
            raise ValueError(f"Vector dimension mismatch: got {len(vector)}, expected {self._dimensions}")
        
        if self._has_vec:
            # Insert into vec0 virtual table
            self.conn.execute(
                "INSERT OR REPLACE INTO vectors (id, embedding) VALUES (?, ?)",
                (id, json.dumps(vector))
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO vector_metadata (id, metadata) VALUES (?, ?)",
                (id, json.dumps(metadata or {}))
            )
        else:
            self.conn.execute(
                "INSERT OR REPLACE INTO vectors_fallback (id, embedding, metadata) VALUES (?, ?, ?)",
                (id, json.dumps(vector), json.dumps(metadata or {}))
            )
        
        self.conn.commit()
    
    def insert_batch(self, items: List[Tuple[str, List[float], Dict[str, Any]]]) -> int:
        """Insert multiple vectors efficiently."""
        count = 0
        
        for id, vector, metadata in items:
            if len(vector) != self._dimensions:
                continue
            
            if self._has_vec:
                self.conn.execute(
                    "INSERT OR REPLACE INTO vectors (id, embedding) VALUES (?, ?)",
                    (id, json.dumps(vector))
                )
                self.conn.execute(
                    "INSERT OR REPLACE INTO vector_metadata (id, metadata) VALUES (?, ?)",
                    (id, json.dumps(metadata or {}))
                )
            else:
                self.conn.execute(
                    "INSERT OR REPLACE INTO vectors_fallback (id, embedding, metadata) VALUES (?, ?, ?)",
                    (id, json.dumps(vector), json.dumps(metadata or {}))
                )
            count += 1
        
        self.conn.commit()
        return count
    
    def search(
        self, 
        query_vector: List[float], 
        limit: int = 10,
        filter_metadata: Dict[str, Any] = None
    ) -> List[VectorSearchResult]:
        """Search for similar vectors using cosine similarity."""
        
        if self._has_vec:
            # Use sqlite-vec's built-in similarity search
            rows = self.conn.execute("""
                SELECT v.id, v.distance, m.metadata
                FROM vectors v
                JOIN vector_metadata m ON v.id = m.id
                WHERE v.embedding MATCH ?
                ORDER BY v.distance
                LIMIT ?
            """, (json.dumps(query_vector), limit)).fetchall()
            
            results = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                
                # Apply metadata filter if specified
                if filter_metadata:
                    if not all(metadata.get(k) == v for k, v in filter_metadata.items()):
                        continue
                
                # Convert distance to similarity score (1 - distance for cosine)
                results.append(VectorSearchResult(
                    id=row["id"],
                    score=1.0 - row["distance"],
                    metadata=metadata
                ))
            
            return results
        else:
            # Fallback: compute cosine similarity in Python
            return self._search_fallback(query_vector, limit, filter_metadata)
    
    def _search_fallback(
        self, 
        query_vector: List[float], 
        limit: int,
        filter_metadata: Dict[str, Any] = None
    ) -> List[VectorSearchResult]:
        """Fallback search without sqlite-vec (slower but works everywhere)."""
        import math
        
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)
        
        rows = self.conn.execute(
            "SELECT id, embedding, metadata FROM vectors_fallback"
        ).fetchall()
        
        results = []
        for row in rows:
            embedding = json.loads(row["embedding"])
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            
            # Apply metadata filter
            if filter_metadata:
                if not all(metadata.get(k) == v for k, v in filter_metadata.items()):
                    continue
            
            score = cosine_similarity(query_vector, embedding)
            results.append(VectorSearchResult(
                id=row["id"],
                score=score,
                metadata=metadata,
                vector=embedding
            ))
        
        # Sort by score descending and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def delete(self, id: str) -> bool:
        """Delete a vector by ID."""
        if self._has_vec:
            self.conn.execute("DELETE FROM vectors WHERE id = ?", (id,))
            self.conn.execute("DELETE FROM vector_metadata WHERE id = ?", (id,))
        else:
            self.conn.execute("DELETE FROM vectors_fallback WHERE id = ?", (id,))
        self.conn.commit()
        return True
    
    def get(self, id: str) -> Optional[VectorSearchResult]:
        """Get a vector by ID."""
        if self._has_vec:
            row = self.conn.execute("""
                SELECT v.id, v.embedding, m.metadata
                FROM vectors v
                JOIN vector_metadata m ON v.id = m.id
                WHERE v.id = ?
            """, (id,)).fetchone()
        else:
            row = self.conn.execute(
                "SELECT id, embedding, metadata FROM vectors_fallback WHERE id = ?",
                (id,)
            ).fetchone()
        
        if not row:
            return None
        
        return VectorSearchResult(
            id=row["id"],
            score=1.0,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            vector=json.loads(row["embedding"]) if row["embedding"] else None
        )
    
    def count(self) -> int:
        """Return total number of vectors."""
        if self._has_vec:
            row = self.conn.execute("SELECT COUNT(*) FROM vectors").fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM vectors_fallback").fetchone()
        return row[0] if row else 0
    
    def close(self):
        self.conn.close()


class CloudflareVectorize(VectorStore):
    """
    Cloudflare Vectorize vector store.
    
    Globally distributed, low-latency vector database.
    Requires Cloudflare account with Vectorize enabled.
    
    API Reference: https://developers.cloudflare.com/vectorize/
    """
    
    API_BASE = "https://api.cloudflare.com/client/v4/accounts/{account_id}/vectorize/v2/indexes/{index_name}"
    
    def __init__(
        self, 
        index_name: str,
        account_id: str,
        api_token: str,
        dimensions: int = 768,
        metric: str = "cosine"
    ):
        self._dimensions = dimensions
        self.index_name = index_name
        self.account_id = account_id
        self.api_token = api_token
        self.metric = metric
        
        # Ensure index exists
        self._ensure_index()
    
    def _api_url(self, endpoint: str = "") -> str:
        base = self.API_BASE.format(
            account_id=self.account_id,
            index_name=self.index_name
        )
        return f"{base}{endpoint}"
    
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    def _ensure_index(self):
        """Create index if it doesn't exist."""
        import requests
        
        # Check if index exists
        response = requests.get(self._api_url(), headers=self._headers())
        if response.status_code == 200:
            return  # Index exists
        
        # Create index
        create_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/vectorize/v2/indexes"
        payload = {
            "name": self.index_name,
            "config": {
                "dimensions": self._dimensions,
                "metric": self.metric
            }
        }
        
        response = requests.post(create_url, headers=self._headers(), json=payload)
        if not response.ok and "already exists" not in response.text.lower():
            raise RuntimeError(f"Failed to create Vectorize index: {response.text}")
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    def insert(self, id: str, vector: List[float], metadata: Dict[str, Any] = None) -> None:
        """Insert a single vector."""
        self.insert_batch([(id, vector, metadata or {})])
    
    def insert_batch(self, items: List[Tuple[str, List[float], Dict[str, Any]]]) -> int:
        """Insert multiple vectors via NDJSON."""
        import requests
        
        # Format as NDJSON
        ndjson_lines = []
        for id, vector, metadata in items:
            if len(vector) != self._dimensions:
                continue
            ndjson_lines.append(json.dumps({
                "id": id,
                "values": vector,
                "metadata": metadata or {}
            }))
        
        if not ndjson_lines:
            return 0
        
        ndjson_body = "\n".join(ndjson_lines)
        
        response = requests.post(
            self._api_url("/upsert"),
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/x-ndjson"
            },
            data=ndjson_body
        )
        
        if not response.ok:
            raise RuntimeError(f"Vectorize upsert failed: {response.text}")
        
        return len(ndjson_lines)
    
    def search(
        self, 
        query_vector: List[float], 
        limit: int = 10,
        filter_metadata: Dict[str, Any] = None
    ) -> List[VectorSearchResult]:
        """Search for similar vectors."""
        import requests
        
        payload = {
            "vector": query_vector,
            "topK": limit,
            "returnMetadata": "all"
        }
        
        if filter_metadata:
            payload["filter"] = filter_metadata
        
        response = requests.post(
            self._api_url("/query"),
            headers=self._headers(),
            json=payload
        )
        
        if not response.ok:
            raise RuntimeError(f"Vectorize query failed: {response.text}")
        
        result = response.json()
        matches = result.get("result", {}).get("matches", [])
        
        return [
            VectorSearchResult(
                id=match["id"],
                score=match.get("score", 0.0),
                metadata=match.get("metadata", {})
            )
            for match in matches
        ]
    
    def delete(self, id: str) -> bool:
        """Delete a vector by ID."""
        import requests
        
        response = requests.post(
            self._api_url("/delete-by-ids"),
            headers=self._headers(),
            json={"ids": [id]}
        )
        
        return response.ok
    
    def get(self, id: str) -> Optional[VectorSearchResult]:
        """Get a vector by ID."""
        import requests
        
        response = requests.post(
            self._api_url("/get-by-ids"),
            headers=self._headers(),
            json={"ids": [id]}
        )
        
        if not response.ok:
            return None
        
        result = response.json()
        vectors = result.get("result", {}).get("vectors", [])
        
        if not vectors:
            return None
        
        v = vectors[0]
        return VectorSearchResult(
            id=v["id"],
            score=1.0,
            metadata=v.get("metadata", {}),
            vector=v.get("values")
        )
    
    def count(self) -> int:
        """Return total number of vectors (approximate)."""
        import requests
        
        response = requests.get(self._api_url("/info"), headers=self._headers())
        if not response.ok:
            return 0
        
        result = response.json()
        return result.get("result", {}).get("vectorCount", 0)


def get_vector_store(
    backend: str = "sqlite",
    **kwargs
) -> VectorStore:
    """
    Factory function to get a vector store.
    
    Args:
        backend: "sqlite" or "cloudflare"
        **kwargs: Backend-specific arguments
            - sqlite: db_path, dimensions
            - cloudflare: index_name, account_id, api_token, dimensions, metric
    
    Returns:
        VectorStore instance
    """
    if backend == "sqlite":
        return SQLiteVectorStore(
            db_path=Path(kwargs.get("db_path", "./index/vectors.db")),
            dimensions=kwargs.get("dimensions", 384)
        )
    elif backend == "cloudflare":
        account_id = kwargs.get("account_id") or os.environ.get("CF_ACCOUNT_ID")
        api_token = kwargs.get("api_token") or os.environ.get("CF_API_TOKEN")
        
        if not account_id or not api_token:
            raise ValueError(
                "Cloudflare credentials required. Set CF_ACCOUNT_ID and CF_API_TOKEN env vars."
            )
        
        return CloudflareVectorize(
            index_name=kwargs.get("index_name", "inchive"),
            account_id=account_id,
            api_token=api_token,
            dimensions=kwargs.get("dimensions", 768),
            metric=kwargs.get("metric", "cosine")
        )
    else:
        raise ValueError(f"Unknown vector store backend: {backend}")

