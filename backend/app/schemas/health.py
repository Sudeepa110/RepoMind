from pydantic import BaseModel
from typing import Optional, Dict, Any

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    gpu_available: bool
    gpu_name: Optional[str] = None
    gemini_configured: bool
    timestamp: str
    system_info: Dict[str, Any]
