"""
Shared pipeline adapters for Vector RAG and GraphRAG.
Demonstrates and validates how the unified ParsedRepository intermediate representation
natively satisfies both downstream pipelines without duplicate parsing.
"""

from typing import List, Tuple, Dict, Any, Optional
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
    """
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    node_ids: set[str] = set()

    repo_node_id = f"repo:{parsed_repo.repository_id}"
    nodes.append(
        GraphNode(
            id=repo_node_id,
            repository_id=parsed_repo.repository_id,
            type=NodeType.REPOSITORY,
            name=parsed_repo.repository_id,
            commit_hash=parsed_repo.commit_hash,
            properties={"total_files": parsed_repo.total_files, "total_symbols": parsed_repo.total_symbols},
        )
    )
    node_ids.add(repo_node_id)

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
        edges.append(
            GraphEdge(
                source_id=repo_node_id,
                target_id=file_node_id,
                relationship=RelationshipType.CONTAINS,
                repository_id=parsed_repo.repository_id,
                is_confirmed=True,
            )
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
                    "docstring": sym.docstring,
                    "signature": sym.signature,
                    "return_type": sym.return_type,
                    "parameters": sym.parameters,
                    "modifiers": sym.modifiers,
                },
            )
            nodes.append(sym_node)
            node_ids.add(sym.symbol_id)

            # Edge: CONTAINS
            parent_id = sym.parent_symbol_id if sym.parent_symbol_id else file_node_id
            edges.append(
                GraphEdge(
                    source_id=parent_id,
                    target_id=sym.symbol_id,
                    relationship=RelationshipType.CONTAINS,
                    repository_id=parsed_repo.repository_id,
                    is_confirmed=True,
                )
            )

        # Edges: INHERITANCE / IMPLEMENTATION
        for inh in file_data.inheritances:
            edges.append(
                GraphEdge(
                    source_id=inh.sub_symbol_id,
                    target_id=f"type:{parsed_repo.repository_id}:{inh.super_name}",
                    relationship=RelationshipType.IMPLEMENTS if inh.relationship == "IMPLEMENTS" else RelationshipType.INHERITS,
                    repository_id=parsed_repo.repository_id,
                    is_confirmed=False,
                    properties={"target_name": inh.super_name},
                )
            )

        # Edges: IMPORTS
        for imp in file_data.imports:
            edges.append(
                GraphEdge(
                    source_id=file_node_id,
                    target_id=f"module:{parsed_repo.repository_id}:{imp.module}",
                    relationship=RelationshipType.IMPORTS,
                    repository_id=parsed_repo.repository_id,
                    is_confirmed=True,
                    properties={"raw_statement": imp.raw_statement, "imported_symbols": imp.imported_symbols},
                )
            )

        # Edges: CALLS
        for call in file_data.calls:
            if call.caller_symbol_id:
                edges.append(
                    GraphEdge(
                        source_id=call.caller_symbol_id,
                        target_id=f"symbol:{parsed_repo.repository_id}:{call.callee_name}",
                        relationship=RelationshipType.CALLS,
                        repository_id=parsed_repo.repository_id,
                        is_confirmed=call.is_confirmed,
                        properties={"receiver": call.receiver, "line": call.location.start_line},
                    )
                )

    return nodes, edges


def to_code_chunks(
    parsed_repo: ParsedRepository,
    max_chunk_lines: int = 100,
) -> List[Dict[str, Any]]:
    """
    Adapter Pipeline A: Converts ParsedRepository into structure-aware code chunks
    ready for Vector RAG embedding and ChromaDB indexing (Phase 4).
    """
    chunks: List[Dict[str, Any]] = []

    for file_path, file_data in parsed_repo.files.items():
        # 1. Symbol-level chunks (functions, methods, classes)
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

