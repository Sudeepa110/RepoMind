"""
Unit tests for shared pipeline adapters (Vector RAG and GraphRAG).
Verifies that ParsedRepository seamlessly translates into:
  1. GraphNode and GraphEdge collections for GraphRAG
  2. Structure-aware code chunks for Vector RAG
"""

import pytest
from backend.app.processing.engine import code_engine
from backend.app.processing.models import ParsedRepository
from backend.app.processing.adapters import to_graph_elements, to_code_chunks
from backend.app.graph.interfaces import NodeType, RelationshipType


def test_adapters_pipeline_transformation():
    py_code = """
import math

class Geometry:
    \"\"\"Geometry utility class.\"\"\"
    def circle_area(self, radius: float) -> float:
        \"\"\"Compute area.\"\"\"
        return math.pi * radius * radius

def compute(r: float) -> float:
    g = Geometry()
    return g.circle_area(r)
"""
    parsed_file = code_engine.parse_source_code(py_code, "math/geo.py", "org/repo")
    assert parsed_file is not None

    parsed_repo = ParsedRepository(
        repository_id="org/repo",
        commit_hash="abc1234",
        files={"math/geo.py": parsed_file},
        total_symbols=len(parsed_file.symbols),
        total_files=1,
        supported_languages=["python"],
    )

    # 1. Test GraphRAG Adapter
    nodes, edges = to_graph_elements(parsed_repo)
    assert len(nodes) >= 4  # Repo, File, Class, 2 Functions/Methods
    assert len(edges) >= 3

    # Check node types
    node_types = {n.type for n in nodes}
    assert NodeType.REPOSITORY in node_types
    assert NodeType.FILE in node_types
    assert NodeType.CLASS in node_types
    assert NodeType.METHOD in node_types
    assert NodeType.FUNCTION in node_types

    # Check edge relationships
    edge_rels = {e.relationship for e in edges}
    assert RelationshipType.CONTAINS in edge_rels
    assert RelationshipType.IMPORTS in edge_rels

    # 2. Test Vector RAG Adapter
    chunks = to_code_chunks(parsed_repo)
    assert len(chunks) == len(parsed_file.symbols)
    for chunk in chunks:
        assert "chunk_id" in chunk
        assert "content" in chunk
        assert "metadata" in chunk
        meta = chunk["metadata"]
        assert meta["repository_id"] == "org/repo"
        assert meta["file_path"] == "math/geo.py"
        assert meta["start_line"] > 0
        assert meta["end_line"] >= meta["start_line"]
        assert "symbol_name" in meta
        assert "symbol_type" in meta

