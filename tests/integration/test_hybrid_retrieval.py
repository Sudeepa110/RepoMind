"""
Integration tests for Hybrid Retrieval Engine (Phase 6).
Verifies coordinated retrieval across Vector RAG (ChromaDB), GraphRAG (NetworkX),
and Keyword Search (SQLite FTS5), including Reciprocal Rank Fusion,
context assembly, and FastAPI endpoints.
"""

import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.processing.engine import CodeUnderstandingEngine
from backend.app.vectorstore.chunker import StructureAwareChunker
from backend.app.vectorstore.interfaces import CodeChunk
from backend.app.retrieval.semantic_search import semantic_search_service
from backend.app.retrieval.keyword_search import keyword_search_engine
from backend.app.graph.builder import graph_builder
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.retrieval.hybrid_retriever import hybrid_retriever
from backend.app.retrieval.retrieval_models import HybridSearchRequest
from backend.app.database.session import AsyncSessionLocal
from backend.app.database.models import RepositoryModel
from sqlalchemy import select


@pytest.fixture
def sample_hybrid_repo():
    """Builds a temporary multi-file codebase and indexes across Vector, Graph, and Keyword stores."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        repo_dir = Path(tmp_dir) / "repo"
        repo_dir.mkdir(parents=True)
        repo_id = "test_hybrid_repo"

        # 1. Create Python auth file
        auth_file = repo_dir / "auth.py"
        auth_file.write_text(
            'import bcrypt\n\n'
            'def hash_password(plain_password: str) -> str:\n'
            '    """Hashes a password with salt."""\n'
            '    salt = bcrypt.gensalt()\n'
            '    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")\n\n'
            'def verify_password(plain_password: str, hashed_password: str) -> bool:\n'
            '    """Verifies plain password against bcrypt hash."""\n'
            '    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))\n\n'
            'def login_user(username: str, password: str):\n'
            '    """Logs in user by verifying credentials."""\n'
            '    return verify_password(password, "mock_hash")\n',
            encoding="utf-8",
        )

        # 2. Create TypeScript database client
        db_file = repo_dir / "database.ts"
        db_file.write_text(
            'export class DatabasePool {\n'
            '  private pool: any;\n\n'
            '  constructor(url: string) {\n'
            '    this.pool = url;\n'
            '  }\n\n'
            '  async query(sql: string): Promise<any> {\n'
            '    return { rows: [] };\n'
            '  }\n'
            '}\n',
            encoding="utf-8",
        )

        engine = CodeUnderstandingEngine()
        files = [auth_file, db_file]
        parsed_repo = engine.parse_repository(repo_dir, files, repo_id=repo_id, commit_hash="c_hybrid")

        # Chunk repository
        chunker = StructureAwareChunker()
        chunks = chunker.chunk_repository(parsed_repo, files, repo_dir)

        # Index into ChromaDB
        semantic_search_service.index_chunks(repo_id, chunks, force_reindex=True)

        # Index into SQLite FTS5
        keyword_search_engine.index_chunks(repo_id, chunks, force_reindex=True)

        # Index into Knowledge Graph
        graph_builder.build_and_persist_graph(parsed_repo)

        yield {
            "repo_id": repo_id,
            "chunks": chunks,
            "parsed_repo": parsed_repo,
        }

        # Cleanup
        semantic_search_service.delete_repository(repo_id)
        keyword_search_engine.delete_repository(repo_id)
        networkx_graph_store.delete(repo_id)


def test_hybrid_search_exact_symbol(sample_hybrid_repo):
    repo_id = sample_hybrid_repo["repo_id"]
    req = HybridSearchRequest(
        query="definition of verify_password",
        top_k=5,
    )

    res = hybrid_retriever.hybrid_search(repo_id, req)

    assert res.total_results > 0
    top = res.results[0]
    assert top.symbol_name == "verify_password"
    assert top.rrf_score > 0.0
    assert "KEYWORD" in top.sources or "VECTOR" in top.sources
    assert len(res.assembled_context.citations) > 0


def test_hybrid_search_callers_intent(sample_hybrid_repo):
    repo_id = sample_hybrid_repo["repo_id"]
    req = HybridSearchRequest(
        query="Who calls verify_password?",
        top_k=5,
    )

    res = hybrid_retriever.hybrid_search(repo_id, req)

    # Intents should include CALLERS
    assert "CALLERS" in res.intents
    # Graph evidence should show login_user calls verify_password
    assert len(res.graph_evidence) >= 1
    call_ev = next((e for e in res.graph_evidence if e.relationship_type == "CALLS"), None)
    assert call_ev is not None
    assert call_ev.source_name == "login_user"
    assert call_ev.target_name == "verify_password"
    assert call_ev.is_confirmed is True

    # Assembled context should mention the relationship
    assert "login_user" in res.assembled_context.formatted_context
    assert "verify_password" in res.assembled_context.formatted_context


def test_hybrid_search_engine_overrides(sample_hybrid_repo):
    repo_id = sample_hybrid_repo["repo_id"]
    # Force disable vector search
    req = HybridSearchRequest(
        query="database connection pool",
        top_k=3,
        include_vector=False,
        include_keyword=True,
    )

    res = hybrid_retriever.hybrid_search(repo_id, req)
    assert "VECTOR" not in res.strategies_used
    assert "KEYWORD" in res.strategies_used


@pytest.mark.asyncio
async def test_hybrid_retrieval_api_endpoints(sample_hybrid_repo):
    repo_id = sample_hybrid_repo["repo_id"]

    # Ensure repository model exists in DB for foreign key / exists check
    async with AsyncSessionLocal() as session:
        check = await session.execute(select(RepositoryModel).where(RepositoryModel.id == repo_id))
        if not check.scalar_one_or_none():
            repo_model = RepositoryModel(
                id=repo_id,
                owner="testhybrid",
                name="hybridrepo",
                url="https://github.com/testhybrid/hybridrepo",
                status="ready",
            )
            session.add(repo_model)
            await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 404 for unknown repository
        res_404 = await client.post(
            "/api/v1/repositories/unknown_repo_id/hybrid-search",
            json={"query": "test", "top_k": 3},
        )
        assert res_404.status_code == 404

        # 2. POST /hybrid-search
        search_res = await client.post(
            f"/api/v1/repositories/{repo_id}/hybrid-search",
            json={"query": "who calls verify_password", "top_k": 5},
        )
        assert search_res.status_code == 200
        data = search_res.json()
        assert data["repository_id"] == repo_id
        assert data["total_results"] >= 1
        assert "CALLERS" in data["intents"]
        assert "assembled_context" in data
        assert len(data["assembled_context"]["citations"]) >= 1

        # 3. POST /analyze-query
        diag_res = await client.post(
            f"/api/v1/repositories/{repo_id}/analyze-query",
            json={"query": "What does login_user invoke?", "top_k": 5},
        )
        assert diag_res.status_code == 200
        diag_data = diag_res.json()
        assert "CALLEES" in diag_data["intents"]
        assert "login_user" in diag_data["extracted_symbols"]
