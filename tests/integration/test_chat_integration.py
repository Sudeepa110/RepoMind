"""
Integration tests for Conversational Chat and Grounded Generation API (Phase 7).
Tests conversation creation, message history, Server-Sent Events (SSE) streaming protocol,
citation validation across hybrid retrieval, and repository isolation.
"""

import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select

from backend.app.main import app
from backend.app.database.session import AsyncSessionLocal, init_db
from backend.app.database.models import RepositoryModel
from backend.app.llm.gemini_client import gemini_client
from backend.app.llm.generation_models import ChatStreamRequest
from backend.app.retrieval.retrieval_models import UnifiedSearchResult, GraphEvidence, AssembledContext, HybridRetrievalResponse
from backend.app.retrieval.hybrid_retriever import hybrid_retriever


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.fixture
async def sample_repo():
    repo_id = "test-chat-repo-001"
    async with AsyncSessionLocal() as session:
        check = await session.execute(select(RepositoryModel).where(RepositoryModel.id == repo_id))
        if not check.scalar_one_or_none():
            repo = RepositoryModel(
                id=repo_id,
                owner="repomind-test",
                name="chat-testing-repo",
                url="https://github.com/repomind-test/chat-testing-repo",
                primary_language="Python",
                status="ready",
            )
            session.add(repo)
            await session.commit()
    return repo_id


@pytest.fixture
def mock_retrieval(monkeypatch):
    """Mocks hybrid retriever to return predictable code chunks and graph relations."""
    def fake_hybrid_search(repo_id, request):
        if "unrelated" in request.query.lower() or "quantum" in request.query.lower():
            return HybridRetrievalResponse(
                query=request.query,
                repository_id=repo_id,
                intents=["CONCEPTUAL"],
                strategies_used=["VECTOR"],
                total_results=0,
                results=[],
                graph_evidence=[],
                assembled_context=AssembledContext(
                    summary="No relevant evidence found.",
                    total_code_chunks=0,
                    total_graph_relationships=0,
                    sources_used=[],
                    formatted_context="No evidence.",
                    citations=[],
                ),
            )

        results = [
            UnifiedSearchResult(
                chunk_id="chunk-auth-01",
                repository_id=repo_id,
                file_path="src/auth/jwt_handler.py",
                symbol_name="create_access_token",
                symbol_type="function",
                language="python",
                start_line=15,
                end_line=35,
                source_code="def create_access_token(data: dict) -> str:\n    return jwt.encode(data, SECRET_KEY, algorithm='HS256')\n",
                retrieval_source="VECTOR",
                sources=["VECTOR", "KEYWORD"],
                original_score=0.92,
                normalized_score=0.94,
                rrf_score=0.033,
                confidence=0.94,
            ),
            UnifiedSearchResult(
                chunk_id="chunk-auth-02",
                repository_id=repo_id,
                file_path="src/auth/jwt_handler.py",
                symbol_name="verify_access_token",
                symbol_type="function",
                language="python",
                start_line=38,
                end_line=60,
                source_code="def verify_access_token(token: str) -> dict:\n    return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])\n",
                retrieval_source="KEYWORD",
                sources=["KEYWORD"],
                original_score=4.8,
                normalized_score=0.88,
                rrf_score=0.025,
                confidence=0.88,
            ),
        ]
        graph_ev = [
            GraphEvidence(
                relationship_type="CALLS",
                source_node_id="src/api/routes.py:login",
                source_name="login",
                target_node_id="src/auth/jwt_handler.py:create_access_token",
                target_name="create_access_token",
                confidence=1.0,
                is_confirmed=True,
                call_count=1,
                lines=[42],
                file_path="src/auth/jwt_handler.py",
                description="login calls create_access_token",
            )
        ]
        return HybridRetrievalResponse(
            query=request.query,
            repository_id=repo_id,
            intents=["CODE_SEARCH", "SEMANTIC"],
            strategies_used=["VECTOR", "KEYWORD", "GRAPH"],
            total_results=2,
            results=results,
            graph_evidence=graph_ev,
            assembled_context=AssembledContext(
                summary="Retrieved 2 code chunks and 1 graph relationship.",
                total_code_chunks=2,
                total_graph_relationships=1,
                sources_used=["VECTOR", "KEYWORD", "GRAPH"],
                formatted_context="[Chunk 1: src/auth/jwt_handler.py:15-35]\n[Chunk 2: src/auth/jwt_handler.py:38-60]",
                citations=[],
            ),
        )

    monkeypatch.setattr(hybrid_retriever, "hybrid_search", fake_hybrid_search)


@pytest.fixture
def mock_gemini(monkeypatch):
    """Mocks Gemini generate and streaming methods."""
    async def fake_generate(prompt, system_instruction=None, temperature=None, max_output_tokens=None, timeout_seconds=None):
        return (
            "Access tokens are generated in `create_access_token` [src/auth/jwt_handler.py:15-35] "
            "and validated in `verify_access_token` [src/auth/jwt_handler.py:38-60]."
        )

    async def fake_generate_stream(prompt, system_instruction=None, temperature=None, max_output_tokens=None, timeout_seconds=None):
        tokens = [
            "Access tokens ",
            "are generated in `create_access_token` ",
            "[src/auth/jwt_handler.py:15-35] ",
            "and validated in `verify_access_token` ",
            "[src/auth/jwt_handler.py:38-60].",
        ]
        for t in tokens:
            yield t

    monkeypatch.setattr(gemini_client, "generate", fake_generate)
    monkeypatch.setattr(gemini_client, "generate_stream", fake_generate_stream)


@pytest.mark.asyncio
async def test_conversation_crud_endpoints(sample_repo):
    repo_id = sample_repo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create conversation
        res = await client.post(f"/api/v1/repositories/{repo_id}/conversations", json={"title": "Test Chat"})
        assert res.status_code == 201
        data = res.json()
        conv_id = data["id"]
        assert data["title"] == "Test Chat"
        assert data["repository_id"] == repo_id

        # 2. List conversations
        list_res = await client.get(f"/api/v1/repositories/{repo_id}/conversations")
        assert list_res.status_code == 200
        convs = list_res.json()
        assert any(c["id"] == conv_id for c in convs)

        # 3. Get conversation detail
        get_res = await client.get(f"/api/v1/repositories/{repo_id}/conversations/{conv_id}")
        assert get_res.status_code == 200
        detail = get_res.json()
        assert detail["id"] == conv_id
        assert detail["messages"] == []

        # 4. Delete conversation
        del_res = await client.delete(f"/api/v1/repositories/{repo_id}/conversations/{conv_id}")
        assert del_res.status_code == 200

        # Verify deletion
        get_after = await client.get(f"/api/v1/repositories/{repo_id}/conversations/{conv_id}")
        assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_non_streaming_chat_endpoint(sample_repo, mock_retrieval, mock_gemini):
    repo_id = sample_repo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "Where are JWT tokens created and verified?",
            "top_k": 5,
        }
        res = await client.post(f"/api/v1/repositories/{repo_id}/chat", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert "create_access_token" in data["content"]
        assert len(data["citations"]) >= 2
        assert data["citations"][0]["file_path"] == "src/auth/jwt_handler.py"
        assert data["citations"][0]["start_line"] == 15
        assert data["evidence_sufficiency"] == "SUFFICIENT"
        assert data["confidence"] > 0.8


@pytest.mark.asyncio
async def test_streaming_chat_sse_protocol(sample_repo, mock_retrieval, mock_gemini):
    repo_id = sample_repo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "Explain JWT implementation details",
            "top_k": 5,
        }
        res = await client.post(f"/api/v1/repositories/{repo_id}/chat/stream", json=payload)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        body_text = res.text
        assert "event: retrieval_started" in body_text
        assert "event: retrieval_completed" in body_text
        assert "event: generation_started" in body_text
        assert "event: token" in body_text
        assert "event: citation" in body_text
        assert "event: done" in body_text


@pytest.mark.asyncio
async def test_no_evidence_grounded_response(sample_repo, mock_retrieval, mock_gemini):
    repo_id = sample_repo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "How is the quantum teleportation algorithm initialized in this project?",
            "top_k": 5,
        }
        res = await client.post(f"/api/v1/repositories/{repo_id}/chat", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert "does not contain sufficient evidence" in data["content"].lower()
        assert data["evidence_sufficiency"] == "NO_EVIDENCE"
        assert len(data["citations"]) == 0
        assert data["confidence"] == 0.0
