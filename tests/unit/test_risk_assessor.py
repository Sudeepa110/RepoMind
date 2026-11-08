"""
Unit tests for Deterministic Risk Assessor (Phase 8).
Verifies formula correctness, risk tiers, and contributing factor breakdowns.
"""

from backend.app.intelligence.risk_assessor import RiskAssessor
from backend.app.intelligence.intelligence_models import (
    AffectedEntity,
    ImpactCategory,
)


def test_low_risk_calculation():
    assessor = RiskAssessor()

    # 1 direct caller in same file, no API, no model
    direct = [
        AffectedEntity(
            symbol_id="repo:f.py:caller",
            name="caller",
            file_path="utils/helper.py",
            category=ImpactCategory.DIRECT,
            depth=1,
        )
    ]
    res = assessor.calculate_risk(
        target_name="helper_func",
        target_file="utils/helper.py",
        direct_entities=direct,
        indirect_entities=[],
        affected_files=["utils/helper.py"],
        unresolved_count=0,
    )

    # 15*1 (direct) + 10*1 (files) = 25.0 -> LOW
    assert res.risk_level == "LOW"
    assert res.risk_score == 25.0
    assert len(res.formula_breakdown) >= 5


def test_medium_risk_calculation():
    assessor = RiskAssessor()

    # 2 direct callers, 1 indirect caller, 2 files
    direct = [
        AffectedEntity(symbol_id="1", name="c1", file_path="f1.py", category=ImpactCategory.DIRECT, depth=1),
        AffectedEntity(symbol_id="2", name="c2", file_path="f2.py", category=ImpactCategory.DIRECT, depth=1),
    ]
    indirect = [
        AffectedEntity(symbol_id="3", name="c3", file_path="f2.py", category=ImpactCategory.INDIRECT, depth=2),
    ]

    res = assessor.calculate_risk(
        target_name="service_func",
        target_file="services/calc.py",
        direct_entities=direct,
        indirect_entities=indirect,
        affected_files=["services/calc.py", "f1.py", "f2.py"],
        unresolved_count=0,
    )

    # 15*2 (direct=30) + 5*1 (indirect=5) + 10*3 (files=30) = 65.0 -> HIGH
    assert res.risk_level == "HIGH"
    assert res.risk_score == 65.0


def test_critical_risk_cap():
    assessor = RiskAssessor()

    # Public API router with 10 callers across 10 files
    direct = [
        AffectedEntity(symbol_id=f"id_{i}", name=f"c_{i}", file_path=f"file_{i}.py", category=ImpactCategory.DIRECT, depth=1)
        for i in range(10)
    ]

    res = assessor.calculate_risk(
        target_name="get_users",
        target_file="backend/api/users.py",
        direct_entities=direct,
        indirect_entities=[],
        affected_files=[f"file_{i}.py" for i in range(10)],
        unresolved_count=2,
    )

    # 15*10 (150) + 20 (api) + 10*10 (100) + 5*2 (10) = 280 -> capped at 100
    assert res.risk_level == "CRITICAL"
    assert res.risk_score == 100.0
    assert res.is_public_api is True
