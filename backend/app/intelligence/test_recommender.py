"""
Evidence-Backed Test Recommender (Phase 8).
Discovers existing repository tests, maps target symbol callers and dependents,
and generates structured unit, integration, and regression test recommendations.
"""

import logging
from typing import Dict, Any, List, Optional, Set

from backend.app.graph.interfaces import (
    BaseGraphStore,
    GraphNode,
    RelationshipType,
    NodeType,
)
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.intelligence.intelligence_models import (
    TestType,
    TestRecommendation,
    TestRecommendationsRequest,
    TestRecommendationsResult,
    create_evidence_chunk,
)
from backend.app.llm.citation_validator import CitationValidator
from backend.app.retrieval.retrieval_models import UnifiedSearchResult

logger = logging.getLogger(__name__)


class TestRecommender:
    """
    Synthesizes targeted test plans and test assertions based on graph relationships.
    """

    def __init__(
        self,
        store: Optional[BaseGraphStore] = None,
        validator: Optional[CitationValidator] = None,
    ):
        self.store = store or networkx_graph_store
        self.validator = validator or CitationValidator()

    def _discover_existing_tests(self, repository_id: str) -> List[str]:
        """Scans the repository knowledge graph for test files."""
        nodes = self.store.get_nodes(repository_id, limit=2000)
        test_files: Set[str] = set()

        for n in nodes:
            if n.file_path:
                p = n.file_path.lower().replace("\\", "/")
                if "test" in p or "spec" in p:
                    test_files.add(n.file_path.replace("\\", "/"))

        return sorted(list(test_files))

    async def recommend(
        self,
        repository_id: str,
        request: TestRecommendationsRequest,
    ) -> TestRecommendationsResult:
        """
        Recommends unit, integration, and regression tests for a target symbol.
        """
        existing_tests = self._discover_existing_tests(repository_id)

        # Resolve target symbol
        target_nodes = self.store.get_nodes(repository_id, query=request.target_symbol, limit=10)
        target_node = None
        for n in target_nodes:
            if n.name == request.target_symbol:
                target_node = n
                break
        if not target_node and target_nodes:
            target_node = target_nodes[0]

        target_file = (target_node.file_path if target_node and target_node.file_path else request.file_path) or "unknown"
        target_name = target_node.name if target_node else request.target_symbol

        recommendations: List[TestRecommendation] = []
        rec_counter = 1
        evidence_chunks: List[UnifiedSearchResult] = []

        if target_node and target_node.file_path and target_node.start_line:
            evidence_chunks.append(create_evidence_chunk(
                chunk_id=f"target_{target_node.id}",
                repository_id=target_node.repository_id or "repo",
                file_path=target_node.file_path,
                start_line=target_node.start_line,
                end_line=target_node.end_line or (target_node.start_line + 5),
                content=f"// Target symbol: {target_node.name}",
                symbol_name=target_node.name,
                symbol_type=target_node.type.value if hasattr(target_node.type, 'value') else str(target_node.type),
                score=1.0,
            ))

        # Check existing matching test
        matched_existing_test = None
        for t in existing_tests:
            if target_name.lower() in t.lower() or (target_node and target_node.file_path and target_node.file_path.split("/")[-1].replace(".py", "") in t):
                matched_existing_test = t
                break

        # 1. UNIT Test Recommendations for Target
        recommendations.append(TestRecommendation(
            recommendation_id=f"REC-{rec_counter:03d}",
            category=TestType.UNIT,
            target_symbol=target_name,
            file_path=target_file,
            reason=f"Verify direct input-output contract, boundary conditions, and error handling for `{target_name}`.",
            suggested_assertions=[
                f"Verify `{target_name}` returns expected output given valid inputs.",
                f"Assert `{target_name}` raises ValueError/TypeError when receiving null or invalid arguments.",
                f"Verify return types conform to schema definitions."
            ],
            existing_test_reference=matched_existing_test,
            priority="HIGH",
        ))
        rec_counter += 1

        # 2. INTEGRATION Test Recommendations for Direct Callers & Callees
        if target_node:
            caller_edges = self.store.get_edges(
                repository_id,
                relationship=RelationshipType.CALLS,
                target_id=target_node.id,
                limit=5,
            )

            for edge in caller_edges:
                caller_node = self.store.get_node(edge.source_id, repository_id)
                caller_name = caller_node.name if caller_node else edge.source_id.split(":")[-1]
                caller_file = (caller_node.file_path if caller_node and caller_node.file_path else target_file) or "unknown"

                recommendations.append(TestRecommendation(
                    recommendation_id=f"REC-{rec_counter:03d}",
                    category=TestType.INTEGRATION,
                    target_symbol=caller_name,
                    file_path=caller_file,
                    reason=f"`{caller_name}` directly invokes `{target_name}`. Validate that parameter handoff and exception bubbling work across files.",
                    suggested_assertions=[
                        f"Test end-to-end invocation of `{caller_name}` invoking `{target_name}`.",
                        f"Ensure error states from `{target_name}` are gracefully handled in `{caller_name}`."
                    ],
                    existing_test_reference=matched_existing_test,
                    priority="HIGH",
                ))
                rec_counter += 1

                if caller_node and caller_node.file_path and caller_node.start_line:
                    evidence_chunks.append(create_evidence_chunk(
                        chunk_id=f"caller_{caller_node.id}",
                        repository_id=caller_node.repository_id or "repo",
                        file_path=caller_node.file_path,
                        start_line=caller_node.start_line,
                        end_line=caller_node.end_line or (caller_node.start_line + 5),
                        content=f"// Caller: {caller_node.name}",
                        symbol_name=caller_node.name,
                        symbol_type=caller_node.type.value if hasattr(caller_node.type, 'value') else str(caller_node.type),
                        score=0.9,
                    ))

            # 3. REGRESSION Test Recommendations
            out_edges = self.store.get_edges(
                repository_id,
                relationship=RelationshipType.CALLS,
                source_id=target_node.id,
                limit=3,
            )
            for edge in out_edges:
                callee_node = self.store.get_node(edge.target_id, repository_id)
                callee_name = callee_node.name if callee_node else edge.target_id.split(":")[-1]
                callee_file = (callee_node.file_path if callee_node and callee_node.file_path else target_file) or "unknown"

                recommendations.append(TestRecommendation(
                    recommendation_id=f"REC-{rec_counter:03d}",
                    category=TestType.REGRESSION,
                    target_symbol=callee_name,
                    file_path=callee_file,
                    reason=f"`{target_name}` depends on downstream callee `{callee_name}`. Verify downstream state regressions.",
                    suggested_assertions=[
                        f"Assert that changes to `{target_name}` do not mutate arguments passed to `{callee_name}`.",
                        f"Verify downstream side effects remain idempotent."
                    ],
                    existing_test_reference=None,
                    priority="MEDIUM",
                ))
                rec_counter += 1

        # Summary text
        lines = [
            f"### Test Recommendations for `{target_name}`",
            "",
            f"Target file: [{target_file}:{target_node.start_line if target_node else 1}]" if target_file else f"Target: `{target_name}`",
            f"Discovered **{len(existing_tests)} existing test file(s)** in repository.",
            f"Generated **{len(recommendations)} recommended test scenario(s)**.",
            "",
        ]

        for r in recommendations:
            lines.append(f"#### [{r.category.value}] {r.recommendation_id}: Test `{r.target_symbol}` ({r.priority} Priority)")
            lines.append(f"- **File**: [{r.file_path}]")
            lines.append(f"- **Rationale**: {r.reason}")
            lines.append("- **Suggested Assertions**:")
            for a in r.suggested_assertions:
                lines.append(f"  - {a}")
            if r.existing_test_reference:
                lines.append(f"- **Existing Test Reference**: [{r.existing_test_reference}]")
            lines.append("")

        summary_text = "\n".join(lines)
        citations = self.validator.validate_citations(
            generated_text=summary_text,
            retrieved_chunks=evidence_chunks,
            include_unverified=True,
        )

        return TestRecommendationsResult(
            target_symbol=target_name,
            existing_tests_found=existing_tests[:10],
            recommendations=recommendations,
            total_recommendations=len(recommendations),
            summary=summary_text,
            citations=citations,
        )


test_recommender = TestRecommender()
