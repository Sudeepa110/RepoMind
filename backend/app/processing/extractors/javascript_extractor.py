"""
JavaScript / TypeScript / TSX AST symbol extractor using Tree-sitter.
Extracts functions, arrow functions, methods, classes, interfaces, inheritance, imports, and calls.
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


class JavaScriptExtractor(BaseExtractor):
    """
    Extracts structured symbols and relations from JavaScript and TypeScript ASTs.
    """

    def __init__(self, language: str = "typescript") -> None:
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

            # Imports: import { a } from 'b'
            if node_type == "import_statement":
                self._handle_import(node, source_bytes, file_path, imports)

            # CommonJS require: const x = require('y')
            elif node_type == "variable_declarator":
                self._check_require(node, source_bytes, file_path, imports)
                # Check for arrow function assignment: const myFunc = () => {}
                func_symbol = self._check_arrow_function_assignment(
                    node,
                    source_bytes,
                    file_path,
                    repo_id,
                    parent_class_id,
                    parent_class_name,
                    symbols,
                )
                if func_symbol:
                    # Traverse function body
                    init_node = self.find_child_by_field(node, "value")
                    if init_node:
                        body_node = self.find_child_by_field(init_node, "body") or init_node
                        for child in body_node.children:
                            _traverse(
                                child,
                                parent_class_id=parent_class_id,
                                parent_class_name=parent_class_name,
                                enclosing_callable_id=func_symbol.symbol_id,
                                depth=depth + 1,
                            )
                    return

            # Comments
            elif node_type == "comment":
                comment_text = self.get_text(node, source_bytes).strip()
                is_jsdoc = comment_text.startswith("/**")
                comments.append(
                    ExtractedComment(
                        content=comment_text,
                        location=self.get_location(node, file_path),
                        is_docstring=is_jsdoc,
                        associated_symbol_id=enclosing_callable_id or parent_class_id,
                    )
                )

            # Interfaces (TypeScript)
            elif node_type == "interface_declaration":
                iface_symbol = self._handle_interface(
                    node,
                    source_bytes,
                    file_path,
                    repo_id,
                    symbols,
                    inheritances,
                )
                if iface_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        for child in body.children:
                            _traverse(
                                child,
                                parent_class_id=iface_symbol.symbol_id,
                                parent_class_name=iface_symbol.name,
                                depth=depth + 1,
                            )
                return

            # Classes
            elif node_type in ("class_declaration", "class"):
                class_symbol = self._handle_class(
                    node,
                    source_bytes,
                    file_path,
                    repo_id,
                    parent_class_name,
                    symbols,
                    inheritances,
                )
                if class_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        for child in body.children:
                            _traverse(
                                child,
                                parent_class_id=class_symbol.symbol_id,
                                parent_class_name=class_symbol.name,
                                depth=depth + 1,
                            )
                return

            # Functions (function declarations & generator functions)
            elif node_type in ("function_declaration", "generator_function_declaration"):
                func_symbol = self._handle_function_declaration(
                    node,
                    source_bytes,
                    file_path,
                    repo_id,
                    symbols,
                )
                if func_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        for child in body.children:
                            _traverse(
                                child,
                                enclosing_callable_id=func_symbol.symbol_id,
                                depth=depth + 1,
                            )
                return

            # Methods inside classes
            elif node_type == "method_definition":
                method_symbol = self._handle_method_definition(
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

            # Function / Method calls
            elif node_type == "call_expression":
                self._handle_call(node, source_bytes, file_path, enclosing_callable_id, calls)

            # Export statement wrapper (e.g. export default function ...)
            elif node_type in ("export_statement", "export_default_declaration"):
                for child in node.children:
                    _traverse(
                        child,
                        parent_class_id=parent_class_id,
                        parent_class_name=parent_class_name,
                        enclosing_callable_id=enclosing_callable_id,
                        depth=depth + 1,
                    )
                return

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

    def _handle_import(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        imports: List[ExtractedImport],
    ) -> None:
        raw_statement = self.get_text(node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        source_node = self.find_child_by_field(node, "source")
        module_name = ""
        if source_node:
            raw_mod = self.get_text(source_node, source_bytes).strip()
            module_name = raw_mod.strip("\"'`;")

        is_relative = module_name.startswith((".", "/"))
        imported_names: List[str] = []

        import_clause = self.find_first_child(node, "import_clause")
        if import_clause:
            for child in import_clause.children:
                if child.type == "identifier":
                    imported_names.append(self.get_text(child, source_bytes).strip())
                elif child.type == "named_imports":
                    for spec in child.children:
                        if spec.type == "import_specifier":
                            name_child = self.find_child_by_field(spec, "name") or spec.children[0]
                            imported_names.append(self.get_text(name_child, source_bytes).strip())
                elif child.type == "namespace_import":
                    imported_names.append("*")

        if module_name:
            imports.append(
                ExtractedImport(
                    module=module_name,
                    imported_symbols=imported_names,
                    is_relative=is_relative,
                    location=loc,
                    raw_statement=raw_statement,
                )
            )

    def _check_require(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        imports: List[ExtractedImport],
    ) -> None:
        value_node = self.find_child_by_field(node, "value")
        if not value_node or value_node.type != "call_expression":
            return

        func_node = self.find_child_by_field(value_node, "function")
        if not func_node or self.get_text(func_node, source_bytes).strip() != "require":
            return

        args = self.find_child_by_field(value_node, "arguments")
        if not args or not args.children:
            return

        for child in args.children:
            if child.type == "string":
                mod = self.get_text(child, source_bytes).strip("\"'`;")
                name_node = self.find_child_by_field(node, "name")
                imported = [self.get_text(name_node, source_bytes).strip()] if name_node else []
                imports.append(
                    ExtractedImport(
                        module=mod,
                        imported_symbols=imported,
                        is_relative=mod.startswith((".", "/")),
                        location=self.get_location(node, file_path),
                        raw_statement=self.get_text(node, source_bytes).strip(),
                    )
                )
                break

    def _check_arrow_function_assignment(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        parent_class_id: Optional[str],
        parent_class_name: Optional[str],
        symbols: List[ExtractedSymbol],
    ) -> Optional[ExtractedSymbol]:
        value_node = self.find_child_by_field(node, "value")
        if not value_node or value_node.type not in ("arrow_function", "function_expression"):
            return None

        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return None

        func_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)
        symbol_type = SymbolType.METHOD if parent_class_id else SymbolType.FUNCTION
        symbol_id = self.generate_symbol_id(
            repo_id, file_path, func_name, symbol_type.value, loc.start_line, parent_class_name
        )

        # Parameters
        parameters: List[str] = []
        params_node = self.find_child_by_field(value_node, "parameters")
        if params_node:
            for child in params_node.children:
                p_text = self.get_text(child, source_bytes).strip()
                if p_text and p_text not in (",", "(", ")"):
                    parameters.append(p_text)

        # Return type
        return_type = None
        ret_node = self.find_child_by_field(value_node, "return_type")
        if ret_node:
            return_type = self.get_text(ret_node, source_bytes).strip()

        source_code = self.get_text(node, source_bytes)
        first_line = source_code.split("\n")[0].strip()

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=func_name,
            symbol_type=symbol_type,
            location=loc,
            source_code=source_code,
            parent_symbol_id=parent_class_id,
            signature=first_line,
            return_type=return_type,
            parameters=parameters,
            modifiers=["const/arrow"],
        )
        symbols.append(symbol)
        return symbol

    def _handle_class(
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

        class_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)
        symbol_id = self.generate_symbol_id(
            repo_id, file_path, class_name, "CLASS", loc.start_line, parent_class_name
        )

        base_classes: List[str] = []
        # Check class_heritage
        for child in node.children:
            if child.type == "class_heritage":
                for h_child in child.children:
                    if h_child.type == "extends_clause":
                        for c in h_child.children:
                            if c.type in ("identifier", "member_expression"):
                                super_name = self.get_text(c, source_bytes).strip()
                                base_classes.append(super_name)
                                inheritances.append(
                                    ExtractedInheritance(
                                        sub_symbol_id=symbol_id,
                                        super_name=super_name,
                                        relationship="INHERITS",
                                    )
                                )
                    elif h_child.type == "implements_clause":
                        for c in h_child.children:
                            if c.type in ("type_identifier", "identifier"):
                                iface_name = self.get_text(c, source_bytes).strip()
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
            name=class_name,
            symbol_type=SymbolType.CLASS,
            location=loc,
            source_code=source_code,
            properties={"base_classes": base_classes},
        )
        symbols.append(symbol)
        return symbol

    def _handle_interface(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        symbols: List[ExtractedSymbol],
        inheritances: List[ExtractedInheritance],
    ) -> Optional[ExtractedSymbol]:
        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return None

        iface_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)
        symbol_id = self.generate_symbol_id(
            repo_id, file_path, iface_name, "INTERFACE", loc.start_line
        )

        # Check extends_type_clause
        for child in node.children:
            if child.type == "extends_type_clause":
                for c in child.children:
                    if c.type in ("type_identifier", "identifier"):
                        super_iface = self.get_text(c, source_bytes).strip()
                        inheritances.append(
                            ExtractedInheritance(
                                sub_symbol_id=symbol_id,
                                super_name=super_iface,
                                relationship="INHERITS",
                            )
                        )

        source_code = self.get_text(node, source_bytes)
        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=iface_name,
            symbol_type=SymbolType.INTERFACE,
            location=loc,
            source_code=source_code,
        )
        symbols.append(symbol)
        return symbol

    def _handle_function_declaration(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        symbols: List[ExtractedSymbol],
    ) -> Optional[ExtractedSymbol]:
        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return None

        func_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)
        symbol_id = self.generate_symbol_id(
            repo_id, file_path, func_name, "FUNCTION", loc.start_line
        )

        parameters: List[str] = []
        params_node = self.find_child_by_field(node, "parameters")
        if params_node:
            for child in params_node.children:
                p_text = self.get_text(child, source_bytes).strip()
                if p_text and p_text not in (",", "(", ")"):
                    parameters.append(p_text)

        return_type = None
        ret_node = self.find_child_by_field(node, "return_type")
        if ret_node:
            return_type = self.get_text(ret_node, source_bytes).strip()

        source_code = self.get_text(node, source_bytes)
        first_line = source_code.split("\n")[0].strip()

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=func_name,
            symbol_type=SymbolType.FUNCTION,
            location=loc,
            source_code=source_code,
            signature=first_line,
            return_type=return_type,
            parameters=parameters,
        )
        symbols.append(symbol)
        return symbol

    def _handle_method_definition(
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
                p_text = self.get_text(child, source_bytes).strip()
                if p_text and p_text not in (",", "(", ")"):
                    parameters.append(p_text)

        return_type = None
        ret_node = self.find_child_by_field(node, "return_type")
        if ret_node:
            return_type = self.get_text(ret_node, source_bytes).strip()

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
        func_node = self.find_child_by_field(node, "function")
        if not func_node:
            return

        loc = self.get_location(node, file_path)
        callee_name = ""
        receiver = None

        if func_node.type == "identifier":
            callee_name = self.get_text(func_node, source_bytes).strip()
        elif func_node.type == "member_expression":
            obj_node = self.find_child_by_field(func_node, "object")
            prop_node = self.find_child_by_field(func_node, "property")
            if prop_node:
                callee_name = self.get_text(prop_node, source_bytes).strip()
            if obj_node:
                receiver = self.get_text(obj_node, source_bytes).strip()
        else:
            callee_name = self.get_text(func_node, source_bytes).strip()

        if callee_name:
            calls.append(
                ExtractedCall(
                    caller_symbol_id=enclosing_callable_id,
                    callee_name=callee_name,
                    receiver=receiver,
                    location=loc,
                    is_confirmed=False,
                )
            )

