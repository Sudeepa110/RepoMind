"""
Repository-scoped Keyword Search Engine using SQLite FTS5.
Provides fast, zero-cost, exact identifier, prefix, and full-text matching
with BM25 relevance ranking boosted for symbol names and file paths.
"""

import json
import logging
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.app.config import settings
from backend.app.vectorstore.interfaces import CodeChunk
from backend.app.retrieval.retrieval_models import UnifiedSearchResult

logger = logging.getLogger(__name__)


def sanitize_filename(repo_id: str) -> str:
    """Sanitize repository ID for safe filesystem storage."""
    safe = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", repo_id)
    return safe[:100]


def clean_fts_token(term: str) -> str:
    """Strip characters that have special syntax meaning in FTS5 and normalize whitespace."""
    clean = re.sub(r'["\*\^:\(\)`\?\[\]]', " ", term)
    return " ".join(clean.split())


FTS_COMMON_STOP_WORDS = {
    "in", "is", "to", "on", "at", "by", "for", "with", "from", "of", "and", "or",
    "the", "a", "an", "how", "what", "where", "which", "who", "why", "does", "do",
    "did", "this", "that", "it", "not", "be", "as", "are", "was", "were", "can",
}


class KeywordSearchEngine:
    """
    Repository-isolated keyword retrieval engine backed by SQLite FTS5.
    Supports BM25 ranking, exact symbol matching, and prefix searches.
    """

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir or (settings.STORAGE_DIR / "keywords")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _get_db_path(self, repository_id: str) -> Path:
        safe_fn = sanitize_filename(repository_id)
        return self.persist_dir / f"{safe_fn}.db"

    def _init_db(self, conn: sqlite3.Connection) -> None:
        """Create metadata and FTS5 tables if they don't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks_meta (
                chunk_id TEXT PRIMARY KEY,
                repository_id TEXT,
                file_path TEXT,
                symbol_id TEXT,
                symbol_name TEXT,
                symbol_type TEXT,
                language TEXT,
                start_line INT,
                end_line INT,
                source_code TEXT,
                signature TEXT,
                docstring TEXT,
                context_header TEXT,
                content_hash TEXT
            )
        """)

        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                symbol_name,
                file_path,
                symbol_type,
                language UNINDEXED,
                signature,
                docstring,
                source_code,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        conn.commit()

    def index_chunks(
        self,
        repository_id: str,
        chunks: List[CodeChunk],
        force_reindex: bool = False,
    ) -> int:
        """
        Indexes a collection of CodeChunk entities into the repository's FTS5 database.
        Supports incremental updates by comparing content hashes.
        """
        if not chunks:
            return 0

        db_path = self._get_db_path(repository_id)

        with self._lock:
            conn = sqlite3.connect(db_path, timeout=30.0)
            try:
                self._init_db(conn)

                if force_reindex:
                    conn.execute("DELETE FROM chunks_meta")
                    conn.execute("DELETE FROM chunks_fts")
                    conn.commit()

                # Get existing hashes for incremental deduplication
                existing_hashes = {}
                if not force_reindex:
                    cur = conn.execute("SELECT chunk_id, content_hash FROM chunks_meta")
                    existing_hashes = {row[0]: row[1] for row in cur.fetchall()}

                indexed_count = 0
                for c in chunks:
                    # Skip if unchanged
                    if c.chunk_id in existing_hashes and existing_hashes[c.chunk_id] == c.content_hash:
                        continue

                    # If modified, remove old entry first
                    if c.chunk_id in existing_hashes:
                        conn.execute("DELETE FROM chunks_meta WHERE chunk_id = ?", (c.chunk_id,))
                        conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (c.chunk_id,))

                    # Insert into chunks_meta
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO chunks_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c.chunk_id,
                            repository_id,
                            c.file_path,
                            c.symbol_id or "",
                            c.symbol_name or "",
                            c.symbol_type or "",
                            c.language,
                            c.start_line,
                            c.end_line,
                            c.source_code,
                            c.signature or "",
                            c.docstring or "",
                            c.context_header or "",
                            c.content_hash,
                        ),
                    )

                    # Insert into chunks_fts
                    conn.execute(
                        """
                        INSERT INTO chunks_fts VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c.chunk_id,
                            c.symbol_name or "",
                            c.file_path,
                            c.symbol_type or "",
                            c.language,
                            c.signature or "",
                            c.docstring or "",
                            c.source_code,
                        ),
                    )
                    indexed_count += 1

                conn.commit()
                logger.info(f"Indexed {indexed_count} chunks in SQLite FTS5 for repository {repository_id}")
                return indexed_count
            finally:
                conn.close()

    def search(
        self,
        repository_id: str,
        query: str,
        top_k: int = 10,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
        symbol_type: Optional[str] = None,
    ) -> List[UnifiedSearchResult]:
        """
        Executes BM25 keyword retrieval matching symbol names, file paths, and source code.
        Boosts symbol_name matches (weight 10.0) and file_path matches (weight 5.0).
        """
        db_path = self._get_db_path(repository_id)
        if not db_path.exists():
            return []

        clean_q = clean_fts_token(query)
        if not clean_q:
            return []

        # Construct tokenized FTS query
        raw_tokens = [t for t in clean_q.split() if len(t) >= 2]
        if not raw_tokens:
            return []

        tokens: List[str] = []
        for rt in raw_tokens:
            if "." in rt:
                for sub in rt.split("."):
                    sub_c = sub.strip()
                    if len(sub_c) >= 2 and sub_c not in tokens:
                        tokens.append(sub_c)
            clean_rt = rt.strip(".")
            if len(clean_rt) >= 2 and clean_rt not in tokens:
                tokens.append(clean_rt)

        if not tokens:
            return []

        # Build FTS match expression: match exact tokens and prefix matches (excluding stop words from prefix expansion)
        match_clauses = []
        for t in tokens:
            t_low = t.lower()
            if t_low not in FTS_COMMON_STOP_WORDS:
                match_clauses.append(f'"{t}"')
                if len(t) >= 3:
                    match_clauses.append(f'"{t}"*')
            elif len(t) >= 3:
                match_clauses.append(f'"{t}"')

        if not match_clauses:
            match_clauses = [f'"{t}"' for t in tokens]

        fts_query = " OR ".join(match_clauses)

        results: List[UnifiedSearchResult] = []

        with self._lock:
            conn = sqlite3.connect(db_path, timeout=10.0)
            try:
                conn.row_factory = sqlite3.Row
                self._init_db(conn)

                # Query FTS with BM25 column weights:
                # symbol_name(10.0), file_path(5.0), symbol_type(2.0), signature(3.0), docstring(2.0), source_code(1.0)
                sql = """
                    SELECT
                        m.chunk_id,
                        m.repository_id,
                        m.file_path,
                        m.symbol_id,
                        m.symbol_name,
                        m.symbol_type,
                        m.language,
                        m.start_line,
                        m.end_line,
                        m.source_code,
                        m.signature,
                        m.docstring,
                        m.context_header,
                        bm25(chunks_fts, 10.0, 5.0, 2.0, 3.0, 2.0, 1.0) as bm25_score
                    FROM chunks_fts f
                    JOIN chunks_meta m ON f.chunk_id = m.chunk_id
                    WHERE chunks_fts MATCH ?
                """
                params = [fts_query]

                if language:
                    sql += " AND m.language = ?"
                    params.append(language)
                if file_path:
                    sql += " AND m.file_path = ?"
                    params.append(file_path)
                if symbol_type:
                    sql += " AND m.symbol_type = ?"
                    params.append(symbol_type.upper())

                sql += " ORDER BY bm25_score ASC LIMIT ?"
                params.append(top_k * 2)

                try:
                    cur = conn.execute(sql, params)
                    rows = cur.fetchall()
                except sqlite3.OperationalError as e:
                    logger.warning(f"FTS query error with expression '{fts_query}': {e}. Falling back to token terms.")
                    # Safe fallback with individual escaped tokens
                    safe_params = [f'"{tokens[0]}"']
                    cur = conn.execute(
                        """
                        SELECT m.chunk_id, m.repository_id, m.file_path, m.symbol_id, m.symbol_name,
                               m.symbol_type, m.language, m.start_line, m.end_line, m.source_code,
                               m.signature, m.docstring, m.context_header,
                               bm25(chunks_fts, 10.0, 5.0, 2.0, 3.0, 2.0, 1.0) as bm25_score
                        FROM chunks_fts f
                        JOIN chunks_meta m ON f.chunk_id = m.chunk_id
                        WHERE chunks_fts MATCH ? ORDER BY bm25_score ASC LIMIT ?
                        """,
                        [safe_params[0], top_k],
                    )
                    rows = cur.fetchall()

                # Fallback to LIKE substring match if FTS yielded no results
                if len(rows) == 0 and tokens:
                    primary_token = tokens[0]
                    like_sql = """
                        SELECT chunk_id, repository_id, file_path, symbol_id, symbol_name,
                               symbol_type, language, start_line, end_line, source_code,
                               signature, docstring, context_header, -1.0 as bm25_score
                        FROM chunks_meta
                        WHERE (symbol_name LIKE ? OR file_path LIKE ? OR source_code LIKE ?)
                    """
                    like_params = [f"%{primary_token}%", f"%{primary_token}%", f"%{primary_token}%"]
                    if language:
                        like_sql += " AND language = ?"
                        like_params.append(language)
                    if file_path:
                        like_sql += " AND file_path = ?"
                        like_params.append(file_path)
                    if symbol_type:
                        like_sql += " AND symbol_type = ?"
                        like_params.append(symbol_type.upper())

                    like_sql += " LIMIT ?"
                    like_params.append(top_k)
                    like_cur = conn.execute(like_sql, like_params)
                    rows = like_cur.fetchall()

                # Format results and normalize scores
                for r in rows[:top_k]:
                    raw_score = float(r["bm25_score"])
                    # Convert negative BM25 score to normalized [0.0, 1.0] range
                    norm_score = max(0.01, min(1.0, 1.0 / (1.0 + abs(raw_score))))

                    # Boost exact symbol match
                    if r["symbol_name"] and r["symbol_name"].lower() in [t.lower() for t in tokens]:
                        norm_score = min(1.0, norm_score * 1.5)

                    results.append(
                        UnifiedSearchResult(
                            chunk_id=r["chunk_id"],
                            repository_id=r["repository_id"],
                            file_path=r["file_path"],
                            symbol_id=r["symbol_id"] or None,
                            symbol_name=r["symbol_name"] or None,
                            symbol_type=r["symbol_type"] or None,
                            language=r["language"] or "text",
                            start_line=r["start_line"],
                            end_line=r["end_line"],
                            source_code=r["source_code"],
                            signature=r["signature"] or None,
                            docstring=r["docstring"] or None,
                            context_header=r["context_header"] or None,
                            retrieval_source="KEYWORD",
                            sources=["KEYWORD"],
                            original_score=raw_score,
                            normalized_score=round(norm_score, 4),
                            rrf_score=0.0,
                            confidence=1.0,
                        )
                    )
            finally:
                conn.close()

        return results

    def delete_repository(self, repository_id: str) -> bool:
        """Deletes the SQLite FTS5 database file for a repository."""
        import gc
        import time

        gc.collect()
        with self._lock:
            db_path = self._get_db_path(repository_id)
            if db_path.exists():
                for _ in range(5):
                    try:
                        db_path.unlink()
                        logger.info(f"Deleted keyword index file {db_path}")
                        return True
                    except OSError:
                        time.sleep(0.05)
                        gc.collect()
                logger.error(f"Failed to delete keyword database {db_path}")
                return False
            return False


# Global singleton instance
keyword_search_engine = KeywordSearchEngine()
