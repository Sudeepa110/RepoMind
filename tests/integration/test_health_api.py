import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app

@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "RepoMind"
        assert data["status"] == "operational"

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "environment" in data
        assert "gpu_available" in data
        assert "gemini_configured" in data
        assert "timestamp" in data
        assert "system_info" in data

@pytest.mark.asyncio
async def test_demo_repositories_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/repositories/demos")
        assert response.status_code == 200
        demos = response.json()
        assert isinstance(demos, list)
        assert len(demos) >= 3
        for demo in demos:
            assert "name" in demo
            assert "url" in demo
            assert "language" in demo

@pytest.mark.asyncio
async def test_validate_repository_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid format
        res_invalid = await client.post(
            "/api/v1/repositories/validate",
            json={"url": "https://invalid-host.com/user/repo"}
        )
        assert res_invalid.status_code == 200
        data_invalid = res_invalid.json()
        assert data_invalid["is_valid"] is False

        # Valid format
        res_valid = await client.post(
            "/api/v1/repositories/validate",
            json={"url": "https://github.com/fastapi/fastapi"}
        )
        assert res_valid.status_code == 200
        data_valid = res_valid.json()
        assert data_valid["is_valid"] is True
        assert data_valid["owner"] == "fastapi"
        assert data_valid["repo"] == "fastapi"

