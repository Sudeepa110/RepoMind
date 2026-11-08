"""
Persistent ChromaDB vector store implementation.
Provides isolated per-repository collections, cosine similarity search,
metadata filtering, incremental deduplication, and repository deletion cleanup.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.app.config import settings
from backend.app.vectorstore.interfaces import (
    BaseVectorStore,
    CodeChunk,
    SearchResult,
    VectorStoreStats,
)

logger = logging.getLogger(__name__)


def sanitize_collection_name(repo_id: str) -> str:
    """
    Sanitizes a repository identifier into a valid ChromaDB collection name:
    - 3-63 characters length.
    - Only [a-zA-Z0-9_-].
    - Must start and end with an alphanumeric character.
    """
    # Replace non-alphanumeric with underscores
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", repo_id)
    # Collapse multiple underscores
    clean = re.sub(r"_+", "_", clean).strip("_")

    name = f"repo_{clean}"
    if len(name) > 63:
        # Hash suffix to guarantee uniqueness if truncated
        import hashlib
        suffix = hashlib.md5(repo_id.encode()).hexdigest()[:8]
        name = f"{name[:54]}_{suffix}"
    if len(name) < 3:
        name = "repo_default"
    return name


class ChromaVectorStore(BaseVectorStore):
    """
    ChromaDB persistent vector store. Manages isolated collections per repository.
    """

    def __init__(self, persist_dir: Optional[Path] = None) -> None:
        self.persist_dir = Path(persist_dir) if persist_dir else settings.CHROMA_PERSIST_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing ChromaDB PersistentClient at {self.persist_dir}")
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

    def _get_or_create_collection(self, repository_id: str):
        """Retrieve or create an isolated collection for the given repository ID."""
        coll_name = sanitize_collection_name(repository_id)
        return self._client.get_or_create_collection(
            name=coll_name,
            metadata={
                "hnsw:space": "cosine",
                "repository_id": repository_id,
            },
        )

    def _get_collection(self, repository_id: str):
        """Retrieve existing collection or return None if not yet created."""
        coll_name = sanitize_collection_name(repository_id)
        try:
            return self._client.get_collection(name=coll_name)
        except Exception:
            return None

    def add_chunks(
        self,
        repository_id: str,
        chunks: List[CodeChunk],
        embeddings: List[List[float]],
        batch_size: int = 100,
    ) -> int:
        """
        Upsert code chunks and their embedding vectors into ChromaDB in batches.
        Flattens metadata to primitive types for ChromaDB compatibility.
        """
        if not chunks or not embeddings:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")

        collection = self._get_or_create_collection(repository_id)

        ids = [c.chunk_id for c in chunks]
        documents = [c.full_content for c in chunks]
        metadatas = []

        for c in chunks:
            # Flatten all metadata fields into primitive types acceptable by ChromaDB
            meta: Dict[str, Any] = {
                "repository_id": c.repository_id,
                "file_path": c.file_path,
                "symbol_id": c.symbol_id or "",
                "symbol_name": c.symbol_name or "",
                "symbol_type": c.symbol_type or "",
                "parent_symbol_id": c.parent_symbol_id or "",
                "language": c.language,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "content_hash": c.content_hash,
                "signature": c.signature or "",
                "docstring": c.docstring or "",
                "part_index": c.part_index,
                "total_parts": c.total_parts,
            }
            metadatas.append(meta)

        # Batch upsert to prevent exceeding ChromaDB request limits
        total_upserted = 0
        for i in range(0, len(ids), batch_size):
            b_ids = ids[i : i + batch_size]
            b_embeddings = embeddings[i : i + batch_size]
            b_documents = documents[i : i + batch_size]
            b_metadatas = metadatas[i : i + batch_size]

            collection.upsert(
                ids=b_ids,
                embeddings=b_embeddings,
                documents=b_documents,
                metadatas=b_metadatas,
            )
            total_upserted += len(b_ids)

        logger.info(f"Successfully upserted {total_upserted} chunks into ChromaDB collection for {repository_id}.")
        return total_upserted

    def search(
        self,
        repository_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Perform semantic similarity retrieval against the repository's isolated collection.
        Converts cosine distance into a bounded similarity score: 1.0 - distance.
        """
        collection = self._get_collection(repository_id)
        if not collection:
            logger.warning(f"No ChromaDB collection found for repository: {repository_id}")
            return []

        # Build where clause if filters provided
        where_clause = None
        if filters:
            clean_filters = {k: v for k, v in filters.items() if v is not None and v != ""}
            if len(clean_filters) == 1:
                where_clause = clean_filters
            elif len(clean_filters) > 1:
                where_clause = {"$and": [{k: v} for k, v in clean_filters.items()]}

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"ChromaDB query error for {repository_id}: {e}")
            return []

        search_results: List[SearchResult] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for idx, chunk_id in enumerate(ids):
            meta = metadatas[idx] if idx < len(metadatas) else {}
            full_content = documents[idx] if idx < len(documents) else ""
            dist = distances[idx] if idx < len(distances) else 1.0

            # Cosine similarity calculation: cosine distance ranges from 0 to 2
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

            chunk = CodeChunk(
                chunk_id=chunk_id,
                repository_id=meta.get("repository_id", repository_id),
                file_path=meta.get("file_path", ""),
                symbol_id=meta.get("symbol_id") or None,
                symbol_name=meta.get("symbol_name") or None,
                symbol_type=meta.get("symbol_type") or None,
                parent_symbol_id=meta.get("parent_symbol_id") or None,
                language=meta.get("language", "Unknown"),
                start_line=int(meta.get("start_line", 1)),
                end_line=int(meta.get("end_line", 1)),
                source_code=full_content,
                signature=meta.get("signature") or None,
                docstring=meta.get("docstring") or None,
                content_hash=meta.get("content_hash", ""),
                full_content=full_content,
                part_index=int(meta.get("part_index", 0)),
                total_parts=int(meta.get("total_parts", 1)),
            )

            search_results.append(
                SearchResult(
                    chunk=chunk,
                    similarity_score=round(similarity, 4),
                    distance=round(dist, 4),
                )
            )

        # Sort by similarity score descending
        search_results.sort(key=lambda r: r.similarity_score, reverse=True)
        return search_results

    def delete_repository(self, repository_id: str) -> bool:
        """Deletes the ChromaDB collection when a repository is deleted."""
        coll_name = sanitize_collection_name(repository_id)
        try:
            self._client.delete_collection(name=coll_name)
            logger.info(f"Deleted ChromaDB collection '{coll_name}' for repository {repository_id}.")
            return True
        except Exception as e:
            logger.debug(f"ChromaDB collection '{coll_name}' deletion notice: {e}")
            return False

    def get_collection_stats(self, repository_id: str) -> VectorStoreStats:
        """Computes chunk counts and language/symbol breakdown for a repository."""
        coll_name = sanitize_collection_name(repository_id)
        collection = self._get_collection(repository_id)

        if not collection:
            return VectorStoreStats(
                repository_id=repository_id,
                collection_name=coll_name,
                total_chunks=0,
                persist_directory=str(self.persist_dir),
            )

        total_chunks = collection.count()
        lang_breakdown: Dict[str, int] = defaultdict(int)
        type_breakdown: Dict[str, int] = defaultdict(int)

        try:
            # Sample metadata for breakdown stats
            sample = collection.get(limit=min(500, total_chunks), include=["metadatas"])
            for meta in sample.get("metadatas", []):
                lang = meta.get("language", "Unknown")
                sym_type = meta.get("symbol_type", "OTHER")
                lang_breakdown[lang] += 1
                type_breakdown[sym_type] += 1
        except Exception as e:
            logger.debug(f"Error sampling metadata for stats: {e}")

        return VectorStoreStats(
            repository_id=repository_id,
            collection_name=coll_name,
            total_chunks=total_chunks,
            language_breakdown=dict(lang_breakdown),
            symbol_type_breakdown=dict(type_breakdown),
            persist_directory=str(self.persist_dir),
        )

    def get_existing_hashes(self, repository_id: str) -> Dict[str, str]:
        """Returns mapping of chunk_id -> content_hash for incremental indexing."""
        collection = self._get_collection(repository_id)
        if not collection:
            return {}

        total = collection.count()
        if total == 0:
            return {}

        try:
            data = collection.get(include=["metadatas"])
            hashes = {}
            for idx, c_id in enumerate(data.get("ids", [])):
                meta = data["metadatas"][idx] if idx < len(data["metadatas"]) else {}
                hashes[c_id] = meta.get("content_hash", "")
            return hashes
        except Exception as e:
            logger.warning(f"Error fetching existing hashes: {e}")
            return {}


# Global default vector store instance
chroma_vector_store = ChromaVectorStore()

