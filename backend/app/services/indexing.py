import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.config import settings
from backend.app.database.session import AsyncSessionLocal
from backend.app.database.models import RepositoryModel, IndexingJobModel, FileMetadataModel
from backend.app.utils.validators import validate_github_url
from backend.app.ingestion.cloner import RepositoryCloner, cleanup_workspace
from backend.app.ingestion.file_filter import filter_repository
from backend.app.ingestion.analyzer import analyze_repository

logger = logging.getLogger("repomind.indexing")

async def get_or_create_repository(
    repo_url: str,
    db: AsyncSession,
    force_reindex: bool = False,
) -> Tuple[RepositoryModel, IndexingJobModel, bool]:
    """
    Retrieves an existing repository or initializes a new repository & job record.
    Returns (repo, job, is_already_ready).
    """
    is_valid, owner, name, err = validate_github_url(repo_url)
    if not is_valid or not owner or not name:
        raise ValueError(f"Invalid GitHub URL: {err}")

    clean_url = f"https://github.com/{owner}/{name}"

    # Check for existing repository record
    stmt = select(RepositoryModel).where(RepositoryModel.url == clean_url)
    result = await db.execute(stmt)
    existing_repo = result.scalar_one_or_none()

    if existing_repo:
        if existing_repo.status == "ready" and not force_reindex:
            # Check latest completed job
            job_stmt = (
                select(IndexingJobModel)
                .where(IndexingJobModel.repository_id == existing_repo.id)
                .order_by(IndexingJobModel.started_at.desc())
            )
            job_res = await db.execute(job_stmt)
            latest_job = job_res.scalars().first()
            if not latest_job:
                latest_job = IndexingJobModel(
                    repository_id=existing_repo.id,
                    status="completed",
                    current_stage="Ready",
                    progress_pct=100,
                )
                db.add(latest_job)
                await db.commit()
                await db.refresh(latest_job)
            return existing_repo, latest_job, True

        # Existing repo needs re-indexing
        existing_repo.status = "pending"
        existing_repo.error_message = None
        new_job = IndexingJobModel(
            repository_id=existing_repo.id,
            status="queued",
            current_stage="Queued for analysis",
            progress_pct=0,
            started_at=datetime.now(timezone.utc),
        )
        db.add(new_job)
        await db.commit()
        await db.refresh(existing_repo)
        await db.refresh(new_job)
        return existing_repo, new_job, False

    # Create new repository record
    new_repo = RepositoryModel(
        owner=owner,
        name=name,
        url=clean_url,
        status="pending",
    )
    db.add(new_repo)
    await db.flush()

    new_job = IndexingJobModel(
        repository_id=new_repo.id,
        status="queued",
        current_stage="Queued for analysis",
        progress_pct=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_repo)
    await db.refresh(new_job)
    return new_repo, new_job, False

async def update_job_progress(
    job_id: str,
    repo_id: str,
    status: str,
    current_stage: str,
    progress_pct: int,
    error_message: Optional[str] = None,
) -> None:
    """Updates indexing job and repository status in a separate atomic session."""
    async with AsyncSessionLocal() as session:
        completed_at = datetime.now(timezone.utc) if status in ("completed", "failed") else None

        job_update = (
            update(IndexingJobModel)
            .where(IndexingJobModel.id == job_id)
            .values(
                status=status,
                current_stage=current_stage,
                progress_pct=progress_pct,
                error_message=error_message,
                completed_at=completed_at,
            )
        )
        await session.execute(job_update)

        repo_status = "ready" if status == "completed" else ("failed" if status == "failed" else "processing")
        repo_update = (
            update(RepositoryModel)
            .where(RepositoryModel.id == repo_id)
            .values(status=repo_status, error_message=error_message)
        )
        await session.execute(repo_update)
        await session.commit()

async def process_repository_job(job_id: str, repo_id: str, repo_url: str) -> None:
    """
    Background worker that runs the full Phase 2 ingestion pipeline:
    1. Shallow clone repository into isolated workspace
    2. Filter files (omit binaries, secrets, node_modules, generated assets)
    3. Static repository analysis (languages, line counts, manifests, entry points)
    4. Save file metadata and directory tree
    """
    cloner = RepositoryCloner()
    repo_workspace: Optional[Path] = None

    try:
        # Stage 1: Cloning (0% -> 25%)
        await update_job_progress(
            job_id, repo_id, status="processing", current_stage="Cloning repository (shallow depth=1)", progress_pct=15
        )

        # Run git clone in thread to prevent blocking the async event loop
        loop = asyncio.get_running_loop()
        clone_result = await loop.run_in_executor(
            None, cloner.clone_repository, repo_url, repo_id, settings.CLONE_TIMEOUT_SECONDS
        )

        if not clone_result.success or not clone_result.target_dir:
            await update_job_progress(
                job_id, repo_id, status="failed", current_stage="Cloning failed", progress_pct=0, error_message=clone_result.error_message
            )
            return

        repo_workspace = Path(clone_result.target_dir)

        # Stage 2: Filtering (25% -> 50%)
        await update_job_progress(
            job_id, repo_id, status="processing", current_stage="Filtering repository files (stripping binaries & secrets)", progress_pct=40
        )

        accepted_files, filtered_files, total_raw_count = await loop.run_in_executor(
            None, filter_repository, repo_workspace
        )

        # Stage 3: Static Analysis (50% -> 85%)
        await update_job_progress(
            job_id, repo_id, status="processing", current_stage="Analyzing language statistics and directory structure", progress_pct=70
        )

        analysis = await loop.run_in_executor(
            None, analyze_repository, repo_workspace, accepted_files
        )

        # Stage 4: Persist Analysis & File Metadata into SQLite (85% -> 100%)
        async with AsyncSessionLocal() as session:
            # Delete old file metadata for this repo if re-indexing
            old_meta_stmt = select(FileMetadataModel).where(FileMetadataModel.repository_id == repo_id)
            old_res = await session.execute(old_meta_stmt)
            for old_f in old_res.scalars().all():
                await session.delete(old_f)

            # Insert new file metadata
            for af in analysis.analyzed_files:
                f_meta = FileMetadataModel(
                    repository_id=repo_id,
                    relative_path=af.relative_path,
                    language=af.language,
                    size_bytes=af.size_bytes,
                    line_count=af.line_count,
                    is_manifest=af.is_manifest,
                    is_entrypoint=af.is_entrypoint,
                    is_doc=af.is_doc,
                )
                session.add(f_meta)

            # Update repository master record
            breakdown_dict = [stat.model_dump() for stat in analysis.language_breakdown]
            repo_update = (
                update(RepositoryModel)
                .where(RepositoryModel.id == repo_id)
                .values(
                    default_branch=clone_result.default_branch or "main",
                    commit_hash=clone_result.commit_hash,
                    primary_language=analysis.primary_language,
                    languages=breakdown_dict,
                    file_count=analysis.file_count,
                    total_size_bytes=analysis.total_size_bytes,
                    manifest_files=analysis.manifest_files,
                    entry_points=analysis.entry_points,
                    readme_content=analysis.readme_content,
                    status="ready",
                    error_message=None,
                )
            )
            await session.execute(repo_update)
            await session.commit()

        # Save directory tree JSON to persistent storage for fast retrieval
        tree_dir = settings.STORAGE_DIR / "trees"
        tree_dir.mkdir(parents=True, exist_ok=True)
        tree_path = tree_dir / f"{repo_id}.json"
        with open(tree_path, "w", encoding="utf-8") as tf:
            json.dump(analysis.directory_tree.model_dump(), tf, indent=2)

        # Mark job completed
        await update_job_progress(
            job_id, repo_id, status="completed", current_stage="Repository ingestion and analysis complete", progress_pct=100
        )

    except Exception as e:
        logger.exception("Error processing repository indexing job %s: %s", job_id, str(e))
        if repo_workspace and repo_workspace.exists():
            cleanup_workspace(repo_workspace)
        await update_job_progress(
            job_id, repo_id, status="failed", current_stage="Failed during processing", progress_pct=0, error_message=str(e)
        )

