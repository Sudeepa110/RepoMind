"""
Cross-File Execution Flow Tracer (Phase 8).
Traces ordered static invocation flows from an entry point symbol across file boundaries,
identifying branches, external dependencies, and execution sequences with verified citations.
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import deque

from backend.app.graph.interfaces import (
    BaseGraphStore,
    GraphNode,
    RelationshipType,
    NodeType,
)
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.intelligence.intelligence_models import (
    ExecutionFlowStep,
    ExecutionFlowRequest,
    ExecutionFlowResult,
    create_evidence_chunk,
)
from backend.app.llm.citation_validator import CitationValidator
from backend.app.retrieval.retrieval_models import UnifiedSearchResult

logger = logging.getLogger(__name__)


class ExecutionFlowTracer:
    """
    Traces invocation chains across files starting from a designated entry point.
    """

    def __init__(
        self,
        store: Optional[BaseGraphStore] = None,
        validator: Optional[CitationValidator] = None,
    ):
        self.store = store or networkx_graph_store
        self.validator = validator or CitationValidator()

    def _resolve_entry_node(
        self, repository_id: str, query: str, file_path: Optional[str] = None
    ) -> Optional[GraphNode]:
        """Resolves the initial entry point symbol."""
        # Exact ID match
        node = self.store.get_node(query, repository_id)
        if node:
            return node

        nodes = self.store.get_nodes(repository_id, query=query, limit=20)
        if not nodes:
            return None

        if file_path:
            norm = file_path.replace("\\", "/").lower()
            filtered = [n for n in nodes if n.file_path and norm in n.file_path.replace("\\", "/").lower()]
            if filtered:
                nodes = filtered

        for n in nodes:
            if n.name == query or n.qualified_name == query:
                return n

        return nodes[0] if nodes else None

    async def trace_flow(
        self,
        repository_id: str,
        request: ExecutionFlowRequest,
    ) -> ExecutionFlowResult:
        """
        Traces execution sequence from entry_point across files.
        """
        entry_node = self._resolve_entry_node(repository_id, request.entry_point, request.file_path)

        if not entry_node:
            return ExecutionFlowResult(
                entry_point=request.entry_point,
                target_symbol=request.target_symbol,
                explanation=f"Entry point symbol '{request.entry_point}' could not be resolved in the repository.",
                limitations=["Entry point not found in AST index."],
            )

        steps: List[ExecutionFlowStep] = []
        involved_files: Set[str] = set()
        if entry_node.file_path:
            involved_files.add(entry_node.file_path)

        unresolved_count = 0
        cross_file_count = 0

        # Step 0: Entry point
        steps.append(ExecutionFlowStep(
            step_index=1,
            symbol_name=entry_node.name,
            symbol_type=entry_node.type.value if hasattr(entry_node.type, 'value') else str(entry_node.type),
            file_path=entry_node.file_path or "",
            start_line=entry_node.start_line,
            end_line=entry_node.end_line,
            caller_symbol=None,
            depth=0,
            crosses_file=False,
            is_external=False,
            is_branch_point=False,
            confidence=1.0,
            resolution_status="CONFIRMED",
        ))

        # Check if targeted path search was requested
        target_node = None
        if request.target_symbol:
            target_node = self._resolve_entry_node(repository_id, request.target_symbol)

        if target_node:
            # Path exploration between source and target
            paths = self.store.find_paths(
                entry_node.id, target_node.id, max_depth=request.max_depth, limit=3
            )
            if paths:
                primary_path = paths[0]
                prev_node = entry_node
                step_idx = 2
                for nid in primary_path[1:]:
                    node = self.store.get_node(nid, repository_id)
                    node_name = node.name if node else nid.split(":")[-1]
                    node_path = node.file_path if node else ""
                    if node_path:
                        involved_files.add(node_path)

                    crosses = bool(node_path and prev_node.file_path and node_path != prev_node.file_path)
                    if crosses:
                        cross_file_count += 1

                    steps.append(ExecutionFlowStep(
                        step_index=step_idx,
                        symbol_name=node_name,
                        symbol_type=node.type.value if node and hasattr(node.type, 'value') else "Function",
                        file_path=node_path,
                        start_line=node.start_line if node else None,
                        end_line=node.end_line if node else None,
                        caller_symbol=prev_node.name,
                        depth=step_idx - 1,
                        crosses_file=crosses,
                        is_external=node is None or nid.startswith("ext:"),
                        is_branch_point=False,
                        confidence=1.0,
                        resolution_status="CONFIRMED" if node else "INFERRED",
                    ))
                    if node:
                        prev_node = node
                    step_idx += 1
        else:
            # Forward BFS call tracing
            visited: Set[str] = {entry_node.id}
            # Queue item: (node_id, current_node, depth)
            queue = deque([(entry_node.id, entry_node, 0)])
            step_idx = 2

            while queue and step_idx <= 25:
                curr_id, curr_node, curr_depth = queue.popleft()

                if curr_depth >= request.max_depth:
                    continue

                out_edges = self.store.get_edges(
                    repository_id,
                    source_id=curr_id,
                    relationship=RelationshipType.CALLS,
                    limit=20,
                )

                is_branch = len(out_edges) > 1
                if steps and steps[-1].symbol_name == curr_node.name:
                    steps[-1].is_branch_point = is_branch

                for edge in out_edges:
                    target_id = edge.target_id
                    callee_node = self.store.get_node(target_id, repository_id)

                    if edge.resolution_status == "UNRESOLVED":
                        unresolved_count += 1

                    is_external = callee_node is None or target_id.startswith("ext:")
                    callee_name = callee_node.name if callee_node else target_id.split(":")[-1]
                    callee_path = callee_node.file_path if callee_node else ""

                    if callee_path:
                        involved_files.add(callee_path)

                    crosses = bool(callee_path and curr_node.file_path and callee_path != curr_node.file_path)
                    if crosses:
                        cross_file_count += 1

                    steps.append(ExecutionFlowStep(
                        step_index=step_idx,
                        symbol_name=callee_name,
                        symbol_type=callee_node.type.value if callee_node and hasattr(callee_node.type, 'value') else "Function",
                        file_path=callee_path,
                        start_line=callee_node.start_line if callee_node else None,
                        end_line=callee_node.end_line if callee_node else None,
                        caller_symbol=curr_node.name,
                        depth=curr_depth + 1,
                        crosses_file=crosses,
                        is_external=is_external,
                        is_branch_point=False,
                        confidence=edge.confidence,
                        resolution_status=edge.resolution_status,
                    ))
                    step_idx += 1

                    if target_id not in visited and curr_depth + 1 < request.max_depth:
                        visited.add(target_id)
                        if callee_node:
                            queue.append((target_id, callee_node, curr_depth + 1))

        # Generate Grounded Explanation
        explanation, citations = self._format_explanation(
            entry_node=entry_node,
            target_symbol=request.target_symbol,
            steps=steps,
            cross_file_count=cross_file_count,
            involved_files=sorted(list(involved_files)),
        )

        limitations = [
            "Execution paths are derived statically from AST call graphs.",
            "Conditional branches (if/else), polymorphism, and dynamic callbacks may alter actual runtime paths.",
            "External framework lifecycle invocations (e.g. middleware, decorators) may precede the entry point."
        ]

        return ExecutionFlowResult(
            entry_point=entry_node.name,
            target_symbol=request.target_symbol,
            total_steps=len(steps),
            cross_file_count=cross_file_count,
            unresolved_calls=unresolved_count,
            steps=steps,
            involved_files=sorted(list(involved_files)),
            explanation=explanation,
            citations=citations,
            limitations=limitations,
        )

    def _format_explanation(
        self,
        entry_node: GraphNode,
        target_symbol: Optional[str],
        steps: List[ExecutionFlowStep],
        cross_file_count: int,
        involved_files: List[str],
    ) -> Tuple[str, List[Any]]:
        evidence_chunks: List[UnifiedSearchResult] = []

        lines = [
            f"### Execution Flow Trace: `{entry_node.name}`",
            "",
            f"Static call trace originates at `{entry_node.name}` in [{entry_node.file_path}:{entry_node.start_line}-{entry_node.end_line}] "
            f"and traverses **{len(steps)} step(s)** across **{len(involved_files)} file(s)** with **{cross_file_count} cross-file transition(s)**.",
            "",
            "#### Trace Sequence",
        ]

        if entry_node.file_path and entry_node.start_line:
            evidence_chunks.append(create_evidence_chunk(
                chunk_id=f"entry_{entry_node.id}",
                repository_id=entry_node.repository_id or "repo",
                file_path=entry_node.file_path,
                start_line=entry_node.start_line,
                end_line=entry_node.end_line or (entry_node.start_line + 5),
                content=f"// Entry point: {entry_node.name}",
                symbol_name=entry_node.name,
                symbol_type=entry_node.type.value if hasattr(entry_node.type, 'value') else str(entry_node.type),
                score=1.0,
            ))

        for step in steps:
            loc_str = f" in [{step.file_path}:{step.start_line}-{step.end_line}]" if step.file_path and step.start_line else ""
            boundary_tag = " *(crosses file boundary)*" if step.crosses_file else ""
            ext_tag = " *(external/library)*" if step.is_external else ""
            caller_str = f" (called by `{step.caller_symbol}`)" if step.caller_symbol else " (Entry Point)"

            lines.append(f"{step.step_index}. **`{step.symbol_name}`**{caller_str}{loc_str}{boundary_tag}{ext_tag}")

            if step.file_path and step.start_line:
                evidence_chunks.append(create_evidence_chunk(
                    chunk_id=f"step_{step.step_index}",
                    repository_id="repo",
                    file_path=step.file_path,
                    start_line=step.start_line,
                    end_line=step.end_line or (step.start_line + 5),
                    content=f"// Step {step.step_index}: {step.symbol_name}",
                    symbol_name=step.symbol_name,
                    symbol_type=step.symbol_type,
                    score=0.9,
                ))

        static_text = "\n".join(lines)
        citations = self.validator.validate_citations(
            generated_text=static_text,
            retrieved_chunks=evidence_chunks,
            include_unverified=True,
        )

        return static_text, citations


execution_flow_tracer = ExecutionFlowTracer()
