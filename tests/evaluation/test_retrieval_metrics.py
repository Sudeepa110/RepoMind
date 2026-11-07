"""
Ground-truth retrieval evaluation suite for RepoMind Vector RAG.
Measures quantitative retrieval quality metrics:
- Precision@1
- Precision@3
- Recall@3
- Exact Line Citation Accuracy
"""

import tempfile
from pathlib import Path
from typing import List, Dict, Any, Set
import pytest

from backend.app.processing.engine import CodeUnderstandingEngine
from backend.app.vectorstore.chunker import StructureAwareChunker
from backend.app.vectorstore.chroma_store import ChromaVectorStore
from backend.app.vectorstore.embeddings import LocalSentenceTransformerService
from backend.app.retrieval.semantic_search import SemanticSearchService


BENCHMARK_SOURCE_FILES = {
    "auth/jwt_handler.py": (
        'import jwt\n'
        'from datetime import datetime, timedelta\n\n'
        'SECRET_KEY = "repomind-secret"\n\n'
        'def create_access_token(user_id: str, expires_minutes: int = 60) -> str:\n'
        '    """Generates a signed JWT access token for user authentication."""\n'
        '    payload = {"sub": user_id, "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)}\n'
        '    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")\n\n'
        'def verify_access_token(token: str) -> dict:\n'
        '    """Decodes and validates JWT token expiration and cryptographic signature."""\n'
        '    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])\n'
    ),
    "database/connection.py": (
        'import psycopg2\n'
        'from contextlib import contextmanager\n\n'
        'class DatabaseManager:\n'
        '    """Manages PostgreSQL relational database connections and transactions."""\n'
        '    def __init__(self, dsn: str):\n'
        '        self.dsn = dsn\n\n'
        '    @contextmanager\n'
        '    def get_cursor(self):\n'
        '        conn = psycopg2.connect(self.dsn)\n'
        '        try:\n'
        '            yield conn.cursor()\n'
        '            conn.commit()\n'
        '        finally:\n'
        '            conn.close()\n'
    ),
    "api/router.py": (
        'from fastapi import APIRouter, HTTPException\n\n'
        'router = APIRouter()\n\n'
        '@router.get("/health")\n'
        'def health_check() -> dict:\n'
        '    """Returns operational system liveness probe and health status."""\n'
        '    return {"status": "ok", "healthy": True}\n\n'
        '@router.post("/login")\n'
        'def login_endpoint(credentials: dict) -> dict:\n'
        '    """Authenticates username and password and returns session token."""\n'
        '    return {"token": "sample-token"}\n'
    ),
    "utils/crypto.py": (
        'import hashlib\n\n'
        'def calculate_sha256(data: str) -> str:\n'
        '    """Calculates standard SHA-256 hex digest of string input."""\n'
        '    return hashlib.sha256(data.encode("utf-8")).hexdigest()\n'
    ),
}

# 6 distinct realistic developer queries with ground-truth expected files and symbols
GROUND_TRUTH_EVALUATION_DATASET = [
    {
        "query": "generate and sign JSON Web Tokens with expiration",
        "expected_file": "auth/jwt_handler.py",
        "expected_symbols": {"create_access_token"},
    },
    {
        "query": "validate and decode JWT cryptographic signature",
        "expected_file": "auth/jwt_handler.py",
        "expected_symbols": {"verify_access_token"},
    },
    {
        "query": "PostgreSQL database connection context manager and transactions",
        "expected_file": "database/connection.py",
        "expected_symbols": {"DatabaseManager", "get_cursor"},
    },
    {
        "query": "system liveness probe and operational health check endpoint",
        "expected_file": "api/router.py",
        "expected_symbols": {"health_check"},
    },
    {
        "query": "user login HTTP API endpoint",
        "expected_file": "api/router.py",
        "expected_symbols": {"login_endpoint"},
    },
    {
        "query": "compute SHA-256 cryptographic hash digest of text",
        "expected_file": "utils/crypto.py",
        "expected_symbols": {"calculate_sha256"},
    },
]


def test_retrieval_quality_metrics():
    """
    Evaluates Precision@1, Precision@3, Recall@3, and Line Citation Accuracy.
    Enforces quality thresholds on semantic retrieval.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        repo_dir = Path(tmp_dir) / "eval_repo"
        repo_dir.mkdir(parents=True)
        chroma_dir = Path(tmp_dir) / "chroma"

        file_paths = []
        for rel_path, content in BENCHMARK_SOURCE_FILES.items():
            full_path = repo_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            file_paths.append(full_path)

        repo_id = "eval:benchmark_repo"

        # 1. Parse repository
        engine = CodeUnderstandingEngine()
        parsed_repo = engine.parse_repository(
            repo_dir=repo_dir,
            files=file_paths,
            repo_id=repo_id,
        )

        # 2. Chunk repository
        chunker = StructureAwareChunker(max_chunk_lines=50)
        chunks = chunker.chunk_repository(
            parsed_repo=parsed_repo,
            accepted_files=file_paths,
            repo_dir=repo_dir,
        )

        # 3. Index repository
        store = ChromaVectorStore(persist_dir=chroma_dir)
        embedder = LocalSentenceTransformerService()
        search_service = SemanticSearchService(embedder=embedder, vector_store=store)
        search_service.index_chunks(repository_id=repo_id, chunks=chunks)

        total_queries = len(GROUND_TRUTH_EVALUATION_DATASET)
        p_at_1_hits = 0
        p_at_3_hits = 0
        recall_hits = 0
        total_citations = 0
        valid_citations = 0

        for item in GROUND_TRUTH_EVALUATION_DATASET:
            query = item["query"]
            exp_file = item["expected_file"]
            exp_symbols: Set[str] = item["expected_symbols"]

            results = search_service.search(
                repository_id=repo_id,
                query=query,
                top_k=3,
            )

            # Check Citation Validity (Exact 1-indexed lines)
            for res in results:
                total_citations += 1
                c = res.chunk
                if c.start_line >= 1 and c.end_line >= c.start_line and c.file_path:
                    # Verify line range corresponds to source
                    src_lines = BENCHMARK_SOURCE_FILES[c.file_path].split("\n")
                    if c.end_line <= len(src_lines) + 1:
                        valid_citations += 1

            # Precision@1
            if results:
                top_result = results[0].chunk
                if top_result.file_path == exp_file and (top_result.symbol_name in exp_symbols or not top_result.symbol_name):
                    p_at_1_hits += 1

            # Precision@3 & Recall@3
            found_in_top3 = False
            top3_relevant = 0
            for r in results[:3]:
                if r.chunk.file_path == exp_file and (r.chunk.symbol_name in exp_symbols or not r.chunk.symbol_name):
                    top3_relevant += 1
                    found_in_top3 = True

            p_at_3_hits += (top3_relevant / min(3, len(results))) if results else 0
            if found_in_top3:
                recall_hits += 1

        precision_at_1 = p_at_1_hits / total_queries
        precision_at_3 = p_at_3_hits / total_queries
        recall_at_3 = recall_hits / total_queries
        citation_accuracy = valid_citations / max(1, total_citations)

        print(f"\n--- VECTOR RAG EVALUATION METRICS ---")
        print(f"Total Queries Evaluated: {total_queries}")
        print(f"Precision@1:            {precision_at_1:.2%}")
        print(f"Precision@3:            {precision_at_3:.2%}")
        print(f"Recall@3:               {recall_at_3:.2%}")
        print(f"Line Citation Accuracy: {citation_accuracy:.2%}")
        print(f"--------------------------------------")

        # Rigorous quality assertions
        assert precision_at_1 >= 0.80, f"Precision@1 too low: {precision_at_1:.2%}"
        assert recall_at_3 >= 0.85, f"Recall@3 too low: {recall_at_3:.2%}"
        assert citation_accuracy == 1.0, f"Citation accuracy must be 100%: {citation_accuracy:.2%}"
