"""
Standardized intermediate representation models for code understanding.
Used as the single shared foundation for both Vector RAG and GraphRAG pipelines.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SymbolType(str, Enum):
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    STRUCT = "STRUCT"
    ENUM = "ENUM"
    TYPE_ALIAS = "TYPE_ALIAS"
    MODULE = "MODULE"


class SymbolLocation(BaseModel):
    file_path: str
    start_line: int = Field(..., description="1-indexed starting line")
    end_line: int = Field(..., description="1-indexed ending line")
    start_column: int = Field(0, description="0-indexed starting column")
    end_column: int = Field(0, description="0-indexed ending column")


class ExtractedSymbol(BaseModel):
    """
    Unified representation of an AST symbol (function, method, class, etc.).
    Preserves exact location, source code, docstrings, parameters, hierarchical scope,
    and a stable content hash for incremental indexing.
    """
    symbol_id: str = Field(..., description="Stable deterministic ID: repo:path#parent.name")
    name: str
    symbol_type: SymbolType
    location: SymbolLocation
    source_code: str
    content_hash: Optional[str] = Field(None, description="SHA-256 fingerprint of normalized source code")
    parent_symbol_id: Optional[str] = None
    docstring: Optional[str] = None
    signature: Optional[str] = None
    return_type: Optional[str] = None
    parameters: List[str] = Field(default_factory=list)
    modifiers: List[str] = Field(default_factory=list)  # e.g. public, async, static, export
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExtractedImport(BaseModel):
    """
    Represents an import statement in source code.
    """
    module: str
    imported_symbols: List[str] = Field(default_factory=list)
    alias: Optional[str] = None
    is_relative: bool = False
    location: SymbolLocation
    raw_statement: str


class ExtractedCall(BaseModel):
    """
    Represents a static or dynamically identifiable function / method invocation.
    Includes resolution classification: CONFIRMED, INFERRED, or UNRESOLVED.
    """
    caller_symbol_id: Optional[str] = None
    callee_name: str
    receiver: Optional[str] = None  # e.g. 'self', 'logger', 'math'
    location: SymbolLocation
    is_confirmed: bool = False  # True if resolved to a verified symbol in file/scope
    resolution_status: str = Field("UNRESOLVED", description="CONFIRMED, INFERRED, or UNRESOLVED")
    is_constructor: bool = False
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExtractedInheritance(BaseModel):
    """
    Represents an inheritance or interface implementation relationship.
    """
    sub_symbol_id: str
    super_name: str
    relationship: str = "INHERITS"  # INHERITS or IMPLEMENTS
    is_confirmed: bool = False
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExtractedComment(BaseModel):
    """
    Represents comments and docstrings.
    """
    content: str
    location: SymbolLocation
    is_docstring: bool = False
    associated_symbol_id: Optional[str] = None


class ParsedFile(BaseModel):
    """
    Complete AST understanding output for a single source code file.
    """
    file_path: str
    repository_id: str
    language: str
    commit_hash: Optional[str] = None
    symbols: List[ExtractedSymbol] = Field(default_factory=list)
    imports: List[ExtractedImport] = Field(default_factory=list)
    calls: List[ExtractedCall] = Field(default_factory=list)
    inheritances: List[ExtractedInheritance] = Field(default_factory=list)
    comments: List[ExtractedComment] = Field(default_factory=list)
    syntax_errors: List[str] = Field(default_factory=list)
    line_count: int = 0
    size_bytes: int = 0


class ParsedRepository(BaseModel):
    """
    Aggregated AST understanding output for an entire repository.
    Serves as the root input to:
      1. Vector RAG chunker & embedding generator
      2. GraphRAG knowledge graph builder
    """
    repository_id: str
    commit_hash: Optional[str] = None
    files: Dict[str, ParsedFile] = Field(default_factory=dict)
    total_symbols: int = 0
    total_files: int = 0
    supported_languages: List[str] = Field(default_factory=list)
