from datetime import datetime, timezone
import platform
import shutil
import subprocess
from fastapi import APIRouter
from fastapi.responses import JSONResponse
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
    except Exception:
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


@router.get("/ready")
async def get_readiness():
    """
    Readiness probe for container orchestrators and production deployment.
    Verifies database connectivity, storage filesystem write permissions,
    and vector/graph directories.
    """
    checks = {}
    is_ready = True

    # 1. Database check
    try:
        from backend.app.database.session import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        is_ready = False

    # 2. Storage filesystem writability
    try:
        settings.init_directories()
        probe_file = settings.STORAGE_DIR / ".write_probe"
        probe_file.write_text("probe", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        checks["storage_filesystem"] = "ok"
    except Exception as e:
        checks["storage_filesystem"] = f"error: {str(e)}"
        is_ready = False

    # 3. Vector and graph storage directories
    checks["chroma_dir"] = "ok" if settings.CHROMA_PERSIST_DIR.exists() else "missing"
    checks["graph_dir"] = "ok" if settings.GRAPH_PERSIST_DIR.exists() else "missing"
    checks["keyword_dir"] = "ok" if settings.KEYWORD_PERSIST_DIR.exists() else "missing"

    status_code = 200 if is_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
        },
    )

