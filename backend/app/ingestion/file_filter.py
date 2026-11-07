import os
from pathlib import Path
from typing import List, Tuple, Set, Optional
from backend.app.config import settings

# Directory blacklist
EXCLUDED_DIRS: Set[str] = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
    ".next",
    ".nuxt",
    ".terraform",
    ".serverless",
    "target",  # Rust/Java target
    "bin",
    "obj",
    "vendor",
    "coverage",
    ".nyc_output",
    ".tox",
    ".nox",
    ".cache",
    ".gradle",
}

# Binary and compiled extensions blacklist
EXCLUDED_EXTENSIONS: Set[str] = {
    # Binaries & Shared Libraries
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pyd", ".o", ".a", ".lib",
    # Compiled Bytecode
    ".pyc", ".pyo", ".class",
    # Archives & Compressed
    ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz", ".iso", ".jar", ".war",
    # Images & Graphics
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".bmp", ".tiff", ".webp",
    # Audio & Video
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac",
    # Documents & Formats
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Database & Heavy Storage
    ".db", ".sqlite", ".sqlite3", ".parquet", ".arrow", ".h5", ".pkl", ".pickle",
    # Web Assembly & Models
    ".wasm", ".tflite", ".onnx", ".pt", ".pth", ".weights",
    # Source Maps & Minified
    ".map",
}

# Explicit filenames to blacklist (secrets, lockfiles, generated)
EXCLUDED_FILENAMES: Set[str] = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "credentials.json",
    "service_account.json",
    ".ds_store",
    "thumbs.db",
}

def is_secret_file(filename: str) -> bool:
    """Checks if a file appears to contain sensitive credentials, keys, or secrets."""
    lowered = filename.lower()

    if lowered in EXCLUDED_FILENAMES:
        if any(sec in lowered for sec in ("credential", "service_account", "id_rsa", "id_dsa", "id_ed25519")):
            return True

    if lowered.startswith(".env") or lowered.endswith(".env"):
        return True

    if any(lowered.endswith(ext) for ext in (".pem", ".key", ".pfx", ".p12", ".crt", ".der", ".pkcs12")):
        return True

    if any(k in lowered for k in ("secret", "credential", "service_account", "serviceaccount", "password", "token")):
        ext = Path(filename).suffix.lower()
        if ext in (".json", ".txt", ".yaml", ".yml", ".ini", ".conf", ""):
            return True

    return False

def is_binary_file(file_path: Path) -> bool:
    """Checks whether a file is binary by inspecting its initial bytes for null characters."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
        return False
    except Exception:
        return True

def should_filter_path(rel_path: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether a relative file path should be excluded based on directory,
    filename, extension, or minification patterns.
    """
    normalized = rel_path.replace("\\", "/").strip("/")
    parts = normalized.split("/")

    # Check directory components
    for part in parts[:-1]:
        if part.lower() in EXCLUDED_DIRS or part.startswith("."):
            return True, f"Excluded directory: {part}"

    filename = parts[-1]
    lowered_name = filename.lower()

    # Check explicit filenames
    if lowered_name in EXCLUDED_FILENAMES:
        return True, f"Excluded filename: {filename}"

    # Check secret patterns
    if is_secret_file(filename):
        return True, "Security filter: sensitive credential or secret file"

    # Check minified code files
    if lowered_name.endswith(".min.js") or lowered_name.endswith(".min.css"):
        return True, "Excluded minified asset"

    # Check extensions
    ext = Path(filename).suffix.lower()
    if ext in EXCLUDED_EXTENSIONS:
        return True, f"Excluded binary extension: {ext}"

    return False, None

def filter_repository(repo_dir: Path) -> Tuple[List[Path], List[Tuple[str, str]], int]:
    """
    Traverses the cloned repository and applies strict filtering rules.

    Returns:
        (accepted_files, filtered_out_files_with_reasons, total_raw_files)
    """
    accepted: List[Path] = []
    filtered: List[Tuple[str, str]] = []
    total_raw_count = 0

    max_size_bytes = settings.MAX_FILE_SIZE_KB * 1024
    max_indexed_files = settings.MAX_INDEXED_FILES

    for root, dirs, files in os.walk(repo_dir):
        # Prune excluded directories in-place to prevent unnecessary traversal
        dirs[:] = [d for d in dirs if d.lower() not in EXCLUDED_DIRS and not d.startswith(".")]

        for file in files:
            total_raw_count += 1
            abs_path = Path(root) / file
            try:
                rel_path = abs_path.relative_to(repo_dir).as_posix()
            except ValueError:
                rel_path = file

            # Fast path check
            should_filter, reason = should_filter_path(rel_path)
            if should_filter:
                filtered.append((rel_path, reason or "Excluded"))
                continue

            # Size check
            try:
                size = abs_path.stat().st_size
                if size > max_size_bytes:
                    filtered.append((rel_path, f"Exceeds max file size ({size // 1024} KB > {settings.MAX_FILE_SIZE_KB} KB)"))
                    continue
                if size == 0:
                    filtered.append((rel_path, "Empty file (0 bytes)"))
                    continue
            except OSError as e:
                filtered.append((rel_path, f"Could not inspect file: {str(e)}"))
                continue

            # Binary content check
            if is_binary_file(abs_path):
                filtered.append((rel_path, "Binary content detected (null byte probe)"))
                continue

            accepted.append(abs_path)

            # Cap at max_indexed_files
            if len(accepted) >= max_indexed_files:
                break

        if len(accepted) >= max_indexed_files:
            break

    return accepted, filtered, total_raw_count
