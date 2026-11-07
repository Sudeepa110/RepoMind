from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class RepositoryValidateRequest(BaseModel):
    url: str = Field(..., description="The GitHub repository URL to validate")

class RepositoryValidationResponse(BaseModel):
    is_valid: bool
    owner: Optional[str] = None
    repo: Optional[str] = None
    normalized_url: Optional[str] = None
    is_accessible: bool = False
    message: Optional[str] = None

class DemoRepository(BaseModel):
    name: str
    owner: str
    url: str
    description: str
    category: str
    language: str
    stars: str

class RepositoryAnalyzeRequest(BaseModel):
    url: str = Field(..., description="The GitHub repository URL to ingest and analyze")
    force_reindex: bool = Field(False, description="Whether to force re-indexing if previously analyzed")

class RepositoryAnalyzeResponse(BaseModel):
    repository_id: str
    job_id: str
    status: str
    message: str

class RepositoryStatusResponse(BaseModel):
    repository_id: str
    job_id: str
    status: str
    current_stage: str
    progress_pct: int
    error_message: Optional[str] = None

class LanguageStatItem(BaseModel):
    name: str
    file_count: int
    line_count: int
    byte_count: int
    percentage: float

class RepositoryDetailResponse(BaseModel):
    id: str
    owner: str
    name: str
    url: str
    default_branch: str
    description: Optional[str] = None
    primary_language: Optional[str] = None
    languages: List[LanguageStatItem] = Field(default_factory=list)
    file_count: int = 0
    total_size_bytes: int = 0
    commit_hash: Optional[str] = None
    status: str
    manifest_files: List[str] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)
    readme_content: Optional[str] = None
    error_message: Optional[str] = None

class RepositoryListItem(BaseModel):
    id: str
    owner: str
    name: str
    url: str
    primary_language: Optional[str] = None
    file_count: int = 0
    status: str
    created_at: str

class FileContentResponse(BaseModel):
    relative_path: str
    language: str
    size_bytes: int
    line_count: int
    content: str
