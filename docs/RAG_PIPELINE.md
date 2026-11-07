# Retrieval-Augmented Generation (RAG) Pipeline

## Objective

RepoMind's RAG pipeline converts unstructured code repositories into syntactically aware, semantically searchable knowledge collections. Unlike basic text RAG, code requires preserving syntactical boundaries, symbol references, and parent scopes.

## Stages of the Pipeline

### 1. Ingestion & Filtering
- Repository is cloned with `depth=1` to minimize resource consumption.
- Irrelevant files are filtered:
  - Dependency trees (`node_modules/`, `venv/`, `.venv/`)
  - VCS metadata (`.git/`)
  - Build artifacts (`dist/`, `build/`, `*.pyc`, `__pycache__/`)
  - Large binary assets (`*.png`, `*.jpg`, `*.zip`, `*.wasm`, `*.exe`)
  - Secret configurations (`.env*`, `*.pem`, `*.key`)

### 2. Syntactic AST Parsing (Tree-sitter)
- Supported languages: Python, TypeScript, JavaScript, Java, C, C++, Go.
- Extracts AST elements:
  - Top-level Functions & Methods
  - Classes & Interfaces
  - Import statements & Parent relationships
  - Docstrings and inline block comments
- Preserves exact line numbers (`start_line`, `end_line`) for citation verification.

### 3. Structure-Aware Chunking
- Prioritizes logical code boundaries (single function or class) rather than raw token cuts.
- Overlap is applied only when a single function exceeds maximum chunk size.
- Chunks carry full metadata: `file_path`, `symbol_name`, `symbol_type`, `language`, `start_line`, `end_line`.

### 4. Dense Embeddings
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Generates 384-dimensional dense vectors locally.
- Capable of running on CPU or NVIDIA GPU with zero external API fees.

### 5. Hybrid Retrieval
- **Dense Semantic Retrieval**: Vector cosine similarity in ChromaDB.
- **Sparse Keyword Search**: BM25 matching on symbol names, function identifiers, and file paths.
- **Reciprocal Rank Fusion (RRF)**: Merges scores from dense and sparse retrieval to maximize precision.

### 6. Grounded Gemini Generation
- Google Gemini API synthesizes answers strictly within retrieved code evidence.
- Prompt safeguards prevent hallucinations and reject instructions embedded within untrusted repository code.
- Every claim cites file paths and line ranges.
