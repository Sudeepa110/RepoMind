"""
Unit tests for Query-Adaptive Retrieval Routing Engine (Phase 9.3).
Verifies that QueryRouter adaptively selects appropriate strategies based on query intent:
- Exact symbol lookup: prioritizes keyword and symbol retrieval.
- Conceptual questions: prioritizes vector retrieval.
- Caller/callee questions: prioritizes graph traversal.
- Inheritance questions: prioritizes graph traversal.
- Dependency questions: prioritizes graph relationships and keyword evidence.
- Architecture questions: combines semantic and structural evidence.
- Mixed questions: engages hybrid retrieval.
- Single-strategy overrides: strictly preserves vector-only, keyword-only, graph-only modes.
"""

import pytest
from backend.app.retrieval.retrieval_models import QueryIntent, RetrievalStrategy
from backend.app.retrieval.query_analyzer import query_analyzer
from backend.app.retrieval.query_router import query_router


def test_routing_exact_symbol_lookup():
    """Exact symbol lookup should prioritize keyword and symbol retrieval without caller traversal."""
    analysis = query_analyzer.analyze("Where is the hash_password function defined in the authentication service?")
    plan = query_router.route(analysis, top_k=5)

    assert plan.keyword_enabled is True
    assert plan.graph_enabled is True
    # Should not traverse incoming callers for definition lookup
    assert "callers" not in plan.graph_operations
    assert plan.vector_enabled is False
    assert RetrievalStrategy.KEYWORD in plan.strategies


def test_routing_conceptual_question():
    """Conceptual questions should prioritize vector retrieval, bypassing graph traversal and keyword noise."""
    analysis = query_analyzer.analyze("Explain how the password verification and hashing lifecycle works conceptually")
    plan = query_router.route(analysis, top_k=5)

    assert plan.vector_enabled is True
    assert plan.keyword_enabled is False
    assert plan.graph_enabled is False
    assert len(plan.graph_operations) == 0
    assert RetrievalStrategy.VECTOR in plan.strategies


def test_routing_caller_callee_question():
    """Caller and callee questions should prioritize graph traversal and keyword chunk matching."""
    # Callers
    callers_analysis = query_analyzer.analyze("Who calls verify_password in this codebase?")
    callers_plan = query_router.route(callers_analysis, top_k=5)
    assert callers_plan.graph_enabled is True
    assert "callers" in callers_plan.graph_operations
    assert callers_plan.keyword_enabled is True
    assert callers_plan.vector_enabled is False
    assert RetrievalStrategy.GRAPH in callers_plan.strategies

    # Callees
    callees_analysis = query_analyzer.analyze("What does AuthController.login invoke?")
    callees_plan = query_router.route(callees_analysis, top_k=5)
    assert callees_plan.graph_enabled is True
    assert "callees" in callees_plan.graph_operations
    assert callees_plan.keyword_enabled is True
    assert callees_plan.vector_enabled is False


def test_routing_inheritance_question():
    """Inheritance queries should prioritize graph traversal and keyword evidence."""
    analysis = query_analyzer.analyze("Which classes inherit from BaseRepository or implement interface?")
    plan = query_router.route(analysis, top_k=5)

    assert plan.graph_enabled is True
    assert "inheritance" in plan.graph_operations
    assert plan.keyword_enabled is True
    assert plan.vector_enabled is False


def test_routing_dependency_question():
    """Dependency queries should prioritize graph relationships and keyword evidence."""
    analysis = query_analyzer.analyze("What modules does src/flask/app.py import or depend on?")
    plan = query_router.route(analysis, top_k=5)

    assert plan.graph_enabled is True
    assert "dependencies" in plan.graph_operations
    assert plan.keyword_enabled is True
    assert plan.vector_enabled is False


def test_routing_architecture_question():
    """Architecture questions should combine semantic and structural evidence."""
    analysis = query_analyzer.analyze("How is this project structured and what is the overall architecture?")
    plan = query_router.route(analysis, top_k=5)

    assert plan.vector_enabled is True
    assert plan.graph_enabled is True
    assert plan.keyword_enabled is True
    assert "dependencies" in plan.graph_operations
    assert RetrievalStrategy.HYBRID in plan.strategies


def test_routing_flow_and_impact_analysis():
    """Execution flow and impact analysis should engage hybrid retrieval across all streams."""
    # Execution flow
    flow_analysis = query_analyzer.analyze("Trace the execution flow from login_endpoint to verify_password")
    flow_plan = query_router.route(flow_analysis, top_k=5)
    assert flow_plan.graph_enabled is True
    assert "callers" in flow_plan.graph_operations or "callees" in flow_plan.graph_operations
    assert flow_plan.vector_enabled is True
    assert flow_plan.keyword_enabled is True

    # Impact analysis
    impact_analysis = query_analyzer.analyze("What is the blast radius and impact of modifying verify_password?")
    impact_plan = query_router.route(impact_analysis, top_k=5)
    assert impact_plan.graph_enabled is True
    assert "impact" in impact_plan.graph_operations
    assert impact_plan.vector_enabled is True
    assert impact_plan.keyword_enabled is True


def test_routing_single_strategy_overrides():
    """Explicit single-strategy overrides must be strictly preserved."""
    analysis = query_analyzer.analyze("Who calls verify_password in this codebase?")

    # 1. Force vector-only
    vector_plan = query_router.route(analysis, top_k=5, include_vector=True, include_keyword=False, include_graph=False)
    assert vector_plan.vector_enabled is True
    assert vector_plan.keyword_enabled is False
    assert vector_plan.graph_enabled is False
    assert vector_plan.strategies == [RetrievalStrategy.VECTOR]

    # 2. Force keyword-only
    keyword_plan = query_router.route(analysis, top_k=5, include_vector=False, include_keyword=True, include_graph=False)
    assert keyword_plan.keyword_enabled is True
    assert keyword_plan.vector_enabled is False
    assert keyword_plan.graph_enabled is False
    assert keyword_plan.strategies == [RetrievalStrategy.KEYWORD]

    # 3. Force graph-only
    graph_plan = query_router.route(analysis, top_k=5, include_vector=False, include_keyword=False, include_graph=True)
    assert graph_plan.graph_enabled is True
    assert graph_plan.vector_enabled is False
    assert graph_plan.keyword_enabled is False
    assert graph_plan.strategies == [RetrievalStrategy.GRAPH]
