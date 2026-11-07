"""
Base extractor interface and common AST utilities for Tree-sitter symbol extraction.
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from collections import defaultdict
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
    def compute_content_hash(source_code: str) -> str:
        """
        Computes a deterministic SHA-256 content fingerprint of normalized source code.
        Normalizes line endings and whitespace to detect semantic code modifications.
        """
        normalized = source_code.strip().replace("\r\n", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def generate_symbol_id(
        repo_id: str,
        file_path: str,
        name: str,
        symbol_type: str,
        parent_scope: Optional[str] = None,
        disambiguation_idx: int = 0,
    ) -> str:
        """
        Generate a stable, deterministic identifier for a code symbol.
        Format: {repo_id}:{file_path}#{parent_scope.}{name}
        Overloaded symbols in the same scope use: ::{disambiguation_idx}

        IMPORTANT: Line numbers are intentionally omitted from symbol IDs.
        Line numbers are source location metadata, not identity. This guarantees that
        inserting unrelated code or comments above a symbol does not alter its ID,
        preserving vector chunk cache hits, graph stability, and commit diffing.
        """
        prefix = f"{parent_scope}." if parent_scope else ""
        clean_file = file_path.replace("\\", "/")
        disambig = f"::{disambiguation_idx}" if disambiguation_idx > 0 else ""
        return f"{repo_id}:{clean_file}#{prefix}{name}{disambig}"

    @classmethod
    def get_scoped_symbol_id(
        cls,
        repo_id: str,
        file_path: str,
        name: str,
        symbol_type: str,
        parent_scope: Optional[str],
        name_counts: Dict[str, int],
    ) -> str:
        """Generates a stable symbol ID and applies deterministic disambiguation for overloads."""
        qual_key = f"{parent_scope}.{name}" if parent_scope else name
        idx = name_counts[qual_key]
        name_counts[qual_key] += 1
        return cls.generate_symbol_id(
            repo_id=repo_id,
            file_path=file_path,
            name=name,
            symbol_type=symbol_type,
            parent_scope=parent_scope,
            disambiguation_idx=idx,
        )

    @staticmethod
    def classify_call_resolution(
        callee_name: str,
        receiver: Optional[str],
        local_symbols: set[str],
        imported_symbols: set[str],
        is_constructor: bool = False,
    ) -> tuple[bool, str]:
        """
        Classifies static call resolution into CONFIRMED, INFERRED, or UNRESOLVED.
        Returns: (is_confirmed: bool, resolution_status: str)
        """
        # 1. Constructor for a local class
        if is_constructor and callee_name in local_symbols:
            return True, "CONFIRMED"

        # 2. Confirmed local function / method
        if callee_name in local_symbols:
            return True, "CONFIRMED"

        # 3. Method on self / this matching a local symbol
        if receiver in ("self", "this") and callee_name in local_symbols:
            return True, "CONFIRMED"

        # 4. Direct call to an explicitly imported function
        if callee_name in imported_symbols:
            return True, "CONFIRMED"

        # 5. Method on an imported module/object (e.g. math.sqrt, logger.info)
        if receiver in imported_symbols:
            return False, "INFERRED"

        # 6. Built-in or standard library functions
        common_builtins = {
            "print", "println", "Printf", "Sprintf", "len", "range", "min", "max",
            "str", "int", "float", "bool", "dict", "list", "set", "tuple",
            "console", "Math", "JSON", "parseInt", "parseFloat",
            "System", "String", "Integer", "Boolean",
            "sizeof", "malloc", "free", "memcpy", "memset",
        }
        if callee_name in common_builtins or receiver in common_builtins:
            return False, "INFERRED"

        # 7. Receiver exists but is an arbitrary dynamic variable
        if receiver:
            return False, "INFERRED"

        # 8. Unresolved dynamic call (callback, argument parameter, indirect invocation)
        return False, "UNRESOLVED"

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
