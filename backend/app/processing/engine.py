"""
Unified Code Understanding Engine.
Shared parsing orchestrator that coordinates Tree-sitter AST parsers and language-specific extractors.
Produces the single intermediate representation consumed by Vector RAG and GraphRAG.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List, Union

from backend.app.config import settings
from backend.app.processing.models import (
    ParsedFile,
    ParsedRepository,
)
from backend.app.processing.treesitter_manager import language_manager
from backend.app.processing.extractors.base import BaseExtractor
from backend.app.processing.extractors.python_extractor import PythonExtractor
from backend.app.processing.extractors.javascript_extractor import JavaScriptExtractor
from backend.app.processing.extractors.java_extractor import JavaExtractor
from backend.app.processing.extractors.c_cpp_extractor import CCppExtractor
from backend.app.processing.extractors.go_extractor import GoExtractor

logger = logging.getLogger(__name__)


class CodeUnderstandingEngine:
    """
    High-level engine for AST-based code understanding.
    Parses individual source files or full repositories into structured intermediate models.
    """

    def __init__(self) -> None:
        self.language_manager = language_manager
        self._extractors: Dict[str, BaseExtractor] = {
            "python": PythonExtractor(),
            "javascript": JavaScriptExtractor("javascript"),
            "typescript": JavaScriptExtractor("typescript"),
            "tsx": JavaScriptExtractor("tsx"),
            "java": JavaExtractor(),
            "c": CCppExtractor("c"),
            "cpp": CCppExtractor("cpp"),
            "go": GoExtractor(),
        }

    def register_extractor(self, language_name: str, extractor: BaseExtractor) -> None:
        """Register a custom or additional language extractor."""
        self._extractors[language_name.lower()] = extractor

    def parse_source_code(
        self,
        source: Union[str, bytes],
        file_path: str,
        repo_id: str,
        commit_hash: Optional[str] = None,
    ) -> Optional[ParsedFile]:
        """
        Parse raw source code (string or bytes) into structured AST symbols.
        """
        source_bytes = source.encode("utf-8") if isinstance(source, str) else source
        suffix = Path(file_path).suffix.lower()
        language_name = self.language_manager.get_language_for_extension(suffix)

        if not language_name or language_name not in self._extractors:
            # Fallback representation for unsupported languages
            line_count = len(source_bytes.split(b"\n"))
            return ParsedFile(
                file_path=file_path,
                repository_id=repo_id,
                language=language_name or "Unknown",
                commit_hash=commit_hash,
                line_count=line_count,
                size_bytes=len(source_bytes),
            )

        tree = self.language_manager.parse_source(source_bytes, language_name)
        if not tree or not tree.root_node:
            logger.warning(f"Failed to generate AST for {file_path}")
            return None

        extractor = self._extractors[language_name]
        try:
            return extractor.extract(
                root_node=tree.root_node,
                source_bytes=source_bytes,
                file_path=file_path,
                repo_id=repo_id,
                commit_hash=commit_hash,
            )
        except Exception as e:
            logger.error(f"Error extracting symbols from {file_path}: {e}", exc_info=True)
            # Return partial fallback rather than crashing
            line_count = len(source_bytes.split(b"\n"))
            return ParsedFile(
                file_path=file_path,
                repository_id=repo_id,
                language=language_name,
                commit_hash=commit_hash,
                syntax_errors=[f"Extractor error: {str(e)}"],
                line_count=line_count,
                size_bytes=len(source_bytes),
            )

    def parse_file(
        self,
        base_dir: Path,
        relative_path: str,
        repo_id: str,
        commit_hash: Optional[str] = None,
    ) -> Optional[ParsedFile]:
        """
        Read and parse a file from disk into structured AST symbols.
        Safely enforces size limits, character encodings, and error handling.
        """
        full_path = base_dir / relative_path
        if not full_path.is_file():
            logger.warning(f"File not found: {full_path}")
            return None

        # Check file size limit (500 KB default)
        file_size = full_path.stat().st_size
        max_bytes = settings.MAX_FILE_SIZE_KB * 1024
        if file_size > max_bytes:
            logger.warning(f"Skipping oversized file {relative_path} ({file_size} bytes > {max_bytes})")
            return None

        try:
            source_bytes = full_path.read_bytes()
        except Exception as e:
            logger.warning(f"Failed to read file {relative_path}: {e}")
            return None

        # Probe for binary null bytes
        if b"\x00" in source_bytes[:8000]:
            logger.debug(f"Skipping binary file with null bytes: {relative_path}")
            return None

        return self.parse_source_code(
            source=source_bytes,
            file_path=relative_path,
            repo_id=repo_id,
            commit_hash=commit_hash,
        )

    def parse_repository(
        self,
        repo_dir: Path,
        files: List[Union[Path, str]],
        repo_id: str,
        commit_hash: Optional[str] = None,
    ) -> ParsedRepository:
        """
        Parse an entire repository of filtered files into a unified ParsedRepository structure.
        """
        parsed_files: Dict[str, ParsedFile] = {}
        total_symbols = 0
        languages_found = set()

        for f_item in files:
            if isinstance(f_item, Path):
                try:
                    rel_path = f_item.relative_to(repo_dir).as_posix()
                except ValueError:
                    rel_path = f_item.as_posix()
            else:
                rel_path = str(f_item).replace("\\", "/")

            parsed = self.parse_file(
                base_dir=repo_dir,
                relative_path=rel_path,
                repo_id=repo_id,
                commit_hash=commit_hash,
            )
            if parsed:
                parsed_files[parsed.file_path] = parsed
                total_symbols += len(parsed.symbols)
                if parsed.language and parsed.language != "Unknown":
                    languages_found.add(parsed.language)

        return ParsedRepository(
            repository_id=repo_id,
            commit_hash=commit_hash,
            files=parsed_files,
            total_symbols=total_symbols,
            total_files=len(parsed_files),
            supported_languages=sorted(list(languages_found)),
        )


# Global default engine instance
code_engine = CodeUnderstandingEngine()
