"""
Dependency & Architecture Intelligence Analyzer (Phase 8).
Calculates structural coupling metrics (in-degree, out-degree, Robert C. Martin's instability metric),
identifies tightly coupled modules and cyclic dependencies, maps external libraries,
and assigns architectural layers.
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict

from backend.app.graph.interfaces import (
    BaseGraphStore,
    GraphNode,
    RelationshipType,
    NodeType,
)
from backend.app.graph.networkx_store import networkx_graph_store
from backend.app.intelligence.intelligence_models import (
    DependencyCouplingMetric,
    DependencyAnalysisResult,
)
from backend.app.llm.citation_validator import CitationValidator
from backend.app.retrieval.retrieval_models import UnifiedSearchResult

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """
    Analyzes architectural dependencies, component coupling, and package boundaries.
    """

    def __init__(
        self,
        store: Optional[BaseGraphStore] = None,
        validator: Optional[CitationValidator] = None,
    ):
        self.store = store or networkx_graph_store
        self.validator = validator or CitationValidator()

    def _infer_layer(self, file_path: str) -> str:
        """Categorizes a file into architectural layers based on repository layout conventions."""
        p = file_path.lower().replace("\\", "/")
        if any(k in p for k in ["/api/", "routes", "endpoints", "controllers", "views"]):
            return "API"
        if any(k in p for k in ["/services/", "service", "usecase", "interactor"]):
            return "SERVICE"
        if any(k in p for k in ["/database/", "/db/", "/vectorstore/", "/graph/", "storage"]):
            return "DATA"
        if any(k in p for k in ["/models/", "/schemas/", "entities", "dtos"]):
            return "MODEL"
        if any(k in p for k in ["/utils/", "/helpers/", "/common/", "validators", "formatters"]):
            return "UTIL"
        if any(k in p for k in ["/core/", "config", "settings"]):
            return "CORE"
        return "DOMAIN"

    def analyze(self, repository_id: str) -> DependencyAnalysisResult:
        """
        Computes repository-wide dependency graph metrics and coupling indices.
        """
        # Retrieve all file nodes or nodes with file_path
        all_nodes = self.store.get_nodes(repository_id, limit=2000)

        # Collect distinct files and their child symbols
        files_to_nodes: Dict[str, List[GraphNode]] = defaultdict(list)
        node_id_to_file: Dict[str, str] = {}

        for n in all_nodes:
            if n.file_path:
                norm_path = n.file_path.replace("\\", "/")
                files_to_nodes[norm_path].append(n)
                node_id_to_file[n.id] = norm_path

        # If file nodes exist directly
        file_nodes = self.store.get_nodes(repository_id, node_type=NodeType.FILE, limit=1000)
        for fn in file_nodes:
            path = fn.file_path or fn.name
            norm_path = path.replace("\\", "/")
            if norm_path not in files_to_nodes:
                files_to_nodes[norm_path] = [fn]
            node_id_to_file[fn.id] = norm_path

        # File-to-file dependency edges
        file_out_deps: Dict[str, Set[str]] = defaultdict(set)
        file_in_deps: Dict[str, Set[str]] = defaultdict(set)
        external_libraries: Set[str] = set()

        all_edges = self.store.get_edges(repository_id, limit=10000)

        for edge in all_edges:
            src_file = node_id_to_file.get(edge.source_id)
            tgt_file = node_id_to_file.get(edge.target_id)

            if edge.relationship in (RelationshipType.IMPORTS, RelationshipType.DEPENDS_ON, RelationshipType.CALLS):
                if edge.target_id.startswith("ext:"):
                    ext_name = edge.target_id.replace("ext:", "").split(":")[0]
                    external_libraries.add(ext_name)

                if src_file and tgt_file and src_file != tgt_file:
                    file_out_deps[src_file].add(tgt_file)
                    file_in_deps[tgt_file].add(src_file)

        # Compute coupling metrics for each file
        file_metrics: List[DependencyCouplingMetric] = []
        layer_dist: Dict[str, int] = defaultdict(int)
        total_instability = 0.0

        for file_path, nodes in files_to_nodes.items():
            in_degree = len(file_in_deps[file_path])
            out_degree = len(file_out_deps[file_path])
            denominator = in_degree + out_degree
            instability = round(out_degree / denominator, 3) if denominator > 0 else 0.0
            total_instability += instability

            is_tight = False
            # Check for circular/tight coupling with any dependent
            for dep in file_out_deps[file_path]:
                if file_path in file_out_deps.get(dep, set()):
                    is_tight = True
                    break

            layer = self._infer_layer(file_path)
            layer_dist[layer] += 1

            # Extract module name from file path
            module_name = file_path.split("/")[-1].replace(".py", "").replace(".ts", "").replace(".js", "")

            # External libraries used directly in file
            file_ext_libs = [
                lib for lib in external_libraries
                if any(lib.lower() in (n.properties.get("imports") or []) for n in nodes)
            ]

            file_metrics.append(DependencyCouplingMetric(
                file_path=file_path,
                module_name=module_name,
                in_degree=in_degree,
                out_degree=out_degree,
                instability=instability,
                is_tightly_coupled=is_tight,
                direct_dependencies=sorted(list(file_out_deps[file_path])),
                direct_dependents=sorted(list(file_in_deps[file_path])),
                external_libraries=sorted(file_ext_libs),
                layer=layer,
            ))

        # Identify tightly coupled pairs (bidirectional references)
        tightly_coupled_pairs: List[Dict[str, Any]] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        for f1 in files_to_nodes:
            for f2 in file_out_deps[f1]:
                if f1 in file_out_deps.get(f2, set()):
                    pair_key = tuple(sorted([f1, f2]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        tightly_coupled_pairs.append({
                            "module_a": f1,
                            "module_b": f2,
                            "nature": "Bidirectional cross-file dependency",
                        })

        total_files = len(files_to_nodes)
        avg_instability = round(total_instability / max(1, total_files), 3)

        # Generate summary
        summary = (
            f"Analyzed {total_files} file(s) across {len(layer_dist)} architectural layers. "
            f"Average Martin's instability metric is {avg_instability:.2f}. "
            f"Detected {len(tightly_coupled_pairs)} tightly coupled bidirectional relationship(s) "
            f"and {len(external_libraries)} external package dependencies."
        )

        return DependencyAnalysisResult(
            total_files=total_files,
            total_modules=total_files,
            average_instability=avg_instability,
            tightly_coupled_pairs=tightly_coupled_pairs,
            file_metrics=sorted(file_metrics, key=lambda m: (m.in_degree + m.out_degree), reverse=True),
            external_libraries=sorted(list(external_libraries)),
            layer_distribution=dict(layer_dist),
            summary=summary,
            citations=[],
        )


dependency_analyzer = DependencyAnalyzer()
