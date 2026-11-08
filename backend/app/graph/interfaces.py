from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field

class NodeType(str, Enum):
    REPOSITORY = "Repository"
    DIRECTORY = "Directory"
    FILE = "File"
    MODULE = "Module"
    CLASS = "Class"
    INTERFACE = "Interface"
    STRUCT = "Struct"
    FUNCTION = "Function"
    METHOD = "Method"
    API_ENDPOINT = "ApiEndpoint"
    DATABASE_MODEL = "DatabaseModel"

class RelationshipType(str, Enum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    IMPLEMENTS = "IMPLEMENTS"
    DEFINES = "DEFINES"
    DEPENDS_ON = "DEPENDS_ON"

class GraphNode(BaseModel):
    id: str = Field(..., description="Unique deterministic identifier e.g. repo:path/to/file:SymbolName")
    repository_id: str
    type: NodeType
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

class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    relationship: RelationshipType
    repository_id: str
    is_confirmed: bool = True  # Distinguish statically verified from unresolved relationships
    confidence: float = 1.0  # 0.0 to 1.0 confidence score
    resolution_status: str = "CONFIRMED"  # CONFIRMED, INFERRED, UNRESOLVED
    properties: Dict[str, Any] = Field(default_factory=dict)

class BaseGraphStore(ABC):
    """
    Abstract interface for Knowledge Graph operations.
    Allows initial lightweight NetworkX implementation with seamless
    future migration to Neo4j or another graph backend if needed.
    """

    @abstractmethod
    def add_node(self, node: GraphNode) -> None:
        """Add or update a node in the graph."""
        pass

    @abstractmethod
    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed relationship between two nodes."""
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Retrieve a node by its unique identifier."""
        pass

    @abstractmethod
    def get_edge(
        self, source_id: str, target_id: str, relationship: Optional[RelationshipType] = None
    ) -> Optional[GraphEdge]:
        """Retrieve an edge between two nodes."""
        pass

    @abstractmethod
    def get_nodes(
        self,
        repository_id: str,
        node_type: Optional[NodeType] = None,
        file_path: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GraphNode]:
        """Retrieve filtered and paginated nodes for a repository."""
        pass

    @abstractmethod
    def get_edges(
        self,
        repository_id: str,
        relationship: Optional[RelationshipType] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GraphEdge]:
        """Retrieve filtered and paginated edges for a repository."""
        pass

    @abstractmethod
    def get_neighbors(self, node_id: str, direction: str = "both") -> List[GraphNode]:
        """Retrieve adjacent nodes."""
        pass

    @abstractmethod
    def get_callers(self, function_id: str) -> List[GraphNode]:
        """Retrieve all functions/methods that call this symbol (incoming CALLS edges)."""
        pass

    @abstractmethod
    def get_callees(self, function_id: str) -> List[GraphNode]:
        """Retrieve all functions/methods called by this symbol (outgoing CALLS edges)."""
        pass

    @abstractmethod
    def get_dependencies(self, symbol_id: str) -> List[GraphNode]:
        """Retrieve dependencies (IMPORTS, INHERITS, DEPENDS_ON)."""
        pass

    @abstractmethod
    def get_subgraph(
        self, center_node_id: str, radius: int = 1, max_nodes: int = 50
    ) -> Dict[str, Any]:
        """Extract an ego subgraph centered on the target node."""
        pass

    @abstractmethod
    def find_paths(
        self, source_id: str, target_id: str, max_depth: int = 5, limit: int = 10
    ) -> List[List[str]]:
        """Find bounded simple paths between two nodes."""
        pass

    @abstractmethod
    def analyze_impact(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """Analyze blast radius / impacted symbols when a node changes."""
        pass

    @abstractmethod
    def get_stats(self, repository_id: str) -> Dict[str, Any]:
        """Get graph statistics (node counts, edge counts, density)."""
        pass

    @abstractmethod
    def save(self, repository_id: str) -> None:
        """Persist graph representation to storage."""
        pass

    @abstractmethod
    def load(self, repository_id: str) -> bool:
        """Load persisted graph from storage."""
        pass

    @abstractmethod
    def delete(self, repository_id: str) -> bool:
        """Delete persisted graph for a repository."""
        pass

