import os
import stat
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from backend.app.config import settings
from backend.app.utils.validators import validate_github_url

class CloneResult(BaseModel):
    success: bool
    repository_id: str
    owner: str
    name: str
    target_dir: Optional[str] = None
    commit_hash: Optional[str] = None
    default_branch: Optional[str] = None
    size_bytes: int = 0
    error_message: Optional[str] = None

def find_git_executable() -> str:
    """Discovers git executable with fallback to GitHub Desktop / standard Windows paths."""
    git_bin = shutil.which("git")
    if git_bin:
        return git_bin

    # Check Windows GitHub Desktop installation
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        gh_desktop = Path(local_app_data) / "GitHubDesktop"
        if gh_desktop.exists():
            for g in gh_desktop.glob("app-*/resources/app/git/cmd/git.exe"):
                if g.exists():
                    return str(g)

    common_paths = [
        Path("C:/Program Files/Git/cmd/git.exe"),
        Path("C:/Program Files/Git/bin/git.exe"),
        Path("C:/Program Files (x86)/Git/cmd/git.exe"),
    ]
    for cp in common_paths:
        if cp.exists():
            return str(cp)

    return "git"

def remove_readonly(func, path, excinfo):
    """
    Error handler for shutil.rmtree on Windows to remove read-only attribute
    on files inside .git directory.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def cleanup_workspace(workspace_dir: Path) -> None:
    """Safely removes an isolated temporary workspace directory."""
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir, onerror=remove_readonly)

def get_dir_size_bytes(directory: Path) -> int:
    """Calculates total byte size of a directory recursively."""
    total = 0
    for root, _, files in os.walk(directory):
        for f in files:
            fp = Path(root) / f
            try:
                total += fp.stat().st_size
            except OSError:
                pass
    return total

class RepositoryCloner:
    """
    Manages secure, shallow Git cloning into isolated temporary workspaces.
    Enforces timeouts, size caps, and security boundaries.
    """

    def __init__(self, temp_base_dir: Optional[Path] = None):
        self.temp_base_dir = temp_base_dir or (settings.STORAGE_DIR / "temp_repos")
        self.temp_base_dir.mkdir(parents=True, exist_ok=True)
        self.git_executable = find_git_executable()

    def clone_repository(
        self,
        repo_url: str,
        repository_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> CloneResult:
        # Validate GitHub URL strictly
        is_valid, owner, name, err = validate_github_url(repo_url)
        if not is_valid or not owner or not name:
            return CloneResult(
                success=False,
                repository_id=repository_id or str(uuid.uuid4()),
                owner=owner or "unknown",
                name=name or "unknown",
                error_message=f"Invalid GitHub URL: {err}",
            )

        repo_id = repository_id or str(uuid.uuid4())
        dest_dir = self.temp_base_dir / repo_id

        # Clean destination if it already exists
        if dest_dir.exists():
            cleanup_workspace(dest_dir)

        dest_dir.mkdir(parents=True, exist_ok=True)
        timeout = timeout_seconds or settings.CLONE_TIMEOUT_SECONDS

        normalized_url = f"https://github.com/{owner}/{name}.git"

        # Git shallow clone arguments:
        # --depth 1: shallow clone only the latest commit
        # --single-branch: fetch only default branch to minimize data transfer
        # --no-tags: do not fetch tags
        # -c core.symlinks=false: prevent malicious symlink traversal outside workspace
        # -c submodule.recurse=false: prevent untrusted submodule fetches
        clone_cmd = [
            self.git_executable,
            "clone",
            "-c", "core.symlinks=false",
            "-c", "submodule.recurse=false",
            "--depth", "1",
            "--single-branch",
            "--no-tags",
            normalized_url,
            str(dest_dir),
        ]

        # Non-interactive Git environment to prevent prompts for private or nonexistent repos
        git_env = os.environ.copy()
        git_env["GIT_TERMINAL_PROMPT"] = "0"
        git_env["GCM_INTERACTIVE"] = "never"
        git_env["GIT_ASKPASS"] = ""
        git_env["GIT_ALLOW_PROTOCOL"] = "https"

        try:
            # Execute clone in isolated subprocess with strict timeout
            process = subprocess.run(
                clone_cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=git_env,
                check=False,
            )

            if process.returncode != 0:
                err_msg = process.stderr.strip() or process.stdout.strip() or "Git clone failed."
                cleanup_workspace(dest_dir)
                return CloneResult(
                    success=False,
                    repository_id=repo_id,
                    owner=owner,
                    name=name,
                    error_message=f"Git clone error: {err_msg}",
                )

            # Check total repository size on disk
            total_size = get_dir_size_bytes(dest_dir)
            max_size_bytes = settings.MAX_REPO_SIZE_MB * 1024 * 1024
            if total_size > max_size_bytes:
                cleanup_workspace(dest_dir)
                return CloneResult(
                    success=False,
                    repository_id=repo_id,
                    owner=owner,
                    name=name,
                    error_message=f"Repository size ({total_size // (1024*1024)} MB) exceeds maximum allowed limit ({settings.MAX_REPO_SIZE_MB} MB).",
                )

            # Extract latest commit hash
            commit_hash = None
            try:
                rev_proc = subprocess.run(
                    [self.git_executable, "-C", str(dest_dir), "rev-parse", "HEAD"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=git_env,
                    check=False,
                )
                if rev_proc.returncode == 0:
                    commit_hash = rev_proc.stdout.strip()
            except Exception:
                pass

            # Extract default branch name
            default_branch = "main"
            try:
                branch_proc = subprocess.run(
                    [self.git_executable, "-C", str(dest_dir), "rev-parse", "--abbrev-ref", "HEAD"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=git_env,
                    check=False,
                )
                if branch_proc.returncode == 0 and branch_proc.stdout.strip():
                    default_branch = branch_proc.stdout.strip()
            except Exception:
                pass

            return CloneResult(
                success=True,
                repository_id=repo_id,
                owner=owner,
                name=name,
                target_dir=str(dest_dir),
                commit_hash=commit_hash,
                default_branch=default_branch,
                size_bytes=total_size,
            )

        except subprocess.TimeoutExpired:
            cleanup_workspace(dest_dir)
            return CloneResult(
                success=False,
                repository_id=repo_id,
                owner=owner,
                name=name,
                error_message=f"Cloning timed out after {timeout} seconds.",
            )
        except Exception as e:
            cleanup_workspace(dest_dir)
            return CloneResult(
                success=False,
                repository_id=repo_id,
                owner=owner,
                name=name,
                error_message=f"Unexpected cloning error: {str(e)}",
            )
