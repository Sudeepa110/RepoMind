"""
Integration tests for Knowledge Graph Construction, Persistence, and API endpoints.
Tests Python, TypeScript, and mixed-language repositories from raw source code parsing
through NetworkX graph persistence, store reload, and graph API querying.
"""

import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.processing.engine import CodeUnderstandingEngine
from backend.app.graph.builder import GraphBuilder
from backend.app.graph.networkx_store import NetworkXGraphStore, networkx_graph_store
from backend.app.graph.traversal import GraphTraversalService
from backend.app.graph.interfaces import (
    GraphNode,
    GraphEdge,
    NodeType,
    RelationshipType,
)


@pytest.fixture
def temp_repo_workspace():
    """Creates a temporary workspace with multi-language code files."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        root = Path(tmp_dir)

        # 1. Python source
        py_dir = root / "src" / "services"
        py_dir.mkdir(parents=True, exist_ok=True)
        (py_dir / "auth.py").write_text(
            """
import hashlib

class AuthService:
    def __init__(self, salt: str):
        self.salt = salt

    def hash_password(self, password: str) -> str:
        return hashlib.sha256((password + self.salt).encode()).hexdigest()

    def authenticate(self, username: str, password: str) -> bool:
        hashed = self.hash_password(password)
        return len(hashed) > 0
""",
            encoding="utf-8",
        )

        (root / "src" / "main.py").write_text(
            """
from services.auth import AuthService

def start_server():
    auth = AuthService("secret_salt")
    return auth.authenticate("admin", "pass")
""",
            encoding="utf-8",
        )

        # 2. TypeScript source
        ts_dir = root / "frontend" / "src"
        ts_dir.mkdir(parents=True, exist_ok=True)
        (ts_dir / "types.ts").write_text(
            """
export interface UserSession {
    token: string;
    expiresAt: number;
}
""",
            encoding="utf-8",
        )

        (ts_dir / "api.ts").write_text(
            """
import { UserSession } from './types';

export class ApiClient {
    async login(user: string): Promise<UserSession> {
        return { token: "tok123", expiresAt: 12345 };
    }
}
""",
            encoding="utf-8",
        )

        yield root


def test_full_knowledge_graph_pipeline(temp_repo_workspace):
    """
    End-to-end integration test:
    1. Parse source files with Tree-sitter (Python + TypeScript)
    2. Build knowledge graph with GraphBuilder
    3. Verify nodes and edges
    4. Save and reload in fresh NetworkXGraphStore
    5. Run traversal queries (callers, callees, dependencies)
    """
    engine = CodeUnderstandingEngine()
    relative_files = [
        "src/services/auth.py",
        "src/main.py",
        "frontend/src/types.ts",
        "frontend/src/api.ts",
    ]
    repo_id = "integration_test_repo"

    # Step 1: AST Parsing
    parsed_repo = engine.parse_repository(
        repo_dir=temp_repo_workspace,
        files=relative_files,
        repo_id=repo_id,
        commit_hash="abc456commit",
    )
    assert parsed_repo.total_files == 4
    assert parsed_repo.total_symbols >= 5

    # Step 2: Build Knowledge Graph
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_graph_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_graph_dir))
        builder = GraphBuilder(store=store)

        stats = builder.build_and_persist_graph(parsed_repo, store=store)
        assert stats["total_nodes"] >= 10
        assert stats["total_edges"] >= 8
        assert stats["density"] > 0.0

        # Step 3: Verify Persistence
        persisted_file = Path(tmp_graph_dir) / f"{repo_id}.json"
        assert persisted_file.exists()

        # Step 4: Reload in a fresh independent store
        fresh_store = NetworkXGraphStore(persist_dir=Path(tmp_graph_dir))
        assert fresh_store.load(repo_id) is True

        # Step 5: Traversal queries
        traversal = GraphTraversalService(store=fresh_store)

        # Callers of hash_password should be authenticate
        callers_res = traversal.find_callers(repo_id, "hash_password")
        assert callers_res["found"] is True
        assert callers_res["total_callers"] >= 1
        assert any(c["caller_name"] == "authenticate" for c in callers_res["callers"])

        # Callees of authenticate should be hash_password
        callees_res = traversal.find_callees(repo_id, "authenticate")
        assert callees_res["found"] is True
        assert callees_res["total_callees"] >= 1
        assert any(c["callee_name"] == "hash_password" for c in callees_res["callees"])

        # Dependencies of src/main.py should include services/auth.py or module
        deps_res = traversal.find_dependencies(repo_id, "src/main.py")
        assert deps_res["found"] is True
        assert deps_res["total_imported_modules"] >= 1

        # TypeScript interface & class
        iface_node = fresh_store.get_nodes(repo_id, node_type=NodeType.INTERFACE)
        assert len(iface_node) >= 1
        assert any(n.name == "UserSession" for n in iface_node)


@pytest.mark.asyncio
async def test_graph_api_endpoints():
    """Verify Graph API endpoints via ASGI transport."""
    repo_id = "api_graph_repo"

    # Pre-populate global networkx_graph_store with test nodes & edges
    node_repo = GraphNode(id="repo:api_graph_repo", repository_id=repo_id, type=NodeType.REPOSITORY, name="api_graph_repo")
    node_file = GraphNode(id="file:api_graph_repo:app.py", repository_id=repo_id, type=NodeType.FILE, name="app.py", file_path="app.py")
    node_func = GraphNode(
        id="api_graph_repo:app.py:start", repository_id=repo_id, type=NodeType.FUNCTION, name="start", file_path="app.py", start_line=1, end_line=10
    )
    edge = GraphEdge(
        source_id=node_file.id, target_id=node_func.id, relationship=RelationshipType.CONTAINS, repository_id=repo_id
    )

    networkx_graph_store.add_node(node_repo)
    networkx_graph_store.add_node(node_file)
    networkx_graph_store.add_node(node_func)
    networkx_graph_store.add_edge(edge)
    networkx_graph_store.save(repo_id)

    # Insert a dummy RepositoryModel in the DB so _verify_repository_exists passes
    from backend.app.database.session import AsyncSessionLocal
    from backend.app.database.models import RepositoryModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        check = await session.execute(select(RepositoryModel).where(RepositoryModel.id == repo_id))
        if not check.scalar_one_or_none():
            repo_model = RepositoryModel(
                id=repo_id,
                owner="testorg",
                name="testgraph",
                url="https://github.com/testorg/testgraph",
                status="ready",
            )
            session.add(repo_model)
            await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 404 for unknown repository
        res_404 = await client.get("/api/v1/repositories/non_existent_id/graph/status")
        assert res_404.status_code == 404

        # 2. Graph status
        status_res = await client.get(f"/api/v1/repositories/{repo_id}/graph/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["repository_id"] == repo_id
        assert status_data["total_nodes"] >= 3
        assert status_data["total_edges"] >= 1

        # 3. Graph nodes listing
        nodes_res = await client.get(f"/api/v1/repositories/{repo_id}/graph/nodes?limit=10")
        assert nodes_res.status_code == 200
        nodes_data = nodes_res.json()
        assert len(nodes_data["nodes"]) >= 3

        # 4. Graph edges listing
        edges_res = await client.get(f"/api/v1/repositories/{repo_id}/graph/edges?relationship=CONTAINS")
        assert edges_res.status_code == 200
        edges_data = edges_res.json()
        assert len(edges_data["edges"]) >= 1

        # 5. Callers endpoint
        callers_res = await client.get(f"/api/v1/repositories/{repo_id}/graph/callers?symbol=start")
        assert callers_res.status_code == 200
        assert callers_res.json()["found"] is True

        # 6. Callees endpoint
        callees_res = await client.get(f"/api/v1/repositories/{repo_id}/graph/callees?symbol=start")
        assert callees_res.status_code == 200
        assert callees_res.json()["found"] is True

        # 7. Subgraph endpoint
        subgraph_res = await client.get(f"/api/v1/repositories/{repo_id}/graph/subgraph?center_node_id={node_func.id}&radius=1")
        assert subgraph_res.status_code == 200
        subgraph_data = subgraph_res.json()
        assert subgraph_data["center_node_id"] == node_func.id
        assert subgraph_data["node_count"] >= 1

        # 8. Impact analysis endpoint
        impact_res = await client.get(f"/api/v1/repositories/{repo_id}/graph/impact?target=start&depth=1")
        assert impact_res.status_code == 200
        assert impact_res.json()["found"] is True
