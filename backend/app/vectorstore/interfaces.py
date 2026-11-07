"""
Abstract interfaces and domain models for Vector RAG and embedding storage.
Ensures clean decoupling of embedding models and vector database backends.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class CodeChunk(BaseModel):
    """
    Structure-aware code chunk with rich source and AST metadata.
    Preserves exact 1-indexed line references, parent symbols, and content hashes.
    """
    chunk_id: str = Field(..., description="Stable chunk identifier: chunk:{symbol_id}")
    repository_id: str
    file_path: str
    symbol_id: Optional[str] = None
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None  # FUNCTION, METHOD, CLASS, INTERFACE, STRUCT, DOC, CONFIG, MODULE
    parent_symbol_id: Optional[str] = None
    language: str
    start_line: int = Field(..., description="1-indexed starting line in original file")
    end_line: int = Field(..., description="1-indexed ending line in original file")
    source_code: str
    signature: Optional[str] = None
    docstring: Optional[str] = None
    content_hash: str = Field(..., description="SHA-256 fingerprint for deduplication")
    context_header: str = Field("", description="Header summarizing file, lines, and scope")
    full_content: str = Field(..., description="Full embeddable text (header + source)")
    part_index: int = Field(0, description="Part index if chunk was split due to length")
    total_parts: int = Field(1, description="Total parts if chunk was split")
    properties: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """
    Result from semantic vector similarity retrieval.
    """
    chunk: CodeChunk
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    distance: float = Field(..., description="Cosine distance metric")


class VectorStoreStats(BaseModel):
    """
    Diagnostic and operational statistics for a repository's vector store.
    """
    repository_id: str
    collection_name: str
    total_chunks: int = 0
    language_breakdown: Dict[str, int] = Field(default_factory=dict)
    symbol_type_breakdown: Dict[str, int] = Field(default_factory=dict)
    persist_directory: str


class BaseEmbeddingService(ABC):
    """
    Abstract interface for generating dense vector embeddings.
    Allows local SentenceTransformers with optional CUDA acceleration and seamless CPU fallback.
    """

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate a dense embedding vector for a single string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate dense embeddings for a batch of strings."""
        pass

    @abstractmethod
    def dimension(self) -> int:
        """Return the output vector dimensionality (e.g. 384 for all-MiniLM-L6-v2)."""
        pass

    @abstractmethod
    def get_device(self) -> str:
        """Return the device currently in use (e.g. 'cpu' or 'cuda:0')."""
        pass


class BaseVectorStore(ABC):
    """
    Abstract interface for persistent vector storage.
    Isolates ChromaDB implementation details so alternative backends can be plugged in if needed.
    """

    @abstractmethod
    def add_chunks(
        self,
        repository_id: str,
        chunks: List[CodeChunk],
        embeddings: List[List[float]],
    ) -> int:
        """Add or update vector chunks in the repository's isolated collection."""
        pass

    @abstractmethod
    def search(
        self,
        repository_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Perform semantic similarity search on the repository collection."""
        pass

    @abstractmethod
    def delete_repository(self, repository_id: str) -> bool:
        """Completely delete the vector collection for a repository."""
        pass

    @abstractmethod
    def get_collection_stats(self, repository_id: str) -> VectorStoreStats:
        """Retrieve operational statistics for a repository's vector collection."""
        pass

    @abstractmethod
    def get_existing_hashes(self, repository_id: str) -> Dict[str, str]:
        """Retrieve mapping of chunk_id -> content_hash for incremental indexing."""
        pass

