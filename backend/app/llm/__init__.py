"""
LLM and Conversational Chat Package (Phase 7).
Provides official Google Gen AI Gemini integration, anti-prompt injection,
grounded generation with clickable citations, and persistent conversational chat.
"""

from backend.app.llm.generation_models import (
    EvidenceSufficiency,
    Citation,
    ChatMessageItem,
    ConversationListItem,
    ConversationDetail,
    CreateConversationRequest,
    ChatStreamRequest,
    StructuredAnswer,
    ChatStreamEventType,
)
from backend.app.llm.gemini_client import (
    GeminiClient,
    gemini_client,
    GeminiError,
    GeminiConfigError,
    GeminiQuotaExceededError,
    GeminiInvalidCredentialsError,
    GeminiModelUnavailableError,
    GeminiSafetyBlockedError,
    GeminiTimeoutError,
)
from backend.app.llm.citation_validator import CitationValidator
from backend.app.llm.conversation_service import ConversationService, conversation_service
from backend.app.llm.generation_service import GenerationService, generation_service, format_sse_event

__all__ = [
    "EvidenceSufficiency",
    "Citation",
    "ChatMessageItem",
    "ConversationListItem",
    "ConversationDetail",
    "CreateConversationRequest",
    "ChatStreamRequest",
    "StructuredAnswer",
    "ChatStreamEventType",
    "GeminiClient",
    "gemini_client",
    "GeminiError",
    "GeminiConfigError",
    "GeminiQuotaExceededError",
    "GeminiInvalidCredentialsError",
    "GeminiModelUnavailableError",
    "GeminiSafetyBlockedError",
    "GeminiTimeoutError",
    "CitationValidator",
    "ConversationService",
    "conversation_service",
    "GenerationService",
    "generation_service",
    "format_sse_event",
]
