# Deployment & Operations Guide

## Overview

RepoMind is engineered for **zero-cost, reproducible local and cloud-ready deployment**:
- **Frontend**: Static React 19 + TypeScript + Vite + Tailwind v4 application (Nginx container on port `3000`, or deployable to Vercel / Netlify / Cloudflare Pages).
- **Backend**: Python 3.11+ FastAPI + Uvicorn API server (port `8000`, deployable to Docker Compose, Render, Railway, Fly.io, or any Linux VPS).
- **Vector Storage**: ChromaDB (`storage/chroma/`).
- **Keyword Index**: Per-repository SQLite FTS5 databases (`storage/keywords/`).
- **Knowledge Graph**: NetworkX JSON node-link persistence (`storage/graphs/`).
- **Metadata & Chat History**: SQLite (`storage/repomind.db`).

---

## Durable Storage Requirements & Limitations

> [!IMPORTANT]
> **Ephemeral vs. Durable Storage on Free Hosting Tiers**  
> Free-tier container services (e.g., Render Free Web Service, Hugging Face Spaces ephemeral containers, Heroku dynos) wipe local disk storage on sleep or restart. Because ChromaDB, SQLite, FTS5 databases, and NetworkX graphs persist to `./storage`, **a persistent disk/volume mounted at `/app/storage` is required** to retain indexed repositories across restarts. Without durable storage, repositories must be re-indexed after container restarts. On startup, RepoMind automatically recovers interrupted indexing jobs so partially indexed repositories never remain stuck in `processing`.

---

## Environment Variable Reference

Copy `.env.example` to `.env` before starting services:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Runtime mode (`development` or `production`). Controls error detail exposure and CORS behavior. |
| `DEBUG` | `true` | Enables/disables raw exception strings in `500` API responses. Set `false` in production. |
| `HOST` | `127.0.0.1` | Bind host (`0.0.0.0` inside Docker). |
| `PORT` | `8000` | Backend HTTP port. |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed browser origins for FastAPI CORS middleware. |
| `GEMINI_API_KEY` | *(empty)* | Optional Google AI Studio API key. If omitted, retrieval, AST explorer, graph, search, and abstention continue functioning normally. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Target Google Gemini model identifier. |
| `GEMINI_TEMPERATURE` | `0.2` | Generation sampling temperature (low temperature reduces hallucination). |
| `GEMINI_MAX_OUTPUT_TOKENS` | `4096` | Maximum tokens generated per response. |
| `GEMINI_TIMEOUT_SECONDS` | `45` | Request timeout for Gemini calls. |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Local dense embedding model (CPU-first with optional CUDA acceleration). |
| `CHROMA_PERSIST_DIR` | `storage/chroma` | Directory for persistent ChromaDB collections. |
| `MAX_REPO_SIZE_MB` | `100` | Maximum allowed cloned repository footprint on disk. |
| `MAX_INDEXED_FILES` | `500` | Maximum files indexed per repository. |
| `MAX_FILE_SIZE_KB` | `500` | Maximum single file size in KB before filtering. |
| `CLONE_TIMEOUT_SECONDS` | `60` | Subprocess timeout for `git clone --depth 1`. |
| `INDEXING_TIMEOUT_SECONDS` | `300` | Overall job timeout safeguard. |
| `MAX_REQUESTS_PER_SESSION` | `100` | Session rate budget reference. |
| `MAX_CONCURRENT_INDEXING_JOBS` | `2` | Maximum concurrent repository indexing jobs (enforced with HTTP `429`). |
| `VITE_API_BASE_URL` | *(empty — uses Vite/Nginx `/api/v1` proxy)* | Optional frontend build-time override for standalone static deployments pointing to an external backend origin. |

---

## Reproducible Docker Compose Deployment

### Startup
```bash
# 1. Configure environment variables
cp .env.example .env
# Optional: set GEMINI_API_KEY=<your-free-ai-studio-key> inside .env

# 2. Build and start services with persistent volume and health checks
docker compose up --build -d

# 3. Verify liveness & readiness probes
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/ready
```

- **Frontend UI**: [http://localhost:3000](http://localhost:3000) (Nginx proxies `/api/*` directly to `backend:8000`).
- **Backend API & Swagger Docs**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs).
- **Persistent Storage**: `./storage` on the host is bind-mounted to `/app/storage` inside `repomind-backend`.

### Shutdown
```bash
# Stop containers while preserving indexed data in ./storage
docker compose down
```

---

## Local Development Setup (Without Docker)

### Backend
```bash
# 1. Create and activate Python 3.11+ virtual environment
python -m venv .venv
source .venv/bin/activate        # On Windows PowerShell: .\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Run FastAPI backend
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # Serves Vite dev server on http://localhost:5173 with proxy to :8000
npm run build    # Produces optimized static bundle in frontend/dist/
```

---

## Health & Readiness Probes

- **`GET /api/v1/health`**: Liveness endpoint reporting backend status, version, GPU availability, Gemini configuration state (boolean only — key value is never exposed), and OS runtime info.
- **`GET /api/v1/ready`**: Container readiness probe verifying:
  - SQLite database connectivity (`SELECT 1`)
  - Write permissions to `STORAGE_DIR`
  - Presence of `chroma`, `graphs`, and `keywords` storage directories (`200 ready` or `503 not_ready`).
