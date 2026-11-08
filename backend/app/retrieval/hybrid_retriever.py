"""
Master Hybrid Retrieval Service.
Combines Vector RAG (ChromaDB), GraphRAG (NetworkX), and Keyword Search (SQLite FTS5)
into a unified, resilient, and calibrated codebase intelligence retrieval system.
"""

import logging
import time
from typing import List, Dict, Any, Optional

from backend.app.retrieval.retrieval_models import (
    QueryIntent,
    RetrievalStrategy,
    QueryAnalysisResult,
    UnifiedSearchResult,
    GraphEvidence,
    HybridSearchRequest,
    HybridRetrievalResponse,
)
from backend.app.retrieval.query_analyzer import query_analyzer, QueryAnalyzer
from backend.app.retrieval.query_router import query_router, QueryRouter, RoutingPlan
from backend.app.retrieval.keyword_search import keyword_search_engine, KeywordSearchEngine
from backend.app.retrieval.semantic_search import semantic_search_service, SemanticSearchService
from backend.app.retrieval.result_fusion import result_fusion, ResultFusion
from backend.app.retrieval.context_assembler import context_assembler, ContextAssembler
from backend.app.graph.traversal import graph_traversal_service, GraphTraversalService
from backend.app.graph.networkx_store import networkx_graph_store

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Unified multi-engine retrieval service combining dense vector embeddings,
    structural knowledge graph traversal, and BM25 keyword matching.
    """

    def __init__(
        self,
        analyzer: Optional[QueryAnalyzer] = None,
        router: Optional[QueryRouter] = None,
        vector_service: Optional[SemanticSearchService] = None,
        keyword_engine: Optional[KeywordSearchEngine] = None,
        graph_service: Optional[GraphTraversalService] = None,
        fusion: Optional[ResultFusion] = None,
        assembler: Optional[ContextAssembler] = None,
    ):
        self.analyzer = analyzer or query_analyzer
        self.router = router or query_router
        self.vector_service = vector_service or semantic_search_service
        self.keyword_engine = keyword_engine or keyword_search_engine
        self.graph_service = graph_service or graph_traversal_service
        self.fusion = fusion or result_fusion
        self.assembler = assembler or context_assembler

    def hybrid_search(
        self,
        repository_id: str,
        request: HybridSearchRequest,
    ) -> HybridRetrievalResponse:
        """
        Executes end-to-end hybrid retrieval:
          1. Query understanding & intent classification
          2. Execution plan routing
          3. Coordinated retrieval across active engines with timing & error isolation
          4. Reciprocal Rank Fusion & deduplication
          5. Evidence context assembly
        """
        start_total = time.perf_counter()
        execution_times: Dict[str, float] = {}
        warnings: List[str] = []

        # 1. Query Analysis
        t0 = time.perf_counter()
        analysis = self.analyzer.analyze(request.query)
        execution_times["query_analysis"] = round((time.perf_counter() - t0) * 1000, 2)

        # 2. Execution Routing
        t0 = time.perf_counter()
        plan = self.router.route(
            analysis,
            top_k=request.top_k,
            include_vector=request.include_vector,
            include_graph=request.include_graph,
            include_keyword=request.include_keyword,
        )
        execution_times["query_routing"] = round((time.perf_counter() - t0) * 1000, 2)

        vector_results: List[UnifiedSearchResult] = []
        keyword_results: List[UnifiedSearchResult] = []
        graph_results: List[UnifiedSearchResult] = []
        graph_evidence: List[GraphEvidence] = []

        # 3. Vector Retrieval Engine
        if plan.vector_enabled:
            t0 = time.perf_counter()
            try:
                raw_vector = self.vector_service.search(
                    repository_id=repository_id,
                    query=request.query,
                    top_k=plan.vector_top_k,
                    language=request.language,
                    file_path=request.file_path,
                    symbol_type=request.symbol_type,
                )
                for r in raw_vector:
                    c = r.chunk
                    vector_results.append(
                        UnifiedSearchResult(
                            chunk_id=c.chunk_id,
                            repository_id=c.repository_id,
                            file_path=c.file_path,
                            symbol_id=c.symbol_id,
                            symbol_name=c.symbol_name,
                            symbol_type=c.symbol_type,
                            language=c.language,
                            start_line=c.start_line,
                            end_line=c.end_line,
                            source_code=c.source_code,
                            signature=c.signature,
                            docstring=c.docstring,
                            context_header=c.context_header,
                            retrieval_source="VECTOR",
                            sources=["VECTOR"],
                            original_score=round(r.similarity_score, 4),
                            normalized_score=round(r.similarity_score, 4),
                            rrf_score=0.0,
                            confidence=1.0,
                        )
                    )
            except Exception as e:
                logger.exception("Vector retrieval failure for repo %s: %s", repository_id, e)
                warnings.append(f"Vector search engine error: {str(e)}")
            finally:
                execution_times["vector_search"] = round((time.perf_counter() - t0) * 1000, 2)

        # 4. Keyword Retrieval Engine
        if plan.keyword_enabled:
            t0 = time.perf_counter()
            try:
                keyword_results = self.keyword_engine.search(
                    repository_id=repository_id,
                    query=request.query,
                    top_k=plan.keyword_top_k,
                    language=request.language,
                    file_path=request.file_path,
                    symbol_type=request.symbol_type,
                )
            except Exception as e:
                logger.exception("Keyword retrieval failure for repo %s: %s", repository_id, e)
                warnings.append(f"Keyword search engine error: {str(e)}")
            finally:
                execution_times["keyword_search"] = round((time.perf_counter() - t0) * 1000, 2)

        # 5. Graph Retrieval Engine
        if plan.graph_enabled:
            t0 = time.perf_counter()
            try:
                # Find candidate symbols to query in graph
                candidate_symbols = list(plan.target_symbols)

                # If no symbols extracted from query, use top symbols from keyword or vector results
                if not candidate_symbols:
                    for item in (keyword_results + vector_results)[:3]:
                        if item.symbol_name and item.symbol_name not in candidate_symbols:
                            candidate_symbols.append(item.symbol_name)

                for sym in candidate_symbols[:3]:
                    # Callers
                    if "callers" in plan.graph_operations or not plan.graph_operations:
                        c_res = self.graph_service.find_callers(repository_id, sym)
                        if c_res.get("found"):
                            for c in c_res.get("callers", []):
                                graph_evidence.append(
                                    GraphEvidence(
                                        relationship_type="CALLS",
                                        source_node_id=c["caller_id"],
                                        source_name=c["caller_name"],
                                        target_node_id=c_res.get("target_id", sym),
                                        target_name=sym,
                                        confidence=c.get("confidence", 1.0),
                                        is_confirmed=c.get("is_confirmed", True),
                                        call_count=c.get("call_count", 1),
                                        lines=c.get("invocation_lines", []),
                                        file_path=c.get("file_path"),
                                        description=f"`{c['caller_name']}` calls `{sym}`",
                                    )
                                )

                    # Callees
                    if "callees" in plan.graph_operations:
                        cl_res = self.graph_service.find_callees(repository_id, sym)
                        if cl_res.get("found"):
                            for cl in cl_res.get("callees", []):
                                graph_evidence.append(
                                    GraphEvidence(
                                        relationship_type="CALLS",
                                        source_node_id=cl_res.get("source_id", sym),
                                        source_name=sym,
                                        target_node_id=cl["callee_id"],
                                        target_name=cl["callee_name"],
                                        confidence=cl.get("confidence", 1.0),
                                        is_confirmed=cl.get("is_confirmed", True),
                                        call_count=cl.get("call_count", 1),
                                        lines=cl.get("invocation_lines", []),
                                        file_path=cl.get("file_path"),
                                        description=f"`{sym}` calls `{cl['callee_name']}`",
                                    )
                                )

                    # Dependencies
                    if "dependencies" in plan.graph_operations:
                        d_res = self.graph_service.find_dependencies(repository_id, sym)
                        if d_res.get("found"):
                            for imp in d_res.get("imported_modules", []):
                                graph_evidence.append(
                                    GraphEvidence(
                                        relationship_type=imp.get("relationship", "IMPORTS"),
                                        source_node_id=d_res.get("target_id", sym),
                                        source_name=sym,
                                        target_node_id=imp["id"],
                                        target_name=imp["name"],
                                        confidence=imp.get("confidence", 1.0),
                                        is_confirmed=True,
                                        file_path=d_res.get("file_path"),
                                        description=f"`{sym}` imports `{imp['name']}`",
                                    )
                                )

                    # Impact
                    if "impact" in plan.graph_operations:
                        imp_res = self.graph_service.analyze_impact(repository_id, sym, depth=2)
                        if imp_res.get("found"):
                            for dc in imp_res.get("direct_callers", []):
                                graph_evidence.append(
                                    GraphEvidence(
                                        relationship_type="IMPACTS",
                                        source_node_id=imp_res.get("target_node_id", sym),
                                        source_name=sym,
                                        target_node_id=dc["node_id"],
                                        target_name=dc["name"],
                                        confidence=dc.get("confidence", 1.0),
                                        is_confirmed=True,
                                        lines=[dc["line"]] if dc.get("line") else [],
                                        file_path=dc.get("file_path"),
                                        description=f"Modifying `{sym}` impacts caller `{dc['name']}`",
                                    )
                                )

                # Convert graph evidence nodes to code search chunks via keyword engine lookup
                # Prioritize answer entities based on query intent!
                evidence_symbols: List[str] = []
                if QueryIntent.EXACT_SYMBOL in analysis.intents:
                    for sym in analysis.extracted_symbols:
                        if sym not in evidence_symbols:
                            evidence_symbols.append(sym)

                for ev in graph_evidence:
                    if QueryIntent.CALLEES in analysis.intents:
                        if ev.target_name and ev.target_name not in evidence_symbols:
                            evidence_symbols.append(ev.target_name)
                    elif QueryIntent.CALLERS in analysis.intents:
                        if ev.source_name and ev.source_name not in evidence_symbols:
                            evidence_symbols.append(ev.source_name)
                    elif QueryIntent.DEPENDENCIES in analysis.intents:
                        if ev.target_name and ev.target_name not in evidence_symbols:
                            evidence_symbols.append(ev.target_name)
                        if ev.file_path and ev.file_path not in evidence_symbols:
                            evidence_symbols.append(ev.file_path)
                    elif QueryIntent.IMPACT_ANALYSIS in analysis.intents:
                        if ev.target_name and ev.target_name not in evidence_symbols:
                            evidence_symbols.append(ev.target_name)
                    else:
                        if ev.target_name and ev.target_name not in evidence_symbols:
                            evidence_symbols.append(ev.target_name)
                        if ev.source_name and ev.source_name not in evidence_symbols:
                            evidence_symbols.append(ev.source_name)

                for ev_sym in evidence_symbols[:5]:
                    kw_matches = self.keyword_engine.search(repository_id, ev_sym, top_k=1)
                    for km in kw_matches:
                        km.retrieval_source = "GRAPH"
                        km.sources = ["GRAPH"]
                        graph_results.append(km)

            except Exception as e:
                logger.exception("Graph retrieval failure for repo %s: %s", repository_id, e)
                warnings.append(f"Graph traversal error: {str(e)}")
            finally:
                execution_times["graph_traversal"] = round((time.perf_counter() - t0) * 1000, 2)

        # 6. Reciprocal Rank Fusion & Deduplication
        t0 = time.perf_counter()

        # Dynamic intent-adjusted engine weights
        weights = {
            "VECTOR": 1.0,
            "KEYWORD": 1.1,
            "GRAPH": 1.0,
        }
        if any(i in analysis.intents for i in (QueryIntent.CALLERS, QueryIntent.CALLEES, QueryIntent.DEPENDENCIES, QueryIntent.IMPACT_ANALYSIS, QueryIntent.INHERITANCE)):
            weights["GRAPH"] = 1.8
            weights["KEYWORD"] = 0.8
            weights["VECTOR"] = 0.7
        elif QueryIntent.EXACT_SYMBOL in analysis.intents:
            weights["KEYWORD"] = 1.5
            weights["VECTOR"] = 0.9
            weights["GRAPH"] = 0.9
        elif QueryIntent.SEMANTIC in analysis.intents:
            weights["VECTOR"] = 1.3
            weights["KEYWORD"] = 1.0
            weights["GRAPH"] = 0.8

        ranked_results = self.fusion.fuse_and_rank(
            vector_results=vector_results,
            keyword_results=keyword_results,
            graph_results=graph_results,
            top_k=request.top_k,
            k=request.rrf_k,
            weights=weights,
        )
        execution_times["fusion_and_ranking"] = round((time.perf_counter() - t0) * 1000, 2)

        # 7. Context Assembly
        t0 = time.perf_counter()
        assembled_context = self.assembler.assemble(
            query=request.query,
            results=ranked_results,
            graph_evidence=graph_evidence,
        )
        execution_times["context_assembly"] = round((time.perf_counter() - t0) * 1000, 2)

        execution_times["total_retrieval"] = round((time.perf_counter() - start_total) * 1000, 2)

        strategies_used = [s.value for s in plan.strategies]

        diagnostics = {
            "intents_detected": [i.value for i in analysis.intents],
            "intent_confidence": analysis.confidence,
            "extracted_symbols": analysis.extracted_symbols,
            "extracted_file_paths": analysis.extracted_file_paths,
            "vector_candidates_count": len(vector_results),
            "keyword_candidates_count": len(keyword_results),
            "graph_candidates_count": len(graph_results),
            "graph_relationships_count": len(graph_evidence),
            "fused_results_count": len(ranked_results),
            "routing_reasons": plan.reasons,
        }

        return HybridRetrievalResponse(
            query=request.query,
            repository_id=repository_id,
            intents=[i.value for i in analysis.intents],
            strategies_used=strategies_used,
            total_results=len(ranked_results),
            results=ranked_results,
            graph_evidence=graph_evidence,
            assembled_context=assembled_context,
            execution_times=execution_times,
            warnings=warnings,
            diagnostics=diagnostics,
        )


# Global singleton instance
hybrid_retriever = HybridRetriever()
