"""
Quantitative Evaluation Benchmark for RepoMind Phase 8 Intelligence.
Measures Change Impact Precision/Recall, Risk Score Monotonicity,
Execution Flow Path Integrity, and Citation Validity.
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
from backend.app.intelligence.impact_analyzer import ChangeImpactAnalyzer
from backend.app.intelligence.execution_flow import ExecutionFlowTracer
from backend.app.intelligence.risk_assessor import RiskAssessor
from backend.app.intelligence.intelligence_models import (
    ImpactAnalysisRequest,
    ExecutionFlowRequest,
    ImpactCategory,
)


@pytest.fixture
def eval_benchmark_fixture():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = NetworkXGraphStore(persist_dir=Path(tmp_dir))
        repo_id = "eval_benchmark_repo"

        # Construct a 5-layer enterprise-style call tree
        # Layer 1: API controllers
        c1 = GraphNode(id="api1", repository_id=repo_id, type=NodeType.FUNCTION, name="create_payment", file_path="api/payment.py", start_line=1, end_line=20)
        c2 = GraphNode(id="api2", repository_id=repo_id, type=NodeType.FUNCTION, name="refund_payment", file_path="api/payment.py", start_line=25, end_line=45)

        # Layer 2: Domain services
        s1 = GraphNode(id="svc1", repository_id=repo_id, type=NodeType.FUNCTION, name="execute_transaction", file_path="services/tx.py", start_line=10, end_line=50)

        # Layer 3: Payment gateways
        g1 = GraphNode(id="gw1", repository_id=repo_id, type=NodeType.FUNCTION, name="call_stripe_api", file_path="gateways/stripe.py", start_line=5, end_line=30)

        # Layer 4: Persistence repositories
        r1 = GraphNode(id="repo1", repository_id=repo_id, type=NodeType.FUNCTION, name="save_tx_record", file_path="db/records.py", start_line=15, end_line=40)

        for n in [c1, c2, s1, g1, r1]:
            store.add_node(n)

        # CALLS: c1 -> s1, c2 -> s1
        store.add_edge(GraphEdge(source_id=c1.id, target_id=s1.id, relationship=RelationshipType.CALLS, repository_id=repo_id))
        store.add_edge(GraphEdge(source_id=c2.id, target_id=s1.id, relationship=RelationshipType.CALLS, repository_id=repo_id))

        # CALLS: s1 -> g1, s1 -> r1
        store.add_edge(GraphEdge(source_id=s1.id, target_id=g1.id, relationship=RelationshipType.CALLS, repository_id=repo_id))
        store.add_edge(GraphEdge(source_id=s1.id, target_id=r1.id, relationship=RelationshipType.CALLS, repository_id=repo_id))

        yield repo_id, store


@pytest.mark.asyncio
async def test_impact_analysis_precision_and_recall(eval_benchmark_fixture):
    repo_id, store = eval_benchmark_fixture
    analyzer = ChangeImpactAnalyzer(store=store, assessor=RiskAssessor(store=store))

    # Evaluate impact of changing domain service `execute_transaction`
    # True direct callers: `create_payment` (c1), `refund_payment` (c2)
    res = await analyzer.analyze(repo_id, ImpactAnalysisRequest(target_symbol="execute_transaction", max_depth=3))

    direct_callers = {e.name for e in res.affected_entities if e.category == ImpactCategory.DIRECT}
    ground_truth_direct = {"create_payment", "refund_payment"}

    # Precision: all found direct callers are in ground truth
    precision = len(direct_callers.intersection(ground_truth_direct)) / max(1, len(direct_callers))
    # Recall: all ground truth direct callers are found
    recall = len(direct_callers.intersection(ground_truth_direct)) / max(1, len(ground_truth_direct))

    assert precision == 1.0, f"Precision was {precision}, expected 1.0"
    assert recall == 1.0, f"Recall was {recall}, expected 1.0"
    assert res.total_affected_files >= 2


@pytest.mark.asyncio
async def test_risk_score_monotonicity(eval_benchmark_fixture):
    """Verifies that risk score strictly increases or remains equal as dependencies expand."""
    _, store = eval_benchmark_fixture
    assessor = RiskAssessor(store=store)

    from backend.app.intelligence.intelligence_models import AffectedEntity

    # 1 dependent
    score_1 = assessor.calculate_risk(
        target_name="test",
        target_file="test.py",
        direct_entities=[AffectedEntity(symbol_id="1", name="e1", file_path="f1.py", category=ImpactCategory.DIRECT)],
        indirect_entities=[],
        affected_files=["test.py", "f1.py"],
    ).risk_score

    # 3 dependents across 3 files
    score_3 = assessor.calculate_risk(
        target_name="test",
        target_file="test.py",
        direct_entities=[
            AffectedEntity(symbol_id="1", name="e1", file_path="f1.py", category=ImpactCategory.DIRECT),
            AffectedEntity(symbol_id="2", name="e2", file_path="f2.py", category=ImpactCategory.DIRECT),
            AffectedEntity(symbol_id="3", name="e3", file_path="f3.py", category=ImpactCategory.DIRECT),
        ],
        indirect_entities=[],
        affected_files=["test.py", "f1.py", "f2.py", "f3.py"],
    ).risk_score

    assert score_3 > score_1, f"Risk score failed monotonicity check: {score_3} <= {score_1}"


@pytest.mark.asyncio
async def test_execution_flow_path_integrity(eval_benchmark_fixture):
    repo_id, store = eval_benchmark_fixture
    tracer = ExecutionFlowTracer(store=store)

    # Trace flow from create_payment
    res = await tracer.trace_flow(repo_id, ExecutionFlowRequest(entry_point="create_payment", max_depth=5))

    assert res.entry_point == "create_payment"
    assert len(res.steps) >= 3

    # Check that each step is a valid successor in the graph
    step_symbols = [s.symbol_name for s in res.steps]
    assert step_symbols[0] == "create_payment"
    assert "execute_transaction" in step_symbols
    assert any(callee in step_symbols for callee in ("call_stripe_api", "save_tx_record"))


@pytest.mark.asyncio
async def test_citation_validity_in_intelligence(eval_benchmark_fixture):
    """Verifies that 100% of generated citations reference existing files and valid line numbers."""
    repo_id, store = eval_benchmark_fixture
    analyzer = ChangeImpactAnalyzer(store=store, assessor=RiskAssessor(store=store))

    res = await analyzer.analyze(repo_id, ImpactAnalysisRequest(target_symbol="execute_transaction"))

    # Every citation generated must have a valid file_path and start_line > 0
    for cit in res.citations:
        assert cit.file_path in ("services/tx.py", "api/payment.py")
        assert cit.start_line > 0
        assert cit.end_line >= cit.start_line
        assert cit.is_verified is True
