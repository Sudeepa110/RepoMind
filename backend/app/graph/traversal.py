"""
Graph Traversal Service.
Provides high-level developer-centric queries on repository knowledge graphs:
callers, callees, inheritance hierarchies, dependency analysis, bounded execution paths,
and impact / blast-radius analysis.
"""

import logging
from typing import Dict, Any, List, Optional, Set

from backend.app.graph.interfaces import (
    BaseGraphStore,
    GraphNode,
    NodeType,
    RelationshipType,
)
from backend.app.graph.networkx_store import networkx_graph_store

logger = logging.getLogger(__name__)


class GraphTraversalService:
    """
    High-level query engine for structural analysis and code traversal over knowledge graphs.
    """

    def __init__(self, store: Optional[BaseGraphStore] = None):
        self.store = store or networkx_graph_store

    def _resolve_symbol_node(
        self, repository_id: str, query: str
    ) -> Optional[GraphNode]:
        """
        Resolves a symbol node by exact ID, qualified name, or symbol name.
        """
        # 1. Exact node ID match
        node = self.store.get_node(query, repository_id)
        if node:
            return node

        # 2. Match by symbol name or qualified name
        nodes = self.store.get_nodes(repository_id, query=query, limit=10)
        # Prioritize exact name match
        for n in nodes:
            if n.name == query or n.qualified_name == query:
                return n

        # Fallback to first substring match if any
        return nodes[0] if nodes else None

    def find_callers(
        self, repository_id: str, symbol_query: str
    ) -> Dict[str, Any]:
        """
        Given a function or method, identifies functions and methods that call it.
        Returns caller name, file, lines, confidence, and call count.
        """
        target = self._resolve_symbol_node(repository_id, symbol_query)
        if not target:
            return {
                "repository_id": repository_id,
                "target_symbol": symbol_query,
                "found": False,
                "error": f"Symbol '{symbol_query}' not found in repository knowledge graph.",
                "total_callers": 0,
                "callers": [],
            }

        edges = self.store.get_edges(
            repository_id,
            relationship=RelationshipType.CALLS,
            target_id=target.id,
            limit=500,
        )

        callers: List[Dict[str, Any]] = []
        for edge in edges:
            caller_node = self.store.get_node(edge.source_id, repository_id)
            caller_name = caller_node.name if caller_node else edge.source_id.split(":")[-1]
            file_path = caller_node.file_path if caller_node else ""
            start_line = caller_node.start_line if caller_node else None

            callers.append({
                "caller_id": edge.source_id,
                "caller_name": caller_name,
                "caller_type": caller_node.type.value if caller_node else "Function",
                "file_path": file_path,
                "start_line": start_line,
                "invocation_lines": edge.properties.get("lines", [start_line] if start_line else []),
                "call_count": edge.properties.get("call_count", 1),
                "confidence": edge.confidence,
                "is_confirmed": edge.is_confirmed,
                "resolution_status": edge.resolution_status,
            })

        return {
            "repository_id": repository_id,
            "target_id": target.id,
            "target_symbol": target.name,
            "target_type": target.type.value,
            "file_path": target.file_path,
            "line": target.start_line,
            "found": True,
            "total_callers": len(callers),
            "callers": callers,
        }

    def find_callees(
        self, repository_id: str, symbol_query: str
    ) -> Dict[str, Any]:
        """
        Given a function or method, identifies functions and methods it calls.
        Returns callee name, file, lines, confidence, and call count.
        """
        source = self._resolve_symbol_node(repository_id, symbol_query)
        if not source:
            return {
                "repository_id": repository_id,
                "source_symbol": symbol_query,
                "found": False,
                "error": f"Symbol '{symbol_query}' not found in repository knowledge graph.",
                "total_callees": 0,
                "callees": [],
            }

        edges = self.store.get_edges(
            repository_id,
            relationship=RelationshipType.CALLS,
            source_id=source.id,
            limit=500,
        )

        callees: List[Dict[str, Any]] = []
        for edge in edges:
            callee_node = self.store.get_node(edge.target_id, repository_id)
            callee_name = callee_node.name if callee_node else edge.target_id.split(":")[-1]
            file_path = callee_node.file_path if callee_node else ""
            start_line = callee_node.start_line if callee_node else None

            callees.append({
                "callee_id": edge.target_id,
                "callee_name": callee_name,
                "callee_type": callee_node.type.value if callee_node else "Function",
                "file_path": file_path,
                "start_line": start_line,
                "invocation_lines": edge.properties.get("lines", []),
                "call_count": edge.properties.get("call_count", 1),
                "confidence": edge.confidence,
                "is_confirmed": edge.is_confirmed,
                "resolution_status": edge.resolution_status,
            })

        return {
            "repository_id": repository_id,
            "source_id": source.id,
            "source_symbol": source.name,
            "source_type": source.type.value,
            "file_path": source.file_path,
            "line": source.start_line,
            "found": True,
            "total_callees": len(callees),
            "callees": callees,
        }

    def find_inheritance_hierarchy(
        self, repository_id: str, class_or_interface_query: str
    ) -> Dict[str, Any]:
        """
        Identifies parent classes, child classes, implemented interfaces,
        and classes implementing a target interface.
        """
        target = self._resolve_symbol_node(repository_id, class_or_interface_query)
        if not target:
            return {
                "repository_id": repository_id,
                "target_symbol": class_or_interface_query,
                "found": False,
                "error": f"Symbol '{class_or_interface_query}' not found in repository knowledge graph.",
                "parent_classes": [],
                "child_classes": [],
                "implemented_interfaces": [],
                "implementors": [],
            }

        # Outgoing INHERITS -> Parent classes
        out_inherits = self.store.get_edges(
            repository_id, relationship=RelationshipType.INHERITS, source_id=target.id
        )
        parent_classes = []
        for e in out_inherits:
            node = self.store.get_node(e.target_id, repository_id)
            parent_classes.append({
                "id": e.target_id,
                "name": node.name if node else e.target_id.split(":")[-1],
                "file_path": node.file_path if node else None,
                "confidence": e.confidence,
                "is_confirmed": e.is_confirmed,
            })

        # Incoming INHERITS -> Child classes (subclasses)
        in_inherits = self.store.get_edges(
            repository_id, relationship=RelationshipType.INHERITS, target_id=target.id
        )
        child_classes = []
        for e in in_inherits:
            node = self.store.get_node(e.source_id, repository_id)
            child_classes.append({
                "id": e.source_id,
                "name": node.name if node else e.source_id.split(":")[-1],
                "file_path": node.file_path if node else None,
                "confidence": e.confidence,
                "is_confirmed": e.is_confirmed,
            })

        # Outgoing IMPLEMENTS -> Implemented interfaces
        out_implements = self.store.get_edges(
            repository_id, relationship=RelationshipType.IMPLEMENTS, source_id=target.id
        )
        implemented_interfaces = []
        for e in out_implements:
            node = self.store.get_node(e.target_id, repository_id)
            implemented_interfaces.append({
                "id": e.target_id,
                "name": node.name if node else e.target_id.split(":")[-1],
                "file_path": node.file_path if node else None,
                "confidence": e.confidence,
                "is_confirmed": e.is_confirmed,
            })

        # Incoming IMPLEMENTS -> Classes implementing this interface
        in_implements = self.store.get_edges(
            repository_id, relationship=RelationshipType.IMPLEMENTS, target_id=target.id
        )
        implementors = []
        for e in in_implements:
            node = self.store.get_node(e.source_id, repository_id)
            implementors.append({
                "id": e.source_id,
                "name": node.name if node else e.source_id.split(":")[-1],
                "file_path": node.file_path if node else None,
                "confidence": e.confidence,
                "is_confirmed": e.is_confirmed,
            })

        return {
            "repository_id": repository_id,
            "target_id": target.id,
            "target_symbol": target.name,
            "target_type": target.type.value,
            "file_path": target.file_path,
            "line": target.start_line,
            "found": True,
            "parent_classes": parent_classes,
            "child_classes": child_classes,
            "implemented_interfaces": implemented_interfaces,
            "implementors": implementors,
        }

    def find_dependencies(
        self, repository_id: str, target_query: str
    ) -> Dict[str, Any]:
        """
        Identifies direct imports, imported modules, and files/symbols depending on this module.
        """
        target = self._resolve_symbol_node(repository_id, target_query)

        # If not a symbol node, maybe a file path
        file_node_id = f"file:{repository_id}:{target_query}"
        file_node = self.store.get_node(file_node_id, repository_id)
        active_node = target or file_node

        if not active_node:
            return {
                "repository_id": repository_id,
                "target": target_query,
                "found": False,
                "error": f"Target '{target_query}' not found in repository knowledge graph.",
                "imported_modules": [],
                "dependent_components": [],
            }

        # Outgoing IMPORTS and DEPENDS_ON
        out_edges = self.store.get_edges(
            repository_id,
            source_id=active_node.id,
            limit=500,
        )
        imported_modules = []
        for e in out_edges:
            if e.relationship in (RelationshipType.IMPORTS, RelationshipType.DEPENDS_ON):
                node = self.store.get_node(e.target_id, repository_id)
                imported_modules.append({
                    "id": e.target_id,
                    "name": node.name if node else e.target_id.split(":")[-1],
                    "type": node.type.value if node else "Module",
                    "relationship": e.relationship.value,
                    "confidence": e.confidence,
                    "properties": e.properties,
                })

        # Incoming IMPORTS and DEPENDS_ON -> Who depends on this
        in_edges = self.store.get_edges(
            repository_id,
            target_id=active_node.id,
            limit=500,
        )
        dependent_components = []
        for e in in_edges:
            if e.relationship in (RelationshipType.IMPORTS, RelationshipType.DEPENDS_ON, RelationshipType.CALLS):
                node = self.store.get_node(e.source_id, repository_id)
                dependent_components.append({
                    "id": e.source_id,
                    "name": node.name if node else e.source_id.split(":")[-1],
                    "type": node.type.value if node else "File",
                    "file_path": node.file_path if node else None,
                    "relationship": e.relationship.value,
                    "confidence": e.confidence,
                })

        return {
            "repository_id": repository_id,
            "target_id": active_node.id,
            "target_name": active_node.name,
            "target_type": active_node.type.value,
            "file_path": active_node.file_path,
            "found": True,
            "total_imported_modules": len(imported_modules),
            "total_dependents": len(dependent_components),
            "imported_modules": imported_modules,
            "dependent_components": dependent_components,
        }

    def find_execution_paths(
        self,
        repository_id: str,
        source_query: str,
        target_query: str,
        max_depth: int = 5,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Explores bounded static invocation paths between two symbols along CALLS edges.
        Note: Static call graphs represent potential invocation paths and do not guarantee
        runtime execution without active runtime trace instrumentation.
        """
        source = self._resolve_symbol_node(repository_id, source_query)
        target = self._resolve_symbol_node(repository_id, target_query)

        if not source or not target:
            missing = []
            if not source:
                missing.append(f"source '{source_query}'")
            if not target:
                missing.append(f"target '{target_query}'")
            return {
                "repository_id": repository_id,
                "found": False,
                "error": f"Could not resolve: {', '.join(missing)} in knowledge graph.",
                "paths": [],
                "disclaimer": "Static analysis represents potential execution paths based on AST call hierarchy.",
            }

        raw_paths = self.store.find_paths(
            source.id, target.id, max_depth=max_depth, limit=limit
        )

        formatted_paths: List[List[Dict[str, Any]]] = []
        for p in raw_paths:
            path_nodes = []
            for nid in p:
                node = self.store.get_node(nid, repository_id)
                path_nodes.append({
                    "id": nid,
                    "name": node.name if node else nid.split(":")[-1],
                    "type": node.type.value if node else "Function",
                    "file_path": node.file_path if node else None,
                    "line": node.start_line if node else None,
                })
            formatted_paths.append(path_nodes)

        return {
            "repository_id": repository_id,
            "source_id": source.id,
            "source_name": source.name,
            "target_id": target.id,
            "target_name": target.name,
            "found": True,
            "total_paths": len(formatted_paths),
            "max_depth": max_depth,
            "paths": formatted_paths,
            "disclaimer": "Static analysis represents potential invocation paths based on AST call hierarchy; dynamic runtime branching may alter actual execution.",
        }

    def analyze_impact(
        self, repository_id: str, target_query: str, depth: int = 2
    ) -> Dict[str, Any]:
        """
        Given a symbol or file, analyzes direct callers, direct dependents, inheriting classes,
        and affected files (blast radius).
        """
        target = self._resolve_symbol_node(repository_id, target_query)
        if not target:
            # Check if file node
            file_node_id = f"file:{repository_id}:{target_query}"
            target = self.store.get_node(file_node_id, repository_id)

        if not target:
            return {
                "repository_id": repository_id,
                "target": target_query,
                "found": False,
                "error": f"Target '{target_query}' not found in repository knowledge graph.",
                "total_impacted_symbols": 0,
                "total_affected_files": 0,
                "affected_files": [],
                "direct_callers": [],
                "direct_dependents": [],
                "inheriting_classes": [],
            }

        res = self.store.analyze_impact(target.id, depth=depth)
        res["repository_id"] = repository_id
        res["found"] = True
        return res


# Global singleton instance
graph_traversal_service = GraphTraversalService()
