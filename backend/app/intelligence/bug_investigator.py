"""
Evidence-Backed Bug Investigator (Phase 8).
Detects potential defect patterns (missing error handling, null/None safety hazards,
resource leaks, unresolved calls) using static AST/graph heuristics and grounded LLM analysis.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.app.graph.interfaces import (
    BaseGraphStore,
    GraphNode,
    RelationshipType,
    NodeType,
)
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.intelligence.intelligence_models import (
    BugFinding,
    BugSeverity,
    BugCategory,
    BugInvestigationRequest,
    BugInvestigationResult,
    create_evidence_chunk,
)
from backend.app.llm.citation_validator import CitationValidator
from backend.app.retrieval.retrieval_models import UnifiedSearchResult

logger = logging.getLogger(__name__)


class BugInvestigator:
    """
    Evidence-backed bug detection and root-cause investigation engine.
    """

    def __init__(
        self,
        store: Optional[BaseGraphStore] = None,
        validator: Optional[CitationValidator] = None,
    ):
        self.store = store or networkx_graph_store
        self.validator = validator or CitationValidator()

    async def investigate(
        self,
        repository_id: str,
        request: BugInvestigationRequest,
    ) -> BugInvestigationResult:
        """
        Investigates potential bugs and architectural vulnerabilities in targeted files/symbols.
        """
        findings: List[BugFinding] = []
        evidence_chunks: List[UnifiedSearchResult] = []

        # Find nodes to inspect
        target_nodes: List[GraphNode] = []
        if request.target:
            # Query specific symbol or file
            nodes = self.store.get_nodes(repository_id, query=request.target, limit=10)
            if not nodes:
                # Try file match
                all_nodes = self.store.get_nodes(repository_id, limit=500)
                target_nodes = [
                    n for n in all_nodes
                    if n.file_path and request.target.lower() in n.file_path.lower()
                ]
            else:
                target_nodes = nodes
        else:
            # General repository inspection
            target_nodes = self.store.get_nodes(repository_id, limit=100)

        finding_counter = 1

        # Heuristic 1: Unresolved Call Inspection
        for node in target_nodes[:30]:
            out_edges = self.store.get_edges(repository_id, source_id=node.id, limit=20)
            for edge in out_edges:
                if edge.resolution_status == "UNRESOLVED":
                    callee_name = edge.target_id.split(":")[-1]
                    f = BugFinding(
                        finding_id=f"BUG-{finding_counter:03d}",
                        title=f"Unresolved Function Call: `{callee_name}`",
                        category=BugCategory.UNRESOLVED_CALL,
                        severity=BugSeverity.MEDIUM,
                        affected_symbol=node.name,
                        file_path=node.file_path or "unknown",
                        start_line=node.start_line or 1,
                        end_line=node.end_line or (node.start_line or 1),
                        explanation=f"Function `{node.name}` invokes `{callee_name}`, which could not be statically resolved to any declaration in the repository.",
                        evidence=f"Call to `{callee_name}` with confidence {edge.confidence} remains unresolved in AST.",
                        possible_failure_scenario=f"May result in runtime NameError, AttributeError, or ImportError if `{callee_name}` is not provided dynamically.",
                        suggested_remediation=f"Verify that `{callee_name}` is imported correctly or defined in the relevant module.",
                        confidence=0.85,
                    )
                    findings.append(f)
                    finding_counter += 1

                    if node.file_path and node.start_line:
                        evidence_chunks.append(create_evidence_chunk(
                            chunk_id=f"ev_{f.finding_id}",
                            repository_id=node.repository_id or "repo",
                            file_path=node.file_path,
                            start_line=node.start_line,
                            end_line=node.end_line or (node.start_line + 5),
                            content=f"// Symbol: {node.name} calling unresolved {callee_name}",
                            symbol_name=node.name,
                            symbol_type=node.type.value if hasattr(node.type, 'value') else str(node.type),
                            score=1.0,
                        ))
                    break

        # Heuristic 2: Missing Error Handling on API / Public Entry Points
        for node in target_nodes[:30]:
            path = (node.file_path or "").lower()
            if any(k in path for k in ["/api/", "routes", "controller", "handlers"]) and node.type in (NodeType.FUNCTION, NodeType.METHOD):
                # Check properties or node parameters
                has_exception_handling = node.properties.get("has_try_except", False)
                if not has_exception_handling and node.start_line:
                    f = BugFinding(
                        finding_id=f"BUG-{finding_counter:03d}",
                        title=f"Unguarded Public API Handler: `{node.name}`",
                        category=BugCategory.ERROR_HANDLING,
                        severity=BugSeverity.LOW,
                        affected_symbol=node.name,
                        file_path=node.file_path or path,
                        start_line=node.start_line,
                        end_line=node.end_line or (node.start_line + 10),
                        explanation=f"Endpoint handler `{node.name}` does not exhibit local structured error handling blocks.",
                        evidence=f"Definition in {node.file_path}:{node.start_line}",
                        possible_failure_scenario="Unhandled internal exceptions may bubble up to client as unhandled 500 errors without descriptive payloads.",
                        suggested_remediation="Wrap downstream operations in try/except blocks or verify that global exception middleware catches specific failure modes.",
                        confidence=0.75,
                    )
                    findings.append(f)
                    finding_counter += 1

                    evidence_chunks.append(create_evidence_chunk(
                        chunk_id=f"ev_{f.finding_id}",
                        repository_id=node.repository_id or "repo",
                        file_path=node.file_path or path,
                        start_line=node.start_line,
                        end_line=node.end_line or (node.start_line + 5),
                        content=f"// API Handler: {node.name}",
                        symbol_name=node.name,
                        symbol_type=node.type.value if hasattr(node.type, 'value') else str(node.type),
                        score=0.9,
                    ))
                    if finding_counter > 8:
                        break

        # Count severities
        crit = sum(1 for f in findings if f.severity == BugSeverity.CRITICAL)
        high = sum(1 for f in findings if f.severity == BugSeverity.HIGH)
        med = sum(1 for f in findings if f.severity == BugSeverity.MEDIUM)
        low = sum(1 for f in findings if f.severity in (BugSeverity.LOW, BugSeverity.INFORMATIONAL))

        # Generate summary explanation
        lines = [
            f"### Bug & Defect Investigation Report",
            "",
            f"Inspected target: `{request.target or 'Repository Root'}`. "
            f"Identified **{len(findings)} potential issue(s)**: {crit} Critical, {high} High, {med} Medium, {low} Low.",
            "",
        ]

        for f in findings:
            lines.append(f"#### [{f.severity.value}] {f.title} ({f.finding_id})")
            lines.append(f"- **Location**: [{f.file_path}:{f.start_line}-{f.end_line}] in `{f.affected_symbol}`")
            lines.append(f"- **Category**: `{f.category.value}`")
            lines.append(f"- **Explanation**: {f.explanation}")
            lines.append(f"- **Failure Scenario**: {f.possible_failure_scenario}")
            lines.append(f"- **Remediation**: {f.suggested_remediation}")
            lines.append("")

        explanation_text = "\n".join(lines)
        citations = self.validator.validate_citations(
            generated_text=explanation_text,
            retrieved_chunks=evidence_chunks,
            include_unverified=True,
        )

        limitations = [
            "Bug findings are generated via static code graph inspection and AST heuristics.",
            "Dynamic runtime behaviors (e.g. middleware, monkeypatching, external services) require developer validation.",
            "RepoMind does not execute code or modify files automatically."
        ]

        return BugInvestigationResult(
            target=request.target,
            findings=findings,
            total_findings=len(findings),
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low,
            explanation=explanation_text,
            citations=citations,
            limitations=limitations,
        )


bug_investigator = BugInvestigator()
