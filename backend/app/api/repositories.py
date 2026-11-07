from fastapi import APIRouter, HTTPException, status
from typing import List
from backend.app.schemas.repository import (
    RepositoryValidateRequest,
    RepositoryValidationResponse,
    DemoRepository,
)
from backend.app.utils.validators import (
    validate_github_url,
    verify_github_repo_accessible,
)

router = APIRouter(prefix="/repositories", tags=["Repositories"])

CURATED_DEMOS: List[DemoRepository] = [
    DemoRepository(
        name="FastAPI",
        owner="fastapi",
        url="https://github.com/fastapi/fastapi",
        description="Modern, fast web framework for building APIs with Python.",
        category="Python / Web",
        language="Python",
        stars="78k+",
    ),
    DemoRepository(
        name="Flask",
        owner="pallets",
        url="https://github.com/pallets/flask",
        description="The Python micro framework for building web applications.",
        category="Python / Backend",
        language="Python",
        stars="69k+",
    ),
    DemoRepository(
        name="Zustand",
        owner="pmndrs",
        url="https://github.com/pmndrs/zustand",
        description="Bearbones state-management solution using simplified flux principles.",
        category="TypeScript / React",
        language="TypeScript",
        stars="50k+",
    ),
    DemoRepository(
        name="Axios",
        owner="axios",
        url="https://github.com/axios/axios",
        description="Promise-based HTTP client for the browser and node.js.",
        category="JavaScript / Library",
        language="JavaScript",
        stars="105k+",
    ),
    DemoRepository(
        name="Gin",
        owner="gin-gonic",
        url="https://github.com/gin-gonic/gin",
        description="Gin is a high-performance HTTP web framework written in Go.",
        category="Go / Backend",
        language="Go",
        stars="77k+",
    ),
]

@router.get("/demos", response_model=List[DemoRepository])
async def get_demo_repositories():
    """Retrieve pre-verified featured demo repositories."""
    return CURATED_DEMOS

@router.post("/validate", response_model=RepositoryValidationResponse)
async def validate_repository_url(req: RepositoryValidateRequest):
    """
    Validates GitHub URL structure, checks for SSRF/malicious components,
    and verifies repository accessibility.
    """
    is_valid, owner, repo, err_msg = validate_github_url(req.url)
    if not is_valid:
        return RepositoryValidationResponse(
            is_valid=False,
            is_accessible=False,
            message=err_msg or "Invalid GitHub URL.",
        )

    clean_url = f"https://github.com/{owner}/{repo}"
    accessible, access_err = await verify_github_repo_accessible(owner, repo)

    return RepositoryValidationResponse(
        is_valid=True,
        owner=owner,
        repo=repo,
        normalized_url=clean_url,
        is_accessible=accessible,
        message=access_err if not accessible else "Repository validated and accessible.",
    )
