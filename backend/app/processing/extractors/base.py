"""
Base extractor interface and common AST utilities for Tree-sitter symbol extraction.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import tree_sitter

from backend.app.processing.models import (
    ParsedFile,
    ExtractedSymbol,
    ExtractedImport,
    ExtractedCall,
    ExtractedInheritance,
    ExtractedComment,
    SymbolLocation,
    SymbolType,
)


class BaseExtractor(ABC):
    """
    Abstract base class for AST symbol extractors.
    All language extractors inherit from this and implement language-specific traversal.
    """

    def __init__(self, language: str) -> None:
        self.language = language

    @abstractmethod
    def extract(
        self,
        root_node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        commit_hash: Optional[str] = None,
    ) -> ParsedFile:
        """Extract structured symbols, imports, calls, and comments from the AST."""
        pass

    @staticmethod
    def get_text(node: tree_sitter.Node, source_bytes: bytes) -> str:
        """Extract UTF-8 text for a node from the source bytes."""
        try:
            return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        except Exception:
            return ""

    @staticmethod
    def get_location(node: tree_sitter.Node, file_path: str) -> SymbolLocation:
        """Convert Tree-sitter 0-indexed points to 1-indexed line locations."""
        return SymbolLocation(
            file_path=file_path,
            start_line=node.start_point.row + 1,
            end_line=node.end_point.row + 1,
            start_column=node.start_point.column,
            end_column=node.end_point.column,
        )

    @staticmethod
    def generate_symbol_id(
        repo_id: str,
        file_path: str,
        name: str,
        symbol_type: str,
        start_line: int,
        parent_name: Optional[str] = None,
    ) -> str:
        """
        Generate a globally unique, deterministic identifier for a code symbol.
        Format: {repo_id}:{file_path}#{parent_name.}{name}:{start_line}
        """
        prefix = f"{parent_name}." if parent_name else ""
        clean_file = file_path.replace("\\", "/")
        return f"{repo_id}:{clean_file}#{prefix}{name}:{start_line}"

    @staticmethod
    def find_child_by_field(node: tree_sitter.Node, field_name: str) -> Optional[tree_sitter.Node]:
        """Find a named field on a node if provided by the grammar."""
        try:
            return node.child_by_field_name(field_name)
        except Exception:
            return None

    @staticmethod
    def find_first_child(node: tree_sitter.Node, child_type: str) -> Optional[tree_sitter.Node]:
        """Find the first direct child matching the given node type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    @staticmethod
    def find_children(node: tree_sitter.Node, child_type: str) -> List[tree_sitter.Node]:
        """Find all direct children matching the given node type."""
        return [c for c in node.children if c.type == child_type]

    @staticmethod
    def collect_syntax_errors(node: tree_sitter.Node, max_errors: int = 10) -> List[str]:
        """Find any ERROR or MISSING nodes in the AST for diagnostic tracking."""
        errors: List[str] = []

        def _traverse(n: tree_sitter.Node):
            if len(errors) >= max_errors:
                return
            if n.type == "ERROR":
                errors.append(f"Syntax error at line {n.start_point.row + 1}, column {n.start_point.column}")
            elif n.is_missing:
                errors.append(f"Missing syntax element at line {n.start_point.row + 1}, column {n.start_point.column}")
            for c in n.children:
                _traverse(c)

        _traverse(node)
        return errors

