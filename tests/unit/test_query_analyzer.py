"""
Unit tests for the Query Intent Analyzer and Strategy Router (Phase 6).
Verifies deterministic query classification across all 11 intents,
symbol extraction, file path parsing, and strategy selection without external LLM calls.
"""

import pytest
from backend.app.retrieval.retrieval_models import QueryIntent, RetrievalStrategy
from backend.app.retrieval.query_analyzer import query_analyzer
from backend.app.retrieval.query_router import query_router


def test_intent_classification_semantic():
    res = query_analyzer.analyze("Explain how password verification and hashing work")
    assert QueryIntent.SEMANTIC in res.intents
    assert RetrievalStrategy.VECTOR in res.recommended_strategies
    assert RetrievalStrategy.KEYWORD in res.recommended_strategies


def test_intent_classification_callers():
    res = query_analyzer.analyze("Who calls verify_password in this codebase?")
    assert QueryIntent.CALLERS in res.intents
    assert "verify_password" in res.extracted_symbols
    assert RetrievalStrategy.GRAPH in res.recommended_strategies


def test_intent_classification_callees():
    res = query_analyzer.analyze("What does handle_login invoke when executed?")
    assert QueryIntent.CALLEES in res.intents
    assert "handle_login" in res.extracted_symbols
    assert RetrievalStrategy.GRAPH in res.recommended_strategies


def test_intent_classification_dependencies():
    res = query_analyzer.analyze("What modules does db_session depend on or import?")
    assert QueryIntent.DEPENDENCIES in res.intents
    assert RetrievalStrategy.GRAPH in res.recommended_strategies


def test_intent_classification_inheritance():
    res = query_analyzer.analyze("Which classes inherit from BaseRepository or implement interface?")
    assert QueryIntent.INHERITANCE in res.intents
    assert "BaseRepository" in res.extracted_symbols
    assert RetrievalStrategy.GRAPH in res.recommended_strategies


def test_intent_classification_impact_analysis():
    res = query_analyzer.analyze("What could break if we change the signature of auth.py or modify authenticate?")
    assert QueryIntent.IMPACT_ANALYSIS in res.intents
    assert "auth.py" in res.extracted_file_paths
    assert RetrievalStrategy.GRAPH in res.recommended_strategies
    assert RetrievalStrategy.VECTOR in res.recommended_strategies


def test_intent_classification_execution_flow():
    res = query_analyzer.analyze("Trace the execution flow from api_router to database_handler")
    assert QueryIntent.EXECUTION_FLOW in res.intents
    assert RetrievalStrategy.GRAPH in res.recommended_strategies


def test_intent_classification_architecture():
    res = query_analyzer.analyze("How is this project structured and what is the overall architecture?")
    assert QueryIntent.ARCHITECTURE in res.intents
    assert RetrievalStrategy.VECTOR in res.recommended_strategies
    assert RetrievalStrategy.GRAPH in res.recommended_strategies


def test_intent_classification_config_or_docs():
    res = query_analyzer.analyze("Where are the environment variables defined in docker-compose.yml and settings?")
    assert QueryIntent.CONFIG_OR_DOCS in res.intents
    assert RetrievalStrategy.KEYWORD in res.recommended_strategies


def test_intent_classification_exact_symbol():
    res = query_analyzer.analyze("Show me the definition of `UserRepository.get_by_email`")
    assert QueryIntent.EXACT_SYMBOL in res.intents
    assert "UserRepository.get_by_email" in res.extracted_symbols
    assert RetrievalStrategy.KEYWORD in res.recommended_strategies


def test_intent_classification_fallback():
    res = query_analyzer.analyze("xyz 123 foo bar")
    assert len(res.intents) > 0
    assert res.confidence <= 0.9


def test_symbol_extraction_varieties():
    # Backticks, function calls, PascalCase, snake_case
    query = "Find `validate_token` and check if TokenService.verify() calls process_auth_payload"
    res = query_analyzer.analyze(query)

    assert "validate_token" in res.extracted_symbols
    assert "TokenService" in res.extracted_symbols or "TokenService.verify" in res.extracted_symbols or "verify" in res.extracted_symbols
    assert "process_auth_payload" in res.extracted_symbols


def test_file_path_extraction():
    query = "Look inside backend/app/auth.py and frontend/src/types/index.ts for user schema"
    res = query_analyzer.analyze(query)

    assert "backend/app/auth.py" in res.extracted_file_paths
    assert "frontend/src/types/index.ts" in res.extracted_file_paths


def test_query_router_user_overrides():
    analysis = query_analyzer.analyze("who calls verify_password")
    # Default should have graph, keyword, and hybrid
    plan_default = query_router.route(analysis, top_k=5)
    assert plan_default.graph_enabled is True
    assert plan_default.keyword_enabled is True

    # User explicitly disables graph
    plan_override = query_router.route(analysis, top_k=5, include_graph=False)
    assert plan_override.graph_enabled is False
    assert "USER_OVERRIDE_GRAPH" in plan_override.reasons

