import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.services.indexing import process_repository_job

@pytest.mark.asyncio
async def test_small_python_repository_ingestion():
    """Test Case 1: Small Python Repository."""
    test_url = "https://github.com/octocat/Spoon-Knife"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Start analysis
        res_analyze = await client.post(
            "/api/v1/repositories/analyze",
            json={"url": test_url, "force_reindex": True}
        )
        assert res_analyze.status_code == 200
        data = res_analyze.json()
        repo_id = data["repository_id"]
        job_id = data["job_id"]

        # Run worker processing
        await process_repository_job(job_id, repo_id, test_url)

        # Verify status
        res_status = await client.get(f"/api/v1/repositories/{repo_id}/status")
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "completed"

        # Verify details
        res_details = await client.get(f"/api/v1/repositories/{repo_id}")
        assert res_details.status_code == 200
        details = res_details.json()
        assert details["owner"].lower() == "octocat"
        assert details["name"].lower() == "spoon-knife"
        assert details["file_count"] >= 1
        assert details["status"] == "ready"

        # Verify tree
        res_tree = await client.get(f"/api/v1/repositories/{repo_id}/tree")
        assert res_tree.status_code == 200

        # Cleanup
        await client.delete(f"/api/v1/repositories/{repo_id}")

@pytest.mark.asyncio
async def test_javascript_typescript_repository_ingestion():
    """Test Case 2: JavaScript/TypeScript Repository."""
    test_url = "https://github.com/expressjs/cookie-parser"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Start analysis
        res_analyze = await client.post(
            "/api/v1/repositories/analyze",
            json={"url": test_url, "force_reindex": True}
        )
        assert res_analyze.status_code == 200
        data = res_analyze.json()
        repo_id = data["repository_id"]
        job_id = data["job_id"]

        # Run worker processing
        await process_repository_job(job_id, repo_id, test_url)

        # Verify status
        res_status = await client.get(f"/api/v1/repositories/{repo_id}/status")
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "completed"

        # Verify details
        res_details = await client.get(f"/api/v1/repositories/{repo_id}")
        assert res_details.status_code == 200
        details = res_details.json()
        assert details["status"] == "ready"
        assert details["owner"].lower() == "expressjs"
        assert details["name"].lower() == "cookie-parser"
        # package.json should be identified as a manifest
        assert any("package.json" in m for m in details["manifest_files"])
        assert any(l["name"] in ("JavaScript", "JSON", "Markdown") for l in details["languages"])

        # Verify file content
        res_file = await client.get(f"/api/v1/repositories/{repo_id}/file?path=index.js")
        assert res_file.status_code == 200
        file_data = res_file.json()
        assert "cookieParser" in file_data["content"]
        assert file_data["language"] == "JavaScript"

        # Cleanup
        await client.delete(f"/api/v1/repositories/{repo_id}")
