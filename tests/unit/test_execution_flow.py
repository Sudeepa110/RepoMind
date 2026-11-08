"""
Unit tests for Cross-File Execution Flow Tracer (Phase 8).
Verifies step sequencing, cross-file transitions, branch points, external calls,
and targeted path tracing.
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
from backend.app.intelligence.execution_flow import ExecutionFlowTracer
from backend.app.intelligence.intelligence_models import ExecutionFlowRequest


@pytest.fixture
def flow_test_fixture():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        repo_id = "flow_repo"

        # Step 1: Controller in api/routes.py
        s1 = GraphNode(
            id="flow_repo:api/routes.py:checkout_handler",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="checkout_handler",
            file_path="api/routes.py",
            start_line=10,
            end_line=30,
        )
        # Step 2: Service in services/order.py (crosses file!)
        s2 = GraphNode(
            id="flow_repo:services/order.py:process_order",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="process_order",
            file_path="services/order.py",
            start_line=40,
            end_line=80,
        )
        # Step 3a: Branch callee in services/order.py (same file)
        s3a = GraphNode(
            id="flow_repo:services/order.py:validate_cart",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="validate_cart",
            file_path="services/order.py",
            start_line=85,
            end_line=100,
        )
        # Step 3b: Branch callee in db/gateway.py (crosses file!)
        s3b = GraphNode(
            id="flow_repo:db/gateway.py:charge_card",
            repository_id=repo_id,
            type=NodeType.FUNCTION,
            name="charge_card",
            file_path="db/gateway.py",
            start_line=15,
            end_line=45,
        )

        for n in [s1, s2, s3a, s3b]:
            store.add_node(n)

        # s1 -> CALLS -> s2 (Cross-file)
        store.add_edge(GraphEdge(
            source_id=s1.id,
            target_id=s2.id,
            relationship=RelationshipType.CALLS,
            repository_id=repo_id,
        ))

        # s2 -> CALLS -> s3a (Branch 1)
        store.add_edge(GraphEdge(
            source_id=s2.id,
            target_id=s3a.id,
            relationship=RelationshipType.CALLS,
            repository_id=repo_id,
        ))

        # s2 -> CALLS -> s3b (Branch 2)
        store.add_edge(GraphEdge(
            source_id=s2.id,
            target_id=s3b.id,
            relationship=RelationshipType.CALLS,
            repository_id=repo_id,
        ))

        tracer = ExecutionFlowTracer(store=store)
        yield repo_id, tracer


@pytest.mark.asyncio
async def test_execution_flow_cross_file_and_branch(flow_test_fixture):
    repo_id, tracer = flow_test_fixture

    req = ExecutionFlowRequest(entry_point="checkout_handler", max_depth=4)
    result = await tracer.trace_flow(repo_id, req)

    assert result.entry_point == "checkout_handler"
    assert result.total_steps >= 3
    assert result.cross_file_count >= 1

    # Check step sequence
    step_names = [s.symbol_name for s in result.steps]
    assert step_names[0] == "checkout_handler"
    assert "process_order" in step_names

    # Check cross_file flag
    cross_file_steps = [s for s in result.steps if s.crosses_file]
    assert len(cross_file_steps) >= 1
    assert any(s.symbol_name == "process_order" for s in cross_file_steps)

    # Check that process_order has branch point
    process_order_step = next(s for s in result.steps if s.symbol_name == "process_order")
    assert process_order_step.is_branch_point is True


@pytest.mark.asyncio
async def test_targeted_path_trace(flow_test_fixture):
    repo_id, tracer = flow_test_fixture

    req = ExecutionFlowRequest(
        entry_point="checkout_handler",
        target_symbol="charge_card",
        max_depth=5,
    )
    result = await tracer.trace_flow(repo_id, req)

    assert result.entry_point == "checkout_handler"
    assert result.target_symbol == "charge_card"
    step_names = [s.symbol_name for s in result.steps]
    assert "checkout_handler" in step_names
    assert "process_order" in step_names
    assert "charge_card" in step_names
