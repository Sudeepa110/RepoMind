"""
NetworkX Knowledge Graph Persistent Storage.
Implements BaseGraphStore using networkx.DiGraph with repository isolation,
safe structured JSON node-link serialization, atomic persistence, and bounded graph traversal.
"""

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

import networkx as nx

from backend.app.config import settings
from backend.app.graph.interfaces import (
    BaseGraphStore,
    GraphNode,
    GraphEdge,
    NodeType,
    RelationshipType,
)

logger = logging.getLogger(__name__)


def sanitize_filename(repo_id: str) -> str:
    """Sanitize repository ID for safe filesystem storage."""
    safe = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", repo_id)
    return safe[:100]


class NetworkXGraphStore(BaseGraphStore):
    """
    In-memory and file-persisted knowledge graph store powered by NetworkX DiGraph.
    Provides isolated graphs per repository with thread-safe access.
    """

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir or settings.GRAPH_PERSIST_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._graphs: Dict[str, nx.DiGraph] = {}
        self._lock = threading.RLock()
        self._name_index: Dict[str, Dict[str, Set[str]]] = {}
        self._qualified_name_index: Dict[str, Dict[str, Set[str]]] = {}

    def _index_node_entry(
        self,
        repository_id: str,
        node_id: str,
        name: Optional[str] = None,
        qualified_name: Optional[str] = None,
    ) -> None:
        """Internal helper to index symbol and qualified names for O(1) resolution."""
        if repository_id not in self._name_index:
            self._name_index[repository_id] = {}
        if repository_id not in self._qualified_name_index:
            self._qualified_name_index[repository_id] = {}

        if name:
            n_clean = str(name).strip().lower()
            if n_clean:
                if n_clean not in self._name_index[repository_id]:
                    self._name_index[repository_id][n_clean] = set()
                self._name_index[repository_id][n_clean].add(node_id)

        if qualified_name:
            q_clean = str(qualified_name).strip().lower()
            if q_clean:
                if q_clean not in self._qualified_name_index[repository_id]:
                    self._qualified_name_index[repository_id][q_clean] = set()
                self._qualified_name_index[repository_id][q_clean].add(node_id)

    def _rebuild_indices(self, repository_id: str) -> None:
        """Rebuilds in-memory inverted indices for a given repository."""
        graph = self._graphs.get(repository_id)
        if not graph:
            return
        self._name_index[repository_id] = {}
        self._qualified_name_index[repository_id] = {}
        for nid, data in graph.nodes(data=True):
            self._index_node_entry(
                repository_id,
                nid,
                name=data.get("name"),
                qualified_name=data.get("qualified_name"),
            )

    def _get_or_create_graph(self, repository_id: str) -> nx.DiGraph:
        with self._lock:
            if repository_id not in self._graphs:
                # Attempt to load from disk first
                if not self.load(repository_id):
                    self._graphs[repository_id] = nx.DiGraph()
            return self._graphs[repository_id]

    def _node_from_data(self, node_id: str, data: Dict[str, Any], default_repo_id: str = "") -> GraphNode:
        """Helper to safely instantiate a GraphNode from graph node attributes."""
        repo_id = data.get("repository_id") or default_repo_id

        # Determine node type safely
        raw_type = data.get("type")
        if isinstance(raw_type, NodeType):
            n_type = raw_type
        elif raw_type and str(raw_type) in [t.value for t in NodeType]:
            n_type = NodeType(str(raw_type))
        else:
            # Fallback based on node ID prefix
            if node_id.startswith("repo:"):
                n_type = NodeType.REPOSITORY
            elif node_id.startswith("file:"):
                n_type = NodeType.FILE
            elif node_id.startswith("module:"):
                n_type = NodeType.MODULE
            elif "class" in node_id.lower():
                n_type = NodeType.CLASS
            else:
                n_type = NodeType.FUNCTION

        name = data.get("name") or node_id.split(":")[-1]

        return GraphNode(
            id=node_id,
            repository_id=repo_id,
            type=n_type,
            name=name,
            qualified_name=data.get("qualified_name"),
            file_path=data.get("file_path"),
            start_line=data.get("start_line"),
            end_line=data.get("end_line"),
            language=data.get("language"),
            commit_hash=data.get("commit_hash"),
            symbol_id=data.get("symbol_id"),
            content_hash=data.get("content_hash"),
            properties=data.get("properties") or {},
        )

    def _edge_from_data(
        self, source_id: str, target_id: str, data: Dict[str, Any], default_repo_id: str = ""
    ) -> GraphEdge:
        """Helper to safely instantiate a GraphEdge from graph edge attributes."""
        repo_id = data.get("repository_id") or default_repo_id

        raw_rel = data.get("relationship")
        if isinstance(raw_rel, RelationshipType):
            rel = raw_rel
        elif raw_rel and str(raw_rel) in [r.value for r in RelationshipType]:
            rel = RelationshipType(str(raw_rel))
        else:
            rel = RelationshipType.DEPENDS_ON

        return GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relationship=rel,
            repository_id=repo_id,
            is_confirmed=data.get("is_confirmed", True),
            confidence=float(data.get("confidence", 1.0)),
            resolution_status=str(data.get("resolution_status", "CONFIRMED")),
            properties=data.get("properties") or {},
        )

    def add_node(self, node: GraphNode) -> None:
        """Add or update a node in the repository graph."""
        with self._lock:
            graph = self._get_or_create_graph(node.repository_id)
            node_attrs = {
                "repository_id": node.repository_id,
                "type": node.type.value,
                "name": node.name,
                "qualified_name": node.qualified_name or "",
                "file_path": node.file_path or "",
                "start_line": node.start_line,
                "end_line": node.end_line,
                "language": node.language or "",
                "commit_hash": node.commit_hash or "",
                "symbol_id": node.symbol_id or "",
                "content_hash": node.content_hash or "",
                "properties": node.properties,
            }
            graph.add_node(node.id, **node_attrs)
            self._index_node_entry(
                node.repository_id,
                node.id,
                name=node.name,
                qualified_name=node.qualified_name,
            )

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed relationship between two nodes."""
        with self._lock:
            graph = self._get_or_create_graph(edge.repository_id)

            # Ensure source and target nodes exist in the graph
            if edge.source_id not in graph:
                graph.add_node(
                    edge.source_id,
                    repository_id=edge.repository_id,
                    name=edge.source_id.split(":")[-1],
                    type=NodeType.FUNCTION.value,
                )
            if edge.target_id not in graph:
                # Infer type from target prefix
                fallback_type = NodeType.MODULE.value if edge.target_id.startswith("module:") else NodeType.FUNCTION.value
                graph.add_node(
                    edge.target_id,
                    repository_id=edge.repository_id,
                    name=edge.target_id.split(":")[-1],
                    type=fallback_type,
                )

            edge_attrs = {
                "repository_id": edge.repository_id,
                "relationship": edge.relationship.value,
                "is_confirmed": edge.is_confirmed,
                "confidence": edge.confidence,
                "resolution_status": edge.resolution_status,
                "properties": edge.properties,
            }
            graph.add_edge(edge.source_id, edge.target_id, **edge_attrs)

    def get_node(self, node_id: str, repository_id: Optional[str] = None) -> Optional[GraphNode]:
        """Retrieve a node by its unique identifier across repos or in a specific repo."""
        with self._lock:
            target_repos = [repository_id] if repository_id else list(self._graphs.keys())

            # If not in memory and repo provided, try loading
            if repository_id and repository_id not in self._graphs:
                self.load(repository_id)
                target_repos = [repository_id]

            for repo_id in target_repos:
                g = self._graphs.get(repo_id)
                if g and node_id in g:
                    return self._node_from_data(node_id, g.nodes[node_id], repo_id)

            # If still not found and no specific repo was passed, scan files
            if not repository_id:
                for f in self.persist_dir.glob("*.json"):
                    rid = f.stem
                    if rid not in self._graphs:
                        self.load(rid)
                        g = self._graphs.get(rid)
                        if g and node_id in g:
                            return self._node_from_data(node_id, g.nodes[node_id], rid)

            return None

    def get_edge(
        self, source_id: str, target_id: str, relationship: Optional[RelationshipType] = None
    ) -> Optional[GraphEdge]:
        """Retrieve an edge between two nodes."""
        with self._lock:
            for repo_id, g in self._graphs.items():
                if g.has_edge(source_id, target_id):
                    edge_data = g.get_edge_data(source_id, target_id)
                    if not relationship or edge_data.get("relationship") == relationship.value:
                        return self._edge_from_data(source_id, target_id, edge_data, repo_id)
            return None

    def get_nodes(
        self,
        repository_id: str,
        node_type: Optional[NodeType] = None,
        file_path: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GraphNode]:
        """Retrieve filtered and paginated nodes for a repository."""
        with self._lock:
            graph = self._get_or_create_graph(repository_id)
            results: List[GraphNode] = []
            q_lower = query.strip().lower() if query else None

            # Fast Inverted Index Lookup optimization:
            if q_lower and repository_id in self._name_index:
                exact_nids: Set[str] = set()
                if q_lower in self._name_index[repository_id]:
                    exact_nids.update(self._name_index[repository_id][q_lower])
                if q_lower in self._qualified_name_index.get(repository_id, {}):
                    exact_nids.update(self._qualified_name_index[repository_id][q_lower])

                if exact_nids:
                    for nid in exact_nids:
                        if nid in graph:
                            data = graph.nodes[nid]
                            if node_type and data.get("type") != node_type.value:
                                continue
                            if file_path and data.get("file_path") != file_path:
                                continue
                            results.append(self._node_from_data(nid, data, repository_id))
                    if results:
                        return results[offset : offset + limit]

            for node_id, data in graph.nodes(data=True):
                # Filter by node type
                if node_type and data.get("type") != node_type.value:
                    continue
                # Filter by file path
                if file_path and data.get("file_path") != file_path:
                    continue
                # Filter by search query on name or qualified_name
                if q_lower:
                    name = str(data.get("name", "")).lower()
                    qname = str(data.get("qualified_name", "")).lower()
                    if q_lower not in name and q_lower not in qname and q_lower not in node_id.lower():
                        continue

                results.append(self._node_from_data(node_id, data, repository_id))

            return results[offset : offset + limit]

    def get_edges(
        self,
        repository_id: str,
        relationship: Optional[RelationshipType] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GraphEdge]:
        """Retrieve filtered and paginated edges for a repository."""
        with self._lock:
            graph = self._get_or_create_graph(repository_id)
            results: List[GraphEdge] = []

            for u, v, data in graph.edges(data=True):
                if relationship and data.get("relationship") != relationship.value:
                    continue
                if source_id and u != source_id:
                    continue
                if target_id and v != target_id:
                    continue

                results.append(self._edge_from_data(u, v, data, repository_id))

            return results[offset : offset + limit]

    def get_neighbors(self, node_id: str, direction: str = "both") -> List[GraphNode]:
        """Retrieve adjacent nodes."""
        with self._lock:
            for repo_id, g in self._graphs.items():
                if node_id in g:
                    neighbor_ids: Set[str] = set()
                    if direction in ("out", "both"):
                        neighbor_ids.update(g.successors(node_id))
                    if direction in ("in", "both"):
                        neighbor_ids.update(g.predecessors(node_id))

                    return [
                        self._node_from_data(nid, g.nodes[nid], repo_id)
                        for nid in neighbor_ids
                        if nid in g
                    ]
            return []

    def get_callers(self, function_id: str) -> List[GraphNode]:
        """Retrieve all functions/methods that call this symbol (incoming CALLS edges)."""
        with self._lock:
            callers: List[GraphNode] = []
            for repo_id, g in self._graphs.items():
                if function_id in g:
                    for pred in g.predecessors(function_id):
                        edge_data = g.get_edge_data(pred, function_id) or {}
                        if edge_data.get("relationship") == RelationshipType.CALLS.value:
                            callers.append(self._node_from_data(pred, g.nodes[pred], repo_id))
            return callers

    def get_callees(self, function_id: str) -> List[GraphNode]:
        """Retrieve all functions/methods called by this symbol (outgoing CALLS edges)."""
        with self._lock:
            callees: List[GraphNode] = []
            for repo_id, g in self._graphs.items():
                if function_id in g:
                    for succ in g.successors(function_id):
                        edge_data = g.get_edge_data(function_id, succ) or {}
                        if edge_data.get("relationship") == RelationshipType.CALLS.value:
                            callees.append(self._node_from_data(succ, g.nodes[succ], repo_id))
            return callees

    def get_dependencies(self, symbol_id: str) -> List[GraphNode]:
        """Retrieve dependencies (outgoing IMPORTS, INHERITS, IMPLEMENTS, DEPENDS_ON)."""
        with self._lock:
            deps: List[GraphNode] = []
            dep_rels = {
                RelationshipType.IMPORTS.value,
                RelationshipType.INHERITS.value,
                RelationshipType.IMPLEMENTS.value,
                RelationshipType.DEPENDS_ON.value,
            }
            for repo_id, g in self._graphs.items():
                if symbol_id in g:
                    for succ in g.successors(symbol_id):
                        edge_data = g.get_edge_data(symbol_id, succ) or {}
                        if edge_data.get("relationship") in dep_rels:
                            deps.append(self._node_from_data(succ, g.nodes[succ], repo_id))
            return deps

    def get_subgraph(
        self, center_node_id: str, radius: int = 1, max_nodes: int = 50
    ) -> Dict[str, Any]:
        """Extract an ego subgraph centered on the target node."""
        with self._lock:
            for repo_id, g in self._graphs.items():
                if center_node_id in g:
                    # Create undirected ego graph to capture both incoming and outgoing relationships
                    ego = nx.ego_graph(g.to_undirected(), center_node_id, radius=radius)
                    nodes_subset = list(ego.nodes())[:max_nodes]

                    sub_di = g.subgraph(nodes_subset)

                    nodes = [
                        self._node_from_data(n, sub_di.nodes[n], repo_id).model_dump()
                        for n in sub_di.nodes()
                    ]
                    edges = [
                        self._edge_from_data(u, v, sub_di.get_edge_data(u, v), repo_id).model_dump()
                        for u, v in sub_di.edges()
                    ]
                    return {
                        "center_node_id": center_node_id,
                        "radius": radius,
                        "node_count": len(nodes),
                        "edge_count": len(edges),
                        "nodes": nodes,
                        "edges": edges,
                    }

            return {
                "center_node_id": center_node_id,
                "radius": radius,
                "node_count": 0,
                "edge_count": 0,
                "nodes": [],
                "edges": [],
            }

    def find_paths(
        self, source_id: str, target_id: str, max_depth: int = 5, limit: int = 10
    ) -> List[List[str]]:
        """Find bounded simple paths between two nodes."""
        with self._lock:
            for repo_id, g in self._graphs.items():
                if source_id in g and target_id in g:
                    paths: List[List[str]] = []
                    try:
                        for p in nx.all_simple_paths(g, source=source_id, target=target_id, cutoff=max_depth):
                            paths.append(p)
                            if len(paths) >= limit:
                                break
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        return []
                    return paths
            return []

    def analyze_impact(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """Analyze blast radius / impacted symbols when a node or file changes."""
        with self._lock:
            for repo_id, g in self._graphs.items():
                if node_id in g:
                    # In a directed call/dependency graph:
                    # Impact flows along INCOMING edges (who calls or depends on this node)
                    rev_g = g.reverse()
                    impacted_nodes: Set[str] = set()

                    # Bounded BFS on reversed graph
                    current_level = {node_id}
                    for _ in range(depth):
                        next_level: Set[str] = set()
                        for curr in current_level:
                            for succ in rev_g.successors(curr):
                                if succ != node_id and succ not in impacted_nodes:
                                    next_level.add(succ)
                                    impacted_nodes.add(succ)
                        current_level = next_level

                    direct_callers: List[Dict[str, Any]] = []
                    direct_dependents: List[Dict[str, Any]] = []
                    inheriting_classes: List[Dict[str, Any]] = []
                    affected_files: Set[str] = set()

                    # Direct impacts (predecessors in g)
                    for pred in g.predecessors(node_id):
                        e_data = g.get_edge_data(pred, node_id) or {}
                        rel = e_data.get("relationship")
                        p_node = self._node_from_data(pred, g.nodes[pred], repo_id)
                        if p_node.file_path:
                            affected_files.add(p_node.file_path)

                        item = {
                            "node_id": p_node.id,
                            "name": p_node.name,
                            "type": p_node.type.value,
                            "file_path": p_node.file_path,
                            "line": p_node.start_line,
                            "confidence": e_data.get("confidence", 1.0),
                        }

                        if rel == RelationshipType.CALLS.value:
                            direct_callers.append(item)
                        elif rel == RelationshipType.INHERITS.value:
                            inheriting_classes.append(item)
                        else:
                            direct_dependents.append(item)

                    target_node = self._node_from_data(node_id, g.nodes[node_id], repo_id)
                    if target_node.file_path:
                        affected_files.add(target_node.file_path)

                    for imp_id in impacted_nodes:
                        if imp_id in g:
                            imp_node = self._node_from_data(imp_id, g.nodes[imp_id], repo_id)
                            if imp_node.file_path:
                                affected_files.add(imp_node.file_path)

                    return {
                        "target_node_id": node_id,
                        "target_name": target_node.name,
                        "target_type": target_node.type.value,
                        "depth": depth,
                        "total_impacted_symbols": len(impacted_nodes),
                        "total_affected_files": len(affected_files),
                        "affected_files": sorted(list(affected_files)),
                        "direct_callers": direct_callers,
                        "direct_dependents": direct_dependents,
                        "inheriting_classes": inheriting_classes,
                        "all_impacted_node_ids": sorted(list(impacted_nodes)),
                    }

            return {
                "target_node_id": node_id,
                "error": "Node not found in graph.",
                "total_impacted_symbols": 0,
                "total_affected_files": 0,
                "affected_files": [],
                "direct_callers": [],
                "direct_dependents": [],
                "inheriting_classes": [],
                "all_impacted_node_ids": [],
            }

    def get_stats(self, repository_id: str) -> Dict[str, Any]:
        """Get graph statistics (node counts, edge counts, density, type breakdowns)."""
        with self._lock:
            graph = self._get_or_create_graph(repository_id)

            node_type_counts: Dict[str, int] = {}
            for _, d in graph.nodes(data=True):
                nt = d.get("type", "Unknown")
                node_type_counts[nt] = node_type_counts.get(nt, 0) + 1

            rel_type_counts: Dict[str, int] = {}
            confirmed_count = 0
            inferred_count = 0
            for _, _, d in graph.edges(data=True):
                rt = d.get("relationship", "Unknown")
                rel_type_counts[rt] = rel_type_counts.get(rt, 0) + 1
                if d.get("is_confirmed", True):
                    confirmed_count += 1
                else:
                    inferred_count += 1

            n = graph.number_of_nodes()
            e = graph.number_of_edges()
            density = nx.density(graph) if n > 1 else 0.0

            safe_fn = sanitize_filename(repository_id)
            p_file = self.persist_dir / f"{safe_fn}.json"

            return {
                "repository_id": repository_id,
                "total_nodes": n,
                "total_edges": e,
                "graph_density": round(float(density), 5),
                "is_persisted": p_file.exists(),
                "node_types": node_type_counts,
                "relationship_types": rel_type_counts,
                "confirmed_edges": confirmed_count,
                "inferred_edges": inferred_count,
            }

    def save(self, repository_id: str) -> None:
        """Persist graph representation to atomic JSON file using safe node-link format."""
        with self._lock:
            if repository_id not in self._graphs:
                logger.warning(f"No in-memory graph found for repo '{repository_id}' to save.")
                return

            graph = self._graphs[repository_id]
            safe_fn = sanitize_filename(repository_id)
            target_path = self.persist_dir / f"{safe_fn}.json"
            tmp_path = self.persist_dir / f"{safe_fn}.json.tmp"

            # Node-link representation
            link_data = nx.node_link_data(graph, edges="edges")
            payload = {
                "repository_id": repository_id,
                "version": "1.0",
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "graph": link_data,
            }

            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                # Atomic rename
                os.replace(tmp_path, target_path)
                logger.info(
                    f"Successfully saved knowledge graph for '{repository_id}' ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges) to {target_path}"
                )
            except Exception as e:
                logger.error(f"Failed to persist graph for '{repository_id}': {e}")
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
                raise

    def load(self, repository_id: str) -> bool:
        """Load persisted graph from storage file with error handling."""
        with self._lock:
            safe_fn = sanitize_filename(repository_id)
            target_path = self.persist_dir / f"{safe_fn}.json"

            if not target_path.exists():
                return False

            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                if "graph" not in payload:
                    logger.error(f"Invalid graph file structure in {target_path}")
                    return False

                g = nx.node_link_graph(payload["graph"], directed=True, multigraph=False, edges="edges")
                self._graphs[repository_id] = g
                self._rebuild_indices(repository_id)
                logger.info(
                    f"Loaded knowledge graph for '{repository_id}' ({g.number_of_nodes()} nodes, {g.number_of_edges()} edges) from {target_path}"
                )
                return True
            except Exception as e:
                logger.error(f"Failed to load graph for '{repository_id}' from {target_path}: {e}")
                return False

    def delete(self, repository_id: str) -> bool:
        """Delete persisted graph for a repository and purge from memory."""
        with self._lock:
            if repository_id in self._graphs:
                del self._graphs[repository_id]
            self._name_index.pop(repository_id, None)
            self._qualified_name_index.pop(repository_id, None)

            safe_fn = sanitize_filename(repository_id)
            target_path = self.persist_dir / f"{safe_fn}.json"
            if target_path.exists():
                try:
                    target_path.unlink()
                    logger.info(f"Deleted graph file {target_path}")
                    return True
                except OSError as e:
                    logger.error(f"Failed to delete graph file {target_path}: {e}")
                    return False
            return False


# Global singleton instance
networkx_graph_store = NetworkXGraphStore()
