"""
Master Grounded Generation Service (Phase 7).
Coordinates Hybrid Retrieval, evidence sufficiency evaluation, anti-prompt injection,
Google Gemini streaming and non-streaming generation, citation validation,
and persistent repository-scoped conversational memory.
"""

import json
import logging
import time
from typing import AsyncIterator, Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import AsyncSessionLocal
from backend.app.database.models import RepositoryModel
from backend.app.llm.generation_models import (
    Citation,
    EvidenceSufficiency,
    StructuredAnswer,
    ChatStreamRequest,
    ChatStreamEventType,
)
from backend.app.llm.gemini_client import (
    GeminiClient,
    gemini_client,
    GeminiError,
    GeminiQuotaExceededError,
    GeminiInvalidCredentialsError,
    GeminiModelUnavailableError,
    GeminiSafetyBlockedError,
    GeminiTimeoutError,
)
from backend.app.llm.citation_validator import CitationValidator
from backend.app.llm.prompt_templates import SYSTEM_INSTRUCTION, build_generation_prompt
from backend.app.llm.conversation_service import ConversationService, conversation_service
from backend.app.retrieval.hybrid_retriever import HybridRetriever, hybrid_retriever
from backend.app.retrieval.retrieval_models import HybridSearchRequest, HybridRetrievalResponse

logger = logging.getLogger(__name__)


def format_sse_event(event_type: ChatStreamEventType, data: Dict[str, Any]) -> str:
    """Formats payload according to standard Server-Sent Events (SSE) protocol."""
    return f"event: {event_type.value}\ndata: {json.dumps(data)}\n\n"


class GenerationService:
    """
    Coordinates grounded answer generation across Hybrid Retrieval, Gemini LLM,
    citation verification, and conversation state persistence.
    """

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
        retriever: Optional[HybridRetriever] = None,
        conv_service: Optional[ConversationService] = None,
        validator: Optional[CitationValidator] = None,
    ):
        self.gemini_client = gemini or gemini_client
        self.hybrid_retriever = retriever or hybrid_retriever
        self.conversation_service = conv_service or conversation_service
        self.citation_validator = validator or CitationValidator()

    def evaluate_evidence_sufficiency(
        self,
        retrieval_response: HybridRetrievalResponse,
    ) -> EvidenceSufficiency:
        """
        Classifies whether retrieved evidence is sufficient to ground an accurate answer.
        """
        results = retrieval_response.results
        graph_ev = retrieval_response.graph_evidence

        if not results and not graph_ev:
            return EvidenceSufficiency.NO_EVIDENCE

        # If there are results, check scores
        if results:
            top_score = results[0].normalized_score
            # If top result has high score or multiple results exist
            if top_score >= 0.5 or len(results) >= 2 or len(graph_ev) >= 2:
                return EvidenceSufficiency.SUFFICIENT
            elif top_score >= 0.2:
                return EvidenceSufficiency.PARTIAL
            else:
                return EvidenceSufficiency.INSUFFICIENT

        if graph_ev:
            return EvidenceSufficiency.PARTIAL

        return EvidenceSufficiency.INSUFFICIENT

    async def generate_answer(
        self,
        repository_id: str,
        request: ChatStreamRequest,
        db: Optional[AsyncSession] = None,
    ) -> StructuredAnswer:
        """
        Executes a complete, non-streaming grounded answer generation workflow.
        """
        if db is not None:
            return await self._generate_answer_internal(db, repository_id, request)
        else:
            async with AsyncSessionLocal() as session:
                return await self._generate_answer_internal(session, repository_id, request)

    async def _generate_answer_internal(
        self,
        db: AsyncSession,
        repository_id: str,
        request: ChatStreamRequest,
    ) -> StructuredAnswer:
        # 1. Verify repository
        stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
        res = await db.execute(stmt)
        repo = res.scalar_one_or_none()
        if not repo:
            raise ValueError(f"Repository {repository_id} not found.")

        # 2. Get or create conversation
        conversation_id = request.conversation_id
        if not conversation_id:
            conv = await self.conversation_service.create_conversation(db, repository_id=repository_id)
            conversation_id = conv.id
        else:
            conv = await self.conversation_service.get_conversation(db, repository_id, conversation_id)
            if not conv:
                conv = await self.conversation_service.create_conversation(
                    db, repository_id=repository_id
                )
                conversation_id = conv.id

        # 3. Add user message
        await self.conversation_service.add_message(
            db=db,
            conversation_id=conversation_id,
            repository_id=repository_id,
            role="user",
            content=request.query,
        )

        # 4. Load recent history prior to current message
        history = await self.conversation_service.get_recent_history(
            db=db, conversation_id=conversation_id, max_messages=6
        )
        # Drop the last user message from history turns so it's not duplicated in prompt
        prior_history = history[:-1] if history else []

        # 5. Execute hybrid retrieval
        retrieval_start = time.perf_counter()
        search_req = HybridSearchRequest(query=request.query, top_k=request.top_k)
        retrieval_resp = self.hybrid_retriever.hybrid_search(repository_id, search_req)
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

        # 6. Evaluate evidence sufficiency
        sufficiency = self.evaluate_evidence_sufficiency(retrieval_resp)

        # 7. Check for NO_EVIDENCE
        if sufficiency == EvidenceSufficiency.NO_EVIDENCE:
            answer_content = (
                "The indexed repository does not contain sufficient evidence to answer this question. "
                "No matching source code chunks or architectural relationships were found in the codebase. "
                "Please verify the query or search for specific function, class, or module names."
            )
            citations: List[Citation] = []
            confidence = 0.0
            gen_latency_ms = 0.0
        else:
            # 8. Build prompt and generate
            prompt = build_generation_prompt(
                query=request.query,
                repository_name=repo.name,
                primary_language=repo.primary_language,
                assembled_evidence=retrieval_resp.assembled_context.formatted_context,
                conversation_history=prior_history,
            )

            gen_start = time.perf_counter()
            answer_content = await self.gemini_client.generate(
                prompt=prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=request.temperature,
            )
            gen_latency_ms = (time.perf_counter() - gen_start) * 1000

            # 9. Validate citations
            citations = self.citation_validator.validate_citations(
                generated_text=answer_content,
                retrieved_chunks=retrieval_resp.results,
                graph_evidence=retrieval_resp.graph_evidence,
            )

            # 10. Compute confidence
            if citations:
                avg_cite_conf = sum(c.confidence for c in citations) / len(citations)
                confidence = round(min(1.0, max(0.6, avg_cite_conf)), 2)
            else:
                confidence = 0.7 if sufficiency == EvidenceSufficiency.SUFFICIENT else 0.5

        insufficient = sufficiency in (EvidenceSufficiency.NO_EVIDENCE, EvidenceSufficiency.INSUFFICIENT) or (
            "insufficient evidence" in answer_content.lower()
        )

        # 11. Persist assistant message
        assistant_msg = await self.conversation_service.add_message(
            db=db,
            conversation_id=conversation_id,
            repository_id=repository_id,
            role="assistant",
            content=answer_content,
            citations=citations,
            retrieval_intents=retrieval_resp.intents,
            retrieval_sources=retrieval_resp.strategies_used,
            confidence=confidence,
            insufficient_evidence=insufficient,
            generation_model=self.gemini_client.model_name,
            generation_latency_ms=round(gen_latency_ms, 2),
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
        )

        return StructuredAnswer(
            answer_id=assistant_msg.id,
            conversation_id=conversation_id,
            repository_id=repository_id,
            content=answer_content,
            citations=citations,
            retrieval_intents=retrieval_resp.intents,
            retrieval_sources=retrieval_resp.strategies_used,
            confidence=confidence,
            evidence_sufficiency=sufficiency,
            generation_model=self.gemini_client.model_name,
            generation_latency_ms=round(gen_latency_ms, 2),
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
            warnings=retrieval_resp.warnings,
        )

    async def stream_answer(
        self,
        repository_id: str,
        request: ChatStreamRequest,
        db: Optional[AsyncSession] = None,
    ) -> AsyncIterator[str]:
        """
        Coordinates streaming answer generation via Server-Sent Events (SSE).
        Yields serialized SSE events for retrieval start, completion, tokens, citations, and completion.
        """
        if db is not None:
            async for chunk in self._stream_answer_internal(db, repository_id, request):
                yield chunk
        else:
            async with AsyncSessionLocal() as session:
                async for chunk in self._stream_answer_internal(session, repository_id, request):
                    yield chunk

    async def _stream_answer_internal(
        self,
        db: AsyncSession,
        repository_id: str,
        request: ChatStreamRequest,
    ) -> AsyncIterator[str]:
        try:
            # 1. Verify repository
            stmt = select(RepositoryModel).where(RepositoryModel.id == repository_id)
            res = await db.execute(stmt)
            repo = res.scalar_one_or_none()
            if not repo:
                yield format_sse_event(
                    ChatStreamEventType.ERROR,
                    {"error": f"Repository '{repository_id}' not found.", "error_type": "NotFoundError"},
                )
                return

            # 2. Get or create conversation
            conversation_id = request.conversation_id
            if not conversation_id:
                conv = await self.conversation_service.create_conversation(db, repository_id=repository_id)
                conversation_id = conv.id
            else:
                conv = await self.conversation_service.get_conversation(db, repository_id, conversation_id)
                if not conv:
                    conv = await self.conversation_service.create_conversation(
                        db, repository_id=repository_id
                    )
                    conversation_id = conv.id

            # 3. Notify retrieval started
            yield format_sse_event(
                ChatStreamEventType.RETRIEVAL_STARTED,
                {
                    "conversation_id": conversation_id,
                    "repository_id": repository_id,
                    "query": request.query,
                },
            )

            # 4. Save user message
            await self.conversation_service.add_message(
                db=db,
                conversation_id=conversation_id,
                repository_id=repository_id,
                role="user",
                content=request.query,
            )

            # 5. Fetch prior conversation history
            history = await self.conversation_service.get_recent_history(
                db=db, conversation_id=conversation_id, max_messages=6
            )
            prior_history = history[:-1] if history else []

            # 6. Execute hybrid retrieval
            retrieval_start = time.perf_counter()
            search_req = HybridSearchRequest(query=request.query, top_k=request.top_k)
            retrieval_resp = self.hybrid_retriever.hybrid_search(repository_id, search_req)
            retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

            # 7. Notify retrieval completed
            yield format_sse_event(
                ChatStreamEventType.RETRIEVAL_COMPLETED,
                {
                    "conversation_id": conversation_id,
                    "intents": retrieval_resp.intents,
                    "strategies_used": retrieval_resp.strategies_used,
                    "total_results": retrieval_resp.total_results,
                    "graph_evidence_count": len(retrieval_resp.graph_evidence),
                    "retrieval_latency_ms": round(retrieval_latency_ms, 2),
                },
            )

            # 8. Evaluate evidence sufficiency
            sufficiency = self.evaluate_evidence_sufficiency(retrieval_resp)

            # 9. Handle NO_EVIDENCE case directly
            if sufficiency == EvidenceSufficiency.NO_EVIDENCE:
                yield format_sse_event(
                    ChatStreamEventType.GENERATION_STARTED,
                    {"model": self.gemini_client.model_name},
                )
                answer_content = (
                    "The indexed repository does not contain sufficient evidence to answer this question. "
                    "No matching source code chunks or architectural relationships were found in the codebase. "
                    "Please verify the query or search for specific function, class, or module names."
                )
                yield format_sse_event(ChatStreamEventType.TOKEN, {"token": answer_content})

                assistant_msg = await self.conversation_service.add_message(
                    db=db,
                    conversation_id=conversation_id,
                    repository_id=repository_id,
                    role="assistant",
                    content=answer_content,
                    citations=[],
                    retrieval_intents=retrieval_resp.intents,
                    retrieval_sources=retrieval_resp.strategies_used,
                    confidence=0.0,
                    insufficient_evidence=True,
                    generation_model=self.gemini_client.model_name,
                    generation_latency_ms=0.0,
                    retrieval_latency_ms=round(retrieval_latency_ms, 2),
                )

                yield format_sse_event(
                    ChatStreamEventType.DONE,
                    {
                        "answer_id": assistant_msg.id,
                        "conversation_id": conversation_id,
                        "repository_id": repository_id,
                        "content": answer_content,
                        "citations": [],
                        "retrieval_intents": retrieval_resp.intents,
                        "retrieval_sources": retrieval_resp.strategies_used,
                        "confidence": 0.0,
                        "evidence_sufficiency": sufficiency.value,
                        "generation_model": self.gemini_client.model_name,
                        "generation_latency_ms": 0.0,
                        "retrieval_latency_ms": round(retrieval_latency_ms, 2),
                    },
                )
                return

            # 10. Normal generation path
            yield format_sse_event(
                ChatStreamEventType.GENERATION_STARTED,
                {"model": self.gemini_client.model_name},
            )

            prompt = build_generation_prompt(
                query=request.query,
                repository_name=repo.name,
                primary_language=repo.primary_language,
                assembled_evidence=retrieval_resp.assembled_context.formatted_context,
                conversation_history=prior_history,
            )

            gen_start = time.perf_counter()
            full_text = ""

            async for token in self.gemini_client.generate_stream(
                prompt=prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=request.temperature,
            ):
                full_text += token
                yield format_sse_event(ChatStreamEventType.TOKEN, {"token": token})

            gen_latency_ms = (time.perf_counter() - gen_start) * 1000

            # 11. Validate citations from full text
            citations = self.citation_validator.validate_citations(
                generated_text=full_text,
                retrieved_chunks=retrieval_resp.results,
                graph_evidence=retrieval_resp.graph_evidence,
            )

            for cite in citations:
                yield format_sse_event(ChatStreamEventType.CITATION, {"citation": cite.model_dump()})

            # 12. Determine confidence
            if citations:
                avg_cite_conf = sum(c.confidence for c in citations) / len(citations)
                confidence = round(min(1.0, max(0.6, avg_cite_conf)), 2)
            else:
                confidence = 0.7 if sufficiency == EvidenceSufficiency.SUFFICIENT else 0.5

            insufficient = (
                sufficiency in (EvidenceSufficiency.NO_EVIDENCE, EvidenceSufficiency.INSUFFICIENT)
                or ("insufficient evidence" in full_text.lower())
            )

            # 13. Persist assistant message
            assistant_msg = await self.conversation_service.add_message(
                db=db,
                conversation_id=conversation_id,
                repository_id=repository_id,
                role="assistant",
                content=full_text,
                citations=citations,
                retrieval_intents=retrieval_resp.intents,
                retrieval_sources=retrieval_resp.strategies_used,
                confidence=confidence,
                insufficient_evidence=insufficient,
                generation_model=self.gemini_client.model_name,
                generation_latency_ms=round(gen_latency_ms, 2),
                retrieval_latency_ms=round(retrieval_latency_ms, 2),
            )

            # 14. Emit DONE event
            yield format_sse_event(
                ChatStreamEventType.DONE,
                {
                    "answer_id": assistant_msg.id,
                    "conversation_id": conversation_id,
                    "repository_id": repository_id,
                    "content": full_text,
                    "citations": [c.model_dump() for c in citations],
                    "retrieval_intents": retrieval_resp.intents,
                    "retrieval_sources": retrieval_resp.strategies_used,
                    "confidence": confidence,
                    "evidence_sufficiency": sufficiency.value,
                    "generation_model": self.gemini_client.model_name,
                    "generation_latency_ms": round(gen_latency_ms, 2),
                    "retrieval_latency_ms": round(retrieval_latency_ms, 2),
                },
            )

        except (
            GeminiQuotaExceededError,
            GeminiInvalidCredentialsError,
            GeminiModelUnavailableError,
            GeminiSafetyBlockedError,
            GeminiTimeoutError,
            GeminiError,
        ) as e:
            logger.error("Gemini LLM error during chat stream: %s", e)
            yield format_sse_event(
                ChatStreamEventType.ERROR,
                {"error": str(e), "error_type": type(e).__name__},
            )
        except Exception as e:
            logger.exception("Unexpected failure during chat stream: %s", e)
            yield format_sse_event(
                ChatStreamEventType.ERROR,
                {"error": f"An unexpected generation error occurred: {str(e)}", "error_type": type(e).__name__},
            )


# Global singleton instance
generation_service = GenerationService()
