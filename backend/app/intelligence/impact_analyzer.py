"""
Change Impact Analyzer (Phase 8).
Performs bounded, cycle-safe graph traversal to detect multi-file consequences of code modifications.
Categorizes affected entities into DIRECT, INDIRECT, STRUCTURAL, and POTENTIAL impacts,
determines file blast radius, calculates risk, and provides grounded explanations.
"""

import logging
from collections import deque
from typing import Dict, Any, List, Optional, Set, Tuple

from backend.app.graph.interfaces import (
    BaseGraphStore,
    GraphNode,
    GraphEdge,
    NodeType,
    RelationshipType,
)
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.intelligence.intelligence_models import (
    ImpactCategory,
    AffectedEntity,
    ImpactAnalysisRequest,
    ImpactAnalysisResult,
    create_evidence_chunk,
)
from backend.app.intelligence.risk_assessor import RiskAssessor, risk_assessor
from backend.app.llm.gemini_client import GeminiClient, gemini_client
from backend.app.llm.citation_validator import CitationValidator
from backend.app.retrieval.retrieval_models import UnifiedSearchResult, GraphEvidence

logger = logging.getLogger(__name__)


class ChangeImpactAnalyzer:
    """
    Evaluates multi-file code change impacts using the repository knowledge graph.
    """

    def __init__(
        self,
        store: Optional[BaseGraphStore] = None,
        assessor: Optional[RiskAssessor] = None,
        llm: Optional[GeminiClient] = None,
        validator: Optional[CitationValidator] = None,
    ):
        self.store = store or networkx_graph_store
        self.assessor = assessor or risk_assessor
        self.llm = llm or gemini_client
        self.validator = validator or CitationValidator()

    def _resolve_target(
        self, repository_id: str, symbol_query: str, file_path: Optional[str] = None
    ) -> Optional[GraphNode]:
        """Resolves target node by ID, exact name + file_path, or general search."""
        # 1. Exact node ID match
        node = self.store.get_node(symbol_query, repository_id)
        if node:
            return node

        # 2. File node match
        if symbol_query.endswith((".py", ".ts", ".js", ".go", ".java", ".cpp", ".rs")):
            file_node_id = f"file:{repository_id}:{symbol_query}"
            node = self.store.get_node(file_node_id, repository_id)
            if node:
                return node

        # 3. Query matching symbols
        nodes = self.store.get_nodes(repository_id, query=symbol_query, limit=20)
        if not nodes:
            return None

        # Filter by file_path if provided
        if file_path:
            norm_target_path = file_path.replace("\\", "/").lower()
            matching_path = [
                n for n in nodes
                if n.file_path and norm_target_path in n.file_path.replace("\\", "/").lower()
            ]
            if matching_path:
                nodes = matching_path

        # Prioritize exact name match
        for n in nodes:
            if n.name == symbol_query or n.qualified_name == symbol_query:
                return n

        return nodes[0] if nodes else None

    async def analyze(
        self,
        repository_id: str,
        request: ImpactAnalysisRequest,
    ) -> ImpactAnalysisResult:
        """
        Executes bounded, cycle-safe impact analysis for a target symbol or file.
        """
        target = self._resolve_target(repository_id, request.target_symbol, request.file_path)

        if not target:
            return ImpactAnalysisResult(
                target_symbol=request.target_symbol,
                target_file=request.file_path,
                explanation=f"Target symbol or file '{request.target_symbol}' could not be located in repository knowledge graph.",
                limitations=["Target symbol not found in AST index."],
            )

        target_file = target.file_path or request.file_path or ""
        max_depth = request.max_depth

        direct_entities: List[AffectedEntity] = []
        indirect_entities: List[AffectedEntity] = []
        structural_entities: List[AffectedEntity] = []
        potential_entities: List[AffectedEntity] = []

        visited: Set[str] = {target.id}
        affected_files_set: Set[str] = set()
        if target_file:
            affected_files_set.add(target_file)

        unresolved_count = 0

        # Step 1: Structural relationships (enclosing class/file, methods within class, inheritance)
        structural_edges = self.store.get_edges(repository_id, source_id=target.id, limit=200)
        structural_edges += self.store.get_edges(repository_id, target_id=target.id, limit=200)

        for edge in structural_edges:
            other_id = edge.source_id if edge.target_id == target.id else edge.target_id
            if other_id in visited:
                continue

            if edge.relationship in (RelationshipType.CONTAINS, RelationshipType.INHERITS, RelationshipType.IMPLEMENTS):
                other_node = self.store.get_node(other_id, repository_id)
                if other_node:
                    visited.add(other_id)
                    rel_desc = (
                        f"inherits from {target.name}" if edge.relationship == RelationshipType.INHERITS
                        else f"contained in / contains {target.name}"
                    )
                    entity = AffectedEntity(
                        symbol_id=other_node.id,
                        name=other_node.name,
                        type=other_node.type.value if hasattr(other_node.type, 'value') else str(other_node.type),
                        file_path=other_node.file_path or target_file,
                        start_line=other_node.start_line,
                        end_line=other_node.end_line,
                        category=ImpactCategory.STRUCTURAL,
                        relationship_path=[rel_desc],
                        depth=1,
                        confidence=edge.confidence,
                        resolution_status=edge.resolution_status,
                    )
                    structural_entities.append(entity)
                    if other_node.file_path:
                        affected_files_set.add(other_node.file_path)

        # Step 2: Inbound Callers & Dependents Traversal (BFS)
        # Queue item: (node_id, current_depth, path_names)
        queue = deque([(target.id, 0, [target.name])])

        while queue:
            curr_id, curr_depth, path = queue.popleft()

            if curr_depth >= max_depth:
                continue

            # Find all incoming edges (who calls or imports curr_id)
            in_edges = self.store.get_edges(repository_id, target_id=curr_id, limit=300)

            for edge in in_edges:
                if edge.resolution_status == "UNRESOLVED":
                    unresolved_count += 1

                source_id = edge.source_id
                source_node = self.store.get_node(source_id, repository_id)

                is_new = source_id not in visited
                if is_new:
                    visited.add(source_id)

                source_name = source_node.name if source_node else source_id.split(":")[-1]
                source_path = source_node.file_path if source_node else ""
                if source_path:
                    affected_files_set.add(source_path)

                step_depth = curr_depth + 1
                rel_path = path + [source_name]

                # Determine category
                if edge.relationship == RelationshipType.CALLS:
                    category = ImpactCategory.DIRECT if step_depth == 1 else ImpactCategory.INDIRECT
                elif edge.relationship in (RelationshipType.IMPORTS, RelationshipType.DEPENDS_ON):
                    category = ImpactCategory.DIRECT if step_depth == 1 else ImpactCategory.INDIRECT
                else:
                    category = ImpactCategory.STRUCTURAL

                # If edge is inferred/unresolved, classify as POTENTIAL if low confidence
                if edge.resolution_status == "UNRESOLVED" or edge.confidence < 0.7:
                    category = ImpactCategory.POTENTIAL

                entity = AffectedEntity(
                    symbol_id=source_id,
                    name=source_name,
                    type=source_node.type.value if source_node and hasattr(source_node.type, 'value') else "Function",
                    file_path=source_path,
                    start_line=source_node.start_line if source_node else None,
                    end_line=source_node.end_line if source_node else None,
                    category=category,
                    relationship_path=rel_path,
                    depth=step_depth,
                    confidence=edge.confidence,
                    resolution_status=edge.resolution_status,
                )

                if category == ImpactCategory.DIRECT:
                    direct_entities.append(entity)
                elif category == ImpactCategory.INDIRECT:
                    indirect_entities.append(entity)
                elif category == ImpactCategory.POTENTIAL:
                    potential_entities.append(entity)
                else:
                    structural_entities.append(entity)

                # Continue BFS traversal for incoming callers/dependents
                if is_new and step_depth < max_depth:
                    queue.append((source_id, step_depth, rel_path))

        all_affected = direct_entities + indirect_entities + structural_entities + potential_entities
        affected_files_list = sorted(list(affected_files_set))

        # Step 3: Deterministic Risk Assessment
        risk_res = self.assessor.calculate_risk(
            target_name=target.name,
            target_file=target_file,
            direct_entities=direct_entities,
            indirect_entities=indirect_entities,
            affected_files=affected_files_list,
            unresolved_count=unresolved_count,
            target_node=target,
        )

        # Step 4: Grounded Explanation & LLM Synthesis
        explanation, citations = await self._generate_explanation(
            target=target,
            target_file=target_file,
            direct=direct_entities,
            indirect=indirect_entities,
            structural=structural_entities,
            potential=potential_entities,
            affected_files=affected_files_list,
            risk_res=risk_res,
        )

        limitations = [
            "Static call graph analysis identifies AST-reachable dependencies; dynamic dispatch, reflection, or monkeypatching are not guaranteed.",
            "Cross-repository external package dependents are not analyzed unless indexed locally.",
            "Runtime conditional branching may bypass certain theoretical execution paths."
        ]

        return ImpactAnalysisResult(
            target_symbol=target.name,
            target_file=target_file,
            direct_count=len(direct_entities),
            indirect_count=len(indirect_entities),
            structural_count=len(structural_entities),
            potential_count=len(potential_entities),
            total_affected_symbols=len(all_affected),
            total_affected_files=len(affected_files_list),
            affected_files=affected_files_list,
            affected_entities=all_affected,
            risk_score=risk_res.risk_score,
            risk_level=risk_res.risk_level,
            explanation=explanation,
            citations=citations,
            limitations=limitations,
        )

    async def _generate_explanation(
        self,
        target: GraphNode,
        target_file: str,
        direct: List[AffectedEntity],
        indirect: List[AffectedEntity],
        structural: List[AffectedEntity],
        potential: List[AffectedEntity],
        affected_files: List[str],
        risk_res: Any,
    ) -> Tuple[str, List[Any]]:
        """Synthesizes structured explanation with inline citations."""
        evidence_chunks: List[UnifiedSearchResult] = []

        # Target snippet citation evidence
        if target_file and target.start_line:
            evidence_chunks.append(create_evidence_chunk(
                chunk_id=f"target_{target.id}",
                repository_id=target.repository_id or "repo",
                file_path=target_file,
                start_line=target.start_line,
                end_line=target.end_line or (target.start_line + 10),
                content=f"// Symbol: {target.name} ({target.type.value if hasattr(target.type, 'value') else target.type})",
                symbol_name=target.name,
                symbol_type=target.type.value if hasattr(target.type, 'value') else str(target.type),
                score=1.0,
            ))

        for e in (direct + indirect)[:10]:
            if e.file_path and e.start_line:
                evidence_chunks.append(create_evidence_chunk(
                    chunk_id=f"aff_{e.symbol_id}",
                    repository_id="repo",
                    file_path=e.file_path,
                    start_line=e.start_line,
                    end_line=e.end_line or (e.start_line + 5),
                    content=f"// Dependent: {e.name} calls/imports target",
                    symbol_name=e.name,
                    symbol_type=e.type,
                    score=0.9,
                ))

        # Default static grounded explanation
        target_line_str = f":{target.start_line}-{target.end_line}" if target.start_line and target.end_line else ""
        target_citation = f"[{target_file}{target_line_str}]" if target_file else target.name

        lines = [
            f"### Change Impact Analysis: `{target.name}`",
            "",
            f"Modifying `{target.name}` in {target_citation} carries a **{risk_res.risk_level}** change risk (Score: **{risk_res.risk_score:.1f}/100**).",
            f"The blast radius spans **{len(affected_files)} file(s)** and **{len(direct) + len(indirect) + len(structural)} symbol(s)**.",
            "",
            "#### Direct Dependents",
        ]

        if direct:
            for d in direct[:5]:
                d_line = f":{d.start_line}-{d.end_line}" if d.start_line and d.end_line else ""
                lines.append(f"- `{d.name}` ({d.type}) in [{d.file_path}{d_line}] via `{' -> '.join(d.relationship_path)}`")
            if len(direct) > 5:
                lines.append(f"- *...and {len(direct) - 5} additional direct caller(s).*")
        else:
            lines.append("- No direct inbound callers or importers detected in the repository.")

        if indirect:
            lines.append("")
            lines.append("#### Indirect (Multi-Hop) Propagation")
            for ind in indirect[:4]:
                i_line = f":{ind.start_line}-{ind.end_line}" if ind.start_line and ind.end_line else ""
                lines.append(f"- `{ind.name}` (depth {ind.depth}) in [{ind.file_path}{i_line}] via `{' -> '.join(ind.relationship_path)}`")
            if len(indirect) > 4:
                lines.append(f"- *...and {len(indirect) - 4} additional transitive dependent(s).*")

        if structural:
            lines.append("")
            lines.append("#### Structural Context")
            for st in structural[:3]:
                s_line = f":{st.start_line}-{st.end_line}" if st.start_line and st.end_line else ""
                lines.append(f"- `{st.name}` ({st.type}) in [{st.file_path}{s_line}]")

        static_text = "\n".join(lines)

        # Validate citations against evidence
        citations = self.validator.validate_citations(
            generated_text=static_text,
            retrieved_chunks=evidence_chunks,
            include_unverified=True,
        )

        return static_text, citations


change_impact_analyzer = ChangeImpactAnalyzer()
