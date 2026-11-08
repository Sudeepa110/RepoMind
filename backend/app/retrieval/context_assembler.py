"""
Structured Context Assembler for future LLM answer generation.
Synthesizes ranked code chunks, exact file & line citations, caller/callee graph evidence,
and retrieval provenance into a compact, structured evidence block.
"""

from typing import List, Dict, Any, Optional

from backend.app.retrieval.retrieval_models import (
    UnifiedSearchResult,
    GraphEvidence,
    AssembledContext,
)


class ContextAssembler:
    """
    Constructs compact, grounded retrieval evidence contexts ready for LLM consumption.
    Preserves exact citations and distinguishes confirmed from inferred links.
    """

    def assemble(
        self,
        query: str,
        results: List[UnifiedSearchResult],
        graph_evidence: Optional[List[GraphEvidence]] = None,
        max_chars: int = 16000,
    ) -> AssembledContext:
        """
        Synthesizes code chunks and structural relationships into structured context.
        """
        evidence_list = graph_evidence or []
        sections: List[str] = []
        citations: List[Dict[str, Any]] = []

        sections.append(f"### [RETRIEVAL EVIDENCE CONTEXT]")
        sections.append(f"**Target Developer Query**: {query}\n")

        # 1. Structural Graph Evidence Section
        if evidence_list:
            sections.append("#### 1. CODE STRUCTURE & RELATIONSHIP EVIDENCE (GraphRAG):")
            for ev in evidence_list:
                status_tag = "CONFIRMED" if ev.is_confirmed else f"INFERRED ({round(ev.confidence * 100)}% conf)"
                lines_str = f"at line(s) {', '.join(map(str, ev.lines))}" if ev.lines else ""
                file_str = f"in {ev.file_path}" if ev.file_path else ""

                rel_desc = (
                    f"- **{ev.relationship_type}**: `{ev.source_name}` $\\rightarrow$ `{ev.target_name}` "
                    f"[{status_tag}] {file_str} {lines_str}"
                )
                if ev.call_count > 1:
                    rel_desc += f" (called {ev.call_count} times)"
                sections.append(rel_desc)
            sections.append("")

        # 2. Source Code Snippets Section
        sections.append("#### 2. RANKED SOURCE CODE IMPLEMENTATIONS:")
        total_code_chars = 0
        chunks_included = 0
        sources_used = set()

        for idx, res in enumerate(results, start=1):
            sources_used.update(res.sources)

            citation = {
                "rank": idx,
                "file_path": res.file_path,
                "start_line": res.start_line,
                "end_line": res.end_line,
                "symbol_name": res.symbol_name,
                "symbol_type": res.symbol_type,
                "sources": res.sources,
                "rrf_score": res.rrf_score,
            }
            citations.append(citation)

            snippet_header = (
                f"\n--- EVIDENCE #{idx}: {res.file_path} (Lines {res.start_line}-{res.end_line}) "
                f"| Symbol: {res.symbol_name or 'file_block'} ({res.symbol_type or 'CODE'}) "
                f"| Source: {res.retrieval_source} [Score: {res.normalized_score}] ---"
            )

            meta_lines = []
            if res.signature:
                meta_lines.append(f"Signature: {res.signature}")
            if res.docstring:
                meta_lines.append(f"Description: {res.docstring}")
            meta_str = ("\n" + "\n".join(meta_lines)) if meta_lines else ""

            code_block = f"\n```{res.language}\n{res.source_code}\n```"

            chunk_text = f"{snippet_header}{meta_str}{code_block}\n"

            # Check character budget
            if total_code_chars + len(chunk_text) > max_chars:
                sections.append("\n[Remaining code chunks truncated to stay within token context limits]")
                break

            sections.append(chunk_text)
            total_code_chars += len(chunk_text)
            chunks_included += 1

        # 3. Citation Summary Table
        sections.append("\n#### 3. VERIFIED EVIDENCE CITATIONS:")
        sections.append("| Rank | File Path | Line Coordinates | Symbol | Source Engine | RRF Score |")
        sections.append("|:---:|:---|:---:|:---|:---:|:---:|")
        for c in citations[:chunks_included]:
            sym = c["symbol_name"] or "-"
            src = "+".join(c["sources"])
            sections.append(
                f"| {c['rank']} | `{c['file_path']}` | `#L{c['start_line']}-L{c['end_line']}` | `{sym}` | {src} | {c['rrf_score']} |"
            )

        formatted_context = "\n".join(sections)

        summary = (
            f"Assembled {chunks_included} code chunks and {len(evidence_list)} graph relationships "
            f"across {len(sources_used)} retrieval engines ({', '.join(sorted(list(sources_used)))})."
        )

        return AssembledContext(
            summary=summary,
            total_code_chunks=chunks_included,
            total_graph_relationships=len(evidence_list),
            sources_used=sorted(list(sources_used)),
            formatted_context=formatted_context,
            citations=citations[:chunks_included],
        )


# Global singleton instance
context_assembler = ContextAssembler()
