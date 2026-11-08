"""
Integration tests for Advanced Repository Intelligence Endpoints (Phase 8).
Tests impact analysis, execution flow, dependency metrics, bug investigation,
risk assessment, test recommendations, and technical documentation APIs.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.main import app
from backend.app.database.session import AsyncSessionLocal
from backend.app.database.models import RepositoryModel
from backend.app.graph.interfaces import (
    GraphNode,
    GraphEdge,
    NodeType,
    RelationshipType,
)
from backend.app.graph.networkx_store import networkx_graph_store


@pytest.fixture(autouse=True)
async def setup_intelligence_test_repo():
    repo_id = "test_intel_repo"

    # Add nodes to graph
    node_api = GraphNode(
        id=f"{repo_id}:backend/api/auth.py:login_endpoint",
        repository_id=repo_id,
        type=NodeType.FUNCTION,
        name="login_endpoint",
        file_path="backend/api/auth.py",
        start_line=10,
        end_line=25,
    )
    node_svc = GraphNode(
        id=f"{repo_id}:backend/services/auth.py:verify_credentials",
        repository_id=repo_id,
        type=NodeType.FUNCTION,
        name="verify_credentials",
        file_path="backend/services/auth.py",
        start_line=30,
        end_line=50,
    )
    node_model = GraphNode(
        id=f"{repo_id}:backend/models/user.py:UserAccount",
        repository_id=repo_id,
        type=NodeType.CLASS,
        name="UserAccount",
        file_path="backend/models/user.py",
        start_line=5,
        end_line=35,
    )

    networkx_graph_store.add_node(node_api)
    networkx_graph_store.add_node(node_svc)
    networkx_graph_store.add_node(node_model)

    # CALLS edge: login_endpoint -> verify_credentials
    networkx_graph_store.add_edge(GraphEdge(
        source_id=node_api.id,
        target_id=node_svc.id,
        relationship=RelationshipType.CALLS,
        repository_id=repo_id,
        confidence=1.0,
        is_confirmed=True,
        resolution_status="CONFIRMED",
    ))

    # Add RepositoryModel to SQLite DB
    async with AsyncSessionLocal() as session:
        check = await session.execute(select(RepositoryModel).where(RepositoryModel.id == repo_id))
        if not check.scalar_one_or_none():
            repo = RepositoryModel(
                id=repo_id,
                owner="testorg",
                name="testintel",
                url="https://github.com/testorg/testintel",
                status="ready",
            )
            session.add(repo)
            await session.commit()

    yield repo_id


@pytest.mark.asyncio
async def test_intelligence_endpoints_e2e(setup_intelligence_test_repo):
    repo_id = setup_intelligence_test_repo
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 404 for unknown repository
        res_404 = await client.post(
            "/api/v1/repositories/non_existent_repo/intelligence/impact-analysis",
            json={"target_symbol": "login_endpoint"}
        )
        assert res_404.status_code == 404

        # 2. Impact Analysis
        res_impact = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/impact-analysis",
            json={"target_symbol": "verify_credentials", "max_depth": 3}
        )
        assert res_impact.status_code == 200
        data_impact = res_impact.json()
        assert data_impact["target_symbol"] == "verify_credentials"
        assert data_impact["direct_count"] >= 1
        assert "login_endpoint" in [e["name"] for e in data_impact["affected_entities"]]

        # 3. Execution Flow
        res_flow = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/execution-flow",
            json={"entry_point": "login_endpoint", "max_depth": 4}
        )
        assert res_flow.status_code == 200
        data_flow = res_flow.json()
        assert data_flow["entry_point"] == "login_endpoint"
        assert data_flow["total_steps"] >= 2
        assert any(s["symbol_name"] == "verify_credentials" for s in data_flow["steps"])

        # 4. Dependency Analysis
        res_dep = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/dependencies",
        )
        assert res_dep.status_code == 200
        data_dep = res_dep.json()
        assert data_dep["total_files"] >= 2
        assert "API" in data_dep["layer_distribution"]

        # 5. Bug Investigation
        res_bug = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/bug-investigation",
            json={"target": "login_endpoint"}
        )
        assert res_bug.status_code == 200
        data_bug = res_bug.json()
        assert "findings" in data_bug
        assert "limitations" in data_bug

        # 6. Risk Assessment
        res_risk = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/risk-assessment",
            json={"target_symbol": "verify_credentials"}
        )
        assert res_risk.status_code == 200
        data_risk = res_risk.json()
        assert data_risk["risk_score"] > 0
        assert data_risk["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert len(data_risk["formula_breakdown"]) >= 5

        # 7. Test Recommendations
        res_tests = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/test-recommendations",
            json={"target_symbol": "verify_credentials"}
        )
        assert res_tests.status_code == 200
        data_tests = res_tests.json()
        assert data_tests["total_recommendations"] >= 1
        assert any(r["category"] in ("UNIT", "INTEGRATION") for r in data_tests["recommendations"])

        # 8. Technical Documentation
        res_doc = await client.post(
            f"/api/v1/repositories/{repo_id}/intelligence/documentation",
            json={"target": "verify_credentials"}
        )
        assert res_doc.status_code == 200
        data_doc = res_doc.json()
        assert "Technical Specification" in data_doc["markdown_documentation"]
        assert "verify_credentials" in data_doc["target_name"]
