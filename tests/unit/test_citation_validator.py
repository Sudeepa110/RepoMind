"""
Unit tests for Citation Validator (Phase 7).
Verifies parsing of [file_path:start_line-end_line] citations, validation against
retrieved chunks and graph evidence, rejection of hallucinated files, and excerpt extraction.
"""

import pytest
from backend.app.retrieval.retrieval_models import UnifiedSearchResult, GraphEvidence
from backend.app.llm.citation_validator import CitationValidator
from backend.app.llm.generation_models import Citation


@pytest.fixture
def sample_chunks():
    return [
        UnifiedSearchResult(
            chunk_id="chunk_1",
            repository_id="repo-123",
            file_path="src/auth/service.py",
            symbol_name="login_user",
            symbol_type="function",
            language="python",
            start_line=20,
            end_line=45,
            source_code="def login_user(username, password):\n    user = get_user(username)\n    return verify(user, password)\n",
            retrieval_source="VECTOR",
            sources=["VECTOR"],
            original_score=0.9,
            normalized_score=0.92,
            rrf_score=0.033,
            confidence=0.92,
        ),
        UnifiedSearchResult(
            chunk_id="chunk_2",
            repository_id="repo-123",
            file_path="src/database/connection.py",
            symbol_name="get_db_session",
            symbol_type="function",
            language="python",
            start_line=10,
            end_line=25,
            source_code="def get_db_session():\n    return SessionLocal()\n",
            retrieval_source="KEYWORD",
            sources=["KEYWORD"],
            original_score=5.2,
            normalized_score=0.85,
            rrf_score=0.025,
            confidence=0.85,
        ),
    ]


@pytest.fixture
def sample_graph_evidence():
    return [
        GraphEvidence(
            relationship_type="CALLS",
            source_node_id="src/auth/service.py:login_user",
            source_name="login_user",
            target_node_id="src/auth/service.py:verify_password",
            target_name="verify_password",
            confidence=1.0,
            is_confirmed=True,
            call_count=1,
            lines=[28],
            file_path="src/auth/service.py",
            description="login_user calls verify_password",
        )
    ]


def test_validate_exact_citations(sample_chunks, sample_graph_evidence):
    validator = CitationValidator()
    text = (
        "User authentication is performed in `login_user` [src/auth/service.py:20-45]. "
        "Database connections are acquired via [src/database/connection.py:10-25]."
    )

    citations = validator.validate_citations(text, sample_chunks, sample_graph_evidence)
    assert len(citations) == 2
    assert citations[0].file_path == "src/auth/service.py"
    assert citations[0].start_line == 20
    assert citations[0].end_line == 45
    assert citations[0].is_verified is True
    assert citations[0].symbol_name == "login_user"

    assert citations[1].file_path == "src/database/connection.py"
    assert citations[1].start_line == 10
    assert citations[1].end_line == 25
    assert citations[1].is_verified is True


def test_validate_single_line_citation(sample_chunks):
    validator = CitationValidator()
    text = "The connection setup starts at [src/database/connection.py:12]."

    citations = validator.validate_citations(text, sample_chunks)
    assert len(citations) == 1
    assert citations[0].file_path == "src/database/connection.py"
    assert citations[0].start_line == 12
    assert citations[0].end_line == 12
    assert citations[0].is_verified is True


def test_reject_hallucinated_file(sample_chunks):
    validator = CitationValidator()
    text = "Payment processing is handled in [src/billing/stripe.py:10-30]."

    citations = validator.validate_citations(text, sample_chunks)
    # The file is not in retrieved evidence or graph evidence
    assert len(citations) == 0


def test_fallback_citations_when_llm_omits(sample_chunks):
    validator = CitationValidator()
    text = "The user login function validates credentials and issues a session token."

    citations = validator.validate_citations(text, sample_chunks)
    # When no inline citations are generated, validator supplies fallback citations from top chunks
    assert len(citations) == 2
    assert citations[0].file_path == "src/auth/service.py"
    assert citations[1].file_path == "src/database/connection.py"


def test_graph_evidence_citation(sample_chunks, sample_graph_evidence):
    validator = CitationValidator()
    # Mentioning a file only in graph evidence or out of chunk bounds
    text = "The call occurs at [src/auth/service.py:28]."
    citations = validator.validate_citations(text, sample_chunks, sample_graph_evidence)
    assert len(citations) == 1
    assert citations[0].file_path == "src/auth/service.py"
    assert citations[0].start_line == 28
    assert citations[0].is_verified is True
