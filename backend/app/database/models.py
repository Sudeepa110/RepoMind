import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

def generate_uuid() -> str:
    return str(uuid.uuid4())

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

class RepositoryModel(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    url: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    default_branch: Mapped[str] = mapped_column(String(50), default="main")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    languages: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    commit_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    readme_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manifest_files: Mapped[List[str]] = mapped_column(JSON, default=list)
    entry_points: Mapped[List[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    jobs: Mapped[List["IndexingJobModel"]] = relationship("IndexingJobModel", back_populates="repository", cascade="all, delete-orphan")
    files: Mapped[List["FileMetadataModel"]] = relationship("FileMetadataModel", back_populates="repository", cascade="all, delete-orphan")

class IndexingJobModel(Base):
    __tablename__ = "indexing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)  # queued, cloning, filtering, analyzing, completed, failed
    current_stage: Mapped[str] = mapped_column(String(50), default="Queued")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    repository: Mapped["RepositoryModel"] = relationship("RepositoryModel", back_populates="jobs")

class FileMetadataModel(Base):
    __tablename__ = "file_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    relative_path: Mapped[str] = mapped_column(String(500), index=True)
    language: Mapped[str] = mapped_column(String(50), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    is_manifest: Mapped[bool] = mapped_column(Boolean, default=False)
    is_entrypoint: Mapped[bool] = mapped_column(Boolean, default=False)
    is_doc: Mapped[bool] = mapped_column(Boolean, default=False)

    repository: Mapped["RepositoryModel"] = relationship("RepositoryModel", back_populates="files")

class AnonymousSessionModel(Base):
    __tablename__ = "anonymous_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

