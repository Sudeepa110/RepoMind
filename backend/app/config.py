import os
from pathlib import Path
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings(BaseModel):
    PROJECT_NAME: str = "RepoMind"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # Allowed CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Google Gemini Configuration (Zero-Cost / Free-Tier)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Embeddings, Vector Store & Knowledge Graph
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
    )
    STORAGE_DIR: Path = BASE_DIR / "storage"
    CHROMA_PERSIST_DIR: Path = BASE_DIR / "storage" / "chroma"
    GRAPH_PERSIST_DIR: Path = BASE_DIR / "storage" / "graphs"
    KEYWORD_PERSIST_DIR: Path = BASE_DIR / "storage" / "keywords"
    SQLITE_DB_PATH: Path = BASE_DIR / "storage" / "repomind.db"

    # Ingestion & Safety Limits
    MAX_REPO_SIZE_MB: int = int(os.getenv("MAX_REPO_SIZE_MB", "100"))
    MAX_INDEXED_FILES: int = int(os.getenv("MAX_INDEXED_FILES", "500"))
    MAX_FILE_SIZE_KB: int = int(os.getenv("MAX_FILE_SIZE_KB", "500"))
    CLONE_TIMEOUT_SECONDS: int = int(os.getenv("CLONE_TIMEOUT_SECONDS", "60"))
    INDEXING_TIMEOUT_SECONDS: int = int(os.getenv("INDEXING_TIMEOUT_SECONDS", "300"))

    # Session & Abuse Limits
    MAX_REQUESTS_PER_SESSION: int = int(os.getenv("MAX_REQUESTS_PER_SESSION", "100"))
    MAX_CONCURRENT_INDEXING_JOBS: int = int(os.getenv("MAX_CONCURRENT_INDEXING_JOBS", "2"))

    def init_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self.GRAPH_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self.KEYWORD_PERSIST_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.init_directories()
