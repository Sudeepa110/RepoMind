"""
Integration test for full end-to-end Vector RAG pipeline:
1. Ingest simulated multi-language repository
2. AST parse using Tree-sitter CodeUnderstandingEngine
3. Chunk using StructureAwareChunker
4. Index using SemanticSearchService with local SentenceTransformers & ChromaDB
5. Execute natural language code search queries
6. Validate similarity scoring, ranking, and exact line citations
"""

import tempfile
from pathlib import Path
import pytest

from backend.app.processing.engine import CodeUnderstandingEngine
from backend.app.vectorstore.chunker import StructureAwareChunker
from backend.app.vectorstore.chroma_store import ChromaVectorStore
from backend.app.vectorstore.embeddings import LocalSentenceTransformerService
from backend.app.retrieval.semantic_search import SemanticSearchService


def test_end_to_end_semantic_retrieval_pipeline():
    """Verify end-to-end parsing, chunking, indexing, and retrieval across Python and TypeScript."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        repo_dir = Path(tmp_dir) / "sample_repo"
        repo_dir.mkdir(parents=True)
        chroma_dir = Path(tmp_dir) / "chroma"

        # 1. Create Python authentication module
        auth_file = repo_dir / "auth.py"
        auth_file.write_text(
            'import bcrypt\n\n'
            'def hash_password(plain_password: str) -> str:\n'
            '    """Hashes a raw password string using salt."""\n'
            '    salt = bcrypt.gensalt()\n'
            '    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")\n\n'
            'def verify_password(plain_password: str, hashed_password: str) -> bool:\n'
            '    """Verifies a plain password against an existing bcrypt hash."""\n'
            '    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))\n',
            encoding="utf-8",
        )

        # 2. Create TypeScript database client
        db_file = repo_dir / "database.ts"
        db_file.write_text(
            'import { Pool } from "pg";\n\n'
            'export class DatabaseConnectionPool {\n'
            '  private pool: Pool;\n\n'
            '  constructor(connectionString: string) {\n'
            '    this.pool = new Pool({ connectionString });\n'
            '  }\n\n'
            '  async executeQuery(sqlQuery: string, params: any[] = []): Promise<any> {\n'
            '    const client = await this.pool.connect();\n'
            '    try {\n'
            '      return await client.query(sqlQuery, params);\n'
            '    } finally {\n'
            '      client.release();\n'
            '    }\n'
            '  }\n'
            '}\n',
            encoding="utf-8",
        )

        # 3. Create Markdown documentation
        doc_file = repo_dir / "README.md"
        doc_file.write_text(
            '# Sample Application\n\n'
            '## Setup and Deployment\n'
            'To deploy this application, configure DATABASE_URL and run docker compose up.\n',
            encoding="utf-8",
        )

        repo_id = "test_owner:sample_repo"

        # 4. Parse with CodeUnderstandingEngine
        engine = CodeUnderstandingEngine()
        parsed_repo = engine.parse_repository(
            repo_dir=repo_dir,
            files=[auth_file, db_file],
            repo_id=repo_id,
        )

        assert parsed_repo.total_files == 2
        assert parsed_repo.total_symbols >= 3  # hash_password, verify_password, DatabaseConnectionPool (+ methods)

        # 5. Chunk with StructureAwareChunker
        chunker = StructureAwareChunker(max_chunk_lines=50)
        chunks = chunker.chunk_repository(
            parsed_repo=parsed_repo,
            accepted_files=[auth_file, db_file, doc_file],
            repo_dir=repo_dir,
        )

        assert len(chunks) >= 4

        # 6. Index with SemanticSearchService
        store = ChromaVectorStore(persist_dir=chroma_dir)
        embedder = LocalSentenceTransformerService()
        search_service = SemanticSearchService(embedder=embedder, vector_store=store)

        indexed_count = search_service.index_chunks(repository_id=repo_id, chunks=chunks)
        assert indexed_count == len(chunks)

        # 7. Semantic Query 1: Password verification
        auth_results = search_service.search(
            repository_id=repo_id,
            query="validate user bcrypt password hash",
            top_k=3,
        )

        assert len(auth_results) > 0
        top_auth = auth_results[0]
        assert top_auth.chunk.file_path == "auth.py"
        assert top_auth.chunk.symbol_name in ("verify_password", "hash_password")
        assert top_auth.similarity_score > 0.4
        # Verify 1-indexed citation
        assert top_auth.chunk.start_line >= 1
        assert top_auth.chunk.end_line >= top_auth.chunk.start_line

        # 8. Semantic Query 2: Database connection pool
        db_results = search_service.search(
            repository_id=repo_id,
            query="PostgreSQL database connection pool query execution",
            top_k=3,
        )

        assert len(db_results) > 0
        top_db = db_results[0]
        assert top_db.chunk.file_path == "database.ts"
        assert top_db.similarity_score > 0.4

        # 9. Filtered query: Only Python symbols
        py_results = search_service.search(
            repository_id=repo_id,
            query="database connection",
            language="Python",
            top_k=5,
        )
        assert all(r.chunk.language == "Python" for r in py_results)

        # 10. Filtered query: Only Documentation symbols
        doc_results = search_service.search(
            repository_id=repo_id,
            query="docker deployment instructions",
            symbol_type="DOC",
            top_k=3,
        )
        assert len(doc_results) > 0
        assert doc_results[0].chunk.symbol_type == "DOC"
        assert doc_results[0].chunk.file_path == "README.md"
