"""
Unit tests for Vector RAG components:
- Local SentenceTransformer embedding service
- Structure-aware chunking and splitting
- Persistent ChromaDB vector store
- Incremental indexing deduplication
- Repository isolation and cleanup
"""

import tempfile
from pathlib import Path
import pytest

from backend.app.processing.models import (
    ParsedRepository,
    ParsedFile,
    ExtractedSymbol,
    SymbolType,
    SymbolLocation,
)
from backend.app.vectorstore.interfaces import CodeChunk
from backend.app.vectorstore.embeddings import LocalSentenceTransformerService
from backend.app.vectorstore.chunker import StructureAwareChunker
from backend.app.vectorstore.chroma_store import ChromaVectorStore, sanitize_collection_name
from backend.app.retrieval.semantic_search import SemanticSearchService


def test_sanitize_collection_name():
    """Verify ChromaDB collection name sanitization satisfies length and character constraints."""
    assert sanitize_collection_name("my-repo").startswith("repo_")
    assert sanitize_collection_name("fastapi/fastapi") == "repo_fastapi_fastapi"
    assert sanitize_collection_name("special@#$%chars!").isalnum() or "_" in sanitize_collection_name("special@#$%chars!")
    # Long repository identifier
    long_id = "a" * 100
    sanitized = sanitize_collection_name(long_id)
    assert len(sanitized) <= 63
    assert len(sanitized) >= 3


def test_embedding_service_dimension_and_batch():
    """Verify local SentenceTransformer embedding output dimension and batch processing."""
    service = LocalSentenceTransformerService()
    assert service.dimension() == 384
    assert service.get_device() in ("cpu", "cuda")

    vec = service.embed_text("def authenticate_user(username, password): pass")
    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(x, float) for x in vec)

    batch_vecs = service.embed_batch(["function one", "function two", "class Three"])
    assert len(batch_vecs) == 3
    assert all(len(v) == 384 for v in batch_vecs)


def test_structure_aware_chunker_ast_symbols():
    """Verify AST symbols are converted to structure-aware CodeChunk objects preserving lines and symbols."""
    chunker = StructureAwareChunker(max_chunk_lines=50, chunk_overlap_lines=10)

    sym1 = ExtractedSymbol(
        symbol_id="test_repo:auth.py#verify_jwt",
        name="verify_jwt",
        symbol_type=SymbolType.FUNCTION,
        location=SymbolLocation(file_path="auth.py", start_line=10, end_line=25, start_column=0, end_column=0),
        source_code="def verify_jwt(token: str) -> dict:\n    \"\"\"Validates JWT token signature.\"\"\"\n    return decode(token)",
        docstring="Validates JWT token signature.",
        content_hash="hash12345678",
    )

    parsed_file = ParsedFile(
        file_path="auth.py",
        repository_id="test_repo",
        language="Python",
        symbols=[sym1],
        line_count=30,
        size_bytes=400,
    )

    chunks = chunker.chunk_parsed_file("test_repo", parsed_file)
    assert len(chunks) == 1

    c = chunks[0]
    assert c.chunk_id == "chunk:test_repo:auth.py#verify_jwt"
    assert c.repository_id == "test_repo"
    assert c.file_path == "auth.py"
    assert c.symbol_name == "verify_jwt"
    assert c.symbol_type == "FUNCTION"
    assert c.start_line == 10
    assert c.end_line == 25
    assert "verify_jwt" in c.context_header
    assert "Lines 10-25" in c.context_header
    assert c.content_hash == "hash12345678"
    assert "def verify_jwt" in c.full_content


def test_structure_aware_chunker_oversized_symbol_splitting():
    """Verify oversized functions/classes are split into overlapping sub-chunks with part numbers."""
    chunker = StructureAwareChunker(max_chunk_lines=15, chunk_overlap_lines=5)

    # Generate 40 lines of code
    long_code_lines = [f"    step_{i} = execute_step_{i}()" for i in range(40)]
    full_code = "def large_processing_pipeline():\n" + "\n".join(long_code_lines)

    sym = ExtractedSymbol(
        symbol_id="test_repo:pipeline.py#large_processing_pipeline",
        name="large_processing_pipeline",
        symbol_type=SymbolType.FUNCTION,
        location=SymbolLocation(file_path="pipeline.py", start_line=100, end_line=140, start_column=0, end_column=0),
        source_code=full_code,
        content_hash="pipelinehash",
    )

    parsed_file = ParsedFile(
        file_path="pipeline.py",
        repository_id="test_repo",
        language="Python",
        symbols=[sym],
        line_count=150,
        size_bytes=1200,
    )

    chunks = chunker.chunk_parsed_file("test_repo", parsed_file)
    assert len(chunks) > 1

    # First sub-chunk
    part1 = chunks[0]
    assert part1.part_index == 0
    assert part1.total_parts == len(chunks)
    assert "Part 1 of" in part1.context_header
    assert part1.start_line == 100

    # Second sub-chunk starts with overlap
    part2 = chunks[1]
    assert part2.part_index == 1
    assert part2.start_line > part1.start_line
    assert part2.start_line < part1.end_line  # Confirms overlap!


def test_structure_aware_chunker_markdown_and_manifest():
    """Verify markdown docs split on headings and configs split with sliding window."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)

        readme_file = tmp_path / "README.md"
        readme_file.write_text(
            "# Overview\nRepoMind is an intelligence platform.\n\n"
            "## Installation\nRun pip install repomind.\n\n"
            "## Architecture\nUses Hybrid Vector RAG and GraphRAG.\n",
            encoding="utf-8",
        )

        config_file = tmp_path / "package.json"
        config_file.write_text('{\n  "name": "repomind",\n  "version": "1.0.0"\n}\n', encoding="utf-8")

        chunker = StructureAwareChunker(max_chunk_lines=50)
        parsed_repo = ParsedRepository(
            repository_id="test_repo",
            files={},
            total_symbols=0,
            total_files=0,
        )

        chunks = chunker.chunk_repository(
            parsed_repo=parsed_repo,
            accepted_files=[readme_file, config_file],
            repo_dir=tmp_path,
        )

        assert len(chunks) >= 3

        # Markdown headings extracted as DOC chunks
        doc_chunks = [c for c in chunks if c.symbol_type == "DOC"]
        assert len(doc_chunks) >= 2
        assert any("Installation" in c.symbol_name for c in doc_chunks)

        # Config file extracted as CONFIG chunk
        cfg_chunks = [c for c in chunks if c.symbol_type == "CONFIG"]
        assert len(cfg_chunks) == 1
        assert cfg_chunks[0].file_path == "package.json"


def test_chroma_vector_store_persistence_and_isolation():
    """Verify ChromaDB stores, persists across reloads, searches with cosine similarity, and isolates collections."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        persist_path = Path(tmp_dir) / "chroma"

        # Initialize first instance
        store1 = ChromaVectorStore(persist_dir=persist_path)
        embedder = LocalSentenceTransformerService()

        c1 = CodeChunk(
            chunk_id="chunk:repoA:auth.py#login",
            repository_id="repoA",
            file_path="auth.py",
            symbol_name="login",
            symbol_type="FUNCTION",
            language="Python",
            start_line=1,
            end_line=10,
            source_code="def login(username, password):\n    return check_credentials(username, password)",
            content_hash="h1",
            context_header="# File: auth.py",
            full_content="def login(username, password):\n    return check_credentials(username, password)",
        )

        c2 = CodeChunk(
            chunk_id="chunk:repoA:db.py#connect",
            repository_id="repoA",
            file_path="db.py",
            symbol_name="connect",
            symbol_type="FUNCTION",
            language="Python",
            start_line=1,
            end_line=8,
            source_code="def connect(db_url):\n    return create_engine(db_url)",
            content_hash="h2",
            context_header="# File: db.py",
            full_content="def connect(db_url):\n    return create_engine(db_url)",
        )

        embeddings = embedder.embed_batch([c1.full_content, c2.full_content])
        upserted = store1.add_chunks("repoA", [c1, c2], embeddings)
        assert upserted == 2

        # Verify collection stats
        stats = store1.get_collection_stats("repoA")
        assert stats.total_chunks == 2
        assert stats.language_breakdown.get("Python") == 2

        # Verify collection isolation: repoB has 0 chunks
        stats_b = store1.get_collection_stats("repoB")
        assert stats_b.total_chunks == 0

        # Perform search for login
        q_emb = embedder.embed_text("user authentication and credential check")
        results = store1.search("repoA", q_emb, top_k=2)
        assert len(results) == 2
        assert results[0].chunk.symbol_name == "login"
        assert 0.0 <= results[0].similarity_score <= 1.0

        # Persistence check: reload store from disk
        store2 = ChromaVectorStore(persist_dir=persist_path)
        hashes = store2.get_existing_hashes("repoA")
        assert len(hashes) == 2
        assert hashes["chunk:repoA:auth.py#login"] == "h1"

        # Delete collection cleanup
        deleted = store2.delete_repository("repoA")
        assert deleted is True
        assert store2.get_collection_stats("repoA").total_chunks == 0
