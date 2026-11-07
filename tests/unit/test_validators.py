import pytest
from backend.app.utils.validators import validate_github_url

def test_valid_github_urls():
    valid_cases = [
        ("https://github.com/fastapi/fastapi", "fastapi", "fastapi"),
        ("https://github.com/pallets/flask.git", "pallets", "flask"),
        ("https://github.com/pmndrs/zustand/", "pmndrs", "zustand"),
        ("https://www.github.com/torvalds/linux", "torvalds", "linux"),
        ("https://github.com/facebook/react.git/", "facebook", "react"),
        ("https://github.com/org-with-hyphens/repo_with_underscores", "org-with-hyphens", "repo_with_underscores"),
    ]

    for url, expected_owner, expected_repo in valid_cases:
        is_valid, owner, repo, err = validate_github_url(url)
        assert is_valid is True, f"Failed for {url}: {err}"
        assert owner == expected_owner
        assert repo == expected_repo
        assert err is None

def test_invalid_github_urls():
    invalid_cases = [
        "",
        "   ",
        "http://github.com/fastapi/fastapi",  # not https
        "https://gitlab.com/fastapi/fastapi",  # not github.com
        "https://evilgithub.com/fastapi/fastapi",
        "https://github.com/fastapi",  # missing repo
        "https://github.com/fastapi/fastapi/tree/master",  # sub-path
        "https://github.com/fastapi/fastapi/pull/123",
        "https://127.0.0.1/fastapi/fastapi",  # SSRF attempt
        "https://localhost/fastapi/fastapi",
        "https://github.com/../fastapi",  # path traversal
        "https://github.com/fastapi/../etc/passwd",
        "https://user:pass@github.com/fastapi/fastapi",  # credentials disallowed
        "https://github.com:8443/fastapi/fastapi",  # non-standard port
    ]

    for url in invalid_cases:
        is_valid, owner, repo, err = validate_github_url(url)
        assert is_valid is False, f"Expected {url} to be invalid"
        assert err is not None
