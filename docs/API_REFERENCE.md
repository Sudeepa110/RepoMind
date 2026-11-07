# API Reference

## Base URL
`/api/v1`

All responses are formatted in JSON unless specified otherwise (e.g. SSE for streaming).

---

## 1. System Health

### `GET /api/v1/health`
Checks server readiness, hardware acceleration status, and system metadata.

**Response `200 OK`**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "gpu_available": false,
  "gpu_name": null,
  "gemini_configured": false,
  "timestamp": "2026-11-07T14:47:18.248659+00:00",
  "system_info": {
    "python_version": "3.15.0",
    "platform": "Windows-11-10.0.26300-SP0",
    "processor": "Intel64 Family 6 Model 183 Stepping 1"
  }
}
```

---

## 2. Repositories

### `GET /api/v1/repositories/demos`
Returns curated public demo repositories for one-click exploration.

**Response `200 OK`**:
```json
[
  {
    "name": "FastAPI",
    "owner": "fastapi",
    "url": "https://github.com/fastapi/fastapi",
    "description": "Modern, fast web framework for building APIs with Python.",
    "category": "Python / Web",
    "language": "Python",
    "stars": "78k+"
  }
]
```

### `POST /api/v1/repositories/validate`
Validates a GitHub URL against SSRF attacks, format violations, and tests public availability.

**Request Body**:
```json
{
  "url": "https://github.com/fastapi/fastapi"
}
```

**Response `200 OK`**:
```json
{
  "is_valid": true,
  "owner": "fastapi",
  "repo": "fastapi",
  "normalized_url": "https://github.com/fastapi/fastapi",
  "is_accessible": true,
  "message": "Repository validated and accessible."
}
```

---

## Planned Endpoints (Upcoming Phases)

- `POST /api/v1/repositories/analyze`: Initiates background cloning and AST parsing (Phase 2).
- `GET /api/v1/repositories/{id}/status`: Polls progress of indexing job (Phase 2).
- `GET /api/v1/repositories/{id}/files`: Returns directory tree for Code Explorer (Phase 3).
- `GET /api/v1/repositories/{id}/file`: Retrieves raw syntax file with line numbering (Phase 3).
- `POST /api/v1/chat/{repo_id}`: Initiates multi-turn RAG chat with streaming citations (Phase 6).
- `GET /api/v1/intelligence/architecture/{id}`: Returns architecture component graph (Phase 7).
