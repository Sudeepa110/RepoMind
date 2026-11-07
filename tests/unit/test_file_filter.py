import os
import tempfile
from pathlib import Path
import pytest
from backend.app.ingestion.file_filter import (
    should_filter_path,
    is_secret_file,
    is_binary_file,
    filter_repository,
)

def test_should_filter_directories():
    # Excluded directories
    assert should_filter_path(".git/config")[0] is True
    assert should_filter_path("node_modules/express/index.js")[0] is True
    assert should_filter_path("venv/lib/python3.11/site-packages/pkg.py")[0] is True
    assert should_filter_path(".venv/bin/activate")[0] is True
    assert should_filter_path("dist/assets/index.js")[0] is True
    assert should_filter_path("build/output.js")[0] is True
    assert should_filter_path("__pycache__/main.cpython-311.pyc")[0] is True
    assert should_filter_path(".idea/workspace.xml")[0] is True
    assert should_filter_path(".vscode/settings.json")[0] is True
    assert should_filter_path("target/debug/app.exe")[0] is True

    # Allowed nested directories
    assert should_filter_path("src/components/Header.tsx")[0] is False
    assert should_filter_path("backend/app/api/routes.py")[0] is False
    assert should_filter_path("lib/utils/helpers.go")[0] is False

def test_should_filter_extensions():
    # Binary and compiled assets
    assert should_filter_path("binary.exe")[0] is True
    assert should_filter_path("library.dll")[0] is True
    assert should_filter_path("lib.so")[0] is True
    assert should_filter_path("bytecode.pyc")[0] is True
    assert should_filter_path("archive.zip")[0] is True
    assert should_filter_path("image.png")[0] is True
    assert should_filter_path("photo.jpg")[0] is True
    assert should_filter_path("video.mp4")[0] is True
    assert should_filter_path("document.pdf")[0] is True
    assert should_filter_path("database.sqlite3")[0] is True
    assert should_filter_path("bundle.js.map")[0] is True

    # Allowed extensions
    assert should_filter_path("app.py")[0] is False
    assert should_filter_path("index.ts")[0] is False
    assert should_filter_path("Main.java")[0] is False
    assert should_filter_path("server.go")[0] is False
    assert should_filter_path("kernel.c")[0] is False
    assert should_filter_path("README.md")[0] is False
    assert should_filter_path("package.json")[0] is False

def test_secret_files_detection():
    # Credential and key files
    assert is_secret_file(".env") is True
    assert is_secret_file(".env.local") is True
    assert is_secret_file(".env.production") is True
    assert is_secret_file("server.key") is True
    assert is_secret_file("certificate.pem") is True
    assert is_secret_file("credentials.json") is True
    assert is_secret_file("service_account.json") is True
    assert is_secret_file("id_rsa") is True

    # Normal code files with similar words shouldn't be blocked if not secrets
    assert is_secret_file("auth_service.py") is False

def test_binary_null_byte_probe():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        text_file = tmp_path / "normal.txt"
        text_file.write_text("Hello, this is regular code with no null bytes.", encoding="utf-8")
        assert is_binary_file(text_file) is False

        bin_file = tmp_path / "corrupt.txt"
        bin_file.write_bytes(b"Header\x00BinaryPayload\x00Data")
        assert is_binary_file(bin_file) is True

def test_filter_repository_integration():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir) / "test_repo"
        repo_dir.mkdir()

        # Create valid files
        (repo_dir / "main.py").write_text("def main(): pass", encoding="utf-8")
        (repo_dir / "README.md").write_text("# Test Repo", encoding="utf-8")
        sub_dir = repo_dir / "src" / "utils"
        sub_dir.mkdir(parents=True)
        (sub_dir / "helpers.ts").write_text("export const add = (a, b) => a + b;", encoding="utf-8")

        # Create files that must be excluded
        (repo_dir / ".env").write_text("SECRET=123", encoding="utf-8")
        (repo_dir / "app.exe").write_bytes(b"MZ\x90\x00executable")
        node_dir = repo_dir / "node_modules" / "pkg"
        node_dir.mkdir(parents=True)
        (node_dir / "index.js").write_text("console.log('vendor');", encoding="utf-8")

        # Run filter
        accepted, filtered, total_raw = filter_repository(repo_dir)

        accepted_rel = [p.relative_to(repo_dir).as_posix() for p in accepted]
        assert "main.py" in accepted_rel
        assert "README.md" in accepted_rel
        assert "src/utils/helpers.ts" in accepted_rel

        # Ensure excluded files are NOT in accepted
        assert ".env" not in accepted_rel
        assert "app.exe" not in accepted_rel
        assert "node_modules/pkg/index.js" not in accepted_rel

