"""
Structure-aware code chunking engine for Vector RAG.
Consumes the shared Phase 3 ParsedRepository intermediate representation,
prioritizes semantic AST symbols (functions, methods, classes, interfaces),
splits oversized symbols into overlapping sub-chunks without losing context,
and provides semantic fallback chunking for Markdown documentation and configuration manifests.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

from backend.app.processing.models import ParsedRepository, ParsedFile, ExtractedSymbol, SymbolType
from backend.app.vectorstore.interfaces import CodeChunk

logger = logging.getLogger(__name__)

# Extensions recognized as documentation or configuration files
DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}
CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml",
    "dockerfile", "makefile", "requirements.txt", "cargo.toml", "package.json",
}


class StructureAwareChunker:
    """
    Transforms parsed repositories into structure-aware CodeChunk objects.
    """

    def __init__(
        self,
        max_chunk_lines: int = 100,
        chunk_overlap_lines: int = 20,
        max_chunk_chars: int = 3000,
    ) -> None:
        self.max_chunk_lines = max_chunk_lines
        self.chunk_overlap_lines = chunk_overlap_lines
        self.max_chunk_chars = max_chunk_chars

    def chunk_repository(
        self,
        parsed_repo: ParsedRepository,
        accepted_files: Optional[List[Union[Path, str]]] = None,
        repo_dir: Optional[Path] = None,
    ) -> List[CodeChunk]:
        """
        Produce complete, structure-aware code chunks for an entire repository.
        Combines AST symbol chunks with non-AST doc and config chunks.
        """
        chunks: List[CodeChunk] = []

        # 1. Process AST-parsed files from ParsedRepository
        for file_path, file_data in parsed_repo.files.items():
            if file_data.symbols:
                file_chunks = self.chunk_parsed_file(parsed_repo.repository_id, file_data)
                chunks.extend(file_chunks)
            else:
                # File was parsed but has no AST symbols (e.g. simple script, markdown, or config)
                fallback_chunks = self._chunk_fallback_file(
                    repo_id=parsed_repo.repository_id,
                    file_path=file_path,
                    language=file_data.language,
                    repo_dir=repo_dir,
                )
                chunks.extend(fallback_chunks)

        # 2. Process non-AST files that were accepted during ingestion (e.g. README.md, package.json)
        if accepted_files and repo_dir:
            parsed_file_set = set(parsed_repo.files.keys())
            for item in accepted_files:
                rel_path = (
                    item.relative_to(repo_dir).as_posix()
                    if isinstance(item, Path)
                    else str(item).replace("\\", "/")
                )
                if rel_path not in parsed_file_set:
                    doc_or_config_chunks = self._chunk_fallback_file(
                        repo_id=parsed_repo.repository_id,
                        file_path=rel_path,
                        language="Documentation" if Path(rel_path).suffix.lower() in DOC_EXTENSIONS else "Configuration",
                        repo_dir=repo_dir,
                    )
                    chunks.extend(doc_or_config_chunks)

        logger.info(f"Generated {len(chunks)} structure-aware code chunks for {parsed_repo.repository_id}.")
        return chunks

    def chunk_parsed_file(
        self,
        repo_id: str,
        parsed_file: ParsedFile,
    ) -> List[CodeChunk]:
        """Generate structure-aware chunks for an individual AST-parsed file."""
        chunks: List[CodeChunk] = []

        for sym in parsed_file.symbols:
            lines = sym.source_code.split("\n")
            line_count = len(lines)

            # If symbol fits within normal limits, emit a single complete chunk
            if line_count <= self.max_chunk_lines and len(sym.source_code) <= self.max_chunk_chars:
                header = self._build_header(
                    repo_id=repo_id,
                    file_path=parsed_file.file_path,
                    start_line=sym.location.start_line,
                    end_line=sym.location.end_line,
                    sym_name=sym.name,
                    sym_type=sym.symbol_type.value,
                    docstring=sym.docstring,
                )
                full_content = f"{header}\n{sym.source_code}"
                content_hash = sym.content_hash or self._compute_hash(sym.source_code)

                chunks.append(
                    CodeChunk(
                        chunk_id=f"chunk:{sym.symbol_id}",
                        repository_id=repo_id,
                        file_path=parsed_file.file_path,
                        symbol_id=sym.symbol_id,
                        symbol_name=sym.name,
                        symbol_type=sym.symbol_type.value,
                        parent_symbol_id=sym.parent_symbol_id,
                        language=parsed_file.language,
                        start_line=sym.location.start_line,
                        end_line=sym.location.end_line,
                        source_code=sym.source_code,
                        signature=sym.signature,
                        docstring=sym.docstring,
                        content_hash=content_hash,
                        context_header=header,
                        full_content=full_content,
                        part_index=0,
                        total_parts=1,
                    )
                )
            else:
                # Symbol is large: perform controlled splitting into overlapping sub-chunks
                sub_chunks = self._split_large_symbol(repo_id, parsed_file, sym, lines)
                chunks.extend(sub_chunks)

        return chunks

    def _split_large_symbol(
        self,
        repo_id: str,
        parsed_file: ParsedFile,
        sym: ExtractedSymbol,
        lines: List[str],
    ) -> List[CodeChunk]:
        """Splits an oversized symbol into overlapping chunks while preserving line coordinates and parent scope."""
        chunks: List[CodeChunk] = []
        total_lines = len(lines)
        step = max(1, self.max_chunk_lines - self.chunk_overlap_lines)

        slices: List[Tuple[int, int]] = []
        start_idx = 0
        while start_idx < total_lines:
            end_idx = min(start_idx + self.max_chunk_lines, total_lines)
            slices.append((start_idx, end_idx))
            if end_idx >= total_lines:
                break
            start_idx += step

        total_parts = len(slices)

        for part_idx, (s_idx, e_idx) in enumerate(slices):
            sub_lines = lines[s_idx:e_idx]
            sub_source = "\n".join(sub_lines)
            sub_start_line = sym.location.start_line + s_idx
            sub_end_line = sym.location.start_line + e_idx - 1

            header = self._build_header(
                repo_id=repo_id,
                file_path=parsed_file.file_path,
                start_line=sub_start_line,
                end_line=sub_end_line,
                sym_name=sym.name,
                sym_type=sym.symbol_type.value,
                docstring=sym.docstring,
                part_info=f"(Part {part_idx + 1} of {total_parts})",
            )
            full_content = f"{header}\n{sub_source}"
            content_hash = self._compute_hash(sub_source)

            chunks.append(
                CodeChunk(
                    chunk_id=f"chunk:{sym.symbol_id}#part_{part_idx + 1}",
                    repository_id=repo_id,
                    file_path=parsed_file.file_path,
                    symbol_id=sym.symbol_id,
                    symbol_name=sym.name,
                    symbol_type=sym.symbol_type.value,
                    parent_symbol_id=sym.parent_symbol_id,
                    language=parsed_file.language,
                    start_line=sub_start_line,
                    end_line=sub_end_line,
                    source_code=sub_source,
                    signature=sym.signature,
                    docstring=sym.docstring,
                    content_hash=content_hash,
                    context_header=header,
                    full_content=full_content,
                    part_index=part_idx,
                    total_parts=total_parts,
                )
            )

        return chunks

    def _chunk_fallback_file(
        self,
        repo_id: str,
        file_path: str,
        language: str,
        repo_dir: Optional[Path],
    ) -> List[CodeChunk]:
        """Generates semantic chunks for markdown docs, READMEs, and config files."""
        if not repo_dir:
            return []

        full_path = repo_dir / file_path
        if not full_path.is_file():
            return []

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        lines = content.split("\n")
        total_lines = len(lines)
        if total_lines == 0 or not content.strip():
            return []

        suffix = Path(file_path).suffix.lower()
        chunks: List[CodeChunk] = []

        # Markdown / README: split on headers (#, ##, ###)
        if suffix in DOC_EXTENSIONS:
            header_indices: List[Tuple[int, str]] = []
            for idx, line in enumerate(lines):
                if re.match(r"^#{1,3}\s+", line):
                    header_indices.append((idx, line.strip()))

            if header_indices:
                for h_idx, (start_line_idx, heading) in enumerate(header_indices):
                    end_line_idx = (
                        header_indices[h_idx + 1][0]
                        if h_idx + 1 < len(header_indices)
                        else total_lines
                    )
                    section_lines = lines[start_line_idx:end_line_idx]
                    section_text = "\n".join(section_lines).strip()
                    if not section_text:
                        continue

                    s_line = start_line_idx + 1
                    e_line = end_line_idx
                    header = f"# Repository: {repo_id} | File: {file_path} (Lines {s_line}-{e_line})\n# Section: {heading}"
                    clean_head = re.sub(r"^#{1,3}\s*", "", heading).strip()

                    chunks.append(
                        CodeChunk(
                            chunk_id=f"chunk:{repo_id}:{file_path}#section_{h_idx + 1}",
                            repository_id=repo_id,
                            file_path=file_path,
                            symbol_name=clean_head,
                            symbol_type="DOC",
                            language="Markdown",
                            start_line=s_line,
                            end_line=e_line,
                            source_code=section_text,
                            docstring=clean_head,
                            content_hash=self._compute_hash(section_text),
                            context_header=header,
                            full_content=f"{header}\n{section_text}",
                        )
                    )
                return chunks

        # Config / Manifest / plain text file: chunk with sliding window
        step = max(1, self.max_chunk_lines - self.chunk_overlap_lines)
        part_idx = 0
        start = 0

        while start < total_lines:
            end = min(start + self.max_chunk_lines, total_lines)
            chunk_lines = lines[start:end]
            chunk_text = "\n".join(chunk_lines).strip()
            if chunk_text:
                s_line = start + 1
                e_line = end
                header = f"# Repository: {repo_id} | File: {file_path} (Lines {s_line}-{e_line})"

                chunks.append(
                    CodeChunk(
                        chunk_id=f"chunk:{repo_id}:{file_path}#part_{part_idx + 1}",
                        repository_id=repo_id,
                        file_path=file_path,
                        symbol_name=Path(file_path).name,
                        symbol_type="CONFIG" if suffix in CONFIG_EXTENSIONS or Path(file_path).name.lower() in CONFIG_EXTENSIONS else "FILE",
                        language=language,
                        start_line=s_line,
                        end_line=e_line,
                        source_code=chunk_text,
                        content_hash=self._compute_hash(chunk_text),
                        context_header=header,
                        full_content=f"{header}\n{chunk_text}",
                        part_index=part_idx,
                    )
                )
                part_idx += 1
            if end >= total_lines:
                break
            start += step

        return chunks

    def _build_header(
        self,
        repo_id: str,
        file_path: str,
        start_line: int,
        end_line: int,
        sym_name: str,
        sym_type: str,
        docstring: Optional[str] = None,
        part_info: str = "",
    ) -> str:
        parts = [f"# File: {file_path} (Lines {start_line}-{end_line})", f"[{sym_type}: {sym_name}]"]
        if part_info:
            parts.append(part_info)
        header = " ".join(parts)
        if docstring:
            header += f"\n# Docstring: {docstring.strip()}"
        return header

    @staticmethod
    def _compute_hash(text: str) -> str:
        norm = text.strip().replace("\r\n", "\n")
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


# Global default chunker instance
chunker = StructureAwareChunker()

