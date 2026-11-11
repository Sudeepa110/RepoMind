import re
from urllib.parse import urlparse
from typing import Tuple, Optional
import httpx

GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$"
)

def validate_github_url(url: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Validates a GitHub repository URL strictly to prevent SSRF and injection.

    Returns:
        (is_valid, owner, repo, error_message)
    """
    if not url or not isinstance(url, str):
        return False, None, None, "URL must be a non-empty string."

    url = url.strip()

    # Reject URLs containing control chars or dangerous traversal strings
    if any(char in url for char in ("\r", "\n", "\0", " ")):
        return False, None, None, "URL contains invalid characters."

    if ".." in url or "\\" in url:
        return False, None, None, "URL contains disallowed path characters."

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, None, None, f"Failed to parse URL: {str(e)}"

    if parsed.scheme.lower() != "https":
        return False, None, None, "Only HTTPS GitHub URLs are allowed."

    hostname = (parsed.hostname or "").lower()
    if hostname not in ("github.com", "www.github.com"):
        return False, None, None, "Destination must be github.com."

    # Prevent port tampering, credentials, or abnormal components
    if parsed.port and parsed.port != 443:
        return False, None, None, "Non-standard port specified."

    if parsed.username or parsed.password:
        return False, None, None, "Credentials in URL are disallowed."

    # Match owner and repo
    normalized_path = parsed.path.rstrip("/")
    if normalized_path.endswith(".git"):
        normalized_path = normalized_path[:-4]

    parts = [p for p in normalized_path.split("/") if p]
    if len(parts) != 2:
        return False, None, None, "URL must point directly to a repository in format: https://github.com/owner/repository"

    owner, repo = parts[0], parts[1]

    # Validate characters in owner and repo
    valid_name_regex = re.compile(r"^[a-zA-Z0-9_.-]+$")
    if not valid_name_regex.match(owner) or not valid_name_regex.match(repo):
        return False, None, None, "Repository or owner name contains invalid characters."

    if owner in (".", "..") or repo in (".", ".."):
        return False, None, None, "Invalid path traversal elements in repository name."

    return True, owner, repo, None


async def _validate_redirect_host(response: httpx.Response) -> None:
    """Rejects HTTP redirects to non-GitHub hosts to prevent SSRF bypasses."""
    if response.next_request:
        target_host = (response.next_request.url.host or "").lower()
        target_scheme = (response.next_request.url.scheme or "").lower()
        if target_scheme != "https" or target_host not in ("github.com", "www.github.com", "api.github.com"):
            raise ValueError(f"Blocked unsafe redirect to host '{target_host}'.")


async def _verify_via_git_ls_remote(owner: str, repo: str, timeout_seconds: float = 10.0) -> Tuple[bool, Optional[str]]:
    """Fallback public accessibility check using non-interactive git ls-remote over HTTPS."""
    import asyncio
    import os
    import subprocess
    import shutil
    from pathlib import Path

    git_bin = shutil.which("git")
    if not git_bin:
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            for cand in (Path(local_app) / "GitHubDesktop").glob("app-*/resources/app/git/cmd/git.exe"):
                if cand.exists():
                    git_bin = str(cand)
                    break
    if not git_bin:
        git_bin = "git"

    git_url = f"https://github.com/{owner}/{repo}.git"
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_ASKPASS"] = ""
    env["GIT_ALLOW_PROTOCOL"] = "https"

    def _run():
        return subprocess.run(
            [git_bin, "ls-remote", "--exit-code", "-h", git_url],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            check=False,
        )

    try:
        proc = await asyncio.to_thread(_run)
        if proc.returncode == 0:
            return True, None
        return False, f"Repository '{owner}/{repo}' is inaccessible or private."
    except Exception:
        return False, "Connection to GitHub timed out while verifying repository."


async def verify_github_repo_accessible(owner: str, repo: str, timeout_seconds: float = 8.0) -> Tuple[bool, Optional[str]]:
    """
    Verifies that the target GitHub repository is public and accessible without downloading.
    Enforces strict redirect hostname checks to prevent SSRF and falls back to git ls-remote on API timeouts.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "User-Agent": "RepoMind-Verifier/1.0",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            event_hooks={"response": [_validate_redirect_host]},
        ) as client:
            resp = await client.get(api_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                is_private = data.get("private", False)
                if is_private:
                    return False, "This repository is private. RepoMind currently supports public repositories only."
                return True, None
            elif resp.status_code == 404:
                return False, f"Repository '{owner}/{repo}' was not found on GitHub. Verify the URL."
            elif resp.status_code in (403, 429) or "rate limit" in resp.text.lower():
                return await _verify_via_git_ls_remote(owner, repo, timeout_seconds)
            else:
                return False, f"GitHub responded with status {resp.status_code}."
    except httpx.TimeoutException:
        return await _verify_via_git_ls_remote(owner, repo, timeout_seconds)
    except Exception as e:
        return False, f"Could not verify repository accessibility: {str(e)}"

