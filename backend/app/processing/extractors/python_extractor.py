"""
Python AST symbol extractor using Tree-sitter.
Extracts functions, methods, classes, base classes, imports, function calls, and docstrings.
Supports arbitrary nesting (closures, nested classes) and stable deterministic symbol IDs.
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


class PythonExtractor(BaseExtractor):
    """
    Extracts structured symbols and relations from Python ASTs.
    """

    def __init__(self) -> None:
        super().__init__("python")

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

        # Context tracker for parent scopes (classes and functions)
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

            # Imports: import x, y
            if node_type == "import_statement":
                self._handle_import_statement(node, source_bytes, file_path, imports)

            # Imports: from x import y, z
            elif node_type == "import_from_statement":
                self._handle_import_from_statement(node, source_bytes, file_path, imports)

            # Comments
            elif node_type == "comment":
                comment_text = self.get_text(node, source_bytes).strip()
                comments.append(
                    ExtractedComment(
                        content=comment_text,
                        location=self.get_location(node, file_path),
                        is_docstring=False,
                        associated_symbol_id=enclosing_callable_id or parent_scope_id,
                    )
                )

            # Classes (supports top-level and nested classes)
            elif node_type == "class_definition":
                class_symbol = self._handle_class_definition(
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
                if class_symbol:
                    body = self.find_child_by_field(node, "body")
                    if body:
                        nested_scope_name = (
                            f"{parent_scope_name}.{class_symbol.name}"
                            if parent_scope_name
                            else class_symbol.name
                        )
                        for child in body.children:
                            _traverse(
                                child,
                                parent_scope_id=class_symbol.symbol_id,
                                parent_scope_name=nested_scope_name,
                                enclosing_callable_id=None,
                                is_inside_class=True,
                                depth=depth + 1,
                            )
                return

            # Functions / Methods / Closures
            elif node_type in ("function_definition", "async_function_definition"):
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
                        nested_scope_name = (
                            f"{parent_scope_name}.{func_symbol.name}"
                            if parent_scope_name
                            else func_symbol.name
                        )
                        for child in body.children:
                            _traverse(
                                child,
                                parent_scope_id=func_symbol.symbol_id,
                                parent_scope_name=nested_scope_name,
                                enclosing_callable_id=func_symbol.symbol_id,
                                is_inside_class=False,
                                depth=depth + 1,
                            )
                return

            # Function / Method calls
            elif node_type == "call":
                self._handle_call(node, source_bytes, file_path, enclosing_callable_id, raw_calls)

            # Traverse child nodes
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
        imported_symbol_names: Set[str] = set()
        for imp in imports:
            imported_symbol_names.add(imp.module)
            imported_symbol_names.update(imp.imported_symbols)
            if imp.alias:
                imported_symbol_names.add(imp.alias)

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

    def _handle_import_statement(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        imports: List[ExtractedImport],
    ) -> None:
        raw_statement = self.get_text(node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        for child in node.children:
            if child.type == "dotted_name":
                module_name = self.get_text(child, source_bytes).strip()
                imports.append(
                    ExtractedImport(
                        module=module_name,
                        imported_symbols=[module_name],
                        location=loc,
                        raw_statement=raw_statement,
                    )
                )
            elif child.type == "aliased_import":
                name_node = self.find_child_by_field(child, "name")
                alias_node = self.find_child_by_field(child, "alias")
                if name_node:
                    module_name = self.get_text(name_node, source_bytes).strip()
                    alias = self.get_text(alias_node, source_bytes).strip() if alias_node else None
                    imports.append(
                        ExtractedImport(
                            module=module_name,
                            imported_symbols=[module_name],
                            alias=alias,
                            location=loc,
                            raw_statement=raw_statement,
                        )
                    )

    def _handle_import_from_statement(
        self,
        node: tree_sitter.Node,
        source_bytes: bytes,
        file_path: str,
        imports: List[ExtractedImport],
    ) -> None:
        raw_statement = self.get_text(node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        module_name = ""
        imported_names: List[str] = []
        is_relative = False

        mod_node = self.find_child_by_field(node, "module_name")
        if mod_node:
            module_name = self.get_text(mod_node, source_bytes).strip()

        # Check for relative import (leading dots)
        for child in node.children:
            if child.type == "relative_import":
                is_relative = True
                module_name = self.get_text(child, source_bytes).strip()
                break

        for child in node.children:
            if child.type == "dotted_name" and child != mod_node:
                imported_names.append(self.get_text(child, source_bytes).strip())
            elif child.type == "aliased_import":
                name_child = self.find_child_by_field(child, "name")
                if name_child:
                    imported_names.append(self.get_text(name_child, source_bytes).strip())
            elif child.type == "wildcard_import":
                imported_names.append("*")

        if module_name or imported_names:
            imports.append(
                ExtractedImport(
                    module=module_name,
                    imported_symbols=imported_names,
                    is_relative=is_relative,
                    location=loc,
                    raw_statement=raw_statement,
                )
            )

    def _handle_class_definition(
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

        class_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        symbol_id = self.get_scoped_symbol_id(
            repo_id=repo_id,
            file_path=file_path,
            name=class_name,
            symbol_type="CLASS",
            parent_scope=parent_scope_name,
            name_counts=name_counts,
        )

        # Extract base classes from superclasses / argument_list
        superclasses_node = self.find_child_by_field(node, "superclasses")
        if not superclasses_node:
            superclasses_node = self.find_first_child(node, "argument_list")

        base_classes: List[str] = []
        if superclasses_node:
            for child in superclasses_node.children:
                if child.type in ("identifier", "dotted_name", "attribute"):
                    base_name = self.get_text(child, source_bytes).strip()
                    if base_name:
                        base_classes.append(base_name)
                        inheritances.append(
                            ExtractedInheritance(
                                sub_symbol_id=symbol_id,
                                super_name=base_name,
                                relationship="INHERITS",
                                is_confirmed=False,
                            )
                        )

        # Extract class docstring
        docstring = self._extract_docstring(node, source_bytes)
        source_code = self.get_text(node, source_bytes)
        content_hash = self.compute_content_hash(source_code)

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=class_name,
            symbol_type=SymbolType.CLASS,
            location=loc,
            source_code=source_code,
            content_hash=content_hash,
            parent_symbol_id=parent_scope_id,
            docstring=docstring,
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
        name_node = self.find_child_by_field(node, "name")
        if not name_node:
            return None

        func_name = self.get_text(name_node, source_bytes).strip()
        loc = self.get_location(node, file_path)

        symbol_type = SymbolType.METHOD if is_inside_class else SymbolType.FUNCTION
        symbol_id = self.get_scoped_symbol_id(
            repo_id=repo_id,
            file_path=file_path,
            name=func_name,
            symbol_type=symbol_type.value,
            parent_scope=parent_scope_name,
            name_counts=name_counts,
        )

        # Extract parameters
        params_node = self.find_child_by_field(node, "parameters")
        parameters: List[str] = []
        if params_node:
            for child in params_node.children:
                if child.type in ("identifier", "typed_parameter", "default_parameter", "typed_default_parameter"):
                    param_text = self.get_text(child, source_bytes).strip()
                    if param_text and param_text not in (",", "(", ")"):
                        parameters.append(param_text)

        # Return type
        return_type = None
        ret_node = self.find_child_by_field(node, "return_type")
        if ret_node:
            return_type = self.get_text(ret_node, source_bytes).strip()

        # Docstring
        docstring = self._extract_docstring(node, source_bytes)

        # Modifiers
        modifiers: List[str] = []
        if node.type == "async_function_definition":
            modifiers.append("async")

        source_code = self.get_text(node, source_bytes)
        content_hash = self.compute_content_hash(source_code)
        first_line = source_code.split("\n")[0].strip() if source_code else f"def {func_name}()"

        symbol = ExtractedSymbol(
            symbol_id=symbol_id,
            name=func_name,
            symbol_type=symbol_type,
            location=loc,
            source_code=source_code,
            content_hash=content_hash,
            parent_symbol_id=parent_scope_id,
            docstring=docstring,
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
        elif func_node.type == "attribute":
            obj_node = self.find_child_by_field(func_node, "object")
            attr_node = self.find_child_by_field(func_node, "attribute")
            if attr_node:
                callee_name = self.get_text(attr_node, source_bytes).strip()
            if obj_node:
                receiver = self.get_text(obj_node, source_bytes).strip()
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

    def _extract_docstring(self, node: tree_sitter.Node, source_bytes: bytes) -> Optional[str]:
        body = self.find_child_by_field(node, "body")
        if not body or not body.children:
            return None

        first_stmt = body.children[0]
        if first_stmt.type == "expression_statement" and first_stmt.children:
            expr = first_stmt.children[0]
            if expr.type == "string":
                text = self.get_text(expr, source_bytes).strip()
                for quote in ('"""', "'''"):
                    if text.startswith(quote) and text.endswith(quote) and len(text) >= 6:
                        return text[3:-3].strip()
                if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
                    return text[1:-1].strip()
                return text
        return None
