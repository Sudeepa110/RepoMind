"""
Semantic code search service using local vector embeddings and ChromaDB.
Transforms natural language developer queries into dense vectors and retrieves
the most relevant structure-aware code chunks with exact source citations.
"""

import logging
from typing import List, Dict, Any, Optional

from backend.app.vectorstore.interfaces import (
    CodeChunk,
    SearchResult,
    VectorStoreStats,
)
from backend.app.vectorstore.embeddings import embedding_service
from backend.app.vectorstore.chroma_store import chroma_vector_store

logger = logging.getLogger(__name__)


class SemanticSearchService:
    """
    High-level service coordinating embedding generation, vector indexing,
    and semantic similarity search over codebases.
    """

    def __init__(
        self,
        embedder=None,
        vector_store=None,
    ) -> None:
        self.embedder = embedder or embedding_service
        self.vector_store = vector_store or chroma_vector_store

    def index_chunks(
        self,
        repository_id: str,
        chunks: List[CodeChunk],
        force_reindex: bool = False,
        batch_size: int = 32,
    ) -> int:
        """
        Indexes a list of structure-aware code chunks into the repository's vector store.
        Implements incremental indexing: skips embedding chunks whose content_hash has not changed.
        """
        if not chunks:
            logger.info(f"No chunks provided for indexing repository {repository_id}.")
            return 0

        # Check existing hashes for incremental deduplication
        chunks_to_index: List[CodeChunk] = chunks
        if not force_reindex:
            existing_hashes = self.vector_store.get_existing_hashes(repository_id)
            if existing_hashes:
                chunks_to_index = [
                    c for c in chunks
                    if c.chunk_id not in existing_hashes or c.content_hash != existing_hashes[c.chunk_id]
                ]
                skipped_count = len(chunks) - len(chunks_to_index)
                if skipped_count > 0:
                    logger.info(
                        f"Incremental indexing for {repository_id}: skipped {skipped_count} unchanged chunks, indexing {len(chunks_to_index)} new/modified chunks."
                    )

        if not chunks_to_index:
            logger.info(f"All {len(chunks)} chunks are already up-to-date in vector store for {repository_id}.")
            return 0

        # Generate dense embeddings for embeddable content
        texts_to_embed = [c.full_content for c in chunks_to_index]
        logger.info(f"Generating embeddings for {len(texts_to_embed)} chunks on device '{self.embedder.get_device()}'...")
        embeddings = self.embedder.embed_batch(texts_to_embed, batch_size=batch_size)

        # Store vectors and metadata in ChromaDB
        indexed_count = self.vector_store.add_chunks(
            repository_id=repository_id,
            chunks=chunks_to_index,
            embeddings=embeddings,
        )

        return indexed_count

    def search(
        self,
        repository_id: str,
        query: str,
        top_k: int = 5,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
        symbol_type: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Perform semantic similarity search on a repository's code chunks.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # Generate dense query embedding
        query_embedding = self.embedder.embed_text(clean_query)

        # Construct metadata filters
        filters: Dict[str, Any] = {}
        if language:
            filters["language"] = language
        if file_path:
            filters["file_path"] = file_path
        if symbol_type:
            filters["symbol_type"] = symbol_type.upper()

        results = self.vector_store.search(
            repository_id=repository_id,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters if filters else None,
        )

        logger.debug(f"Retrieved {len(results)} results for query '{clean_query}' in {repository_id}.")
        return results

    def get_stats(self, repository_id: str) -> VectorStoreStats:
        """Get operational vector store stats for a repository."""
        return self.vector_store.get_collection_stats(repository_id)

    def delete_repository(self, repository_id: str) -> bool:
        """Deletes all vector data for a repository."""
        return self.vector_store.delete_repository(repository_id)


# Global default semantic search service instance
semantic_search_service = SemanticSearchService()

