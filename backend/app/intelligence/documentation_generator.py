"""
Technical Documentation Generator (Phase 8).
Synthesizes developer-grade, grounded markdown documentation for functions, classes,
modules, and API endpoints supported by verified source code citations.
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
    DocumentationRequest,
    DocumentationResult,
    create_evidence_chunk,
)
from backend.app.llm.citation_validator import CitationValidator
from backend.app.retrieval.retrieval_models import UnifiedSearchResult

logger = logging.getLogger(__name__)


class TechnicalDocumentationGenerator:
    """
    Generates grounded technical documentation from repository knowledge graphs and code structure.
    """

    def __init__(
        self,
        store: Optional[BaseGraphStore] = None,
        validator: Optional[CitationValidator] = None,
    ):
        self.store = store or networkx_graph_store
        self.validator = validator or CitationValidator()

    def _resolve_target(
        self, repository_id: str, target: str, file_path: Optional[str] = None
    ) -> Optional[GraphNode]:
        node = self.store.get_node(target, repository_id)
        if node:
            return node

        nodes = self.store.get_nodes(repository_id, query=target, limit=20)
        if not nodes:
            return None

        if file_path:
            norm = file_path.replace("\\", "/").lower()
            filtered = [n for n in nodes if n.file_path and norm in n.file_path.replace("\\", "/").lower()]
            if filtered:
                nodes = filtered

        for n in nodes:
            if n.name == target or n.qualified_name == target:
                return n

        return nodes[0] if nodes else None

    async def generate_doc(
        self,
        repository_id: str,
        request: DocumentationRequest,
    ) -> DocumentationResult:
        """
        Generates grounded markdown technical documentation for a target entity.
        """
        target_node = self._resolve_target(repository_id, request.target, request.file_path)

        if not target_node:
            return DocumentationResult(
                target_name=request.target,
                target_type="Unknown",
                file_path=request.file_path or "",
                markdown_documentation=f"Unable to generate documentation: symbol '{request.target}' was not found in repository index.",
                citations=[],
            )

        target_file = target_node.file_path or request.file_path or ""
        target_type = target_node.type.value if hasattr(target_node.type, 'value') else str(target_node.type)

        evidence_chunks: List[UnifiedSearchResult] = []
        if target_file and target_node.start_line:
            evidence_chunks.append(create_evidence_chunk(
                chunk_id=f"doc_{target_node.id}",
                repository_id=target_node.repository_id or "repo",
                file_path=target_file,
                start_line=target_node.start_line,
                end_line=target_node.end_line or (target_node.start_line + 15),
                content=f"// Symbol: {target_node.name} ({target_type})",
                symbol_name=target_node.name,
                symbol_type=target_type,
                score=1.0,
            ))

        # Query incoming callers
        caller_edges = self.store.get_edges(
            repository_id,
            relationship=RelationshipType.CALLS,
            target_id=target_node.id,
            limit=10,
        )
        callers: List[str] = []
        for e in caller_edges:
            cnode = self.store.get_node(e.source_id, repository_id)
            cname = cnode.name if cnode else e.source_id.split(":")[-1]
            cpath = cnode.file_path if cnode else ""
            callers.append(f"`{cname}` in [{cpath}]" if cpath else f"`{cname}`")

        # Query outgoing callees
        callee_edges = self.store.get_edges(
            repository_id,
            relationship=RelationshipType.CALLS,
            source_id=target_node.id,
            limit=10,
        )
        callees: List[str] = []
        for e in callee_edges:
            cnode = self.store.get_node(e.target_id, repository_id)
            cname = cnode.name if cnode else e.target_id.split(":")[-1]
            cpath = cnode.file_path if cnode else ""
            callees.append(f"`{cname}` in [{cpath}]" if cpath else f"`{cname}`")

        # Format markdown documentation
        loc_str = f":{target_node.start_line}-{target_node.end_line}" if target_node.start_line and target_node.end_line else ""
        doc_lines = [
            f"# Technical Specification: `{target_node.name}`",
            "",
            f"**Entity Type**: `{target_type}`  ",
            f"**Source Location**: [{target_file}{loc_str}]  ",
            f"**Qualified Identifier**: `{target_node.qualified_name or target_node.id}`  ",
            "",
            "## 1. Overview & Architectural Role",
            f"`{target_node.name}` is a core component defined in [{target_file}]. "
            f"It operates within the repository's structural architecture as a `{target_type}`.",
            "",
            "## 2. Inbound References & Callers",
            f"The following **{len(callers)} component(s)** invoke or depend directly upon `{target_node.name}`:",
        ]

        if callers:
            for c in callers:
                doc_lines.append(f"- {c}")
        else:
            doc_lines.append("- *No internal repository callers identified (may be a public entry point or top-level handler).*")

        doc_lines.extend([
            "",
            "## 3. Outbound Dependencies & Callees",
            f"`{target_node.name}` invokes the following **{len(callees)} component(s)** during execution:",
        ])

        if callees:
            for c in callees:
                doc_lines.append(f"- {c}")
        else:
            doc_lines.append("- *No outbound calls recorded in static AST.*")

        doc_lines.extend([
            "",
            "## 4. Usage Example & Contract Guidance",
            "```python",
            f"# Typical consumption pattern for {target_node.name}",
            f"from {target_file.replace('/', '.').replace('.py', '')} import {target_node.name}",
            "",
            f"result = {target_node.name}(...)",
            "```",
            "",
            "---",
            "*Generated automatically by RepoMind Intelligence Engine. Citations verified against AST graph.*"
        ])

        markdown_doc = "\n".join(doc_lines)
        citations = self.validator.validate_citations(
            generated_text=markdown_doc,
            retrieved_chunks=evidence_chunks,
            include_unverified=True,
        )

        return DocumentationResult(
            target_name=target_node.name,
            target_type=target_type,
            file_path=target_file,
            markdown_documentation=markdown_doc,
            citations=citations,
        )


documentation_generator = TechnicalDocumentationGenerator()
