"""
Unit tests for Graph Traversal Operations.
Tests find_callers, find_callees, inheritance hierarchy, dependencies,
bounded execution paths, cycle/recursion safety, impact analysis, and missing symbols.
"""

import tempfile
from pathlib import Path
import pytest

from backend.app.graph.interfaces import (
    GraphNode,
    GraphEdge,
    NodeType,
    RelationshipType,
)
from backend.app.graph.networkx_store import NetworkXGraphStore
from backend.app.graph.traversal import GraphTraversalService


@pytest.fixture
def sample_graph_service():
    """Builds a rich sample knowledge graph fixture for traversal tests."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        repo_id = "acme_app"

        # Nodes
        repo_node = GraphNode(id="repo:acme_app", repository_id=repo_id, type=NodeType.REPOSITORY, name="acme_app")
        f_main = GraphNode(id="file:acme_app:main.py", repository_id=repo_id, type=NodeType.FILE, name="main.py", file_path="main.py")
        f_auth = GraphNode(id="file:acme_app:auth.py", repository_id=repo_id, type=NodeType.FILE, name="auth.py", file_path="auth.py")
        f_models = GraphNode(id="file:acme_app:models.py", repository_id=repo_id, type=NodeType.FILE, name="models.py", file_path="models.py")

        # Symbols
        sym_main = GraphNode(
            id="acme_app:main.py:main", repository_id=repo_id, type=NodeType.FUNCTION, name="main", file_path="main.py", start_line=10, end_line=25
        )
        sym_login = GraphNode(
            id="acme_app:main.py:login_endpoint", repository_id=repo_id, type=NodeType.FUNCTION, name="login_endpoint", file_path="main.py", start_line=30, end_line=45
        )
        sym_auth_user = GraphNode(
            id="acme_app:auth.py:authenticate_user", repository_id=repo_id, type=NodeType.FUNCTION, name="authenticate_user", file_path="auth.py", start_line=15, end_line=35
        )
        sym_verify_pwd = GraphNode(
            id="acme_app:auth.py:verify_password", repository_id=repo_id, type=NodeType.FUNCTION, name="verify_password", file_path="auth.py", start_line=40, end_line=50
        )
        sym_hash_pwd = GraphNode(
            id="acme_app:auth.py:hash_password", repository_id=repo_id, type=NodeType.FUNCTION, name="hash_password", file_path="auth.py", start_line=55, end_line=65
        )

        # Classes and Interfaces
        sym_base_repo = GraphNode(
            id="acme_app:models.py:BaseRepository", repository_id=repo_id, type=NodeType.CLASS, name="BaseRepository", file_path="models.py", start_line=5, end_line=20
        )
        sym_user_repo = GraphNode(
            id="acme_app:models.py:UserRepository", repository_id=repo_id, type=NodeType.CLASS, name="UserRepository", file_path="models.py", start_line=25, end_line=50
        )
        sym_auth_interface = GraphNode(
            id="acme_app:models.py:AuthInterface", repository_id=repo_id, type=NodeType.INTERFACE, name="AuthInterface", file_path="models.py", start_line=55, end_line=70
        )

        for n in [repo_node, f_main, f_auth, f_models, sym_main, sym_login, sym_auth_user, sym_verify_pwd, sym_hash_pwd, sym_base_repo, sym_user_repo, sym_auth_interface]:
            store.add_node(n)

        # Edges: Call hierarchy (main -> login_endpoint -> authenticate_user -> verify_password -> hash_password)
        store.add_edge(GraphEdge(source_id=sym_main.id, target_id=sym_login.id, relationship=RelationshipType.CALLS, repository_id=repo_id, confidence=1.0))
        store.add_edge(GraphEdge(source_id=sym_login.id, target_id=sym_auth_user.id, relationship=RelationshipType.CALLS, repository_id=repo_id, confidence=1.0, properties={"call_count": 2, "lines": [35, 40]}))
        store.add_edge(GraphEdge(source_id=sym_auth_user.id, target_id=sym_verify_pwd.id, relationship=RelationshipType.CALLS, repository_id=repo_id, confidence=0.9, properties={"call_count": 1, "lines": [25]}))
        store.add_edge(GraphEdge(source_id=sym_verify_pwd.id, target_id=sym_hash_pwd.id, relationship=RelationshipType.CALLS, repository_id=repo_id, confidence=0.95))

        # Inheritance & Interface
        store.add_edge(GraphEdge(source_id=sym_user_repo.id, target_id=sym_base_repo.id, relationship=RelationshipType.INHERITS, repository_id=repo_id, confidence=1.0))
        store.add_edge(GraphEdge(source_id=sym_user_repo.id, target_id=sym_auth_interface.id, relationship=RelationshipType.IMPLEMENTS, repository_id=repo_id, confidence=1.0))

        # Imports & Dependencies
        store.add_edge(GraphEdge(source_id=f_main.id, target_id=f_auth.id, relationship=RelationshipType.IMPORTS, repository_id=repo_id, confidence=1.0))
        store.add_edge(GraphEdge(source_id=f_auth.id, target_id=f_models.id, relationship=RelationshipType.IMPORTS, repository_id=repo_id, confidence=1.0))

        service = GraphTraversalService(store=store)
        yield service, store, repo_id


def test_find_callers_and_callees(sample_graph_service):
    """Verify find_callers and find_callees with invocation lines and call counts."""
    service, store, repo_id = sample_graph_service

    # Callers of authenticate_user should be login_endpoint
    caller_res = service.find_callers(repo_id, "authenticate_user")
    assert caller_res["found"] is True
    assert caller_res["total_callers"] == 1
    assert caller_res["callers"][0]["caller_name"] == "login_endpoint"
    assert caller_res["callers"][0]["call_count"] == 2
    assert 35 in caller_res["callers"][0]["invocation_lines"]

    # Callees of authenticate_user should be verify_password
    callee_res = service.find_callees(repo_id, "authenticate_user")
    assert callee_res["found"] is True
    assert callee_res["total_callees"] == 1
    assert callee_res["callees"][0]["callee_name"] == "verify_password"
    assert callee_res["callees"][0]["call_count"] == 1


def test_inheritance_and_implementation_traversal(sample_graph_service):
    """Verify parent/child classes and implemented interfaces."""
    service, store, repo_id = sample_graph_service

    # Query UserRepository
    res_user = service.find_inheritance_hierarchy(repo_id, "UserRepository")
    assert res_user["found"] is True
    assert len(res_user["parent_classes"]) == 1
    assert res_user["parent_classes"][0]["name"] == "BaseRepository"
    assert len(res_user["implemented_interfaces"]) == 1
    assert res_user["implemented_interfaces"][0]["name"] == "AuthInterface"

    # Query BaseRepository -> child_classes should include UserRepository
    res_base = service.find_inheritance_hierarchy(repo_id, "BaseRepository")
    assert res_base["found"] is True
    assert len(res_base["child_classes"]) == 1
    assert res_base["child_classes"][0]["name"] == "UserRepository"

    # Query AuthInterface -> implementors should include UserRepository
    res_iface = service.find_inheritance_hierarchy(repo_id, "AuthInterface")
    assert res_iface["found"] is True
    assert len(res_iface["implementors"]) == 1
    assert res_iface["implementors"][0]["name"] == "UserRepository"


def test_dependency_traversal(sample_graph_service):
    """Verify module imports and dependent components."""
    service, store, repo_id = sample_graph_service

    res_auth = service.find_dependencies(repo_id, "auth.py")
    assert res_auth["found"] is True
    # auth.py imports models.py
    assert any(m["id"] == "file:acme_app:models.py" for m in res_auth["imported_modules"])
    # main.py imports auth.py, so main.py is a dependent component
    assert any(d["id"] == "file:acme_app:main.py" for d in res_auth["dependent_components"])


def test_bounded_execution_paths(sample_graph_service):
    """Verify path exploration between symbols and depth bounding."""
    service, store, repo_id = sample_graph_service

    # Path from main to hash_password: main -> login_endpoint -> authenticate_user -> verify_password -> hash_password
    path_res = service.find_execution_paths(
        repo_id, "main", "hash_password", max_depth=5
    )
    assert path_res["found"] is True
    assert path_res["total_paths"] >= 1
    p = path_res["paths"][0]
    names = [node["name"] for node in p]
    assert names == ["main", "login_endpoint", "authenticate_user", "verify_password", "hash_password"]
    assert "disclaimer" in path_res

    # Unreachable path
    unreachable = service.find_execution_paths(
        repo_id, "hash_password", "main", max_depth=5
    )
    assert unreachable["found"] is True
    assert unreachable["total_paths"] == 0


def test_cyclic_and_recursive_calls():
    """Verify recursive calls and cyclic dependencies don't cause infinite loops."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        repo_id = "cycles_repo"

        # Mutual recursion: func_a calls func_b, func_b calls func_a
        node_a = GraphNode(id="c:a", repository_id=repo_id, type=NodeType.FUNCTION, name="func_a")
        node_b = GraphNode(id="c:b", repository_id=repo_id, type=NodeType.FUNCTION, name="func_b")
        # Direct recursion: fibonacci calls fibonacci
        node_fib = GraphNode(id="c:fib", repository_id=repo_id, type=NodeType.FUNCTION, name="fibonacci")

        store.add_node(node_a)
        store.add_node(node_b)
        store.add_node(node_fib)

        store.add_edge(GraphEdge(source_id=node_a.id, target_id=node_b.id, relationship=RelationshipType.CALLS, repository_id=repo_id))
        store.add_edge(GraphEdge(source_id=node_b.id, target_id=node_a.id, relationship=RelationshipType.CALLS, repository_id=repo_id))
        store.add_edge(GraphEdge(source_id=node_fib.id, target_id=node_fib.id, relationship=RelationshipType.CALLS, repository_id=repo_id))

        service = GraphTraversalService(store=store)

        # 1. Mutual recursion path bounded
        paths = service.find_execution_paths(repo_id, "func_a", "func_b", max_depth=3)
        assert paths["found"] is True
        assert paths["total_paths"] >= 1

        # 2. Impact analysis on cycle terminates safely
        impact = service.analyze_impact(repo_id, "func_a", depth=3)
        assert impact["found"] is True
        assert "c:b" in impact["all_impacted_node_ids"]

        # 3. Callers of recursive function
        callers_fib = service.find_callers(repo_id, "fibonacci")
        assert callers_fib["found"] is True
        assert callers_fib["total_callers"] == 1
        assert callers_fib["callers"][0]["caller_name"] == "fibonacci"


def test_impact_blast_radius_analysis(sample_graph_service):
    """Verify impact analysis calculates direct callers, affected files, and blast radius."""
    service, store, repo_id = sample_graph_service

    # Modifying verify_password impacts authenticate_user (direct caller), login_endpoint, and main
    impact = service.analyze_impact(repo_id, "verify_password", depth=3)
    assert impact["found"] is True
    assert impact["target_name"] == "verify_password"
    assert len(impact["direct_callers"]) == 1
    assert impact["direct_callers"][0]["name"] == "authenticate_user"
    assert "main.py" in impact["affected_files"]
    assert "auth.py" in impact["affected_files"]
    assert impact["total_impacted_symbols"] >= 2


def test_missing_and_ambiguous_symbols(sample_graph_service):
    """Verify graceful handling when symbol does not exist in graph."""
    service, store, repo_id = sample_graph_service

    res = service.find_callers(repo_id, "non_existent_symbol")
    assert res["found"] is False
    assert "not found" in res["error"]
    assert res["total_callers"] == 0

    path_res = service.find_execution_paths(repo_id, "non_existent_1", "non_existent_2")
    assert path_res["found"] is False
    assert len(path_res["paths"]) == 0
