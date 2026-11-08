"""
Conversational Chat API Endpoints (Phase 7).
Provides repository-scoped conversation management and Server-Sent Events (SSE)
streaming grounded answer generation powered by Google Gemini and Hybrid Retrieval.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.database.models import RepositoryModel
from backend.app.llm.generation_models import (
    ConversationListItem,
    ConversationDetail,
    CreateConversationRequest,
    ChatStreamRequest,
    StructuredAnswer,
)
from backend.app.llm.conversation_service import conversation_service
from backend.app.llm.generation_service import generation_service

router = APIRouter(prefix="/repositories/{repository_id}", tags=["Conversational Chat"])


async def _verify_repository_exists(repository_id: str, db: AsyncSession) -> RepositoryModel:
    stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found.",
        )
    return repo


@router.post("/conversations", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
async def create_conversation_endpoint(
    repository_id: str,
    request: CreateConversationRequest = CreateConversationRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new conversation session scoped to the repository.
    """
    await _verify_repository_exists(repository_id, db)
    return await conversation_service.create_conversation(
        db=db,
        repository_id=repository_id,
        title=request.title,
    )


@router.get("/conversations", response_model=List[ConversationListItem])
async def list_conversations_endpoint(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all saved conversations for the repository, ordered by last activity.
    """
    await _verify_repository_exists(repository_id, db)
    return await conversation_service.list_conversations(
        db=db,
        repository_id=repository_id,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(
    repository_id: str,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves full conversation history with all messages and citations.
    """
    await _verify_repository_exists(repository_id, db)
    conv = await conversation_service.get_conversation(
        db=db,
        repository_id=repository_id,
        conversation_id=conversation_id,
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conv


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
async def delete_conversation_endpoint(
    repository_id: str,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes a conversation and all its associated messages.
    """
    await _verify_repository_exists(repository_id, db)
    success = await conversation_service.delete_conversation(
        db=db,
        repository_id=repository_id,
        conversation_id=conversation_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return {"message": "Conversation deleted successfully."}


@router.post("/chat/stream")
async def chat_stream_endpoint(
    repository_id: str,
    request: ChatStreamRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Streams a grounded answer via Server-Sent Events (SSE).
    Emits retrieval status, progressive tokens, citations, and completion metadata.
    """
    await _verify_repository_exists(repository_id, db)

    return StreamingResponse(
        generation_service.stream_answer(repository_id=repository_id, request=request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat", response_model=StructuredAnswer)
async def chat_non_streaming_endpoint(
    repository_id: str,
    request: ChatStreamRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Synchronous non-streaming answer generation.
    Returns complete grounded answer with citations and metrics.
    """
    await _verify_repository_exists(repository_id, db)
    return await generation_service.generate_answer(
        repository_id=repository_id,
        request=request,
        db=db,
    )
