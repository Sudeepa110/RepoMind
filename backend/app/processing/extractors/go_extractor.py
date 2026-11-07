"""
Go AST symbol extractor using Tree-sitter.
Extracts functions, methods (with receivers), structs, interfaces, imports, and calls.
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


class GoExtractor(BaseExtractor):
    """
    Extracts structured symbols and relations from Go ASTs.
    """

    def __init__(self) -> None:
        super().__init__("go")

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
            enclosing_callable_id: Optional[str] = None,
            depth: int = 0,
        ):
            if depth > 100:
                return

            node_type = node.type

            # Imports
            if node_type == "import_declaration":
                self._handle_import(node, source_bytes, file_path, imports)
                return

            # Comments
            elif node_type == "comment":
                comment_text = self.get_text(node, source_bytes).strip()
                comments.append(
                    ExtractedComment(
                        content=comment_text,
                        location=self.get_location(node, file_path),
                        is_docstring=False,
                        associated_symbol_id=enclosing_callable_id,
                    )
                )

            # Type declarations (struct, interface)
            elif node_type == "type_declaration":
                self._handle_type_declaration(node, source_bytes, file_path, repo_id, symbols)
                return

            # Functions: func Foo()
            elif node_type == "function_declaration":
                func_symbol = self._handle_function_declaration(
                    node, source_bytes, file_path, repo_id, symbols
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

            # Methods: func (r *Receiver) Method()
            elif node_type == "method_declaration":
                method_symbol = self._handle_method_declaration(
                    node, source_bytes, file_path, repo_id, symbols
                )
                if method_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        for child in body.children:
                            _traverse(
                                child,
                                enclosing_callable_id=method_symbol.symbol_id,
                                depth=depth + 1,
                            )
                return

            # Calls: call_expression
            elif node_type == "call_expression":
                self._handle_call(node, source_bytes, file_path, enclosing_callable_id, calls)

            # Default recursive traversal
            for child in node.children:
                _traverse(
                    child,
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
        raw_stmt = self.get_text(node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        for child in node.children:
            if child.type == "import_spec":
                path_node = self.find_child_by_field(child, "path")
                if path_node:
                    import_path = self.get_text(path_node, source_bytes).strip('"')
                    name_node = self.find_child_by_field(child, "name")
                    alias = self.get_text(name_node, source_bytes).strip() if name_node else None
                    imports.append(
                        ExtractedImport(
                            module=import_path,
                            imported_symbols=[alias or import_path.split("/")[-1]],
                            alias=alias,
                            is_relative=import_path.startswith((".", "/")),
                            location=loc,
                            raw_statement=raw_stmt,
                        )
                    )
            elif child.type == "import_spec_list":
                for spec in child.children:
                    if spec.type == "import_spec":
                        p_node = self.find_child_by_field(spec, "path")
                        if p_node:
                            i_path = self.get_text(p_node, source_bytes).strip('"')
                            n_node = self.find_child_by_field(spec, "name")
                            al = self.get_text(n_node, source_bytes).strip() if n_node else None
                            imports.append(
                                ExtractedImport(
                                    module=i_path,
                                    imported_symbols=[al or i_path.split("/")[-1]],
                                    alias=al,
                                    is_relative=i_path.startswith((".", "/")),
                                    location=loc,
                                    raw_statement=raw_stmt,
                                )
                            )

    def _handle_type_declaration(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        symbols: List[ExtractedSymbol],
    ) -> None:
        for child in node.children:
            if child.type == "type_spec":
                name_node = self.find_child_by_field(child, "name")
                type_node = self.find_child_by_field(child, "type")
                if not name_node or not type_node:
                    continue

                type_name = self.get_text(name_node, source_bytes).strip()
                loc = self.get_location(child, file_path)

                if type_node.type == "struct_type":
                    sym_type = SymbolType.STRUCT
                elif type_node.type == "interface_type":
                    sym_type = SymbolType.INTERFACE
                else:
                    sym_type = SymbolType.TYPE_ALIAS

                symbol_id = self.generate_symbol_id(
                    repo_id, file_path, type_name, sym_type.value, loc.start_line
                )
                source_code = self.get_text(child, source_bytes)

                symbols.append(
                    ExtractedSymbol(
                        symbol_id=symbol_id,
                        name=type_name,
                        symbol_type=sym_type,
                        location=loc,
                        source_code=source_code,
                    )
                )

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
                if child.type == "parameter_declaration":
                    p_text = self.get_text(child, source_bytes).strip()
                    if p_text:
                        parameters.append(p_text)

        return_type = None
        res_node = self.find_child_by_field(node, "result")
        if res_node:
            return_type = self.get_text(res_node, source_bytes).strip()

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

    def _handle_method_declaration(
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

        method_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        receiver_node = self.find_child_by_field(node, "receiver")
        receiver_type = ""
        if receiver_node:
            recv_text = self.get_text(receiver_node, source_bytes).strip("()")
            # Extract type e.g. "*User" -> "User"
            parts = recv_text.split()
            if len(parts) >= 2:
                receiver_type = parts[1].replace("*", "").strip()
            elif parts:
                receiver_type = parts[0].replace("*", "").strip()

        symbol_id = self.generate_symbol_id(
            repo_id, file_path, method_name, "METHOD", loc.start_line, receiver_type or None
        )

        parameters: List[str] = []
        params_node = self.find_child_by_field(node, "parameters")
        if params_node:
            for child in params_node.children:
                if child.type == "parameter_declaration":
                    p_text = self.get_text(child, source_bytes).strip()
                    if p_text:
                        parameters.append(p_text)

        return_type = None
        res_node = self.find_child_by_field(node, "result")
        if res_node:
            return_type = self.get_text(res_node, source_bytes).strip()

        source_code = self.get_text(node, source_bytes)
        first_line = source_code.split("\n")[0].strip()

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=method_name,
            symbol_type=SymbolType.METHOD,
            location=loc,
            source_code=source_code,
            signature=first_line,
            return_type=return_type,
            parameters=parameters,
            properties={"receiver": receiver_type},
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
        elif func_node.type == "selector_expression":
            operand_node = self.find_child_by_field(func_node, "operand")
            field_node = self.find_child_by_field(func_node, "field")
            if field_node:
                callee_name = self.get_text(field_node, source_bytes).strip()
            if operand_node:
                receiver = self.get_text(operand_node, source_bytes).strip()
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

