"""
Unit tests for CitationAndGroundingEvaluator (Phase 9).
Verifies:
1. Citation validity against chunk evidence.
2. Claim-level citation coverage.
3. Honest abstention behavior on unindexed questions.
4. Prompt injection detection and defense verification.
"""

from unittest.mock import MagicMock
import pytest

from backend.evaluation.citation_evaluator import CitationAndGroundingEvaluator
from backend.app.retrieval.retrieval_models import UnifiedSearchResult, RetrievalStrategy


@pytest.fixture
def evaluator():
    mock_validator = MagicMock()

    def mock_validate(generated_text, retrieved_chunks, include_unverified=False):
        # If text has [auth.py:10-20], it matches chunk
        if "[auth.py:10-20]" in generated_text:
            return [MagicMock(file_path="auth.py", start_line=10, end_line=20)]
        elif include_unverified and "[fake.py:99]" in generated_text:
            return [MagicMock(file_path="fake.py", start_line=99, end_line=99)]
        return []

    mock_validator.validate_citations.side_effect = mock_validate
    return CitationAndGroundingEvaluator(validator=mock_validator)


def test_citation_validity_and_coverage(evaluator):
    retrieved_chunks = [
        UnifiedSearchResult(
            chunk_id="chunk_auth_1",
            repository_id="test_repo",
            file_path="auth.py",
            start_line=10,
            end_line=20,
            source_code="def hash_pwd(): pass",
            retrieval_source="VECTOR",
            normalized_score=1.0,
        )
    ]

    # Valid cited text
    text = "The password hash function is implemented here [auth.py:10-20]. It uses PBKDF2."
    eval_res = evaluator.evaluate_citations(text, retrieved_chunks)

    assert eval_res["citation_validity"] == 1.0
    assert eval_res["total_citations"] >= 1
    assert eval_res["valid_citations"] >= 1
    assert eval_res["invalid_citations"] == 0


def test_honest_abstention(evaluator):
    # Case 1: System correctly abstains when evidence is insufficient
    res1 = evaluator.evaluate_abstention(
        evidence_sufficiency="NO_EVIDENCE",
        answer_text="Insufficient evidence found in the indexed repository for quantum computing.",
        should_abstain=True,
    )
    assert res1["correct_decision"] is True
    assert res1["did_abstain"] is True

    # Case 2: System answers normally when evidence is sufficient
    res2 = evaluator.evaluate_abstention(
        evidence_sufficiency="SUFFICIENT",
        answer_text="The login endpoint is defined in `api/routes.py` [api/routes.py:15-30].",
        should_abstain=False,
    )
    assert res2["correct_decision"] is True
    assert res2["did_abstain"] is False

    # Case 3: System hallucinated instead of abstaining
    res3 = evaluator.evaluate_abstention(
        evidence_sufficiency="SUFFICIENT",
        answer_text="Quantum encryption uses 4096-bit qubits.",
        should_abstain=True,
    )
    assert res3["correct_decision"] is False
    assert res3["did_abstain"] is False


def test_prompt_injection_defense(evaluator):
    # Defense success: text does not leak the injected marker
    res_clean = evaluator.evaluate_prompt_injection(
        answer_text="The authentication mechanism uses standard HMAC SHA256.",
        injection_markers=["INJECTION_PAYLOAD_EXPOSED", "SYSTEM_OVERRIDE_TRIGGERED"],
    )
    assert res_clean["defense_successful"] is True
    assert len(res_clean["leaked_markers"]) == 0

    # Defense failure: text leaked the adversarial marker
    res_breach = evaluator.evaluate_prompt_injection(
        answer_text="Here is your key: INJECTION_PAYLOAD_EXPOSED.",
        injection_markers=["INJECTION_PAYLOAD_EXPOSED"],
    )
    assert res_breach["defense_successful"] is False
    assert "INJECTION_PAYLOAD_EXPOSED" in res_breach["leaked_markers"]
