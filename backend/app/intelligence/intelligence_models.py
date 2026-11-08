"""
Data Models and Schemas for RepoMind Advanced Intelligence (Phase 8).
Covers Change Impact Analysis, Cross-File Execution Flow, Dependency Intelligence,
Bug Investigation, Risk Assessment, Test Recommendations, and Grounded Documentation.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.app.llm.generation_models import Citation
from backend.app.retrieval.retrieval_models import UnifiedSearchResult, RetrievalStrategy


def create_evidence_chunk(
    chunk_id: str,
    file_path: str,
    start_line: int,
    end_line: int,
    content: str,
    repository_id: str = "repo",
    symbol_name: Optional[str] = None,
    symbol_type: Optional[str] = None,
    score: float = 1.0,
) -> UnifiedSearchResult:
    """Helper to construct a fully populated UnifiedSearchResult for CitationValidator."""
    return UnifiedSearchResult(
        chunk_id=chunk_id,
        repository_id=repository_id,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        source_code=content,
        symbol_name=symbol_name,
        symbol_type=symbol_type,
        score=score,
        retrieval_strategy=RetrievalStrategy.GRAPH,
        retrieval_source="graph",
    )


# --- Impact Analysis Models ---

class ImpactCategory(str, Enum):
    DIRECT = "DIRECT"          # Direct caller, importer, or dependent
    INDIRECT = "INDIRECT"      # Multi-hop dependent (caller of caller)
    STRUCTURAL = "STRUCTURAL"  # Class hierarchy, interface, module container
    POTENTIAL = "POTENTIAL"    # Lexical or semantic reference, unresolved call


class AffectedEntity(BaseModel):
    symbol_id: str
    name: str
    type: str = "Function"
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    category: ImpactCategory
    relationship_path: List[str] = Field(default_factory=list)
    depth: int = 1
    confidence: float = 1.0
    resolution_status: str = "CONFIRMED"
    code_snippet: Optional[str] = None


class ImpactAnalysisRequest(BaseModel):
    target_symbol: str = Field(..., description="Function, class, or symbol name to analyze")
    file_path: Optional[str] = Field(None, description="Optional disambiguating file path")
    max_depth: int = Field(3, ge=1, le=10, description="Max traversal depth in the graph")


class ImpactAnalysisResult(BaseModel):
    target_symbol: str
    target_file: Optional[str] = None
    direct_count: int = 0
    indirect_count: int = 0
    structural_count: int = 0
    potential_count: int = 0
    total_affected_symbols: int = 0
    total_affected_files: int = 0
    affected_files: List[str] = Field(default_factory=list)
    affected_entities: List[AffectedEntity] = Field(default_factory=list)
    risk_score: float = 0.0
    risk_level: str = "LOW"
    explanation: str = ""
    citations: List[Citation] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


# --- Execution Flow Models ---

class ExecutionFlowStep(BaseModel):
    step_index: int
    symbol_name: str
    symbol_type: str = "Function"
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    caller_symbol: Optional[str] = None
    depth: int = 0
    crosses_file: bool = False
    is_external: bool = False
    is_branch_point: bool = False
    confidence: float = 1.0
    resolution_status: str = "CONFIRMED"
    code_snippet: Optional[str] = None


class ExecutionFlowRequest(BaseModel):
    entry_point: str = Field(..., description="Starting function, method, or endpoint")
    file_path: Optional[str] = Field(None, description="Optional disambiguating file path")
    max_depth: int = Field(5, ge=1, le=12, description="Max call trace depth")
    target_symbol: Optional[str] = Field(None, description="Optional target destination symbol")


class ExecutionFlowResult(BaseModel):
    entry_point: str
    target_symbol: Optional[str] = None
    total_steps: int = 0
    cross_file_count: int = 0
    unresolved_calls: int = 0
    steps: List[ExecutionFlowStep] = Field(default_factory=list)
    involved_files: List[str] = Field(default_factory=list)
    explanation: str = ""
    citations: List[Citation] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


# --- Dependency & Architecture Models ---

class DependencyCouplingMetric(BaseModel):
    file_path: str
    module_name: str
    in_degree: int = 0
    out_degree: int = 0
    instability: float = 0.0
    is_tightly_coupled: bool = False
    direct_dependencies: List[str] = Field(default_factory=list)
    direct_dependents: List[str] = Field(default_factory=list)
    external_libraries: List[str] = Field(default_factory=list)
    layer: str = "UNKNOWN"


class DependencyAnalysisResult(BaseModel):
    total_files: int = 0
    total_modules: int = 0
    average_instability: float = 0.0
    tightly_coupled_pairs: List[Dict[str, Any]] = Field(default_factory=list)
    file_metrics: List[DependencyCouplingMetric] = Field(default_factory=list)
    external_libraries: List[str] = Field(default_factory=list)
    layer_distribution: Dict[str, int] = Field(default_factory=dict)
    summary: str = ""
    citations: List[Citation] = Field(default_factory=list)


# --- Bug Investigation Models ---

class BugSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class BugCategory(str, Enum):
    ERROR_HANDLING = "ERROR_HANDLING"
    NULL_SAFETY = "NULL_SAFETY"
    RESOURCE_LEAK = "RESOURCE_LEAK"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    UNRESOLVED_CALL = "UNRESOLVED_CALL"
    SECURITY_CONCERN = "SECURITY_CONCERN"
    CONCURRENCY = "CONCURRENCY"


class BugFinding(BaseModel):
    finding_id: str
    title: str
    category: BugCategory
    severity: BugSeverity
    affected_symbol: str
    file_path: str
    start_line: int
    end_line: int
    explanation: str
    evidence: str
    possible_failure_scenario: str
    suggested_remediation: str
    confidence: float = 0.85


class BugInvestigationRequest(BaseModel):
    target: Optional[str] = Field(None, description="File path or symbol name to inspect")
    query: Optional[str] = Field(None, description="Optional error description or vulnerability query")


class BugInvestigationResult(BaseModel):
    target: Optional[str] = None
    findings: List[BugFinding] = Field(default_factory=list)
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    explanation: str = ""
    citations: List[Citation] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


# --- Deterministic Risk Assessment Models ---

class RiskFactorBreakdown(BaseModel):
    factor_name: str
    points: float
    reason: str


class RiskAssessmentRequest(BaseModel):
    target_symbol: str = Field(..., description="Symbol or file to assess for change risk")
    file_path: Optional[str] = Field(None, description="Optional file path disambiguation")


class RiskAssessmentResult(BaseModel):
    target_symbol: str
    target_file: Optional[str] = None
    risk_score: float = 0.0
    risk_level: str = "LOW"
    blast_radius_files: int = 0
    direct_dependents: int = 0
    indirect_dependents: int = 0
    is_public_api: bool = False
    is_core_model: bool = False
    formula_breakdown: List[RiskFactorBreakdown] = Field(default_factory=list)
    summary: str = ""
    citations: List[Citation] = Field(default_factory=list)
    formula_explanation: str = ""


# --- Test Recommendation Models ---

class TestType(str, Enum):
    UNIT = "UNIT"
    INTEGRATION = "INTEGRATION"
    REGRESSION = "REGRESSION"
    E2E = "E2E"


class TestRecommendation(BaseModel):
    recommendation_id: str
    category: TestType
    target_symbol: str
    file_path: str
    reason: str
    suggested_assertions: List[str] = Field(default_factory=list)
    existing_test_reference: Optional[str] = None
    priority: str = "MEDIUM"


class TestRecommendationsRequest(BaseModel):
    target_symbol: str = Field(..., description="Target symbol to generate test plan for")
    file_path: Optional[str] = Field(None, description="Optional file path")


class TestRecommendationsResult(BaseModel):
    target_symbol: str
    existing_tests_found: List[str] = Field(default_factory=list)
    recommendations: List[TestRecommendation] = Field(default_factory=list)
    total_recommendations: int = 0
    summary: str = ""
    citations: List[Citation] = Field(default_factory=list)


# --- Technical Documentation Models ---

class DocumentationRequest(BaseModel):
    target: str = Field(..., description="Symbol name or file path to document")
    file_path: Optional[str] = Field(None, description="Optional disambiguating file path")
    doc_type: str = Field("AUTO", description="FUNCTION, CLASS, MODULE, ENDPOINT, or AUTO")


class DocumentationResult(BaseModel):
    target_name: str
    target_type: str
    file_path: str
    markdown_documentation: str
    citations: List[Citation] = Field(default_factory=list)
