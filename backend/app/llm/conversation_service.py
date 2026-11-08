"""
Conversation Management Service (Phase 7).
Persists repository-scoped conversations and message histories into SQLite via SQLAlchemy.
Enforces repository isolation and bounds conversation history turns for LLM prompts.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database.models import ConversationModel, ChatMessageModel
from backend.app.llm.generation_models import (
    ConversationListItem,
    ConversationDetail,
    ChatMessageItem,
    Citation,
)

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Manages chat sessions and persistent message exchanges scoped to individual repositories.
    """

    async def create_conversation(
        self,
        db: AsyncSession,
        repository_id: str,
        title: Optional[str] = None,
    ) -> ConversationDetail:
        """Initializes a new repository-scoped conversation."""
        conv = ConversationModel(
            repository_id=repository_id,
            title=title or "New Conversation",
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

        return ConversationDetail(
            id=conv.id,
            repository_id=conv.repository_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            messages=[],
        )

    async def list_conversations(
        self,
        db: AsyncSession,
        repository_id: str,
    ) -> List[ConversationListItem]:
        """Lists all conversations for a given repository ordered by most recently updated."""
        stmt = (
            select(
                ConversationModel,
                func.count(ChatMessageModel.id).label("msg_count"),
            )
            .outerjoin(ChatMessageModel, ConversationModel.id == ChatMessageModel.conversation_id)
            .where(ConversationModel.repository_id == repository_id)
            .group_by(ConversationModel.id)
            .order_by(desc(ConversationModel.updated_at))
        )
        res = await db.execute(stmt)
        rows = res.all()

        items: List[ConversationListItem] = []
        for conv, count in rows:
            items.append(
                ConversationListItem(
                    id=conv.id,
                    repository_id=conv.repository_id,
                    title=conv.title,
                    message_count=count,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                )
            )
        return items

    async def get_conversation(
        self,
        db: AsyncSession,
        repository_id: str,
        conversation_id: str,
    ) -> Optional[ConversationDetail]:
        """Fetches full conversation history with messages. Validates repository ownership."""
        stmt = (
            select(ConversationModel)
            .options(selectinload(ConversationModel.messages))
            .where(
                ConversationModel.id == conversation_id,
                ConversationModel.repository_id == repository_id,
            )
        )
        res = await db.execute(stmt)
        conv = res.scalar_one_or_none()
        if not conv:
            return None

        msg_items: List[ChatMessageItem] = []
        for m in sorted(conv.messages, key=lambda x: x.created_at):
            citations = [Citation(**c) for c in (m.citations or [])]
            msg_items.append(
                ChatMessageItem(
                    id=m.id,
                    conversation_id=m.conversation_id,
                    role=m.role,
                    content=m.content,
                    citations=citations,
                    retrieval_intents=m.retrieval_intents or [],
                    retrieval_sources=m.retrieval_sources or [],
                    confidence=m.confidence,
                    insufficient_evidence=m.insufficient_evidence,
                    generation_model=m.generation_model,
                    generation_latency_ms=m.generation_latency_ms,
                    retrieval_latency_ms=m.retrieval_latency_ms,
                    created_at=m.created_at,
                )
            )

        return ConversationDetail(
            id=conv.id,
            repository_id=conv.repository_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            messages=msg_items,
        )

    async def delete_conversation(
        self,
        db: AsyncSession,
        repository_id: str,
        conversation_id: str,
    ) -> bool:
        """Deletes a conversation and its messages. Enforces repository isolation."""
        stmt = (
            delete(ConversationModel)
            .where(
                ConversationModel.id == conversation_id,
                ConversationModel.repository_id == repository_id,
            )
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount > 0

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        repository_id: str,
        role: str,
        content: str,
        citations: Optional[List[Citation]] = None,
        retrieval_intents: Optional[List[str]] = None,
        retrieval_sources: Optional[List[str]] = None,
        confidence: float = 1.0,
        insufficient_evidence: bool = False,
        generation_model: Optional[str] = None,
        generation_latency_ms: Optional[float] = None,
        retrieval_latency_ms: Optional[float] = None,
    ) -> ChatMessageItem:
        """Adds a user or assistant message to the conversation."""
        # Convert citations to primitive dicts for JSON column
        cite_dicts = [c.model_dump() for c in (citations or [])]

        msg = ChatMessageModel(
            conversation_id=conversation_id,
            repository_id=repository_id,
            role=role,
            content=content,
            citations=cite_dicts,
            retrieval_intents=retrieval_intents or [],
            retrieval_sources=retrieval_sources or [],
            confidence=confidence,
            insufficient_evidence=insufficient_evidence,
            generation_model=generation_model,
            generation_latency_ms=generation_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
        )
        db.add(msg)

        # Update conversation updated_at and title if it was first user message
        conv_stmt = select(ConversationModel).where(ConversationModel.id == conversation_id)
        conv_res = await db.execute(conv_stmt)
        conv = conv_res.scalar_one_or_none()
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            if conv.title == "New Conversation" and role == "user":
                conv.title = content[:60].strip() + ("..." if len(content) > 60 else "")

        await db.commit()
        await db.refresh(msg)

        return ChatMessageItem(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            citations=citations or [],
            retrieval_intents=msg.retrieval_intents,
            retrieval_sources=msg.retrieval_sources,
            confidence=msg.confidence,
            insufficient_evidence=msg.insufficient_evidence,
            generation_model=msg.generation_model,
            generation_latency_ms=msg.generation_latency_ms,
            retrieval_latency_ms=msg.retrieval_latency_ms,
            created_at=msg.created_at,
        )

    async def get_recent_history(
        self,
        db: AsyncSession,
        conversation_id: str,
        max_messages: int = 6,
    ) -> List[Dict[str, str]]:
        """Returns ordered recent message history formatted for LLM context prompts."""
        stmt = (
            select(ChatMessageModel)
            .where(ChatMessageModel.conversation_id == conversation_id)
            .order_by(desc(ChatMessageModel.created_at))
            .limit(max_messages)
        )
        res = await db.execute(stmt)
        rows = res.scalars().all()

        ordered = list(reversed(rows))
        return [{"role": r.role, "content": r.content} for r in ordered]


# Global singleton instance
conversation_service = ConversationService()
