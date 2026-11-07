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


async def verify_github_repo_accessible(owner: str, repo: str, timeout_seconds: float = 8.0) -> Tuple[bool, Optional[str]]:
    """
    Verifies that the target GitHub repository is public and accessible without downloading.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "User-Agent": "RepoMind-Verifier/1.0",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = await client.get(api_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                is_private = data.get("private", False)
                if is_private:
                    return False, "This repository is private. RepoMind currently supports public repositories only."
                return True, None
            elif resp.status_code == 404:
                return False, f"Repository '{owner}/{repo}' was not found on GitHub. Verify the URL."
            elif resp.status_code == 403 and "rate limit" in resp.text.lower():
                # If GitHub REST rate limited anonymous check, fallback to checking web URL
                web_url = f"https://github.com/{owner}/{repo}"
                web_resp = await client.head(web_url, headers={"User-Agent": "RepoMind-Verifier/1.0"})
                if web_resp.status_code == 200:
                    return True, None
                return False, f"GitHub access returned HTTP {web_resp.status_code}."
            else:
                return False, f"GitHub responded with status {resp.status_code}."
    except httpx.TimeoutException:
        return False, "Connection to GitHub timed out while verifying repository."
    except Exception as e:
        return False, f"Could not verify repository accessibility: {str(e)}"

