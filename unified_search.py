"""
Unified Search Service

This module provides a consistent search interface across all data sources
and search implementations in the codebase. Supports advanced search operators
including AND, OR, NOT, parentheses, and quoted phrases.
"""

import sqlite3
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
import html


class QueryParser:
    """Advanced query parser supporting boolean operators and phrases."""
    
    def __init__(self):
        self.tokens = []
        self.pos = 0
    
    def tokenize(self, query: str) -> List[str]:
        """Tokenize query into operators, phrases, and terms."""
        # Pattern matches: quoted phrases, parentheses, operators, and words
        pattern = r'"[^"]*"|\(|\)|AND|OR|NOT|\S+'
        return re.findall(pattern, query, re.IGNORECASE)
    
    def parse(self, query: str) -> str:
        """Parse advanced search query into FTS5 compatible syntax."""
        if not query.strip():
            return ""
            
        # Handle simple queries without operators
        if not any(op in query.upper() for op in ['AND', 'OR', 'NOT', '(', ')', '"']):
            return self._expand_simple_query(query)
        
        self.tokens = self.tokenize(query)
        self.pos = 0
        
        try:
            result = self._parse_or_expression()
            return result if result else query
        except Exception:
            # Fallback to simple expansion on parse error
            return self._expand_simple_query(query)
    
    def _expand_simple_query(self, query: str) -> str:
        """Expand simple query with wildcards."""
        parts = [p for p in query.replace('\u2013', ' ').replace('\u2014', ' ').split() if p]
        expanded = []
        for part in parts:
            if len(part) > 2 and not any(op in part for op in ['"', "'", ":"]):
                expanded.append(part + '*')
            else:
                expanded.append(part)
        return " ".join(expanded)
    
    def _current_token(self) -> Optional[str]:
        """Get current token."""
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    
    def _consume_token(self) -> Optional[str]:
        """Consume and return current token."""
        token = self._current_token()
        self.pos += 1
        return token
    
    def _parse_or_expression(self) -> str:
        """Parse OR expressions (lowest precedence)."""
        left = self._parse_and_expression()
        
        while self._current_token() and self._current_token().upper() == 'OR':
            self._consume_token()  # consume 'OR'
            right = self._parse_and_expression()
            left = f"({left}) OR ({right})"
        
        return left
    
    def _parse_and_expression(self) -> str:
        """Parse AND expressions (medium precedence)."""
        left = self._parse_not_expression()
        
        while (self._current_token() and 
               self._current_token().upper() == 'AND'):
            self._consume_token()  # consume 'AND'
            right = self._parse_not_expression()
            left = f"({left}) AND ({right})"
        
        return left
    
    def _parse_not_expression(self) -> str:
        """Parse NOT expressions (high precedence)."""
        if self._current_token() and self._current_token().upper() == 'NOT':
            self._consume_token()  # consume 'NOT'
            expr = self._parse_primary_expression()
            return f"NOT ({expr})"
        
        return self._parse_primary_expression()
    
    def _parse_primary_expression(self) -> str:
        """Parse primary expressions (terms, phrases, parentheses)."""
        token = self._current_token()
        
        if not token:
            return ""
        
        if token == '(':
            self._consume_token()  # consume '('
            expr = self._parse_or_expression()
            if self._current_token() == ')':
                self._consume_token()  # consume ')'
            return f"({expr})"
        
        elif token.startswith('"') and token.endswith('"'):
            # Quoted phrase
            self._consume_token()
            phrase = token[1:-1]  # Remove quotes
            return f'"{phrase}"'
        
        else:
            # Regular term
            self._consume_token()
            # Add wildcard to terms longer than 2 characters
            if len(token) > 2 and not any(op in token for op in ['"', "'", ":"]):
                return f"{token}*"
            return token


class UnifiedSearchService:
    """Unified search service that works with SQLite FTS5 databases."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.query_parser = QueryParser()
        self._ensure_db()

    def _ensure_db(self):
        """Ensure database and tables exist."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")

        # Create main docs table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS docs(
                id TEXT PRIMARY KEY,
                conv_id TEXT,
                title TEXT,
                role TEXT,
                ts REAL,
                date TEXT,
                source TEXT,
                content TEXT,
                account TEXT,
                extra TEXT
            )
        """)

        # Create FTS5 virtual table if it doesn't exist
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                content, title, role, source, conv_id, ts, date, account, doc_id UNINDEXED, tokenize='porter'
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_date ON docs(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_account ON docs(account)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_ts ON docs(ts)")

        # Create saved searches table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_searches(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                query TEXT NOT NULL,
                filters TEXT,  -- JSON string of filters
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                description TEXT
            )
        """)

        # Populate FTS table if empty
        try:
            fts_count = conn.execute("SELECT COUNT(*) FROM docs_fts").fetchone()[0]
            if fts_count == 0:
                conn.execute("""
                    INSERT INTO docs_fts(rowid, content, title, role, source, conv_id, ts, date, account, doc_id)
                    SELECT rowid, content, title, role, source, conv_id, CAST(ts AS TEXT), date, COALESCE(account, 'default'), id
                    FROM docs
                """)
        except Exception:
            pass

        conn.commit()
        conn.close()

    def _normalize_text(self, text: Any) -> str:
        """Normalize text for consistent searching."""
        if text is None:
            return ""
        text = html.unescape(str(text))
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _expand_query(self, query: str) -> str:
        """Expand query using advanced parser with boolean operators."""
        return self.query_parser.parse(query)

    def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        provider: Optional[str] = None,
        role: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "rank",
        account: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Unified search across all entities.

        Returns:
            Tuple of (results, total_count)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Build base query
        base_sql = """
            SELECT d.id, d.conv_id, d.title, d.role, d.date, d.source, d.ts, d.account,
                   snippet(docs_fts, 0, '<mark>', '</mark>', ' … ', 12) as snip
            FROM docs_fts
            JOIN docs d ON d.rowid = docs_fts.rowid
            WHERE docs_fts MATCH ?
        """

        params = []
        search_query = self._expand_query(query) if query else ""
        params.append(search_query)

        # Add filters
        if provider:
            if provider == "claude":
                base_sql += " AND d.source LIKE '%anthropic%'"
            elif provider == "chatgpt":
                base_sql += " AND d.source LIKE '%chatgpt%'"

        if role:
            if role == "assistant":
                base_sql += " AND (d.role = 'assistant' OR d.role = 'system')"
            else:
                base_sql += " AND d.role = ?"
                params.append(role)

        if date_from:
            base_sql += " AND (d.date IS NOT NULL AND d.date >= ?)"
            params.append(date_from)

        if date_to:
            base_sql += " AND (d.date IS NOT NULL AND d.date <= ?)"
            params.append(date_to)

        if account:
            base_sql += " AND d.account = ?"
            params.append(account)

        # Get total count
        count_sql = base_sql.replace(
            "SELECT d.id, d.conv_id, d.title, d.role, d.date, d.source, d.ts, d.account, snippet(docs_fts, 0, '<mark>', '</mark>', ' … ', 12) as snip",
            "SELECT COUNT(*)"
        )

        total_count = conn.execute(count_sql, tuple(params)).fetchone()[0]

        # Add sorting and pagination
        if sort_by == "newest":
            base_sql += " ORDER BY (d.date IS NULL), d.date DESC, rank"
        elif sort_by == "oldest":
            base_sql += " ORDER BY (d.date IS NULL), d.date ASC, rank"
        else:
            base_sql += " ORDER BY rank"

        base_sql += f" LIMIT {limit} OFFSET {offset}"

        rows = conn.execute(base_sql, tuple(params)).fetchall()
        conn.close()

        # Format results
        results = []
        for row in rows:
            result = {
                "id": row["id"],
                "conv_id": row["conv_id"],
                "title": row["title"] or "Untitled",
                "role": row["role"],
                "date": row["date"],
                "source": row["source"],
                "timestamp": row["ts"],
                "account": row["account"],
                "snippet": row["snip"],
                "relevance_score": 1.0  # Could be enhanced with actual scoring
            }
            results.append(result)

        return results, total_count

    def get_conversation_context(self, conv_id: str) -> List[Dict[str, Any]]:
        """Get full conversation context for a given conversation ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT title, role, date, ts, content, source FROM docs WHERE conv_id=? ORDER BY ts, rowid",
            (conv_id,)
        ).fetchall()

        conn.close()

        messages = []
        for row in rows:
            messages.append({
                "role": row["role"],
                "date": row["date"],
                "content": row["content"],
                "timestamp": row["ts"],
                "source": row["source"]
            })

        return messages

    def get_conversation_title(self, conv_id: str) -> str:
        """Get conversation title."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT title FROM docs WHERE conv_id=? LIMIT 1",
            (conv_id,)
        ).fetchone()

        conn.close()

        return row["title"] if row else "Untitled Conversation"

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        try:
            total_docs = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
            total_conversations = conn.execute("SELECT COUNT(DISTINCT conv_id) FROM docs").fetchone()[0]
            sources = conn.execute("SELECT source, COUNT(*) as count FROM docs GROUP BY source ORDER BY count DESC").fetchall()
            accounts = conn.execute("SELECT account, COUNT(*) as count FROM docs GROUP BY account ORDER BY count DESC").fetchall()

            stats = {
                "total_documents": total_docs,
                "total_conversations": total_conversations,
                "sources": {row["source"]: row["count"] for row in sources},
                "accounts": {row["account"]: row["count"] for row in accounts}
            }
        except Exception as e:
            stats = {"error": str(e)}

        conn.close()
        return stats

    def add_document(self, doc_data: Dict[str, Any]) -> bool:
        """Add a single document to the search index."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Extract and normalize data
            doc_id = doc_data.get("id")
            if not doc_id:
                return False

            conv_id = doc_data.get("conv_id", "")
            title = doc_data.get("title", "")
            role = doc_data.get("role", "")
            ts = doc_data.get("ts", 0.0)
            source = doc_data.get("source", "")
            content = self._normalize_text(doc_data.get("content", ""))
            account = doc_data.get("account", "default")
            extra = json.dumps(doc_data.get("extra", {})) if doc_data.get("extra") else None

            # Convert timestamp to date
            date_str = None
            if ts:
                try:
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    date_str = dt.strftime('%Y-%m-%d')
                except Exception:
                    date_str = None

            # Insert into main table
            conn.execute("""
                INSERT OR REPLACE INTO docs(id, conv_id, title, role, ts, date, source, content, account, extra)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (doc_id, conv_id, title, role, ts, date_str, source, content, account, extra))

            # Insert into FTS table
            conn.execute("""
                INSERT INTO docs_fts(rowid, content, title, role, source, conv_id, ts, date, account, doc_id)
                VALUES ((SELECT rowid FROM docs WHERE id=?),?,?,?,?,?,?,?,?,?)
            """, (doc_id, content, title, role, source, conv_id, str(ts), date_str, account, doc_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error adding document: {e}")
            return False

    def bulk_add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Add multiple documents to the search index. Returns number added."""
        added = 0
        conn = sqlite3.connect(self.db_path)

        try:
            for doc_data in documents:
                if self.add_document(doc_data):
                    added += 1

            conn.close()
            return added

        except Exception as e:
            print(f"Error in bulk add: {e}")
            conn.close()
            return added

    # Saved Searches Methods
    def save_search(self, name: str, query: str, filters: Dict[str, Any] = None, description: str = "") -> bool:
        """Save a search with given name and parameters."""
        try:
            conn = sqlite3.connect(self.db_path)
            filters_json = json.dumps(filters) if filters else "{}"
            
            conn.execute("""
                INSERT OR REPLACE INTO saved_searches(name, query, filters, description, created_at)
                VALUES (?,?,?,?, CURRENT_TIMESTAMP)
            """, (name, query, filters_json, description))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving search: {e}")
            return False

    def get_saved_searches(self) -> List[Dict[str, Any]]:
        """Get all saved searches ordered by access count."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        rows = conn.execute("""
            SELECT id, name, query, filters, description, created_at, accessed_at, access_count
            FROM saved_searches
            ORDER BY access_count DESC, created_at DESC
        """).fetchall()
        
        conn.close()
        
        searches = []
        for row in rows:
            try:
                filters = json.loads(row['filters']) if row['filters'] else {}
            except:
                filters = {}
                
            searches.append({
                'id': row['id'],
                'name': row['name'],
                'query': row['query'],
                'filters': filters,
                'description': row['description'],
                'created_at': row['created_at'],
                'accessed_at': row['accessed_at'],
                'access_count': row['access_count']
            })
        
        return searches

    def get_saved_search(self, search_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific saved search by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Update access count and timestamp
        conn.execute("""
            UPDATE saved_searches 
            SET accessed_at = CURRENT_TIMESTAMP, access_count = access_count + 1
            WHERE id = ?
        """, (search_id,))
        
        row = conn.execute("""
            SELECT id, name, query, filters, description, created_at, accessed_at, access_count
            FROM saved_searches WHERE id = ?
        """, (search_id,)).fetchone()
        
        conn.commit()
        conn.close()
        
        if not row:
            return None
            
        try:
            filters = json.loads(row['filters']) if row['filters'] else {}
        except:
            filters = {}
            
        return {
            'id': row['id'],
            'name': row['name'],
            'query': row['query'],
            'filters': filters,
            'description': row['description'],
            'created_at': row['created_at'],
            'accessed_at': row['accessed_at'],
            'access_count': row['access_count']
        }

    def delete_saved_search(self, search_id: int) -> bool:
        """Delete a saved search."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting saved search: {e}")
            return False

    def export_search_results(self, results: List[Dict[str, Any]], format: str = "json") -> str:
        """Export search results in various formats."""
        if format.lower() == "json":
            return json.dumps(results, indent=2, default=str)
        
        elif format.lower() == "csv":
            if not results:
                return ""
            
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
            return output.getvalue()
        
        elif format.lower() == "txt":
            lines = []
            for i, result in enumerate(results, 1):
                lines.append(f"Result {i}:")
                lines.append(f"  Title: {result.get('title', 'N/A')}")
                lines.append(f"  Role: {result.get('role', 'N/A')}")
                lines.append(f"  Date: {result.get('date', 'N/A')}")
                lines.append(f"  Source: {result.get('source', 'N/A')}")
                lines.append(f"  Content: {result.get('snippet', 'N/A')}")
                lines.append("")
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")




