# RepoMind

> **AI-Powered GitHub Repository Intelligence Platform**  
> Interact with any public GitHub codebase using natural language, structure-aware AST parsing, dense and sparse vector retrieval, and grounded LLM reasoning with clickable line citations.

---

## Overview

RepoMind is a developer-focused repository intelligence platform engineered with a **zero-cost-first strategy**. Rather than relying on simple character chunking or generic chatbot prompting, RepoMind extracts syntactic structure (classes, functions, methods, imports) via Tree-sitter, indexes code in local ChromaDB vector storage using Sentence Transformers, and generates factually grounded responses powered by Google Gemini with mandatory source citations.

## Key Features

- **Public Zero-Cost Demo**: Anyone can submit a public GitHub repository without registration or installing software locally.
- **Syntactic Code Understanding**: AST-based code extraction via Tree-sitter preserving exact start/end line coordinates and symbol hierarchies.
- **Hybrid Search & Grounding**: Dense semantic search combined with sparse keyword matching and reranking.
- **Mandatory Source Citations**: Every technical claim references verified files and line numbers.
- **Hardened Security Boundary**: Strict SSRF prevention, isolated temporary workspaces, and zero execution of cloned repository code.

---

## Technology Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide React, Axios.
- **Backend API**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2, HTTPX.
- **Parsing**: Tree-sitter multi-language grammars.
- **Embeddings**: Sentence Transformers (`sentence-transformers/all-MiniLM-L6-v2`).
- **Vector Storage**: ChromaDB (isolated per-repository collections).
- **LLM Reasoning**: Google Gemini API (via eligible free-tier Google AI Studio).
- **Metadata**: SQLite database via SQLAlchemy.

---

## Project Structure

```
RepoMind/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI REST route handlers
│   │   │   ├── health.py    # Health & system status endpoint
│   │   │   └── repositories.py # Repo validation & demo endpoints
│   │   ├── ingestion/       # Git cloner & file filtering engine (Phase 2)
│   │   ├── processing/      # Tree-sitter parser & chunker (Phase 3)
│   │   ├── vectorstore/     # ChromaDB manager (Phase 4)
│   │   ├── retrieval/       # Hybrid retriever & reranker (Phase 5)
│   │   ├── rag/             # Gemini synthesis & context builder (Phase 6)
│   │   ├── intelligence/    # Architecture & impact analyzers (Phase 7)
│   │   ├── services/        # Session & indexing management
│   │   ├── schemas/         # Pydantic models
│   │   ├── utils/           # Validation & SSRF guards
│   │   ├── config.py        # Settings & environment configuration
│   │   └── main.py          # FastAPI application entry point
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/      # Header, Footer, URL input, How It Works, Demos
│   │   ├── pages/           # LandingPage, DashboardPreview
│   │   ├── services/        # Axios API client
│   │   ├── types/           # TypeScript definitions
│   │   ├── App.tsx          # Main application orchestrator
│   │   └── index.css        # Tailwind v4 styles
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── tests/
│   ├── unit/                # Unit test suite (validators, etc.)
│   └── integration/         # API integration test suite
├── docs/                    # Architectural & operational documentation
├── storage/                 # Local durable SQLite & ChromaDB directories
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Git

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/your-username/repomind.git
cd repomind

# Configure environment variables
cp .env.example .env

# Install backend dependencies
pip install -r requirements.txt

# Run backend development server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at `http://127.0.0.1:8000`.  
Interactive Swagger documentation is at `http://127.0.0.1:8000/api/v1/docs`.

### 2. Frontend Setup

```bash
cd frontend

# Install frontend dependencies
npm install

# Run frontend development server
npm run dev
```

The frontend dashboard will be available at `http://localhost:3000`.

---

## Running Tests

```bash
# Run backend unit and integration tests
python -m pytest -v

# Run frontend production build test
cd frontend
npm run build
```

---

## Current Status: Phase 1 Completed

Phase 1 establishes the project foundation:
- Clean modular directory structure
- FastAPI backend with `/api/v1/health` and `/api/v1/repositories/validate`
- React 19 + TypeScript + Tailwind CSS v4 frontend with responsive dark dashboard
- Strict URL validation & SSRF protection
- 100% automated test pass rate for unit and integration suites
