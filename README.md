# RepoMind

> **AI-Powered GitHub Repository Intelligence Platform**  
> *Hybrid Vector RAG + GraphRAG for Deep Code Understanding*  
> Interact with any public GitHub codebase using natural language, AST syntax parsing, dense/sparse vector retrieval, and a knowledge graph representing function calls, dependencies, and component relationships.

---

## Architecture: Hybrid Vector RAG + GraphRAG

RepoMind is built on a **unified code understanding foundation** powered by Tree-sitter. Code elements extracted from source files flow into two parallel pipelines:

1. **Vector RAG Pipeline**: Structure-aware chunking, local dense embeddings (`sentence-transformers/all-MiniLM-L6-v2`), and persistent ChromaDB storage for semantic concept retrieval.
2. **GraphRAG Pipeline**: Knowledge graph construction via NetworkX (`CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, `IMPLEMENTS`) for structural and call-hierarchy traversal.
3. **Unified Hybrid Retrieval**: Query intent router directs queries to Vector RAG, GraphRAG, or a fused hybrid context, feeding Google Gemini to generate factually grounded answers with mandatory line citations.

---

## Key Features

- **Public Zero-Cost Demo**: Anyone can submit a public GitHub repository without registration or installing software locally.
- **Tree-sitter Code Understanding**: Multi-language AST parsing (Python, TypeScript, JavaScript, Java, C, C++, Go) extracting symbols with exact line coordinates.
- **Dual Pipeline Knowledge Engine**: Combines ChromaDB vector search with NetworkX graph traversal.
- **Grounded Answers & Citations**: Clickable file and line citations for every answer.
- **Hardened Security Boundary**: Strict SSRF prevention, isolated temporary workspaces, and zero execution of cloned repository code.

---

## Technology Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide React, Axios.
- **Backend API**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2, HTTPX.
- **Code Parsing**: Tree-sitter multi-language grammars.
- **Vector Storage**: ChromaDB (isolated per-repository collections).
- **Knowledge Graph**: NetworkX via abstract `BaseGraphStore` interface.
- **Embeddings**: Sentence Transformers (`sentence-transformers/all-MiniLM-L6-v2`).
- **LLM Reasoning**: Google Gemini API (via eligible free-tier Google AI Studio).
- **Metadata**: SQLite database via SQLAlchemy / aiosqlite.

---

## 10-Phase Roadmap

- [x] **Phase 1**: Project Foundation & Baseline Scaffolding
- [x] **Phase 2**: GitHub Repository Ingestion & File Filtering
- [x] **Phase 3**: Tree-sitter Code Understanding & Shared Parsing Pipeline
- [x] **Phase 4**: Vector RAG & ChromaDB Persistent Storage
- [x] **Phase 5**: Knowledge Graph Construction using NetworkX
- [ ] **Phase 6**: GraphRAG & Graph Traversal (Call graphs, Dependencies, Scopes)
- [ ] **Phase 7**: Unified Hybrid Retrieval, Query Routing & Context Fusion
- [ ] **Phase 8**: Gemini Integration, Grounded Generation & Clickable Citations
- [ ] **Phase 9**: Advanced Repository Intelligence & Change Impact Analysis
- [ ] **Phase 10**: Multi-User Security, Performance Optimization & Public Deployment

---

## Running Tests

```bash
# Run backend test suite
python -m pytest -v

# Run frontend production build
cd frontend
npm run build
```
