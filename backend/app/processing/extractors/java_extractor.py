"""
Java AST symbol extractor using Tree-sitter.
Extracts classes, interfaces, records, enums, methods, constructors, imports, inheritance, and calls.
"""

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
from backend.app.processing.extractors.base import BaseExtractor


class JavaExtractor(BaseExtractor):
    """
    Extracts structured symbols and relations from Java ASTs.
    """

    def __init__(self) -> None:
        super().__init__("java")

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
        calls: List[ExtractedCall] = []
        inheritances: List[ExtractedInheritance] = []
        comments: List[ExtractedComment] = []

        line_count = len(source_bytes.split(b"\n"))
        size_bytes = len(source_bytes)
        syntax_errors = self.collect_syntax_errors(root_node)

        def _traverse(
            node: tree_sitter.Node,
            parent_class_id: Optional[str] = None,
            parent_class_name: Optional[str] = None,
            enclosing_callable_id: Optional[str] = None,
            depth: int = 0,
        ):
            if depth > 100:
                return

            node_type = node.type

            # Imports: import java.util.List;
            if node_type == "import_declaration":
                raw_stmt = self.get_text(node, source_bytes).strip()
                loc = self.get_location(node, file_path)
                scoped_id = self.find_first_child(node, "scoped_identifier")
                identifier = self.find_first_child(node, "identifier")
                target = scoped_id or identifier
                mod_name = self.get_text(target, source_bytes).strip() if target else raw_stmt
                imports.append(
                    ExtractedImport(
                        module=mod_name,
                        imported_symbols=[mod_name.split(".")[-1]],
                        location=loc,
                        raw_statement=raw_stmt,
                    )
                )
                return

            # Comments & Javadoc
            elif node_type in ("comment", "block_comment", "line_comment"):
                comment_text = self.get_text(node, source_bytes).strip()
                is_javadoc = comment_text.startswith("/**")
                comments.append(
                    ExtractedComment(
                        content=comment_text,
                        location=self.get_location(node, file_path),
                        is_docstring=is_javadoc,
                        associated_symbol_id=enclosing_callable_id or parent_class_id,
                    )
                )

            # Class / Interface / Record / Enum declarations
            elif node_type in ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration"):
                type_symbol = self._handle_type_declaration(
                    node,
                    source_bytes,
                    file_path,
                    repo_id,
                    parent_class_name,
                    symbols,
                    inheritances,
                )
                if type_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        for child in body.children:
                            _traverse(
                                child,
                                parent_class_id=type_symbol.symbol_id,
                                parent_class_name=type_symbol.name,
                                depth=depth + 1,
                            )
                return

            # Methods & Constructors
            elif node_type in ("method_declaration", "constructor_declaration"):
                method_symbol = self._handle_method(
                    node,
                    source_bytes,
                    file_path,
                    repo_id,
                    parent_class_id,
                    parent_class_name,
                    symbols,
                )
                if method_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        for child in body.children:
                            _traverse(
                                child,
                                parent_class_id=parent_class_id,
                                parent_class_name=parent_class_name,
                                enclosing_callable_id=method_symbol.symbol_id,
                                depth=depth + 1,
                            )
                return

            # Method invocations: obj.method()
            elif node_type == "method_invocation":
                self._handle_call(node, source_bytes, file_path, enclosing_callable_id, calls)

            # Default recursive traversal
            for child in node.children:
                _traverse(
                    child,
                    parent_class_id=parent_class_id,
                    parent_class_name=parent_class_name,
                    enclosing_callable_id=enclosing_callable_id,
                    depth=depth + 1,
                )

        _traverse(root_node)

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

    def _handle_type_declaration(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        parent_class_name: Optional[str],
        symbols: List[ExtractedSymbol],
        inheritances: List[ExtractedInheritance],
    ) -> Optional[ExtractedSymbol]:
        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return None

        type_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        if node.type == "interface_declaration":
            symbol_type = SymbolType.INTERFACE
        elif node.type == "enum_declaration":
            symbol_type = SymbolType.ENUM
        else:
            symbol_type = SymbolType.CLASS

        symbol_id = self.generate_symbol_id(
            repo_id, file_path, type_name, symbol_type.value, loc.start_line, parent_class_name
        )

        # Modifiers
        modifiers: List[str] = []
        mod_node = self.find_first_child(node, "modifiers")
        if mod_node:
            modifiers = [self.get_text(c, source_bytes).strip() for c in mod_node.children]

        # Superclass (extends)
        superclass_node = self.find_first_child(node, "superclass")
        base_classes: List[str] = []
        if superclass_node:
            for child in superclass_node.children:
                if child.type in ("type_identifier", "scoped_type_identifier"):
                    super_name = self.get_text(child, source_bytes).strip()
                    base_classes.append(super_name)
                    inheritances.append(
                        ExtractedInheritance(
                            sub_symbol_id=symbol_id,
                            super_name=super_name,
                            relationship="INHERITS",
                        )
                    )

        # Super-interfaces (implements)
        super_ifaces = self.find_first_child(node, "super_interfaces")
        if super_ifaces:
            type_list = self.find_first_child(super_ifaces, "type_list") or super_ifaces
            for child in type_list.children:
                if child.type in ("type_identifier", "scoped_type_identifier"):
                    iface_name = self.get_text(child, source_bytes).strip()
                    inheritances.append(
                        ExtractedInheritance(
                            sub_symbol_id=symbol_id,
                            super_name=iface_name,
                            relationship="IMPLEMENTS",
                        )
                    )

        source_code = self.get_text(node, source_bytes)
        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=type_name,
            symbol_type=symbol_type,
            location=loc,
            source_code=source_code,
            modifiers=modifiers,
            properties={"base_classes": base_classes},
        )
        symbols.append(symbol)
        return symbol

    def _handle_method(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        parent_class_id: Optional[str],
        parent_class_name: Optional[str],
        symbols: List[ExtractedSymbol],
    ) -> Optional[ExtractedSymbol]:
        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return None

        method_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)
        symbol_id = self.generate_symbol_id(
            repo_id, file_path, method_name, "METHOD", loc.start_line, parent_class_name
        )

        parameters: List[str] = []
        params_node = self.find_child_by_field(node, "parameters")
        if params_node:
            for child in params_node.children:
                if child.type == "formal_parameter":
                    param_text = self.get_text(child, source_bytes).strip()
                    if param_text:
                        parameters.append(param_text)

        return_type = None
        type_node = self.find_child_by_field(node, "type")
        if type_node:
            return_type = self.get_text(type_node, source_bytes).strip()

        modifiers: List[str] = []
        mod_node = self.find_first_child(node, "modifiers")
        if mod_node:
            modifiers = [self.get_text(c, source_bytes).strip() for c in mod_node.children]

        source_code = self.get_text(node, source_bytes)
        first_line = source_code.split("\n")[0].strip()

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=method_name,
            symbol_type=SymbolType.METHOD,
            location=loc,
            source_code=source_code,
            parent_symbol_id=parent_class_id,
            signature=first_line,
            return_type=return_type,
            parameters=parameters,
            modifiers=modifiers,
        )
        symbols.append(symbol)
        return symbol

    def _handle_call(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        enclosing_callable_id: Optional[str],
        calls: List[ExtractedCall],
    ) -> None:
        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return

        callee_name = self.get_text(name_node, source_bytes).strip()
        obj_node = self.find_child_by_field(node, "object")
        receiver = self.get_text(obj_node, source_bytes).strip() if obj_node else None

        calls.append(
            ExtractedCall(
                caller_symbol_id=enclosing_callable_id,
                callee_name=callee_name,
                receiver=receiver,
                location=self.get_location(node, file_path),
                is_confirmed=False,
            )
        )

