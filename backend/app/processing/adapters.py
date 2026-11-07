"""
Shared pipeline adapters for Vector RAG and GraphRAG.
Demonstrates and validates how the unified ParsedRepository intermediate representation
natively satisfies both downstream pipelines without duplicate parsing.
Includes edge deduplication, static target resolution, and confidence classification.
"""

from typing import List, Tuple, Dict, Any, Optional, Set
from collections import defaultdict
from pathlib import Path

from backend.app.graph.interfaces import (
    GraphNode,
    GraphEdge,
    NodeType,
    RelationshipType,
)
from backend.app.processing.models import (
    ParsedRepository,
    ParsedFile,
    ExtractedSymbol,
    SymbolType,
)


def to_graph_elements(
    parsed_repo: ParsedRepository
) -> Tuple[List[GraphNode], List[GraphEdge]]:
    """
    Adapter Pipeline B: Converts ParsedRepository into GraphNode and GraphEdge collections
    ready for NetworkX / Graph store insertion (Phase 5).

    Performs:
      1. Deterministic graph node generation for repository, files, and AST symbols.
      2. Strict edge deduplication (aggregates multiple calls into single edge with line counts).
      3. Resolution classification (distinguishes confirmed internal links from inferred/unresolved).
    """
    nodes: List[GraphNode] = []
    node_ids: Set[str] = set()

    # Index all defined symbols across the repository for target resolution
    symbols_by_id: Dict[str, ExtractedSymbol] = {}
    symbols_by_name: Dict[str, List[ExtractedSymbol]] = defaultdict(list)
    file_symbols_by_name: Dict[str, Dict[str, ExtractedSymbol]] = defaultdict(dict)

    for f_path, file_data in parsed_repo.files.items():
        for sym in file_data.symbols:
            symbols_by_id[sym.symbol_id] = sym
            symbols_by_name[sym.name].append(sym)
            file_symbols_by_name[f_path][sym.name] = sym

    # 1. Root Repository Node
    repo_node_id = f"repo:{parsed_repo.repository_id}"
    nodes.append(
        GraphNode(
            id=repo_node_id,
            repository_id=parsed_repo.repository_id,
            type=NodeType.REPOSITORY,
            name=parsed_repo.repository_id,
            commit_hash=parsed_repo.commit_hash,
            properties={
                "total_files": parsed_repo.total_files,
                "total_symbols": parsed_repo.total_symbols,
                "supported_languages": parsed_repo.supported_languages,
            },
        )
    )
    node_ids.add(repo_node_id)

    # Dictionary to aggregate and deduplicate edges: (source_id, target_id, relationship) -> GraphEdge
    edge_map: Dict[Tuple[str, str, RelationshipType], GraphEdge] = {}

    def _add_or_merge_edge(
        source_id: str,
        target_id: str,
        relationship: RelationshipType,
        is_confirmed: bool,
        confidence: float,
        properties: Optional[Dict[str, Any]] = None,
        line: Optional[int] = None,
    ) -> None:
        key = (source_id, target_id, relationship)
        props = properties.copy() if properties else {}
        props["confidence"] = confidence

        if key in edge_map:
            existing = edge_map[key]
            # Increment call count if call
            if relationship == RelationshipType.CALLS:
                existing.properties["call_count"] = existing.properties.get("call_count", 1) + 1
                if line:
                    lines = existing.properties.get("lines", [])
                    if line not in lines:
                        lines.append(line)
                    existing.properties["lines"] = lines
            # Update confirmation if stronger
            if is_confirmed and not existing.is_confirmed:
                existing.is_confirmed = True
                existing.properties["confidence"] = confidence
        else:
            if relationship == RelationshipType.CALLS:
                props["call_count"] = 1
                if line:
                    props["lines"] = [line]
            edge_map[key] = GraphEdge(
                source_id=source_id,
                target_id=target_id,
                relationship=relationship,
                repository_id=parsed_repo.repository_id,
                is_confirmed=is_confirmed,
                properties=props,
            )

    # 2. Iterate Files and AST Symbols
    for file_path, file_data in parsed_repo.files.items():
        file_node_id = f"file:{parsed_repo.repository_id}:{file_path}"
        nodes.append(
            GraphNode(
                id=file_node_id,
                repository_id=parsed_repo.repository_id,
                type=NodeType.FILE,
                name=Path(file_path).name,
                file_path=file_path,
                start_line=1,
                end_line=file_data.line_count,
                language=file_data.language,
                commit_hash=parsed_repo.commit_hash,
                properties={"size_bytes": file_data.size_bytes},
            )
        )
        node_ids.add(file_node_id)

        # Edge: REPOSITORY -> CONTAINS -> FILE
        _add_or_merge_edge(
            source_id=repo_node_id,
            target_id=file_node_id,
            relationship=RelationshipType.CONTAINS,
            is_confirmed=True,
            confidence=1.0,
        )

        # Symbols: CLASS, INTERFACE, FUNCTION, METHOD
        for sym in file_data.symbols:
            if sym.symbol_type == SymbolType.CLASS:
                n_type = NodeType.CLASS
            elif sym.symbol_type == SymbolType.INTERFACE:
                n_type = NodeType.INTERFACE
            elif sym.symbol_type == SymbolType.METHOD:
                n_type = NodeType.METHOD
            else:
                n_type = NodeType.FUNCTION

            sym_node = GraphNode(
                id=sym.symbol_id,
                repository_id=parsed_repo.repository_id,
                type=n_type,
                name=sym.name,
                file_path=file_path,
                start_line=sym.location.start_line,
                end_line=sym.location.end_line,
                language=file_data.language,
                commit_hash=parsed_repo.commit_hash,
                properties={
                    "content_hash": sym.content_hash,
                    "docstring": sym.docstring,
                    "signature": sym.signature,
                    "return_type": sym.return_type,
                    "parameters": sym.parameters,
                    "modifiers": sym.modifiers,
                },
            )
            nodes.append(sym_node)
            node_ids.add(sym.symbol_id)

            # Edge: CONTAINS (links to parent symbol or file)
            parent_id = sym.parent_symbol_id if sym.parent_symbol_id else file_node_id
            _add_or_merge_edge(
                source_id=parent_id,
                target_id=sym.symbol_id,
                relationship=RelationshipType.CONTAINS,
                is_confirmed=True,
                confidence=1.0,
            )

        # Edges: INHERITANCE / IMPLEMENTATION with local resolution
        for inh in file_data.inheritances:
            rel = (
                RelationshipType.IMPLEMENTS
                if inh.relationship == "IMPLEMENTS"
                else RelationshipType.INHERITS
            )
            # Resolve target: Is the superclass defined in this repo?
            target_id = f"type:{parsed_repo.repository_id}:{inh.super_name}"
            is_conf = False
            conf = 0.7
            if inh.super_name in file_symbols_by_name[file_path]:
                target_id = file_symbols_by_name[file_path][inh.super_name].symbol_id
                is_conf = True
                conf = 1.0
            elif inh.super_name in symbols_by_name:
                target_id = symbols_by_name[inh.super_name][0].symbol_id
                is_conf = True
                conf = 0.9

            _add_or_merge_edge(
                source_id=inh.sub_symbol_id,
                target_id=target_id,
                relationship=rel,
                is_confirmed=is_conf,
                confidence=conf,
                properties={"target_name": inh.super_name},
            )

        # Edges: IMPORTS
        for imp in file_data.imports:
            _add_or_merge_edge(
                source_id=file_node_id,
                target_id=f"module:{parsed_repo.repository_id}:{imp.module}",
                relationship=RelationshipType.IMPORTS,
                is_confirmed=True,
                confidence=1.0,
                properties={
                    "raw_statement": imp.raw_statement,
                    "imported_symbols": imp.imported_symbols,
                    "alias": imp.alias,
                    "is_relative": imp.is_relative,
                },
            )

        # Edges: CALLS with local resolution and deduplication
        for call in file_data.calls:
            caller_id = call.caller_symbol_id or file_node_id

            # Resolve target ID and confidence
            target_id = f"unresolved:{parsed_repo.repository_id}:{call.callee_name}"
            is_conf = False
            conf = 0.3
            res_type = call.resolution_status

            # Check if callee is defined locally in the same file
            if call.callee_name in file_symbols_by_name[file_path]:
                target_id = file_symbols_by_name[file_path][call.callee_name].symbol_id
                is_conf = True
                conf = 1.0
                res_type = "CONFIRMED_LOCAL"
            # Check if callee matches a known repository-wide symbol
            elif call.callee_name in symbols_by_name and len(symbols_by_name[call.callee_name]) == 1:
                target_id = symbols_by_name[call.callee_name][0].symbol_id
                is_conf = False
                conf = 0.8
                res_type = "INFERRED_REPO"
            elif call.receiver:
                target_id = f"receiver:{parsed_repo.repository_id}:{call.receiver}.{call.callee_name}"
                is_conf = False
                conf = 0.6
                res_type = "INFERRED_RECEIVER"

            _add_or_merge_edge(
                source_id=caller_id,
                target_id=target_id,
                relationship=RelationshipType.CALLS,
                is_confirmed=is_conf,
                confidence=conf,
                properties={
                    "receiver": call.receiver,
                    "resolution": res_type,
                    "is_constructor": call.is_constructor,
                },
                line=call.location.start_line,
            )

    return nodes, list(edge_map.values())


def to_code_chunks(
    parsed_repo: ParsedRepository,
    max_chunk_lines: int = 100,
) -> List[Dict[str, Any]]:
    """
    Adapter Pipeline A: Converts ParsedRepository into structure-aware code chunks
    ready for Vector RAG embedding and ChromaDB indexing (Phase 4).

    Preserves 1-indexed start and end lines, exact source code, docstrings, signatures,
    and content hashes for incremental deduplication.
    """
    chunks: List[Dict[str, Any]] = []

    for file_path, file_data in parsed_repo.files.items():
        for sym in file_data.symbols:
            metadata = {
                "repository_id": parsed_repo.repository_id,
                "file_path": file_path,
                "symbol_id": sym.symbol_id,
                "symbol_name": sym.name,
                "symbol_type": sym.symbol_type.value,
                "language": file_data.language,
                "start_line": sym.location.start_line,
                "end_line": sym.location.end_line,
                "content_hash": sym.content_hash or "",
                "docstring": sym.docstring or "",
                "signature": sym.signature or "",
                "parent_symbol_id": sym.parent_symbol_id or "",
                "commit_hash": parsed_repo.commit_hash or "",
            }

            # Code chunk content with contextual header
            header = f"# File: {file_path} (Lines {sym.location.start_line}-{sym.location.end_line})\n"
            if sym.docstring:
                header += f"# Description: {sym.docstring}\n"

            content = f"{header}{sym.source_code}"

            chunks.append({
                "chunk_id": f"chunk:{sym.symbol_id}",
                "content": content,
                "metadata": metadata,
            })

    return chunks
