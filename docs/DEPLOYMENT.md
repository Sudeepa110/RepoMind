# Deployment Guide

## Overview

RepoMind is architected for zero-cost public deployment.
- **Frontend**: Static React build deployable to Vercel, Netlify, or Cloudflare Pages.
- **Backend**: Python 3.11+ FastAPI application deployable to Render, Railway, Fly.io, or any Linux VPS.
- **Vector Storage**: ChromaDB with durable mounted volume storage (`/app/storage/chroma`).
- **Metadata**: SQLite database (`/app/storage/repomind.db`) with forward-compatibility path to PostgreSQL.

---

## Zero-Cost Considerations

1. **Persistent Volumes**: ChromaDB and SQLite require non-ephemeral storage. If deploying to container platforms with ephemeral disks, attach a persistent volume (e.g., Render Disk or Railway Volume mounted at `/app/storage`).
2. **Gemini Free Tier**: Obtain a free API key at [Google AI Studio](https://aistudio.google.com/). Configure rate-limit backoffs in `backend/app/config.py`.
3. **Local Embedding Computation**: Sentence Transformers (`all-MiniLM-L6-v2`) runs directly on the backend container CPU or GPU with zero per-token embedding costs.

---

## Docker Deployment

To launch the full stack locally or on a virtual machine using Docker Compose:

```bash
# 1. Set environment variables
cp .env.example .env
# Edit .env and set GEMINI_API_KEY

# 2. Build and launch containers
docker-compose up --build -d

# 3. Verify health
curl http://localhost:8000/api/v1/health
```

The frontend will run on port 3000 and the backend API on port 8000.
