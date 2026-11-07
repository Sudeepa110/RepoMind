"""
Pydantic schemas for Vector RAG search and index status operations.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language code search query")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of results to return")
    language: Optional[str] = Field(None, description="Optional filter by programming language")
    file_path: Optional[str] = Field(None, description="Optional filter by file path")
    symbol_type: Optional[str] = Field(None, description="Optional filter by symbol type (e.g. FUNCTION, CLASS, METHOD)")


class SearchChunkResult(BaseModel):
    chunk_id: str
    repository_id: str
    file_path: str
    symbol_id: Optional[str] = None
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None
    language: str
    start_line: int
    end_line: int
    source_code: str
    signature: Optional[str] = None
    docstring: Optional[str] = None
    context_header: Optional[str] = None
    similarity_score: float
    distance: float
    part_index: int = 0
    total_parts: int = 1


class SearchResponse(BaseModel):
    query: str
    repository_id: str
    total_results: int
    results: List[SearchChunkResult]


class VectorIndexStatusResponse(BaseModel):
    repository_id: str
    collection_name: str
    total_chunks: int
    language_breakdown: Dict[str, int] = Field(default_factory=dict)
    symbol_type_breakdown: Dict[str, int] = Field(default_factory=dict)
    status: str
    persist_directory: str

