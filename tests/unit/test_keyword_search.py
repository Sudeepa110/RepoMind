"""
Unit tests for the SQLite FTS5 Keyword Search Engine (Phase 6).
Verifies BM25 relevance scoring, symbol name boosting, incremental indexing,
metadata filtering, and repository isolation.
"""

import pytest
import tempfile
from pathlib import Path
from backend.app.vectorstore.interfaces import CodeChunk
from backend.app.retrieval.keyword_search import KeywordSearchEngine, clean_fts_token, sanitize_filename


@pytest.fixture
def temp_keyword_engine(tmp_path):
    engine = KeywordSearchEngine(persist_dir=tmp_path / "keywords")
    return engine


@pytest.fixture
def sample_chunks():
    return [
        CodeChunk(
            chunk_id="chunk_1",
            repository_id="test_repo",
            file_path="auth/service.py",
            symbol_id="auth.service.authenticate_user",
            symbol_name="authenticate_user",
            symbol_type="FUNCTION",
            language="python",
            start_line=10,
            end_line=25,
            source_code="def authenticate_user(username: str, password: str):\n    return verify_password(password)",
            signature="def authenticate_user(username: str, password: str) -> bool",
            docstring="Authenticates user against hashed database credential.",
            content_hash="hash_1",
            full_content="def authenticate_user(username: str, password: str):\n    return verify_password(password)",
            part_index=1,
            total_parts=1,
        ),
        CodeChunk(
            chunk_id="chunk_2",
            repository_id="test_repo",
            file_path="auth/hasher.py",
            symbol_id="auth.hasher.verify_password",
            symbol_name="verify_password",
            symbol_type="FUNCTION",
            language="python",
            start_line=5,
            end_line=15,
            source_code="def verify_password(plain_pwd: str, hashed_pwd: str):\n    return bcrypt.checkpw(plain_pwd, hashed_pwd)",
            signature="def verify_password(plain_pwd: str, hashed_pwd: str) -> bool",
            docstring="Verifies raw password matches bcrypt hash.",
            content_hash="hash_2",
            full_content="def verify_password(plain_pwd: str, hashed_pwd: str):\n    return bcrypt.checkpw(plain_pwd, hashed_pwd)",
            part_index=1,
            total_parts=1,
        ),
        CodeChunk(
            chunk_id="chunk_3",
            repository_id="test_repo",
            file_path="db/session.py",
            symbol_id="db.session.DatabaseSession",
            symbol_name="DatabaseSession",
            symbol_type="CLASS",
            language="python",
            start_line=1,
            end_line=30,
            source_code="class DatabaseSession:\n    def __init__(self):\n        self.pool = create_pool()",
            signature="class DatabaseSession",
            docstring="Manages pooled database connection sessions.",
            content_hash="hash_3",
            full_content="class DatabaseSession:\n    def __init__(self):\n        self.pool = create_pool()",
            part_index=1,
            total_parts=1,
        ),
    ]


def test_sanitize_helpers():
    assert sanitize_filename("owner/repo:name") == "owner_repo_name"
    assert clean_fts_token('foo "bar" * ^ (baz)') == "foo bar baz"


def test_index_and_search_bm25(temp_keyword_engine, sample_chunks):
    repo_id = "test_owner/test_repo"
    indexed_count = temp_keyword_engine.index_chunks(repo_id, sample_chunks)
    assert indexed_count == 3

    # Exact symbol search: "verify_password"
    results = temp_keyword_engine.search(repo_id, "verify_password", top_k=5)
    assert len(results) >= 1
    top = results[0]
    assert top.symbol_name == "verify_password"
    assert top.retrieval_source == "KEYWORD"
    assert "KEYWORD" in top.sources
    assert top.file_path == "auth/hasher.py"
    assert top.normalized_score > 0.0


def test_incremental_indexing_deduplication(temp_keyword_engine, sample_chunks):
    repo_id = "test_owner/test_repo"
    # First indexing
    count_1 = temp_keyword_engine.index_chunks(repo_id, sample_chunks)
    assert count_1 == 3

    # Second indexing without changes should index 0 chunks
    count_2 = temp_keyword_engine.index_chunks(repo_id, sample_chunks)
    assert count_2 == 0

    # Force reindex should re-insert all
    count_3 = temp_keyword_engine.index_chunks(repo_id, sample_chunks, force_reindex=True)
    assert count_3 == 3


def test_metadata_filtering(temp_keyword_engine, sample_chunks):
    repo_id = "test_owner/test_repo"
    temp_keyword_engine.index_chunks(repo_id, sample_chunks)

    # Search with symbol_type filter = CLASS
    res_class = temp_keyword_engine.search(repo_id, "session", symbol_type="CLASS")
    assert len(res_class) == 1
    assert res_class[0].symbol_name == "DatabaseSession"

    # Search with file_path filter
    res_file = temp_keyword_engine.search(repo_id, "password", file_path="auth/hasher.py")
    assert len(res_file) == 1
    assert res_file[0].file_path == "auth/hasher.py"


def test_delete_repository_keyword_index(temp_keyword_engine, sample_chunks):
    repo_id = "test_owner/delete_test"
    temp_keyword_engine.index_chunks(repo_id, sample_chunks)
    db_path = temp_keyword_engine._get_db_path(repo_id)
    assert db_path.exists()

    deleted = temp_keyword_engine.delete_repository(repo_id)
    assert deleted is True
    assert not db_path.exists()
