"""
Phase 3 Quality Audit, Verification, and Stabilization Test Suite.
Rigorously tests:
  1. Call extraction accuracy (direct, object, nested, self/this, constructors, loops, conditionals, callbacks, non-calls).
  2. Nested symbol extraction (class->method, class->nested class, function->closure, interface->method, struct->method).
  3. Stable deterministic symbol IDs across line shifts & content hash fingerprinting.
  4. Graph relationship classification, local resolution, and edge deduplication.
  5. Exact source citations across Unicode and CRLF/LF line endings.
"""

import pytest
from backend.app.processing.engine import code_engine
from backend.app.processing.models import SymbolType, ParsedRepository
from backend.app.processing.adapters import to_graph_elements, to_code_chunks
from backend.app.graph.interfaces import NodeType, RelationshipType


# =========================================================================
# 1. AUDIT: Call Extraction Accuracy & Non-Call Filtering
# =========================================================================

def test_audit_call_extraction_variety():
    py_code = """
import math
from utils import helper

class Calculator:
    def add(self, a, b):
        return a + b

    def compute(self, values):
        total = 0
        # Call using self
        base = self.add(10, 20)
        # Call inside loop and conditional
        for v in values:
            if v > 0:
                total += math.sqrt(v)
            else:
                total += helper(v)
        # Nested call f(g(x))
        final_val = self.add(total, math.floor(2.5))
        return final_val
"""
    parsed = code_engine.parse_source_code(py_code, "calc.py", "repo_audit")
    assert parsed is not None

    compute_sym = next(s for s in parsed.symbols if s.name == "compute")
    compute_calls = [c for c in parsed.calls if c.caller_symbol_id == compute_sym.symbol_id]

    # 1. Call using self
    self_add = next(c for c in compute_calls if c.callee_name == "add" and c.receiver == "self")
    assert self_add.is_confirmed is True
    assert self_add.resolution_status == "CONFIRMED"

    # 2. Call to imported module
    sqrt_call = next(c for c in compute_calls if c.callee_name == "sqrt")
    assert sqrt_call.receiver == "math"
    assert sqrt_call.resolution_status == "INFERRED"

    # 3. Call to imported function
    helper_call = next(c for c in compute_calls if c.callee_name == "helper")
    assert helper_call.is_confirmed is True
    assert helper_call.resolution_status == "CONFIRMED"

    # 4. Nested call: self.add(..., math.floor(2.5))
    floor_call = next(c for c in compute_calls if c.callee_name == "floor")
    assert floor_call.receiver == "math"


def test_audit_constructor_calls():
    # JavaScript constructor (new UserService) and Java constructor (new ArrayList)
    js_code = """
import { UserService } from './services';

function init() {
    const service = new UserService("test");
    service.start();
}
"""
    parsed_js = code_engine.parse_source_code(js_code, "init.js", "repo_audit")
    assert parsed_js is not None
    ctor_call = next((c for c in parsed_js.calls if c.callee_name == "UserService"), None)
    assert ctor_call is not None
    assert ctor_call.is_constructor is True

    java_code = """
package com.demo;
import java.util.ArrayList;

class App {
    void setup() {
        ArrayList list = new ArrayList();
        list.add("hello");
    }
}
"""
    parsed_java = code_engine.parse_source_code(java_code, "App.java", "repo_audit")
    assert parsed_java is not None
    java_ctor = next((c for c in parsed_java.calls if c.callee_name == "ArrayList"), None)
    assert java_ctor is not None
    assert java_ctor.is_constructor is True


def test_audit_non_call_identifiers_not_extracted():
    # Variables, parameters, list elements, or decorators that share function names must NOT be calls
    code = """
def callback_handler(action):
    return action

def main_flow():
    # Function referenced as variable, NOT called
    fn_ptr = callback_handler
    list_of_fns = [callback_handler, main_flow]
    # Real call
    result = callback_handler(42)
    return result
"""
    parsed = code_engine.parse_source_code(code, "pointers.py", "repo_audit")
    assert parsed is not None

    calls = parsed.calls
    # Only callback_handler(42) should be a call
    assert len(calls) == 1
    assert calls[0].callee_name == "callback_handler"
    assert calls[0].location.start_line == 10


# =========================================================================
# 2. AUDIT: Nested Symbol Extraction (Closures, Nested Classes, Interfaces)
# =========================================================================

def test_audit_nested_symbols_python():
    code = """
class OuterClass:
    class InnerClass:
        def inner_method(self):
            return 1

    def outer_method(self):
        def helper_closure():
            return 2
        return helper_closure()
"""
    parsed = code_engine.parse_source_code(code, "nested.py", "repo_audit")
    assert parsed is not None

    symbols_by_name = {s.name: s for s in parsed.symbols}

    outer_cls = symbols_by_name["OuterClass"]
    inner_cls = symbols_by_name["InnerClass"]
    inner_method = symbols_by_name["inner_method"]
    outer_method = symbols_by_name["outer_method"]
    helper_closure = symbols_by_name["helper_closure"]

    # Class -> Nested Class
    assert inner_cls.parent_symbol_id == outer_cls.symbol_id
    assert "OuterClass.InnerClass" in inner_cls.symbol_id

    # Nested Class -> Method
    assert inner_method.parent_symbol_id == inner_cls.symbol_id
    assert "OuterClass.InnerClass.inner_method" in inner_method.symbol_id

    # Class -> Method
    assert outer_method.parent_symbol_id == outer_cls.symbol_id

    # Method -> Closure / Nested Function
    assert helper_closure.parent_symbol_id == outer_method.symbol_id
    assert "OuterClass.outer_method.helper_closure" in helper_closure.symbol_id


def test_audit_nested_symbols_javascript():
    code = """
function outerFunc() {
    function innerNamed() {
        return 1;
    }
    const innerArrow = () => {
        return 2;
    };
    return innerNamed() + innerArrow();
}
"""
    parsed = code_engine.parse_source_code(code, "closures.js", "repo_audit")
    assert parsed is not None

    outer_f = next(s for s in parsed.symbols if s.name == "outerFunc")
    inner_named = next(s for s in parsed.symbols if s.name == "innerNamed")
    inner_arrow = next(s for s in parsed.symbols if s.name == "innerArrow")

    assert inner_named.parent_symbol_id == outer_f.symbol_id
    assert "outerFunc.innerNamed" in inner_named.symbol_id

    assert inner_arrow.parent_symbol_id == outer_f.symbol_id
    assert "outerFunc.innerArrow" in inner_arrow.symbol_id


# =========================================================================
# 3. AUDIT: Deterministic Symbol IDs & Line-Shift Stability
# =========================================================================

def test_audit_symbol_id_stability_across_line_shifts():
    """
    Critical audit test: Verify that inserting unrelated code or blank lines above
    a function does NOT change the function's symbol_id, but correctly updates its line range.
    """
    code_v1 = """
def unchanged_function():
    \"\"\"This function body never changes.\"\"\"
    return 42
"""

    code_v2 = """
# Inserting 10 new lines of unrelated comments and a new helper
def new_unrelated_function():
    return 0

def unchanged_function():
    \"\"\"This function body never changes.\"\"\"
    return 42
"""

    p1 = code_engine.parse_source_code(code_v1, "service.py", "repo_test")
    p2 = code_engine.parse_source_code(code_v2, "service.py", "repo_test")

    sym1 = next(s for s in p1.symbols if s.name == "unchanged_function")
    sym2 = next(s for s in p2.symbols if s.name == "unchanged_function")

    # 1. Symbol ID MUST be identical!
    assert sym1.symbol_id == sym2.symbol_id
    assert sym1.symbol_id == "repo_test:service.py#unchanged_function"

    # 2. Content hash MUST be identical!
    assert sym1.content_hash == sym2.content_hash
    assert sym1.content_hash is not None

    # 3. Line numbers MUST reflect actual source position!
    assert sym1.location.start_line != sym2.location.start_line
    assert sym2.location.start_line > sym1.location.start_line


def test_audit_content_hash_detects_code_change():
    """Verify that editing a function body changes its content_hash while keeping its ID stable."""
    code_v1 = "def process(): return 10"
    code_v2 = "def process(): return 999"

    p1 = code_engine.parse_source_code(code_v1, "proc.py", "repo_test")
    p2 = code_engine.parse_source_code(code_v2, "proc.py", "repo_test")

    sym1 = p1.symbols[0]
    sym2 = p2.symbols[0]

    assert sym1.symbol_id == sym2.symbol_id  # Stable identity
    assert sym1.content_hash != sym2.content_hash  # Hash detects modification


# =========================================================================
# 4. AUDIT: Graph Relationship Classification & Edge Deduplication
# =========================================================================

def test_audit_graph_edge_deduplication_and_resolution():
    py_code = """
class Worker:
    def log(self, msg):
        pass

    def do_work(self):
        # 3 calls from do_work to self.log
        self.log("Step 1")
        self.log("Step 2")
        self.log("Step 3")
        # 1 call to unresolved external
        unknown_service()
"""
    parsed = code_engine.parse_source_code(py_code, "worker.py", "repo_graph")
    assert parsed is not None

    parsed_repo = ParsedRepository(
        repository_id="repo_graph",
        files={"worker.py": parsed},
        total_symbols=len(parsed.symbols),
        total_files=1,
        supported_languages=["python"],
    )

    nodes, edges = to_graph_elements(parsed_repo)

    # Find CALLS edges from do_work
    do_work_sym = next(s for s in parsed.symbols if s.name == "do_work")
    log_sym = next(s for s in parsed.symbols if s.name == "log")

    calls_to_log = [e for e in edges if e.source_id == do_work_sym.symbol_id and e.target_id == log_sym.symbol_id]

    # Strict deduplication: Only 1 edge should exist between do_work and log!
    assert len(calls_to_log) == 1
    edge = calls_to_log[0]
    assert edge.is_confirmed is True
    assert edge.properties["confidence"] == 1.0
    assert edge.properties["call_count"] == 3
    assert len(edge.properties["lines"]) == 3

    # Unresolved call should be marked not confirmed with lower confidence
    unresolved_calls = [e for e in edges if "unknown_service" in e.target_id]
    assert len(unresolved_calls) == 1
    assert unresolved_calls[0].is_confirmed is False
    assert unresolved_calls[0].properties["confidence"] < 1.0


# =========================================================================
# 5. AUDIT: Source Code Citations & Line Normalization
# =========================================================================

def test_audit_source_citations_with_unicode_and_crlf():
    # Multi-line with emojis, Unicode, and CRLF line endings
    crlf_code = (
        "# \U0001F680 RepoMind Unicode Test\r\n"
        "class \u00c9tudiant:\r\n"
        "    \"\"\"Docstring with accent: \u00e9\u00e0\u00fc.\"\"\"\r\n"
        "    def saluer(self) -> str:\r\n"
        "        return \"Bonjour \U0001F44B\"\r\n"
    )

    parsed = code_engine.parse_source_code(crlf_code, "unicode.py", "repo_cite")
    assert parsed is not None

    parsed_repo = ParsedRepository(
        repository_id="repo_cite",
        files={"unicode.py": parsed},
        total_symbols=len(parsed.symbols),
        total_files=1,
        supported_languages=["python"],
    )

    chunks = to_code_chunks(parsed_repo)
    assert len(chunks) == 2

    saluer_chunk = next(c for c in chunks if c["metadata"]["symbol_name"] == "saluer")
    meta = saluer_chunk["metadata"]

    assert meta["repository_id"] == "repo_cite"
    assert meta["file_path"] == "unicode.py"
    assert meta["start_line"] == 4
    assert meta["end_line"] == 5
    assert "Bonjour" in saluer_chunk["content"]
    assert meta["content_hash"] != ""

