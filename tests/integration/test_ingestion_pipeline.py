import os
import shutil
import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.ingestion.cloner import RepositoryCloner, cleanup_workspace
from backend.app.services.indexing import process_repository_job

@pytest.mark.asyncio
async def test_cloner_invalid_and_inaccessible_urls():
    cloner = RepositoryCloner()

    # Invalid URL format
    res_invalid = cloner.clone_repository("https://invalid-host.com/test/repo")
    assert res_invalid.success is False
    assert "Invalid GitHub URL" in (res_invalid.error_message or "")

    # Nonexistent repo on GitHub
    res_nonexistent = cloner.clone_repository("https://github.com/repomind-test-nonexistent/definitely-not-real-12345")
    assert res_nonexistent.success is False
    assert "Git clone error" in (res_nonexistent.error_message or "")

@pytest.mark.asyncio
async def test_api_analyze_validation_and_path_traversal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Invalid URL to analyze endpoint
        res_bad = await client.post(
            "/api/v1/repositories/analyze",
            json={"url": "https://notgithub.com/foo/bar"}
        )
        assert res_bad.status_code == 400

        # 2. Path traversal attack check on /file endpoint
        res_traversal = await client.get(
            "/api/v1/repositories/fake-id/file?path=../../etc/passwd"
        )
        assert res_traversal.status_code == 400
        assert "path traversal" in res_traversal.json()["detail"].lower()

@pytest.mark.asyncio
async def test_full_ingestion_pipeline_with_test_repo():
    """
    Tests end-to-end ingestion pipeline using a lightweight test git repository:
    shallow clone -> file filtering -> analysis -> tree & file endpoint verification.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test with public small repository: octocat/Hello-World
        test_url = "https://github.com/octocat/Hello-World"

        # 1. Start analysis
        res_analyze = await client.post(
            "/api/v1/repositories/analyze",
            json={"url": test_url, "force_reindex": True}
        )
        assert res_analyze.status_code == 200
        data = res_analyze.json()
        assert "repository_id" in data
        assert "job_id" in data
        repo_id = data["repository_id"]
        job_id = data["job_id"]

        # Run worker processing directly to ensure completion in test environment
        await process_repository_job(job_id, repo_id, test_url)

        # 2. Check status
        res_status = await client.get(f"/api/v1/repositories/{repo_id}/status")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["status"] == "completed"
        assert status_data["progress_pct"] == 100

        # 3. Check repository details
        res_details = await client.get(f"/api/v1/repositories/{repo_id}")
        assert res_details.status_code == 200
        details = res_details.json()
        assert details["owner"].lower() == "octocat"
        assert details["name"].lower() == "hello-world"
        assert details["file_count"] >= 1
        assert details["status"] == "ready"

        # 4. Check directory tree
        res_tree = await client.get(f"/api/v1/repositories/{repo_id}/tree")
        assert res_tree.status_code == 200
        tree = res_tree.json()
        assert tree["type"] == "directory"

        # 5. Check file retrieval
        res_file = await client.get(f"/api/v1/repositories/{repo_id}/file?path=README")
        assert res_file.status_code == 200
        file_data = res_file.json()
        assert "content" in file_data
        assert "Hello World" in file_data["content"]
        assert file_data["line_count"] >= 1

        # 6. List repositories
        res_list = await client.get("/api/v1/repositories")
        assert res_list.status_code == 200
        repos = res_list.json()
        assert any(r["id"] == repo_id for r in repos)

        # 7. Cleanup via DELETE
        res_delete = await client.delete(f"/api/v1/repositories/{repo_id}")
        assert res_delete.status_code == 200

