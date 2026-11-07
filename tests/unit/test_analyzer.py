import tempfile
from pathlib import Path
import pytest
from backend.app.ingestion.analyzer import (
    detect_file_language,
    count_file_lines,
    extract_readme,
    build_directory_tree,
    analyze_repository,
)

def test_detect_file_language():
    assert detect_file_language(Path("app.py")) == "Python"
    assert detect_file_language(Path("index.ts")) == "TypeScript"
    assert detect_file_language(Path("component.tsx")) == "TypeScript"
    assert detect_file_language(Path("server.js")) == "JavaScript"
    assert detect_file_language(Path("Main.java")) == "Java"
    assert detect_file_language(Path("main.go")) == "Go"
    assert detect_file_language(Path("system.c")) == "C"
    assert detect_file_language(Path("driver.cpp")) == "C++"
    assert detect_file_language(Path("Cargo.toml")) == "TOML"
    assert detect_file_language(Path("Dockerfile")) == "Dockerfile"
    assert detect_file_language(Path("Makefile")) == "Makefile"
    assert detect_file_language(Path("README.md")) == "Markdown"

def test_count_file_lines():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".py") as f:
        f.write("def foo():\n\n    return 42\n")
        f_path = Path(f.name)

    try:
        lines = count_file_lines(f_path)
        assert lines == 2  # 2 non-empty lines
    finally:
        f_path.unlink()

def test_analyze_repository_structure():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir) / "sample_repo"
        repo_dir.mkdir()

        (repo_dir / "README.md").write_text("# Sample Project\nArchitecture documentation.", encoding="utf-8")
        (repo_dir / "package.json").write_text('{"name": "test"}', encoding="utf-8")
        (repo_dir / "index.ts").write_text("console.log('main');", encoding="utf-8")
        
        src_dir = repo_dir / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("print('python app')", encoding="utf-8")

        accepted = [
            repo_dir / "README.md",
            repo_dir / "package.json",
            repo_dir / "index.ts",
            src_dir / "app.py",
        ]

        analysis = analyze_repository(repo_dir, accepted)

        assert analysis.file_count == 4
        assert analysis.total_line_count > 0
        assert "package.json" in analysis.manifest_files
        assert any("index.ts" in ep or "app.py" in ep for ep in analysis.entry_points)
        assert analysis.readme_content is not None
        assert "Sample Project" in analysis.readme_content

        # Tree checks
        tree = analysis.directory_tree
        assert tree.type == "directory"
        child_names = [c.name for c in tree.children] if tree.children else []
        assert "src" in child_names
        assert "index.ts" in child_names

