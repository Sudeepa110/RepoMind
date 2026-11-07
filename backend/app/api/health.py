from datetime import datetime, timezone
import platform
import shutil
import subprocess
from fastapi import APIRouter
from backend.app.config import settings
from backend.app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])

def check_gpu_status():
    """Detect if GPU is available on the host machine."""
    # Try torch if installed
    try:
        import torch
        if torch.cuda.is_available():
            return True, torch.cuda.get_device_name(0)
    except ImportError:
        pass

    # Fallback to nvidia-smi check
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                return True, res.stdout.strip().splitlines()[0]
        except Exception:
            pass

    return False, None

@router.get("/health", response_model=HealthResponse)
async def get_health():
    """
    Returns system status, environment configuration, GPU detection,
    and server availability.
    """
    gpu_available, gpu_name = check_gpu_status()
    now_iso = datetime.now(timezone.utc).isoformat()

    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        gemini_configured=bool(settings.GEMINI_API_KEY.strip()),
        timestamp=now_iso,
        system_info={
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
    )
