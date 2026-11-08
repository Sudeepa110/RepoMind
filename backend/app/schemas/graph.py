"""
Pydantic schemas for Knowledge Graph APIs.
Defines request and response models for graph status, nodes, edges, callers,
callees, dependencies, inheritance, execution paths, and impact analysis.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class GraphStatusResponse(BaseModel):
    repository_id: str
    total_nodes: int
    total_edges: int
    graph_density: float
    is_persisted: bool
    node_types: Dict[str, int]
    relationship_types: Dict[str, int]
    confirmed_edges: int
    inferred_edges: int


class GraphNodeItem(BaseModel):
    id: str
    repository_id: str
    type: str
    name: str
    qualified_name: Optional[str] = None
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    language: Optional[str] = None
    commit_hash: Optional[str] = None
    symbol_id: Optional[str] = None
    content_hash: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdgeItem(BaseModel):
    source_id: str
    target_id: str
    relationship: str
    repository_id: str
    is_confirmed: bool
    confidence: float
    resolution_status: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphNodesResponse(BaseModel):
    repository_id: str
    total: int
    limit: int
    offset: int
    nodes: List[GraphNodeItem]


class GraphEdgesResponse(BaseModel):
    repository_id: str
    total: int
    limit: int
    offset: int
    edges: List[GraphEdgeItem]


class CallerItem(BaseModel):
    caller_id: str
    caller_name: str
    caller_type: str
    file_path: str
    start_line: Optional[int] = None
    invocation_lines: List[int] = Field(default_factory=list)
    call_count: int = 1
    confidence: float = 1.0
    is_confirmed: bool = True
    resolution_status: str = "CONFIRMED"


class CallersResponse(BaseModel):
    repository_id: str
    target_id: Optional[str] = None
    target_symbol: str
    target_type: Optional[str] = None
    file_path: Optional[str] = None
    line: Optional[int] = None
    found: bool
    total_callers: int
    callers: List[CallerItem]
    error: Optional[str] = None


class CalleeItem(BaseModel):
    callee_id: str
    callee_name: str
    callee_type: str
    file_path: str
    start_line: Optional[int] = None
    invocation_lines: List[int] = Field(default_factory=list)
    call_count: int = 1
    confidence: float = 1.0
    is_confirmed: bool = True
    resolution_status: str = "CONFIRMED"


class CalleesResponse(BaseModel):
    repository_id: str
    source_id: Optional[str] = None
    source_symbol: str
    source_type: Optional[str] = None
    file_path: Optional[str] = None
    line: Optional[int] = None
    found: bool
    total_callees: int
    callees: List[CalleeItem]
    error: Optional[str] = None


class InheritanceItem(BaseModel):
    id: str
    name: str
    file_path: Optional[str] = None
    confidence: float = 1.0
    is_confirmed: bool = True


class InheritanceHierarchyResponse(BaseModel):
    repository_id: str
    target_id: Optional[str] = None
    target_symbol: str
    target_type: Optional[str] = None
    file_path: Optional[str] = None
    line: Optional[int] = None
    found: bool
    parent_classes: List[InheritanceItem]
    child_classes: List[InheritanceItem]
    implemented_interfaces: List[InheritanceItem]
    implementors: List[InheritanceItem]
    error: Optional[str] = None


class DependencyItem(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    file_path: Optional[str] = None
    relationship: str
    confidence: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)


class DependenciesResponse(BaseModel):
    repository_id: str
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    target_type: Optional[str] = None
    file_path: Optional[str] = None
    found: bool
    total_imported_modules: int
    total_dependents: int
    imported_modules: List[DependencyItem]
    dependent_components: List[DependencyItem]
    error: Optional[str] = None


class ExecutionPathNode(BaseModel):
    id: str
    name: str
    type: str
    file_path: Optional[str] = None
    line: Optional[int] = None


class ExecutionPathsResponse(BaseModel):
    repository_id: str
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    found: bool
    total_paths: int = 0
    max_depth: int = 5
    paths: List[List[ExecutionPathNode]] = Field(default_factory=list)
    disclaimer: str
    error: Optional[str] = None


class ImpactItem(BaseModel):
    node_id: str
    name: str
    type: str
    file_path: Optional[str] = None
    line: Optional[int] = None
    confidence: float = 1.0


class ImpactAnalysisResponse(BaseModel):
    repository_id: str
    target_node_id: str
    target_name: Optional[str] = None
    target_type: Optional[str] = None
    depth: int = 2
    found: bool
    total_impacted_symbols: int
    total_affected_files: int
    affected_files: List[str]
    direct_callers: List[ImpactItem]
    direct_dependents: List[ImpactItem]
    inheriting_classes: List[ImpactItem]
    all_impacted_node_ids: List[str]
    error: Optional[str] = None


class SubgraphResponse(BaseModel):
    center_node_id: str
    radius: int
    node_count: int
    edge_count: int
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
