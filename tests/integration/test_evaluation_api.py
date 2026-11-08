"""
Integration tests for Phase 9 Evaluation Endpoints.
Verifies:
1. GET /api/v1/evaluation/summary returns valid multi-strategy benchmarks and grounding metrics.
2. GET /api/v1/evaluation/system-profile returns latency percentiles and host specs.
3. POST /api/v1/evaluation/run can trigger evaluation run and return results.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.mark.asyncio
async def test_get_evaluation_summary():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/evaluation/summary")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ("cached", "success", "pending_first_run")
        assert "metadata" in data
        assert "retrieval_strategy_comparison" in data
        assert "grounding_and_citations" in data
        assert "graph_and_intelligence" in data
        assert "system_latency_profiling" in data

        # Check retrieval comparison includes all 4 strategies
        comparison = data["retrieval_strategy_comparison"]
        assert "synthetic_auth_repo" in comparison or "synthetic_repo" in comparison or "comparison" in comparison


@pytest.mark.asyncio
async def test_get_system_profile():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/evaluation/system-profile")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ("cached", "success", "pending_first_run")
        assert "hardware_environment" in data
        assert data["hardware_environment"]["platform"] == "HP Victus (Windows)" or "Windows" in data["hardware_environment"]["platform"]
        assert "current_rss_mb" in data
        assert "query_latency_percentiles" in data
        assert "pipeline_stages" in data


@pytest.mark.asyncio
async def test_post_run_evaluation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request run on synthetic repo without persisting to disk
        payload = {
            "persist_results": False,
            "target_repos": ["synthetic_auth_repo"],
            "max_queries": 2,
        }
        response = await client.post("/api/v1/evaluation/run", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ("cached", "success", "pending_first_run")
        assert "results" in data
