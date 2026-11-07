"""
Go AST symbol extractor using Tree-sitter.
Extracts functions, methods (with receivers), structs, interfaces, imports, and calls.
Links methods to their receiver structs and supports stable deterministic symbol IDs.
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
        raw_calls: List[dict] = []
        inheritances: List[ExtractedInheritance] = []
        comments: List[ExtractedComment] = []
        name_counts: Dict[str, int] = defaultdict(int)

        line_count = len(source_bytes.split(b"\n"))
        size_bytes = len(source_bytes)
        syntax_errors = self.collect_syntax_errors(root_node)

        # First pass: Collect all struct/interface types so methods can link to them
        type_symbol_ids: Dict[str, str] = {}

        def _find_types(node: tree_sitter.Node):
            for child in node.children:
                if child.type == "type_declaration":
                    self._handle_type_declaration(
                        child, source_bytes, file_path, repo_id, symbols, name_counts, type_symbol_ids
                    )
            for child in node.children:
                _find_types(child)

        _find_types(root_node)

        def _traverse(
            node: tree_sitter.Node,
            enclosing_callable_id: Optional[str] = None,
            parent_scope_name: Optional[str] = None,
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

            # Skip type_declaration since already handled in first pass
            elif node_type == "type_declaration":
                return

            # Functions: func Foo()
            elif node_type == "function_declaration":
                func_symbol = self._handle_function_declaration(
                    node, source_bytes, file_path, repo_id, parent_scope_name, symbols, name_counts
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
                                enclosing_callable_id=func_symbol.symbol_id,
                                parent_scope_name=nested_scope,
                                depth=depth + 1,
                            )
                return

            # Methods: func (r *Receiver) Method()
            elif node_type == "method_declaration":
                method_symbol = self._handle_method_declaration(
                    node, source_bytes, file_path, repo_id, type_symbol_ids, symbols, name_counts
                )
                if method_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        nested_scope = method_symbol.name
                        for child in body.children:
                            _traverse(
                                child,
                                enclosing_callable_id=method_symbol.symbol_id,
                                parent_scope_name=nested_scope,
                                depth=depth + 1,
                            )
                return

            # Calls: call_expression
            elif node_type == "call_expression":
                self._handle_call(node, source_bytes, file_path, enclosing_callable_id, raw_calls)

            # Default recursive traversal
            for child in node.children:
                _traverse(
                    child,
                    enclosing_callable_id=enclosing_callable_id,
                    parent_scope_name=parent_scope_name,
                    depth=depth + 1,
                )

        _traverse(root_node)

        # Post-traversal resolution: Classify call confirmation status
        local_symbol_names: Set[str] = {s.name for s in symbols}
        imported_symbol_names: Set[str] = set()
        for imp in imports:
            imported_symbol_names.add(imp.module)
            imported_symbol_names.update(imp.imported_symbols)

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
        name_counts: Dict[str, int],
        type_symbol_ids: Dict[str, str],
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

                symbol_id = self.get_scoped_symbol_id(
                    repo_id=repo_id,
                    file_path=file_path,
                    name=type_name,
                    symbol_type=sym_type.value,
                    parent_scope=None,
                    name_counts=name_counts,
                )
                type_symbol_ids[type_name] = symbol_id

                source_code = self.get_text(child, source_bytes)
                content_hash = self.compute_content_hash(source_code)

                symbols.append(
                    ExtractedSymbol(
                        symbol_id=symbol_id,
                        name=type_name,
                        symbol_type=sym_type,
                        location=loc,
                        source_code=source_code,
                        content_hash=content_hash,
                    )
                )

    def _handle_function_declaration(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        repo_id: str,
        parent_scope_name: Optional[str],
        symbols: List[ExtractedSymbol],
        name_counts: Dict[str, int],
    ) -> Optional[ExtractedSymbol]:
        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return None

        func_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)
        symbol_id = self.get_scoped_symbol_id(
            repo_id=repo_id,
            file_path=file_path,
            name=func_name,
            symbol_type="FUNCTION",
            parent_scope=parent_scope_name,
            name_counts=name_counts,
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
        content_hash = self.compute_content_hash(source_code)
        first_line = source_code.split("\n")[0].strip()

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=func_name,
            symbol_type=SymbolType.FUNCTION,
            location=loc,
            source_code=source_code,
            content_hash=content_hash,
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
        type_symbol_ids: Dict[str, str],
        symbols: List[ExtractedSymbol],
        name_counts: Dict[str, int],
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
            parts = recv_text.split()
            if len(parts) >= 2:
                receiver_type = parts[1].replace("*", "").strip()
            elif parts:
                receiver_type = parts[0].replace("*", "").strip()

        parent_symbol_id = type_symbol_ids.get(receiver_type)
        symbol_id = self.get_scoped_symbol_id(
            repo_id=repo_id,
            file_path=file_path,
            name=method_name,
            symbol_type="METHOD",
            parent_scope=receiver_type or None,
            name_counts=name_counts,
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
        content_hash = self.compute_content_hash(source_code)
        first_line = source_code.split("\n")[0].strip()

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=method_name,
            symbol_type=SymbolType.METHOD,
            location=loc,
            source_code=source_code,
            content_hash=content_hash,
            parent_symbol_id=parent_symbol_id,
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
            raw_calls.append({
                "caller_symbol_id": enclosing_callable_id,
                "callee_name": callee_name,
                "receiver": receiver,
                "location": loc,
                "is_constructor": False,
            })
