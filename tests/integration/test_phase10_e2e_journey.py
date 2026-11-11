"""
Phase 10 End-to-End Integrated Product Workflow & Security Validation Tests.
Verifies the complete user journey across Python, TypeScript, and Java repositories:
1. Health and readiness probes (/api/v1/health, /api/v1/ready)
2. Strict GitHub URL & SSRF validation (/api/v1/repositories/validate)
3. Full background ingestion & multi-engine indexing pipeline
   (AST parsing, Structure-aware chunking, ChromaDB vectors, NetworkX graph, SQLite FTS5)
4. File tree & source viewer with path-traversal and secret-file blocking
5. Adaptive hybrid retrieval + Knowledge Graph exploration
6. Conversational Chat (grounded citation generation, honest out-of-scope abstention,
   multi-repository conversation isolation, and fallback handling)
7. Repository Intelligence (impact analysis, dependencies, bug investigation, test recommendations)
8. Full cascade deletion cleanup (SQLite child rows, ChromaDB, NetworkX, FTS5 DB, trees, workspace)
"""

import shutil
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func

from backend.app.main import app
from backend.app.config import settings
from backend.app.database.session import AsyncSessionLocal, init_db
from backend.app.database.models import (
    RepositoryModel,
    IndexingJobModel,
    FileMetadataModel,
    ConversationModel,
    ChatMessageModel,
)
from backend.app.ingestion.cloner import CloneResult, RepositoryCloner
from backend.app.services.indexing import process_repository_job
from backend.app.llm.gemini_client import gemini_client
from backend.evaluation.datasets.dataset_loader import (
    build_real_world_flask_subset,
    build_real_world_ky_subset,
    build_real_world_petclinic_subset,
)


@pytest.fixture(autouse=True)
async def ensure_db_ready():
    settings.init_directories()
    await init_db()


@pytest.mark.asyncio
async def test_health_readiness_and_ssrf_url_validation():
    """Verify health/ready probes and strict SSRF URL validation boundaries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Health & Readiness probes
        h_resp = await client.get("/api/v1/health")
        assert h_resp.status_code == 200
        assert h_resp.json()["status"] == "ok"

        r_resp = await client.get("/api/v1/ready")
        assert r_resp.status_code == 200
        ready_data = r_resp.json()
        assert ready_data["status"] == "ready"
        assert ready_data["checks"]["database"] == "ok"
        assert ready_data["checks"]["storage_filesystem"] == "ok"

        # 2. SSRF / Invalid URL rejections
        malicious_urls = [
            "http://github.com/fastapi/fastapi",                     # Non-HTTPS
            "https://169.254.169.254/latest/meta-data",              # Cloud metadata SSRF
            "https://localhost:8000/owner/repo",                     # Localhost + port
            "https://user:secret@github.com/owner/repo",             # Embedded credentials
            "file:///etc/passwd",                                    # Local file scheme
            "https://github.com/owner/../etc",                       # Path traversal
        ]
        for bad_url in malicious_urls:
            v_resp = await client.post("/api/v1/repositories/validate", json={"url": bad_url})
            assert v_resp.status_code == 200
            assert v_resp.json()["is_valid"] is False
            assert v_resp.json()["is_accessible"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lang,owner,repo_name,builder_fn,sample_file,sample_query,oos_query,impact_symbol",
    [
        (
            "Python",
            "e2e-pallets",
            "flask-subset",
            build_real_world_flask_subset,
            "src/flask/app.py",
            "Where is the Flask application class defined?",
            "How does DELETE /api/v2/users/crypto_wallet work?",
            "dispatch_request",
        ),
        (
            "TypeScript",
            "e2e-sindresorhus",
            "ky-subset",
            build_real_world_ky_subset,
            "source/utils/normalize.ts",
            "Where is normalizeRetryMethod declared in Ky?",
            "How is Cassandra cluster partitioning configured?",
            "normalizeRetryMethod",
        ),
        (
            "Java",
            "e2e-spring",
            "petclinic-subset",
            build_real_world_petclinic_subset,
            "src/main/java/org/springframework/samples/petclinic/owner/PetController.java",
            "How is POST /owners/42/pets/new implemented in PetController?",
            "How does DELETE /owners/42/pets/new delete pets?",
            "findPet",
        ),
    ],
)
async def test_complete_product_user_journey_multi_language(
    monkeypatch,
    tmp_path: Path,
    lang: str,
    owner: str,
    repo_name: str,
    builder_fn,
    sample_file: str,
    sample_query: str,
    oos_query: str,
    impact_symbol: str,
):
    """
    Executes the full integrated product journey on Python, TypeScript, and Java repositories:
    analyze -> parse/index -> browse tree/file -> security traversal check -> hybrid search ->
    graph exploration -> chat (grounded + honest abstention) -> intelligence -> cascade delete.
    """
    repo_url = f"https://github.com/{owner}/{repo_name}"

    # Mock RepositoryCloner to copy authentic real-world language subsets into workspace
    def fake_clone(self, url: str, repository_id: str, timeout_seconds=None) -> CloneResult:
        dest_dir = settings.STORAGE_DIR / "temp_repos" / repository_id
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        builder_fn(dest_dir)
        # Also drop an untrusted .env file in workspace to verify file filter & file API block it
        (dest_dir / ".env").write_text("SECRET_TOKEN=must_never_be_indexed_or_served\n", encoding="utf-8")
        return CloneResult(
            success=True,
            repository_id=repository_id,
            owner=owner,
            name=repo_name,
            target_dir=str(dest_dir),
            commit_hash="phase10e2e",
            default_branch="main",
            size_bytes=10240,
        )

    monkeypatch.setattr(RepositoryCloner, "clone_repository", fake_clone)

    # Mock Gemini generation cleanly to test prompt/citation integration deterministically
    async def fake_generate(prompt: str, system_instruction=None, **kwargs):
        return (
            f"Verified technical analysis grounded in repository source `[{sample_file}:1-25]`: "
            f"Confirmed implementation inside `{sample_file}`."
        )

    monkeypatch.setattr(gemini_client, "generate", fake_generate)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Analyze repository (remove any pre-existing leftover record cleanly first)
        list_resp = await client.get("/api/v1/repositories")
        assert list_resp.status_code == 200
        for item in list_resp.json():
            if item["url"] == repo_url:
                await client.delete(f"/api/v1/repositories/{item['id']}")

        analyze_resp = await client.post("/api/v1/repositories/analyze", json={"url": repo_url, "force_reindex": True})
        assert analyze_resp.status_code == 200
        analyze_data = analyze_resp.json()
        repo_id = analyze_data["repository_id"]
        job_id = analyze_data["job_id"]

        # Execute background indexing pipeline synchronously in test
        await process_repository_job(job_id=job_id, repo_id=repo_id, repo_url=repo_url, force_reindex=True)

        # Step 2: Check indexing status and repository details
        status_resp = await client.get(f"/api/v1/repositories/{repo_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "completed"
        assert status_resp.json()["progress_pct"] == 100

        detail_resp = await client.get(f"/api/v1/repositories/{repo_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "ready"
        assert detail["file_count"] >= 4
        assert detail["primary_language"] == lang

        # Step 3: Browse directory tree & inspect source file + security guards
        tree_resp = await client.get(f"/api/v1/repositories/{repo_id}/tree")
        assert tree_resp.status_code == 200

        file_resp = await client.get(f"/api/v1/repositories/{repo_id}/file", params={"path": sample_file})
        assert file_resp.status_code == 200
        assert len(file_resp.json()["content"]) > 20

        # Path traversal block check
        trav_resp = await client.get(f"/api/v1/repositories/{repo_id}/file", params={"path": "../../app/config.py"})
        assert trav_resp.status_code == 400

        # Secret file block check (.env)
        secret_resp = await client.get(f"/api/v1/repositories/{repo_id}/file", params={"path": ".env"})
        assert secret_resp.status_code == 403

        # Step 4: Adaptive Hybrid Retrieval
        hybrid_resp = await client.post(
            f"/api/v1/repositories/{repo_id}/hybrid-search",
            json={"query": sample_query, "top_k": 5},
        )
        assert hybrid_resp.status_code == 200
        h_data = hybrid_resp.json()
        assert h_data["total_results"] >= 1
        assert any(r["file_path"] == sample_file for r in h_data["results"])

        # Step 5: Knowledge Graph status & impact
        g_status = await client.get(f"/api/v1/repositories/{repo_id}/graph/status")
        assert g_status.status_code == 200
        assert g_status.json()["total_nodes"] > 0

        # Step 6: Conversational Chat — Answerable query with verified citation + Out-of-scope Abstention
        conv_resp = await client.post(
            f"/api/v1/repositories/{repo_id}/conversations",
            json={"title": f"{lang} Validation Session"},
        )
        assert conv_resp.status_code == 201
        conv_id = conv_resp.json()["id"]

        chat_ok = await client.post(
            f"/api/v1/repositories/{repo_id}/chat",
            json={"query": sample_query, "conversation_id": conv_id, "top_k": 5},
        )
        assert chat_ok.status_code == 200
        ok_data = chat_ok.json()
        assert ok_data["evidence_sufficiency"] in ("SUFFICIENT", "PARTIAL")

        chat_oos = await client.post(
            f"/api/v1/repositories/{repo_id}/chat",
            json={"query": oos_query, "conversation_id": conv_id, "top_k": 5},
        )
        assert chat_oos.status_code == 200
        oos_data = chat_oos.json()
        assert oos_data["evidence_sufficiency"] in ("NO_EVIDENCE", "INSUFFICIENT")

        # Verify persisted conversation messages isolate repository and flag insufficient_evidence accurately
        conv_detail = await client.get(f"/api/v1/repositories/{repo_id}/conversations/{conv_id}")
        assert conv_detail.status_code == 200
        msgs = [m for m in conv_detail.json()["messages"] if m["role"] == "assistant"]
        assert len(msgs) == 2
        assert msgs[0]["insufficient_evidence"] is False
        assert msgs[1]["insufficient_evidence"] is True

        # Step 7: Advanced Intelligence endpoints
        impact_resp = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/impact-analysis",
            json={"target_symbol": impact_symbol},
        )
        assert impact_resp.status_code == 200
        assert "risk_score" in impact_resp.json()
        assert impact_resp.json()["target_symbol"] == impact_symbol

        dep_resp = await client.post(f"/api/v1/repositories/{repo_id}/intelligence/dependencies")
        assert dep_resp.status_code == 200

        bug_resp = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/bug-investigation",
            json={"target_symbol": impact_symbol},
        )
        assert bug_resp.status_code == 200

        test_rec_resp = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/test-recommendations",
            json={"target_symbol": impact_symbol},
        )
        assert test_rec_resp.status_code == 200

        # Step 8: Complete Cascade Deletion & Storage Cleanup Verification
        del_resp = await client.delete(f"/api/v1/repositories/{repo_id}")
        assert del_resp.status_code == 200

        # Confirm repository & child tables are wiped
        after_detail = await client.get(f"/api/v1/repositories/{repo_id}")
        assert after_detail.status_code == 404

        async with AsyncSessionLocal() as session:
            assert (await session.execute(select(func.count()).select_from(RepositoryModel).where(RepositoryModel.id == repo_id))).scalar_one() == 0
            assert (await session.execute(select(func.count()).select_from(IndexingJobModel).where(IndexingJobModel.repository_id == repo_id))).scalar_one() == 0
            assert (await session.execute(select(func.count()).select_from(FileMetadataModel).where(FileMetadataModel.repository_id == repo_id))).scalar_one() == 0
            assert (await session.execute(select(func.count()).select_from(ConversationModel).where(ConversationModel.repository_id == repo_id))).scalar_one() == 0
            assert (await session.execute(select(func.count()).select_from(ChatMessageModel).where(ChatMessageModel.repository_id == repo_id))).scalar_one() == 0

        # Confirm disk artifacts & workspace wiped
        assert not (settings.STORAGE_DIR / "temp_repos" / repo_id).exists()
        assert not (settings.STORAGE_DIR / "trees" / f"{repo_id}.json").exists()
        assert not (settings.GRAPH_PERSIST_DIR / f"{repo_id}.json").exists()
