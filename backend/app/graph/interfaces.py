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
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    language: Optional[str] = None
    commit_hash: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    relationship: RelationshipType
    repository_id: str
    is_confirmed: bool = True  # Distinguish statically verified from unresolved relationships
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
    def get_subgraph(self, center_node_id: str, radius: int = 1) -> Dict[str, Any]:
        """Extract an ego subgraph centered on the target node."""
        pass

    @abstractmethod
    def save(self, repository_id: str) -> None:
        """Persist graph representation to storage."""
        pass

    @abstractmethod
    def load(self, repository_id: str) -> bool:
        """Load persisted graph from storage."""
        pass
