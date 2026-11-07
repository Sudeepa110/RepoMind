import asyncio
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.config import settings
from backend.app.database.session import get_db
from backend.app.database.models import RepositoryModel, IndexingJobModel, FileMetadataModel
from backend.app.schemas.repository import (
    RepositoryValidateRequest,
    RepositoryValidationResponse,
    DemoRepository,
    RepositoryAnalyzeRequest,
    RepositoryAnalyzeResponse,
    RepositoryStatusResponse,
    RepositoryDetailResponse,
    RepositoryListItem,
    FileContentResponse,
)
from backend.app.utils.validators import validate_github_url, verify_github_repo_accessible
from backend.app.services.indexing import (
    get_or_create_repository,
    process_repository_job,
)
from backend.app.ingestion.cloner import cleanup_workspace

router = APIRouter(prefix="/repositories", tags=["Repositories"])

CURATED_DEMOS: List[DemoRepository] = [
    DemoRepository(
        name="FastAPI",
        owner="fastapi",
        url="https://github.com/fastapi/fastapi",
        description="Modern, fast web framework for building APIs with Python.",
        category="Python / Web",
        language="Python",
        stars="78k+",
    ),
    DemoRepository(
        name="Flask",
        owner="pallets",
        url="https://github.com/pallets/flask",
        description="The Python micro framework for building web applications.",
        category="Python / Backend",
        language="Python",
        stars="69k+",
    ),
    DemoRepository(
        name="Zustand",
        owner="pmndrs",
        url="https://github.com/pmndrs/zustand",
        description="Bearbones state-management solution using simplified flux principles.",
        category="TypeScript / React",
        language="TypeScript",
        stars="50k+",
    ),
    DemoRepository(
        name="Axios",
        owner="axios",
        url="https://github.com/axios/axios",
        description="Promise-based HTTP client for the browser and node.js.",
        category="JavaScript / Library",
        language="JavaScript",
        stars="105k+",
    ),
    DemoRepository(
        name="Gin",
        owner="gin-gonic",
        url="https://github.com/gin-gonic/gin",
        description="Gin is a high-performance HTTP web framework written in Go.",
        category="Go / Backend",
        language="Go",
        stars="77k+",
    ),
]

@router.get("/demos", response_model=List[DemoRepository])
async def get_demo_repositories():
    """Retrieve pre-verified featured demo repositories."""
    return CURATED_DEMOS

@router.post("/validate", response_model=RepositoryValidationResponse)
async def validate_repository_url(req: RepositoryValidateRequest):
    """
    Validates GitHub URL structure, checks for SSRF/malicious components,
    and verifies repository accessibility.
    """
    is_valid, owner, repo, err_msg = validate_github_url(req.url)
    if not is_valid:
        return RepositoryValidationResponse(
            is_valid=False,
            is_accessible=False,
            message=err_msg or "Invalid GitHub URL.",
        )

    clean_url = f"https://github.com/{owner}/{repo}"
    accessible, access_err = await verify_github_repo_accessible(owner, repo)

    return RepositoryValidationResponse(
        is_valid=True,
        owner=owner,
        repo=repo,
        normalized_url=clean_url,
        is_accessible=accessible,
        message=access_err if not accessible else "Repository validated and accessible.",
    )

@router.post("/analyze", response_model=RepositoryAnalyzeResponse)
async def analyze_repository_endpoint(
    req: RepositoryAnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers asynchronous shallow cloning, file filtering, and static analysis
    for a public GitHub repository.
    """
    is_valid, owner, name, err_msg = validate_github_url(req.url)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg or "Invalid GitHub repository URL.",
        )

    try:
        repo, job, is_ready = await get_or_create_repository(
            repo_url=req.url,
            db=db,
            force_reindex=req.force_reindex,
        )

        if is_ready:
            return RepositoryAnalyzeResponse(
                repository_id=repo.id,
                job_id=job.id,
                status="completed",
                message="Repository is already indexed and ready for exploration.",
            )

        # Trigger background processing task
        background_tasks.add_task(process_repository_job, job.id, repo.id, repo.url)

        return RepositoryAnalyzeResponse(
            repository_id=repo.id,
            job_id=job.id,
            status="queued",
            message="Repository queued for background shallow cloning and static analysis.",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate repository analysis: {str(e)}",
        )

@router.get("/{repository_id}/status", response_model=RepositoryStatusResponse)
async def get_repository_status(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves current indexing progress, pipeline stage, and status."""
    stmt = (
        select(IndexingJobModel)
        .where(IndexingJobModel.repository_id == repository_id)
        .order_by(IndexingJobModel.started_at.desc())
    )
    result = await db.execute(stmt)
    job = result.scalars().first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No indexing job found for this repository ID.",
        )

    return RepositoryStatusResponse(
        repository_id=repository_id,
        job_id=job.id,
        status=job.status,
        current_stage=job.current_stage,
        progress_pct=job.progress_pct,
        error_message=job.error_message,
    )

@router.get("/{repository_id}", response_model=RepositoryDetailResponse)
async def get_repository_details(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves repository metadata, language stats, manifests, and entry points."""
    stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found.",
        )

    languages_data = repo.languages if isinstance(repo.languages, list) else []

    return RepositoryDetailResponse(
        id=repo.id,
        owner=repo.owner,
        name=repo.name,
        url=repo.url,
        default_branch=repo.default_branch,
        description=repo.description,
        primary_language=repo.primary_language,
        languages=languages_data,
        file_count=repo.file_count,
        total_size_bytes=repo.total_size_bytes,
        commit_hash=repo.commit_hash,
        status=repo.status,
        manifest_files=repo.manifest_files or [],
        entry_points=repo.entry_points or [],
        readme_content=repo.readme_content,
        error_message=repo.error_message,
    )

@router.get("/{repository_id}/tree")
async def get_repository_tree(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns the nested directory tree of the indexed repository."""
    # Check repository exists
    stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    tree_path = settings.STORAGE_DIR / "trees" / f"{repository_id}.json"
    if not tree_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directory tree not available yet or repository processing failed.",
        )

    try:
        with open(tree_path, "r", encoding="utf-8") as tf:
            return json.load(tf)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to read tree: {str(e)}")

@router.get("/{repository_id}/file", response_model=FileContentResponse)
async def get_repository_file(
    repository_id: str,
    path: str = Query(..., description="Relative file path inside the repository"),
    db: AsyncSession = Depends(get_db),
):
    """
    Safely retrieves a specific sanitized source file's contents with line count.
    Guarded against path traversal attacks.
    """
    # Path traversal validation
    clean_path = path.replace("\\", "/").strip("/")
    if ".." in clean_path.split("/") or clean_path.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path traversal sequence.")

    workspace_dir = settings.STORAGE_DIR / "temp_repos" / repository_id
    target_file = workspace_dir / clean_path

    # Verify target file is strictly inside the workspace
    try:
        resolved_target = target_file.resolve()
        resolved_workspace = workspace_dir.resolve()
        if not str(resolved_target).startswith(str(resolved_workspace)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Access denied: path outside workspace.")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path resolution error.")

    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File '{clean_path}' not found in repository.")

    try:
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(500 * 1024)  # cap read at 500 KB for safety
        
        lines = len(content.splitlines())
        size = target_file.stat().st_size
        ext = target_file.suffix.lower()

        from backend.app.ingestion.analyzer import EXTENSION_LANGUAGE_MAP
        lang = EXTENSION_LANGUAGE_MAP.get(ext, "Plain Text")

        return FileContentResponse(
            relative_path=clean_path,
            language=lang,
            size_bytes=size,
            line_count=lines,
            content=content,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error reading file: {str(e)}")

@router.get("", response_model=List[RepositoryListItem])
async def list_repositories(db: AsyncSession = Depends(get_db)):
    """Lists indexed repositories."""
    stmt = select(RepositoryModel).order_by(RepositoryModel.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    repos = result.scalars().all()

    return [
        RepositoryListItem(
            id=r.id,
            owner=r.owner,
            name=r.name,
            url=r.url,
            primary_language=r.primary_language,
            file_count=r.file_count,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in repos
    ]

@router.delete("/{repository_id}")
async def delete_repository(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Deletes repository metadata and cleans up storage."""
    stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    # Cleanup disk files
    workspace_dir = settings.STORAGE_DIR / "temp_repos" / repository_id
    cleanup_workspace(workspace_dir)

    tree_path = settings.STORAGE_DIR / "trees" / f"{repository_id}.json"
    if tree_path.exists():
        try:
            tree_path.unlink()
        except OSError:
            pass

    await db.delete(repo)
    await db.commit()

    return {"status": "success", "message": f"Repository '{repo.owner}/{repo.name}' deleted successfully."}
