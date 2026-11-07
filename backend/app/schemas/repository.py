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

