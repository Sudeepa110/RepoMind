"""
Unit tests for Context Assembler (Phase 6).
Verifies structured synthesis of code chunks, exact file & line citations,
graph evidence distinction (confirmed vs inferred), and character budget boundaries.
"""

import pytest
from backend.app.retrieval.retrieval_models import UnifiedSearchResult, GraphEvidence
from backend.app.retrieval.context_assembler import ContextAssembler


@pytest.fixture
def assembler():
    return ContextAssembler()


def test_context_assembler_full_synthesis(assembler):
    query = "How is user password verified?"

    results = [
        UnifiedSearchResult(
            chunk_id="chunk_1",
            repository_id="repo1",
            file_path="src/auth.py",
            symbol_name="verify_password",
            symbol_type="FUNCTION",
            language="python",
            start_line=12,
            end_line=20,
            source_code="def verify_password(plain, hashed):\n    return checkpw(plain, hashed)",
            signature="def verify_password(plain: str, hashed: str) -> bool",
            docstring="Verifies raw password matches bcrypt hash.",
            retrieval_source="HYBRID (VECTOR + KEYWORD)",
            sources=["VECTOR", "KEYWORD"],
            original_score=0.92,
            normalized_score=0.95,
            rrf_score=0.034,
        )
    ]

    graph_evidence = [
        GraphEvidence(
            relationship_type="CALLS",
            source_node_id="auth.login",
            source_name="login",
            target_node_id="auth.verify_password",
            target_name="verify_password",
            confidence=1.0,
            is_confirmed=True,
            call_count=2,
            lines=[45, 52],
            file_path="src/auth.py",
            description="`login` calls `verify_password`",
        ),
        GraphEvidence(
            relationship_type="CALLS",
            source_node_id="auth.oauth",
            source_name="oauth_handler",
            target_node_id="auth.verify_password",
            target_name="verify_password",
            confidence=0.8,
            is_confirmed=False,
            call_count=1,
            lines=[80],
            file_path="src/oauth.py",
            description="`oauth_handler` calls `verify_password`",
        ),
    ]

    context = assembler.assemble(query=query, results=results, graph_evidence=graph_evidence, max_chars=10000)

    assert context.total_code_chunks == 1
    assert context.total_graph_relationships == 2
    assert "VECTOR" in context.sources_used
    assert "KEYWORD" in context.sources_used

    # Check structural evidence presence and confirmed status
    assert "1. CODE STRUCTURE & RELATIONSHIP EVIDENCE (GraphRAG):" in context.formatted_context
    assert "[CONFIRMED]" in context.formatted_context
    assert "[INFERRED (80% conf)]" in context.formatted_context
    assert "`login` $\\rightarrow$ `verify_password`" in context.formatted_context

    # Check code snippet section
    assert "2. RANKED SOURCE CODE IMPLEMENTATIONS:" in context.formatted_context
    assert "--- EVIDENCE #1: src/auth.py (Lines 12-20)" in context.formatted_context
    assert "def verify_password(plain, hashed):" in context.formatted_context

    # Check citation summary table
    assert "3. VERIFIED EVIDENCE CITATIONS:" in context.formatted_context
    assert "| `src/auth.py` | `#L12-L20` | `verify_password` |" in context.formatted_context
    assert len(context.citations) == 1
    assert context.citations[0]["file_path"] == "src/auth.py"
    assert context.citations[0]["start_line"] == 12


def test_context_assembler_budget_truncation(assembler):
    query = "Test truncation"
    results = [
        UnifiedSearchResult(
            chunk_id=f"c_{i}",
            repository_id="repo1",
            file_path=f"file_{i}.py",
            symbol_name=f"func_{i}",
            symbol_type="FUNCTION",
            language="python",
            start_line=1,
            end_line=50,
            source_code="x = 1\n" * 50,
            retrieval_source="VECTOR",
            sources=["VECTOR"],
            original_score=0.8,
            normalized_score=0.8,
            rrf_score=0.016,
        )
        for i in range(5)
    ]

    # Set very small max_chars (e.g. 500)
    context = assembler.assemble(query=query, results=results, graph_evidence=[], max_chars=600)
    assert context.total_code_chunks < 5
    assert "[Remaining code chunks truncated to stay within token context limits]" in context.formatted_context

