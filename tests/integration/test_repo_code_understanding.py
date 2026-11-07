"""
Integration test for full repository code understanding and shared parsing.
Verifies parsing of a multi-language repository structure from disk.
"""

import tempfile
from pathlib import Path
import pytest
from backend.app.ingestion.file_filter import filter_repository
from backend.app.processing.engine import code_engine
from backend.app.processing.adapters import to_graph_elements, to_code_chunks


def test_full_repository_parsing_flow():
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir)

        # 1. Python file
        py_file = repo_path / "app.py"
        py_file.write_text(
            """
import os

class App:
    def run(self):
        print("Running")
""",
            encoding="utf-8",
        )

        # 2. TypeScript file
        ts_file = repo_path / "server.ts"
        ts_file.write_text(
            """
import express from 'express';

export interface Config {
    port: number;
}

export function start(cfg: Config): void {
    console.log(cfg.port);
}
""",
            encoding="utf-8",
        )

        # 3. Go file
        go_file = repo_path / "main.go"
        go_file.write_text(
            """
package main

import "fmt"

func main() {
    fmt.Println("RepoMind Engine")
}
""",
            encoding="utf-8",
        )

        # 4. Filter repository using Phase 2 ingestion filter
        accepted, filtered, total = filter_repository(repo_path)
        assert len(accepted) == 3

        # 5. Parse repository using Phase 3 Code Understanding Engine
        parsed_repo = code_engine.parse_repository(
            repo_dir=repo_path,
            files=accepted,
            repo_id="test/repomind-sample",
            commit_hash="commit_xyz999",
        )

        assert parsed_repo.repository_id == "test/repomind-sample"
        assert parsed_repo.commit_hash == "commit_xyz999"
        assert parsed_repo.total_files == 3
        assert parsed_repo.total_symbols >= 4
        assert "python" in parsed_repo.supported_languages
        assert "typescript" in parsed_repo.supported_languages
        assert "go" in parsed_repo.supported_languages

        # 6. Verify GraphRAG Adapter
        nodes, edges = to_graph_elements(parsed_repo)
        assert len(nodes) >= 7  # Repo + 3 files + at least 3 symbols
        assert len(edges) >= 6

        # 7. Verify Vector RAG Adapter
        chunks = to_code_chunks(parsed_repo)
        assert len(chunks) == parsed_repo.total_symbols
        for ch in chunks:
            assert ch["metadata"]["repository_id"] == "test/repomind-sample"
            assert ch["metadata"]["commit_hash"] == "commit_xyz999"

