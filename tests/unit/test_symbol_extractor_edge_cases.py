"""
Unit tests for edge cases in the code understanding pipeline:
- Syntax error and malformed source handling
- Empty files and whitespace-only files
- Unsupported extensions
- Oversized files
- Deterministic symbol IDs
"""

import tempfile
from pathlib import Path
import pytest
from backend.app.processing.engine import code_engine
from backend.app.processing.models import SymbolType


def test_syntax_error_resilience():
    # Intentionally broken Python syntax with missing parentheses, keywords, etc.
    broken_code = """
def broken_func(a, b
    print("Oops")

class IncompleteClass
    def intact_method(self):
        return 42
"""
    parsed = code_engine.parse_source_code(broken_code, "broken.py", "repo_1")
    assert parsed is not None
    # Verify parser detected errors but did not crash
    assert len(parsed.syntax_errors) > 0
    # Resilient extraction: Tree-sitter still manages to extract valid subtrees!
    # intact_method or broken_func should still be partially extracted or handled safely
    assert parsed.language == "python"
    assert parsed.file_path == "broken.py"


def test_empty_and_whitespace_file():
    parsed_empty = code_engine.parse_source_code("", "empty.py", "repo_1")
    assert parsed_empty is not None
    assert len(parsed_empty.symbols) == 0
    assert len(parsed_empty.imports) == 0
    assert len(parsed_empty.calls) == 0

    parsed_whitespace = code_engine.parse_source_code("   \n\n\t  \n", "spaces.ts", "repo_1")
    assert parsed_whitespace is not None
    assert len(parsed_whitespace.symbols) == 0


def test_unsupported_extension_graceful_fallback():
    text_content = "This is a plain markdown file with no grammar."
    parsed = code_engine.parse_source_code(text_content, "notes.txt", "repo_1")
    assert parsed is not None
    assert parsed.language == "Unknown"
    assert len(parsed.symbols) == 0
    assert parsed.size_bytes > 0


def test_oversized_file_protection():
    with tempfile.TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)
        large_file = dir_path / "huge.py"
        # Write 600 KB file (exceeds default 500 KB limit)
        large_file.write_text("x = 1\n" * 100_000, encoding="utf-8")

        parsed = code_engine.parse_file(dir_path, "huge.py", "repo_1")
        assert parsed is None  # Safely skipped


def test_deterministic_symbol_ids():
    code = """
class Calculator:
    def add(self, a, b):
        return a + b
"""
    parsed_1 = code_engine.parse_source_code(code, "calc.py", "repo_x")
    parsed_2 = code_engine.parse_source_code(code, "calc.py", "repo_x")

    assert parsed_1 is not None and parsed_2 is not None
    symbols_1 = [s.symbol_id for s in parsed_1.symbols]
    symbols_2 = [s.symbol_id for s in parsed_2.symbols]
    assert symbols_1 == symbols_2
    assert len(symbols_1) == 2
    assert "repo_x:calc.py#Calculator:" in symbols_1[0]
    assert "repo_x:calc.py#Calculator.add:" in symbols_1[1]

