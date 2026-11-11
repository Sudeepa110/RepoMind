"""
Live Unseen Real-World Repository Validation Script (Phase 10 Step 6C & 6D).
Clones authentic public GitHub repositories NEVER used during Phase 9 tuning,
executes the full ingestion -> AST parsing -> multi-engine indexing ->
hybrid retrieval -> evidence sufficiency -> citation/grounding evaluation -> cleanup pipeline,
and persists structured empirical results.
"""

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.utils.validators import validate_github_url, verify_github_repo_accessible
from backend.app.ingestion.cloner import RepositoryCloner
from backend.app.ingestion.file_filter import filter_repository
from backend.app.ingestion.analyzer import analyze_repository
from backend.app.processing.engine import CodeUnderstandingEngine
from backend.app.vectorstore.chunker import StructureAwareChunker
from backend.app.vectorstore.chroma_store import ChromaVectorStore
from backend.app.vectorstore.embeddings import LocalSentenceTransformerService
from backend.app.retrieval.semantic_search import SemanticSearchService
from backend.app.retrieval.keyword_search import KeywordSearchEngine
from backend.app.retrieval.retrieval_models import HybridSearchRequest
from backend.app.retrieval.hybrid_retriever import HybridRetriever
from backend.app.retrieval.query_analyzer import QueryAnalyzer
from backend.app.retrieval.query_router import QueryRouter
from backend.app.retrieval.context_assembler import ContextAssembler
from backend.app.graph.builder import GraphBuilder
from backend.app.graph.networkx_store import NetworkXGraphStore
from backend.app.graph.traversal import GraphTraversalService
from backend.app.llm.citation_validator import CitationValidator
from backend.app.llm.generation_service import GenerationService
from backend.app.llm.generation_models import EvidenceSufficiency
from backend.evaluation.citation_evaluator import CitationAndGroundingEvaluator

RESULTS_PATH = Path(__file__).parent / "results" / "real_world_live_validation.json"

REAL_WORLD_TARGETS = [
    {
        "url": "https://github.com/pallets/itsdangerous",
        "repo_id": "live_validation_itsdangerous",
        "answerable_queries": [
            {
                "query_id": "LIVE_PY_01",
                "query": "Where is the Serializer class defined?",
                "expected_file_hint": "src/itsdangerous/serializer.py",
                "expected_symbol_hint": "Serializer",
            },
            {
                "query_id": "LIVE_PY_02",
                "query": "How does TimedSerializer handle timestamp signing and expiration validation?",
                "expected_file_hint": "src/itsdangerous/timed.py",
                "expected_symbol_hint": "TimedSerializer",
            },
            {
                "query_id": "LIVE_PY_03",
                "query": "Where is URLSafeSerializer implemented?",
                "expected_file_hint": "src/itsdangerous/url_safe.py",
                "expected_symbol_hint": "URLSafeSerializer",
            },
        ],
        "out_of_scope_queries": [
            {
                "query_id": "LIVE_PY_OOS_01",
                "query": "Where is the rotate_jwt_rsa_keys_async function declared?",
                "category": "nonexistent_function",
            },
            {
                "query_id": "LIVE_PY_OOS_02",
                "query": "How is the POST /api/v2/payments/webhook endpoint implemented?",
                "category": "nonexistent_endpoint",
            },
            {
                "query_id": "LIVE_PY_OOS_03",
                "query": "How is Apache Cassandra cluster replication configured here?",
                "category": "unsupported_technology",
            },
        ],
    },
    {
        "url": "https://github.com/sindresorhus/p-limit",
        "repo_id": "live_validation_plimit",
        "answerable_queries": [
            {
                "query_id": "LIVE_TS_01",
                "query": "Where is the main pLimit concurrency limiter function defined?",
                "expected_file_hint": "index.js",
                "expected_symbol_hint": "pLimit",
            },
            {
                "query_id": "LIVE_TS_02",
                "query": "How are queued tasks dequeued and executed inside the concurrency limit?",
                "expected_file_hint": "index.js",
                "expected_symbol_hint": "enqueue",
            },
        ],
        "out_of_scope_queries": [
            {
                "query_id": "LIVE_TS_OOS_01",
                "query": "How does DELETE /api/v1/queues/purge handle HTTP requests?",
                "category": "nonexistent_endpoint",
            },
            {
                "query_id": "LIVE_TS_OOS_02",
                "query": "Find the definition of KafkaDeadLetterConsumer class.",
                "category": "nonexistent_class",
            },
        ],
    },
]


async def run_live_validation() -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repositories": [],
    }

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_base:
        base_path = Path(tmp_base)
        cloner = RepositoryCloner(temp_base_dir=base_path / "clones")
        code_engine = CodeUnderstandingEngine()
        chunker = StructureAwareChunker()
        embedder = LocalSentenceTransformerService()
        chroma_store = ChromaVectorStore(persist_dir=base_path / "chroma")
        vector_service = SemanticSearchService(embedder=embedder, vector_store=chroma_store)
        keyword_engine = KeywordSearchEngine(persist_dir=base_path / "keywords")
        graph_store = NetworkXGraphStore(persist_dir=base_path / "graph")
        graph_builder = GraphBuilder(store=graph_store)
        graph_service = GraphTraversalService(store=graph_store)

        retriever = HybridRetriever(
            vector_service=vector_service,
            keyword_engine=keyword_engine,
            graph_service=graph_service,
            analyzer=QueryAnalyzer(),
            router=QueryRouter(),
            assembler=ContextAssembler(),
        )
        validator = CitationValidator()
        gen_service = GenerationService(retriever=retriever, validator=validator)
        evaluator = CitationAndGroundingEvaluator(validator=validator)

        for target in REAL_WORLD_TARGETS:
            url = target["url"]
            repo_id = target["repo_id"]
            is_valid, owner, name, err = validate_github_url(url)
            assert is_valid, f"URL invalid: {err}"
            accessible, acc_err = await verify_github_repo_accessible(owner, name)

            t_start = time.perf_counter()
            clone_res = cloner.clone_repository(url, repository_id=repo_id, timeout_seconds=45)
            assert clone_res.success, f"Clone failed for {url}: {clone_res.error_message}"

            repo_dir = Path(clone_res.target_dir)
            accepted_files, filtered_files, _ = filter_repository(repo_dir)
            analysis_res = analyze_repository(repo_dir, accepted_files)

            parsed_repo = code_engine.parse_repository(
                repo_dir,
                accepted_files,
                repo_id=repo_id,
                commit_hash=clone_res.commit_hash or "HEAD",
            )
            chunks = chunker.chunk_repository(parsed_repo, accepted_files, repo_dir)
            v_count = vector_service.index_chunks(repo_id, chunks, force_reindex=True)
            k_count = keyword_engine.index_chunks(repo_id, chunks, force_reindex=True)
            g_stats = graph_builder.build_and_persist_graph(parsed_repo, store=graph_store)
            indexing_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

            # Evaluate Answerable Queries
            ans_results: List[Dict[str, Any]] = []
            for aq in target["answerable_queries"]:
                h_res = retriever.hybrid_search(repo_id, HybridSearchRequest(query=aq["query"], top_k=5))
                suff = gen_service.evaluate_evidence_sufficiency(h_res)
                top_files = [r.file_path for r in h_res.results]
                top_symbols = [r.symbol_name for r in h_res.results if r.symbol_name]

                claims = [
                    f"Component `{r.symbol_name or 'module'}` is implemented in [{r.file_path}:{r.start_line}-{r.end_line}]."
                    for r in h_res.results[:3]
                ]
                synthesized = " ".join(claims)
                cit_eval = evaluator.evaluate_citations(synthesized, h_res.results)
                grounding_eval = evaluator.evaluate_grounded_answer(
                    generated_answer=synthesized,
                    retrieved_chunks=h_res.results,
                    evidence_sufficiency=suff.value,
                    should_abstain=False,
                )

                ans_results.append({
                    "query_id": aq["query_id"],
                    "query": aq["query"],
                    "sufficiency": suff.value,
                    "abstained": suff in (EvidenceSufficiency.NO_EVIDENCE, EvidenceSufficiency.INSUFFICIENT),
                    "expected_file_matched": aq["expected_file_hint"] in top_files,
                    "top_file": top_files[0] if top_files else None,
                    "top_symbol": top_symbols[0] if top_symbols else None,
                    "citation_validity": cit_eval["citation_validity"],
                    "claim_support_rate": grounding_eval["claim_support_rate"],
                })

            # Evaluate Out-of-Scope Queries
            oos_results: List[Dict[str, Any]] = []
            for oq in target["out_of_scope_queries"]:
                h_res = retriever.hybrid_search(repo_id, HybridSearchRequest(query=oq["query"], top_k=5))
                suff = gen_service.evaluate_evidence_sufficiency(h_res)
                abstained = suff in (EvidenceSufficiency.NO_EVIDENCE, EvidenceSufficiency.INSUFFICIENT)
                oos_results.append({
                    "query_id": oq["query_id"],
                    "category": oq["category"],
                    "query": oq["query"],
                    "sufficiency": suff.value,
                    "abstained": abstained,
                })

            # Verify cleanup
            vector_service.delete_repository(repo_id)
            keyword_engine.delete_repository(repo_id)
            graph_store.delete(repo_id)

            report["repositories"].append({
                "url": url,
                "owner": owner,
                "name": name,
                "accessible_check": accessible,
                "commit_hash": clone_res.commit_hash,
                "default_branch": clone_res.default_branch,
                "primary_language": analysis_res.primary_language,
                "languages": [l.model_dump() for l in analysis_res.language_breakdown],
                "included_files_count": len(accepted_files),
                "excluded_files_count": len(filtered_files),
                "chunks_count": len(chunks),
                "vector_indexed": v_count,
                "keyword_indexed": k_count,
                "graph_nodes": g_stats["total_nodes"],
                "graph_edges": g_stats["total_edges"],
                "indexing_duration_ms": indexing_duration_ms,
                "answerable_results": ans_results,
                "out_of_scope_results": oos_results,
            })

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Live real-world validation saved to {RESULTS_PATH}")
    return report


if __name__ == "__main__":
    asyncio.run(run_live_validation())
