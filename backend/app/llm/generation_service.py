"""
Master Grounded Generation Service (Phase 7).
Coordinates Hybrid Retrieval, evidence sufficiency evaluation, anti-prompt injection,
Google Gemini streaming and non-streaming generation, citation validation,
and persistent repository-scoped conversational memory.
"""

import json
import logging
import re
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
from backend.app.retrieval.endpoint_matcher import (
    extract_endpoint_from_query,
    match_endpoint_against_chunks,
    RouteMatchStatus,
)
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
        Multi-factor classification of whether retrieved evidence is sufficient,
        partial, insufficient, or absent to ground an accurate answer.
        Evaluates exact API route matching, symbol matches, confirmed graph relations,
        distinctive external technologies, domain term alignment, and calibrated similarity.
        """
        results = retrieval_response.results
        graph_ev = retrieval_response.graph_evidence
        raw_query = retrieval_response.query or ""
        query = raw_query.lower()
        diagnostics = retrieval_response.diagnostics or {}

        # ---------------------------------------------------------
        # 1. API Route & Endpoint Matching Check (Phase 9.4 + Full-Repo Discovery)
        # ---------------------------------------------------------
        endpoint_target = extract_endpoint_from_query(raw_query)
        if endpoint_target:
            repo_chunks = []
            if (
                retrieval_response.repository_id
                and self.hybrid_retriever
                and getattr(self.hybrid_retriever, "keyword_engine", None)
            ):
                repo_chunks = self.hybrid_retriever.keyword_engine.get_all_repository_chunks(
                    retrieval_response.repository_id
                )
            scan_chunks = repo_chunks if repo_chunks else results
            if not scan_chunks and not graph_ev:
                return EvidenceSufficiency.NO_EVIDENCE
            route_match = match_endpoint_against_chunks(endpoint_target, scan_chunks)
            if route_match.status == RouteMatchStatus.EXACT_MATCH:
                if repo_chunks and route_match.matched_file:
                    existing_ids = {r.chunk_id for r in results}
                    matched_file_chunks = [
                        c for c in repo_chunks
                        if c.file_path == route_match.matched_file and c.chunk_id not in existing_ids
                    ]
                    if matched_file_chunks and not any(r.file_path == route_match.matched_file for r in results):
                        retrieval_response.results.extend(matched_file_chunks[:2])
                return EvidenceSufficiency.SUFFICIENT
            elif route_match.status == RouteMatchStatus.METHOD_MISMATCH:
                # Path exists, but HTTP method is unsupported (e.g. DELETE /login)
                return EvidenceSufficiency.INSUFFICIENT
            elif route_match.status in (RouteMatchStatus.PREFIX_ONLY, RouteMatchStatus.NOT_FOUND):
                # The endpoint path is absent or only a common prefix matches
                return EvidenceSufficiency.NO_EVIDENCE

        if not results and not graph_ev:
            return EvidenceSufficiency.NO_EVIDENCE

        # ---------------------------------------------------------
        # 2. Confirmed Structural Graph Evidence
        # ---------------------------------------------------------
        confirmed_graph = [e for e in graph_ev if getattr(e, "is_confirmed", True)]
        if confirmed_graph:
            return EvidenceSufficiency.SUFFICIENT

        # ---------------------------------------------------------
        # 3. Qualified Symbol Check (e.g. Class.method, Class::method)
        # ---------------------------------------------------------
        qualified_matches = re.findall(
            r"\b([A-Z][a-zA-Z0-9_]*)[.:#]([a-zA-Z_][a-zA-Z0-9_]*)\b",
            raw_query,
        )
        combined_code = " ".join(f"{r.symbol_name or ''} {r.source_code}".lower() for r in results)
        if qualified_matches:
            for cls_name, member_name in qualified_matches:
                if member_name.lower() not in combined_code:
                    return EvidenceSufficiency.NO_EVIDENCE

        # ---------------------------------------------------------
        # 4. Distinctive External Technology / Out-of-Scope Concepts
        # ---------------------------------------------------------
        DISTINCTIVE_SUBJECT_TERMS = {
            "cassandra", "solidity", "kafka", "biometric", "facial", "fingerprint",
            "crypto_wallet", "cryptocurrency", "bitcoin", "ethereum", "blockchain",
            "couchbase", "dynamodb", "clickhouse", "neo4j", "kubernetes", "k8s",
            "terraform", "graphql", "grpc", "protobuf", "credit_card", "creditcard",
            "aws", "azure", "gcp", "stripe", "paypal", "salesforce", "twilio",
            "sendgrid", "s3", "lambda", "sqs", "sns", "ecs", "eks", "datadog",
            "pypi", "mortgage", "airline", "hipaa", "adjudicator", "coredump",
            "quantum", "entropy", "hsm", "aerodynamic", "crispr", "telehealth",
            "passphrase", "gpu", "gpus", "inference", "pytorch", "tensorflow",
        }
        words = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", query))
        distinctive_in_query = words.intersection(DISTINCTIVE_SUBJECT_TERMS)
        if distinctive_in_query:
            found = [t for t in distinctive_in_query if t in combined_code]
            if not found:
                return EvidenceSufficiency.NO_EVIDENCE

        # ---------------------------------------------------------
        # 5. Query-Extracted Symbol Verification
        # ---------------------------------------------------------
        query_symbols = set(diagnostics.get("extracted_symbols", [])) if diagnostics else set()
        intent = diagnostics.get("intent")
        top_score = results[0].original_score if results else 0.0

        if query_symbols:
            # Check if any symbol exactly matches a retrieved chunk's symbol_name
            exact_match = any(
                r.symbol_name in query_symbols or (r.symbol_name and r.symbol_name.lower() in {s.lower() for s in query_symbols})
                for r in results
            )
            if exact_match:
                return EvidenceSufficiency.SUFFICIENT

            # Check if definition statement exists in source code
            def_matched = False
            for sym in query_symbols:
                sym_l = sym.lower()
                patterns = [
                    f"def {sym_l}", f"class {sym_l}", f"function {sym_l}",
                    f"interface {sym_l}", f"void {sym_l}", f"public {sym_l}",
                ]
                if any(p in combined_code for p in patterns):
                    def_matched = True
                    break
            if def_matched:
                return EvidenceSufficiency.SUFFICIENT

            if intent in ("EXACT_SYMBOL", "SYMBOL"):
                if top_score < 0.35:
                    return EvidenceSufficiency.NO_EVIDENCE
                else:
                    return EvidenceSufficiency.INSUFFICIENT

        # ---------------------------------------------------------
        # 6. Domain Term Alignment & Calibrated Similarity
        # ---------------------------------------------------------
        stop_terms = {
            "what", "where", "which", "when", "does", "have", "this", "that", "from", "with",
            "explain", "show", "find", "code", "repo", "repository", "codebase", "project",
            "function", "functions", "method", "methods", "class", "classes", "module", "modules",
            "file", "files", "defined", "definition", "implemented", "implementation", "call",
            "calls", "invokes", "invoke", "trace", "flow", "impact", "blast", "radius",
            "auth", "flask", "express", "petclinic", "spring", "sindresorhus", "pallets",
            "stored", "configured", "database", "service", "client", "request", "response",
            "used", "using", "uses", "handle", "handles", "handled", "perform", "performs",
            "performed", "algorithm",
        }
        domain_terms = {w for w in words if len(w) >= 4 and w not in stop_terms}
        matched_domain_terms = {t for t in domain_terms if t in combined_code}

        # Check if retrieved symbol name aligns with query domain terms
        for r in results:
            if r.symbol_name:
                sym_lower = r.symbol_name.lower()
                if any(t == sym_lower or (len(t) >= 4 and t in sym_lower) for t in domain_terms):
                    if top_score >= 0.45:
                        return EvidenceSufficiency.SUFFICIENT

        if domain_terms and not matched_domain_terms:
            if top_score < 0.35:
                return EvidenceSufficiency.NO_EVIDENCE
            else:
                return EvidenceSufficiency.INSUFFICIENT

        if domain_terms and matched_domain_terms:
            coverage = len(matched_domain_terms) / len(domain_terms)
            if top_score >= 0.65:
                return EvidenceSufficiency.SUFFICIENT
            elif top_score >= 0.50 and coverage >= 0.3:
                return EvidenceSufficiency.SUFFICIENT
            elif top_score >= 0.35 and coverage >= 0.2:
                return EvidenceSufficiency.PARTIAL
            elif top_score >= 0.28:
                return EvidenceSufficiency.INSUFFICIENT
            else:
                return EvidenceSufficiency.NO_EVIDENCE

        # ---------------------------------------------------------
        # 7. Conceptual / Architectural Queries
        # ---------------------------------------------------------
        if top_score >= 0.55:
            return EvidenceSufficiency.SUFFICIENT
        elif top_score >= 0.38:
            return EvidenceSufficiency.PARTIAL
        elif top_score >= 0.28:
            return EvidenceSufficiency.INSUFFICIENT
        else:
            return EvidenceSufficiency.NO_EVIDENCE

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

        # 7. Check for NO_EVIDENCE or INSUFFICIENT
        if sufficiency in (EvidenceSufficiency.NO_EVIDENCE, EvidenceSufficiency.INSUFFICIENT):
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

            # 9. Handle NO_EVIDENCE or INSUFFICIENT case directly
            if sufficiency in (EvidenceSufficiency.NO_EVIDENCE, EvidenceSufficiency.INSUFFICIENT):
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
