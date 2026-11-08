"""
Domain models and Pydantic schemas for the Hybrid Retrieval Engine.
Defines query intents, retrieval strategies, unified search results,
graph evidence, context assembly, and hybrid search API requests/responses.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    """Categorized intents for developer codebase questions."""
    SEMANTIC = "SEMANTIC"                  # General conceptual code understanding
    EXACT_SYMBOL = "EXACT_SYMBOL"          # Exact function, class, or variable lookup
    CALLERS = "CALLERS"                    # Who calls this symbol (incoming invocations)
    CALLEES = "CALLEES"                    # What does this symbol invoke (outgoing calls)
    DEPENDENCIES = "DEPENDENCIES"          # Module imports and component dependencies
    INHERITANCE = "INHERITANCE"            # Class hierarchy and interface realization
    EXECUTION_FLOW = "EXECUTION_FLOW"      # Call paths and sequence of operations
    IMPACT_ANALYSIS = "IMPACT_ANALYSIS"    # Blast radius and modification consequences
    ARCHITECTURE = "ARCHITECTURE"          # Repository structure, directories, entry points
    CONFIG_OR_DOCS = "CONFIG_OR_DOCS"      # Configuration files, manifests, and documentation
    UNKNOWN = "UNKNOWN"                    # Fallback for ambiguous queries


class RetrievalStrategy(str, Enum):
    """Underlying retrieval mechanisms."""
    VECTOR = "VECTOR"                      # Dense semantic embedding search (ChromaDB)
    GRAPH = "GRAPH"                        # Structural code relationship traversal (NetworkX)
    KEYWORD = "KEYWORD"                    # Exact text and identifier BM25 matching (SQLite FTS5)
    HYBRID = "HYBRID"                      # Coordinated multi-strategy fusion


class QueryAnalysisResult(BaseModel):
    """Result of lightweight deterministic query analysis and intent extraction."""
    original_query: str
    intents: List[QueryIntent]
    extracted_symbols: List[str] = Field(default_factory=list)
    extracted_file_paths: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    recommended_strategies: List[RetrievalStrategy] = Field(default_factory=list)
    intent_reasons: Dict[str, str] = Field(default_factory=dict)


class UnifiedSearchResult(BaseModel):
    """
    Standardized result entity representing a retrieved code component.
    Preserves provenance across Vector, Graph, and Keyword retrieval engines.
    """
    chunk_id: str
    repository_id: str
    file_path: str
    symbol_id: Optional[str] = None
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None      # FUNCTION, METHOD, CLASS, INTERFACE, DOC, etc.
    language: str = "text"
    start_line: int
    end_line: int
    source_code: str
    signature: Optional[str] = None
    docstring: Optional[str] = None
    context_header: Optional[str] = None
    retrieval_source: str                  # e.g. "VECTOR", "GRAPH", "KEYWORD", "HYBRID"
    sources: List[str] = Field(default_factory=list)  # ["VECTOR", "KEYWORD"] if retrieved by both
    original_score: float = 0.0            # Raw score from primary engine
    normalized_score: float = 0.0          # Normalized score in [0.0, 1.0]
    rrf_score: float = 0.0                 # Reciprocal Rank Fusion score
    confidence: float = 1.0                # Structural confidence for graph evidence
    resolution_status: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEvidence(BaseModel):
    """Structural relationship evidence extracted from GraphRAG traversal."""
    relationship_type: str                 # CALLS, IMPORTS, INHERITS, IMPLEMENTS, CONTAINS
    source_node_id: str
    source_name: str
    target_node_id: str
    target_name: str
    confidence: float = 1.0
    is_confirmed: bool = True
    call_count: int = 1
    lines: List[int] = Field(default_factory=list)
    file_path: Optional[str] = None
    description: Optional[str] = None


class AssembledContext(BaseModel):
    """Structured evidence context assembled for future LLM consumption."""
    summary: str
    total_code_chunks: int
    total_graph_relationships: int
    sources_used: List[str]
    formatted_context: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class HybridSearchRequest(BaseModel):
    """Request payload for unified hybrid retrieval."""
    query: str = Field(..., min_length=1, description="Natural language developer query")
    top_k: int = Field(5, ge=1, le=50, description="Max ranked code results to return")
    include_vector: Optional[bool] = Field(None, description="Force enable/disable Vector search")
    include_graph: Optional[bool] = Field(None, description="Force enable/disable Graph retrieval")
    include_keyword: Optional[bool] = Field(None, description="Force enable/disable Keyword search")
    language: Optional[str] = Field(None, description="Optional programming language filter")
    file_path: Optional[str] = Field(None, description="Optional file path filter")
    symbol_type: Optional[str] = Field(None, description="Optional symbol type filter")
    rrf_k: int = Field(60, ge=1, le=200, description="Reciprocal Rank Fusion k constant")


class HybridRetrievalResponse(BaseModel):
    """Comprehensive response from the Hybrid Retrieval Engine."""
    query: str
    repository_id: str
    intents: List[str]
    strategies_used: List[str]
    total_results: int
    results: List[UnifiedSearchResult]
    graph_evidence: List[GraphEvidence] = Field(default_factory=list)
    assembled_context: AssembledContext
    execution_times: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)

