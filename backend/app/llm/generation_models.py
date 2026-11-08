"""
Pydantic domain models and schemas for Gemini LLM Generation and Conversational Chat (Phase 7).
Defines citation entities, structured answer objects, conversation schemas,
and Server-Sent Event (SSE) streaming protocols.
"""

from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EvidenceSufficiency(str, Enum):
    """Classification of retrieved repository evidence sufficiency."""
    SUFFICIENT = "SUFFICIENT"            # Clear, direct evidence to ground the answer
    PARTIAL = "PARTIAL"                  # Some relevant code found, but missing parts
    INSUFFICIENT = "INSUFFICIENT"        # Retrieved code is tangential or inconclusive
    NO_EVIDENCE = "NO_EVIDENCE"          # No relevant chunks retrieved from repository


class Citation(BaseModel):
    """
    Validated citation entity referencing exact source file coordinates.
    Guaranteed to match actual retrieved code chunks or structural graph relations.
    """
    citation_id: str
    file_path: str
    start_line: int
    end_line: int
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None
    source_excerpt: Optional[str] = None
    retrieval_source: str = "HYBRID"     # e.g., "VECTOR", "GRAPH", "KEYWORD", "HYBRID"
    confidence: float = 1.0              # Provenance confidence
    is_verified: bool = True             # Validated against supplied evidence
    reason: Optional[str] = None


class ChatMessageItem(BaseModel):
    """Single chat message in conversation history."""
    id: str
    conversation_id: str
    role: str                            # "user" or "assistant"
    content: str
    citations: List[Citation] = Field(default_factory=list)
    retrieval_intents: List[str] = Field(default_factory=list)
    retrieval_sources: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    insufficient_evidence: bool = False
    generation_model: Optional[str] = None
    generation_latency_ms: Optional[float] = None
    retrieval_latency_ms: Optional[float] = None
    created_at: datetime


class ConversationListItem(BaseModel):
    """Summary item for conversation listing sidebar."""
    id: str
    repository_id: str
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    """Full conversation detail with ordered message history."""
    id: str
    repository_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageItem] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    """Payload to initialize a new conversation."""
    title: Optional[str] = Field(None, max_length=255, description="Optional conversation topic title")


class ChatStreamRequest(BaseModel):
    """Request payload for conversational chat stream."""
    query: str = Field(..., min_length=1, max_length=4000, description="Developer natural-language question")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID or None for auto-created")
    top_k: int = Field(5, ge=1, le=20, description="Max code chunk evidence items to retrieve")
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model generation temperature override")


class StructuredAnswer(BaseModel):
    """Complete, validated answer returned at end of chat or non-streaming call."""
    answer_id: str
    conversation_id: str
    repository_id: str
    content: str
    citations: List[Citation] = Field(default_factory=list)
    retrieval_intents: List[str] = Field(default_factory=list)
    retrieval_sources: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.SUFFICIENT
    generation_model: str
    generation_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    warnings: List[str] = Field(default_factory=list)


class ChatStreamEventType(str, Enum):
    """Event names for Server-Sent Events (SSE) streaming protocol."""
    RETRIEVAL_STARTED = "retrieval_started"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    GENERATION_STARTED = "generation_started"
    TOKEN = "token"
    CITATION = "citation"
    WARNING = "warning"
    ERROR = "error"
    DONE = "done"
