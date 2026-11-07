"""
C and C++ AST symbol extractor using Tree-sitter.
Extracts functions, methods, classes, structs, headers/includes, inheritance,
constructor calls (new_expression), and regular calls.
Supports nesting and stable deterministic symbol IDs.
"""

from typing import Optional, List, Dict, Any, Set
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
from backend.app.processing.extractors.base import BaseExtractor


class CCppExtractor(BaseExtractor):
    """
    Extracts structured symbols and relations from C and C++ ASTs.
    """

    def __init__(self, language: str = "cpp") -> None:
        super().__init__(language)

    def extract(
        self,
        root_node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        commit_hash: Optional[str] = None,
    ) -> ParsedFile:
        symbols: List[ExtractedSymbol] = []
        imports: List[ExtractedImport] = []
        raw_calls: List[dict] = []
        inheritances: List[ExtractedInheritance] = []
        comments: List[ExtractedComment] = []
        name_counts: Dict[str, int] = defaultdict(int)

        line_count = len(source_bytes.split(b"\n"))
        size_bytes = len(source_bytes)
        syntax_errors = self.collect_syntax_errors(root_node)

        def _traverse(
            node: tree_sitter.Node,
            parent_scope_id: Optional[str] = None,
            parent_scope_name: Optional[str] = None,
            enclosing_callable_id: Optional[str] = None,
            is_inside_class: bool = False,
            depth: int = 0,
        ):
            if depth > 100:
                return

            node_type = node.type

            # Includes: #include <stdio.h> or #include "header.h"
            if node_type == "preproc_include":
                raw_stmt = self.get_text(node, source_bytes).strip()
                path_node = self.find_child_by_field(node, "path")
                if path_node:
                    include_path = self.get_text(path_node, source_bytes).strip('<>"')
                    is_rel = not self.get_text(path_node, source_bytes).startswith("<")
                    imports.append(
                        ExtractedImport(
                            module=include_path,
                            imported_symbols=[include_path],
                            is_relative=is_rel,
                            location=self.get_location(node, file_path),
                            raw_statement=raw_stmt,
                        )
                    )
                return

            # Comments
            elif node_type == "comment":
                comment_text = self.get_text(node, source_bytes).strip()
                comments.append(
                    ExtractedComment(
                        content=comment_text,
                        location=self.get_location(node, file_path),
                        is_docstring=comment_text.startswith("/**"),
                        associated_symbol_id=enclosing_callable_id or parent_scope_id,
                    )
                )

            # Class or Struct specifiers
            elif node_type in ("class_specifier", "struct_specifier"):
                type_symbol = self._handle_class_or_struct(
                    node,
                    source_bytes,
                    file_path,
                    repo_id,
                    parent_scope_id,
                    parent_scope_name,
                    symbols,
                    inheritances,
                    name_counts,
                )
                if type_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        nested_scope = (
                            f"{parent_scope_name}.{type_symbol.name}"
                            if parent_scope_name
                            else type_symbol.name
                        )
                        for child in body.children:
                            _traverse(
                                child,
                                parent_scope_id=type_symbol.symbol_id,
                                parent_scope_name=nested_scope,
                                enclosing_callable_id=None,
                                is_inside_class=True,
                                depth=depth + 1,
                            )
                return

            # Functions / Methods
            elif node_type == "function_definition":
                func_symbol = self._handle_function_definition(
                    node,
                    source_bytes,
                    file_path,
                    repo_id,
                    parent_scope_id,
                    parent_scope_name,
                    is_inside_class,
                    symbols,
                    name_counts,
                )
                if func_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        nested_scope = (
                            f"{parent_scope_name}.{func_symbol.name}"
                            if parent_scope_name
                            else func_symbol.name
                        )
                        for child in body.children:
                            _traverse(
                                child,
                                parent_scope_id=func_symbol.symbol_id,
                                parent_scope_name=nested_scope,
                                enclosing_callable_id=func_symbol.symbol_id,
                                is_inside_class=False,
                                depth=depth + 1,
                            )
                return

            # Call expressions
            elif node_type == "call_expression":
                self._handle_call(node, source_bytes, file_path, enclosing_callable_id, raw_calls)

            # C++ new expressions: new Vector3D(...)
            elif node_type == "new_expression":
                self._handle_new_expression(node, source_bytes, file_path, enclosing_callable_id, raw_calls)

            # Default recursive traversal
            for child in node.children:
                _traverse(
                    child,
                    parent_scope_id=parent_scope_id,
                    parent_scope_name=parent_scope_name,
                    enclosing_callable_id=enclosing_callable_id,
                    is_inside_class=is_inside_class,
                    depth=depth + 1,
                )

        _traverse(root_node)

        # Post-traversal resolution: Classify call confirmation status
        local_symbol_names: Set[str] = {s.name for s in symbols}
        imported_symbol_names: Set[str] = {imp.module for imp in imports}

        calls: List[ExtractedCall] = []
        for rc in raw_calls:
            is_confirmed, res_status = self.classify_call_resolution(
                callee_name=rc["callee_name"],
                receiver=rc["receiver"],
                local_symbols=local_symbol_names,
                imported_symbols=imported_symbol_names,
                is_constructor=rc.get("is_constructor", False),
            )
            calls.append(
                ExtractedCall(
                    caller_symbol_id=rc["caller_symbol_id"],
                    callee_name=rc["callee_name"],
                    receiver=rc["receiver"],
                    location=rc["location"],
                    is_confirmed=is_confirmed,
                    resolution_status=res_status,
                    is_constructor=rc.get("is_constructor", False),
                )
            )

        return ParsedFile(
            file_path=file_path,
            repository_id=repo_id,
            language=self.language,
            commit_hash=commit_hash,
            symbols=symbols,
            imports=imports,
            calls=calls,
            inheritances=inheritances,
            comments=comments,
            syntax_errors=syntax_errors,
            line_count=line_count,
            size_bytes=size_bytes,
        )

    def _handle_class_or_struct(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        parent_scope_id: Optional[str],
        parent_scope_name: Optional[str],
        symbols: List[ExtractedSymbol],
        inheritances: List[ExtractedInheritance],
        name_counts: Dict[str, int],
    ) -> Optional[ExtractedSymbol]:
        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return None

        type_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)
        sym_type = SymbolType.STRUCT if node.type == "struct_specifier" else SymbolType.CLASS

        symbol_id = self.get_scoped_symbol_id(
            repo_id=repo_id,
            file_path=file_path,
            name=type_name,
            symbol_type=sym_type.value,
            parent_scope=parent_scope_name,
            name_counts=name_counts,
        )

        base_classes: List[str] = []
        base_clause = self.find_first_child(node, "base_class_clause")
        if base_clause:
            for child in base_clause.children:
                if child.type == "type_identifier":
                    b_name = self.get_text(child, source_bytes).strip()
                    base_classes.append(b_name)
                    inheritances.append(
                        ExtractedInheritance(
                            sub_symbol_id=symbol_id,
                            super_name=b_name,
                            relationship="INHERITS",
                            is_confirmed=False,
                        )
                    )

        source_code = self.get_text(node, source_bytes)
        content_hash = self.compute_content_hash(source_code)
        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=type_name,
            symbol_type=sym_type,
            location=loc,
            source_code=source_code,
            content_hash=content_hash,
            parent_symbol_id=parent_scope_id,
            properties={"base_classes": base_classes},
        )
        symbols.append(symbol)
        return symbol

    def _handle_function_definition(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        parent_scope_id: Optional[str],
        parent_scope_name: Optional[str],
        is_inside_class: bool,
        symbols: List[ExtractedSymbol],
        name_counts: Dict[str, int],
    ) -> Optional[ExtractedSymbol]:
        declarator = self.find_child_by_field(node, "declarator")
        if not declarator:
            return None

        func_decl = declarator
        while func_decl and func_decl.type != "function_declarator":
            nested = self.find_first_child(func_decl, "function_declarator")
            if nested:
                func_decl = nested
                break
            child_decl = self.find_child_by_field(func_decl, "declarator")
            if not child_decl:
                break
            func_decl = child_decl

        name_node = self.find_child_by_field(func_decl, "declarator") if func_decl else None
        if not name_node:
            name_node = self.find_first_child(func_decl or declarator, "identifier")

        if not name_node:
            return None

        func_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        is_method = is_inside_class or "::" in func_name
        sym_type = SymbolType.METHOD if is_method else SymbolType.FUNCTION

        symbol_id = self.get_scoped_symbol_id(
            repo_id=repo_id,
            file_path=file_path,
            name=func_name,
            symbol_type=sym_type.value,
            parent_scope=parent_scope_name,
            name_counts=name_counts,
        )

        parameters: List[str] = []
        params_node = self.find_child_by_field(func_decl or declarator, "parameters")
        if params_node:
            for child in params_node.children:
                if child.type == "parameter_declaration":
                    p_text = self.get_text(child, source_bytes).strip()
                    if p_text:
                        parameters.append(p_text)

        return_type = None
        type_node = self.find_child_by_field(node, "type")
        if type_node:
            return_type = self.get_text(type_node, source_bytes).strip()

        source_code = self.get_text(node, source_bytes)
        content_hash = self.compute_content_hash(source_code)
        first_line = source_code.split("\n")[0].strip()

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=func_name,
            symbol_type=sym_type,
            location=loc,
            source_code=source_code,
            content_hash=content_hash,
            parent_symbol_id=parent_scope_id,
            signature=first_line,
            return_type=return_type,
            parameters=parameters,
        )
        symbols.append(symbol)
        return symbol

    def _handle_call(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        enclosing_callable_id: Optional[str],
        raw_calls: List[dict],
    ) -> None:
        func_node = self.find_child_by_field(node, "function")
        if not func_node:
            return

        loc = self.get_location(node, file_path)
        callee_name = ""
        receiver = None

        if func_node.type == "identifier":
            callee_name = self.get_text(func_node, source_bytes).strip()
        elif func_node.type == "field_expression":
            arg_node = self.find_child_by_field(func_node, "argument")
            field_node = self.find_child_by_field(func_node, "field")
            if field_node:
                callee_name = self.get_text(field_node, source_bytes).strip()
            if arg_node:
                receiver = self.get_text(arg_node, source_bytes).strip()
        else:
            callee_name = self.get_text(func_node, source_bytes).strip()

        if callee_name:
            raw_calls.append({
                "caller_symbol_id": enclosing_callable_id,
                "callee_name": callee_name,
                "receiver": receiver,
                "location": loc,
                "is_constructor": False,
            })

    def _handle_new_expression(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        enclosing_callable_id: Optional[str],
        raw_calls: List[dict],
    ) -> None:
        type_node = self.find_child_by_field(node, "type")
        if not type_node:
            return

        callee_name = self.get_text(type_node, source_bytes).strip()
        raw_calls.append({
            "caller_symbol_id": enclosing_callable_id,
            "callee_name": callee_name,
            "receiver": None,
            "location": self.get_location(node, file_path),
            "is_constructor": True,
        })
