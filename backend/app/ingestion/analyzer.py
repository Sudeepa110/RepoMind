import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Mapping of file extensions to programming languages
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    # Primary Supported Languages
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    # Additional Standard Languages
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "ReStructuredText",
    ".txt": "Text",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".sql": "SQL",
    ".dockerfile": "Dockerfile",
}

# Configuration manifests to identify
MANIFEST_FILENAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "cargo.toml",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "tsconfig.json",
    "makefile",
    "cmakelists.txt",
}

# Typical entry-point candidates across languages
ENTRY_POINT_FILENAMES = {
    "main.py",
    "app.py",
    "run.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.ts",
    "index.js",
    "main.ts",
    "main.js",
    "server.ts",
    "server.js",
    "app.ts",
    "app.js",
    "main.go",
    "main.java",
    "app.tsx",
}

class LanguageStat(BaseModel):
    name: str
    file_count: int = 0
    line_count: int = 0
    byte_count: int = 0
    percentage: float = 0.0

class AnalyzedFile(BaseModel):
    relative_path: str
    language: str
    size_bytes: int
    line_count: int
    is_manifest: bool = False
    is_entrypoint: bool = False
    is_doc: bool = False

class TreeNode(BaseModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    size: int = 0
    language: Optional[str] = None
    line_count: Optional[int] = None
    children: Optional[List["TreeNode"]] = None

class RepositoryAnalysis(BaseModel):
    file_count: int
    total_size_bytes: int
    total_line_count: int
    primary_language: Optional[str] = None
    language_breakdown: List[LanguageStat]
    manifest_files: List[str]
    entry_points: List[str]
    readme_content: Optional[str] = None
    analyzed_files: List[AnalyzedFile]
    directory_tree: TreeNode

def detect_file_language(file_path: Path) -> str:
    """Detects programming language from extension or known filename."""
    name_lower = file_path.name.lower()

    if name_lower == "dockerfile" or name_lower.startswith("dockerfile."):
        return "Dockerfile"
    if name_lower == "makefile":
        return "Makefile"

    ext = file_path.suffix.lower()
    return EXTENSION_LANGUAGE_MAP.get(ext, "Plain Text")

def count_file_lines(file_path: Path) -> int:
    """Counts non-empty lines in a text file safely."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0

def extract_readme(repo_dir: Path) -> Optional[str]:
    """Finds and extracts repository README content up to 100 KB."""
    candidates = ["readme.md", "readme.rst", "readme.txt", "readme"]
    for item in os.listdir(repo_dir):
        if item.lower() in candidates:
            readme_path = repo_dir / item
            if readme_path.is_file():
                try:
                    with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
                        return f.read(100 * 1024)
                except Exception:
                    pass
    return None

def build_directory_tree(repo_dir: Path, accepted_files: List[Path]) -> TreeNode:
    """
    Constructs a clean nested tree representing the sanitized repository directory structure.
    """
    root_node = TreeNode(
        name=repo_dir.name,
        path="",
        type="directory",
        children=[],
    )

    tree_map: Dict[str, TreeNode] = {"": root_node}

    for abs_path in accepted_files:
        try:
            rel_path = abs_path.relative_to(repo_dir).as_posix()
        except ValueError:
            continue

        parts = rel_path.split("/")
        current_path = ""
        current_node = root_node

        # Build intermediate directories
        for part in parts[:-1]:
            current_path = f"{current_path}/{part}" if current_path else part
            if current_path not in tree_map:
                new_dir_node = TreeNode(
                    name=part,
                    path=current_path,
                    type="directory",
                    children=[],
                )
                tree_map[current_path] = new_dir_node
                if current_node.children is not None:
                    current_node.children.append(new_dir_node)
            current_node = tree_map[current_path]

        # Add the file node
        filename = parts[-1]
        try:
            size = abs_path.stat().st_size
        except OSError:
            size = 0
        lang = detect_file_language(abs_path)
        lines = count_file_lines(abs_path)

        file_node = TreeNode(
            name=filename,
            path=rel_path,
            type="file",
            size=size,
            language=lang,
            line_count=lines,
        )

        if current_node.children is not None:
            current_node.children.append(file_node)

    # Sort tree children: directories first, then alphabetical
    def sort_tree(node: TreeNode):
        if node.children:
            node.children.sort(key=lambda c: (0 if c.type == "directory" else 1, c.name.lower()))
            for child in node.children:
                sort_tree(child)

    sort_tree(root_node)
    return root_node

def analyze_repository(repo_dir: Path, accepted_files: List[Path]) -> RepositoryAnalysis:
    """
    Performs complete static analysis of the accepted repository files:
    language detection, lines of code, manifests, entry points, and directory structure.
    """
    analyzed_files: List[AnalyzedFile] = []
    language_counts: Dict[str, Dict[str, int]] = {}
    manifest_files: List[str] = []
    entry_points: List[str] = []

    total_size = 0
    total_lines = 0

    for abs_path in accepted_files:
        try:
            rel_path = abs_path.relative_to(repo_dir).as_posix()
        except ValueError:
            rel_path = abs_path.name

        filename = abs_path.name
        filename_lower = filename.lower()
        size = abs_path.stat().st_size if abs_path.exists() else 0
        lang = detect_file_language(abs_path)
        lines = count_file_lines(abs_path)

        total_size += size
        total_lines += lines

        # Manifest check
        is_manifest = filename_lower in MANIFEST_FILENAMES
        if is_manifest:
            manifest_files.append(rel_path)

        # Entry-point candidate check
        is_entrypoint = filename_lower in ENTRY_POINT_FILENAMES or rel_path.lower() in ("src/main.py", "src/index.ts", "src/index.js", "src/app.tsx")
        if is_entrypoint:
            entry_points.append(rel_path)

        # Doc file check
        is_doc = lang in ("Markdown", "ReStructuredText", "Text") or "doc" in rel_path.lower()

        analyzed_files.append(
            AnalyzedFile(
                relative_path=rel_path,
                language=lang,
                size_bytes=size,
                line_count=lines,
                is_manifest=is_manifest,
                is_entrypoint=is_entrypoint,
                is_doc=is_doc,
            )
        )

        # Aggregate language stats
        if lang not in language_counts:
            language_counts[lang] = {"file_count": 0, "line_count": 0, "byte_count": 0}
        language_counts[lang]["file_count"] += 1
        language_counts[lang]["line_count"] += lines
        language_counts[lang]["byte_count"] += size

    # Build language breakdown
    breakdown: List[LanguageStat] = []
    for lang, counts in language_counts.items():
        pct = (counts["line_count"] / total_lines * 100.0) if total_lines > 0 else 0.0
        breakdown.append(
            LanguageStat(
                name=lang,
                file_count=counts["file_count"],
                line_count=counts["line_count"],
                byte_count=counts["byte_count"],
                percentage=round(pct, 1),
            )
        )

    # Sort breakdown by line count descending
    breakdown.sort(key=lambda s: s.line_count, reverse=True)
    primary_language = breakdown[0].name if breakdown else None

    # Extract README
    readme_content = extract_readme(repo_dir)

    # Build directory tree
    directory_tree = build_directory_tree(repo_dir, accepted_files)

    return RepositoryAnalysis(
        file_count=len(analyzed_files),
        total_size_bytes=total_size,
        total_line_count=total_lines,
        primary_language=primary_language,
        language_breakdown=breakdown,
        manifest_files=manifest_files,
        entry_points=entry_points,
        readme_content=readme_content,
        analyzed_files=analyzed_files,
        directory_tree=directory_tree,
    )

