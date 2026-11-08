"""
API Route & Endpoint Extraction and Exact Matching Engine (Phase 9.4).
Provides structurally justified endpoint matching for HTTP APIs across Python (Flask/FastAPI),
TypeScript (Express), and Java (Spring Boot).
Distinguishes exact endpoint matches from partial route matches, prefix-only matches,
and HTTP method mismatches.
"""

import re
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field


class RouteMatchStatus(str, Enum):
    """Classification of an endpoint matching inquiry against codebase evidence."""
    EXACT_MATCH = "EXACT_MATCH"          # Both route path (or parameterized equivalent) and HTTP method match
    METHOD_MISMATCH = "METHOD_MISMATCH"  # Path exists in codebase, but declared HTTP method differs from query
    PREFIX_ONLY = "PREFIX_ONLY"          # Only a common ancestor prefix matches (e.g. /api/v1 vs /api/v2/users/crypto_wallet)
    NOT_FOUND = "NOT_FOUND"              # Path does not exist in the codebase


class EndpointTarget(BaseModel):
    """Specification of an API endpoint extracted from a developer query."""
    method: Optional[str] = None         # e.g., "GET", "POST", "DELETE", "PUT", "PATCH"
    path: str                            # e.g., "/api/v2/users/crypto_wallet"
    raw_query_match: str                 # e.g., "DELETE /api/v2/users/crypto_wallet"
    normalized_segments: List[str] = Field(default_factory=list)


class RouteMatchResult(BaseModel):
    """Detailed structural result of matching an endpoint inquiry against retrieved code chunks."""
    status: RouteMatchStatus
    target_method: Optional[str] = None
    target_path: str
    matched_method: Optional[str] = None
    matched_path: Optional[str] = None
    matched_file: Optional[str] = None
    is_supported: bool = False           # True ONLY when status == EXACT_MATCH
    explanation: str


# Regex patterns for query endpoint extraction
HTTP_METHOD_REGEX = r"\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\b"
PATH_REGEX = r"(/[a-zA-Z0-9_\-\.:<>{}\*]+(?:/[a-zA-Z0-9_\-\.:<>{}\*]*)*)"

QUERY_METHOD_PATH_PATTERN = re.compile(
    rf"{HTTP_METHOD_REGEX}\s+{PATH_REGEX}",
    re.IGNORECASE,
)
QUERY_PATH_ENDPOINT_PATTERN = re.compile(
    rf"(?:endpoint|route|path|handler|url)\s+(?:for\s+)?{PATH_REGEX}",
    re.IGNORECASE,
)
QUERY_TRAILING_ENDPOINT_PATTERN = re.compile(
    rf"{PATH_REGEX}\s+(?:endpoint|route|handler|path|api)\b",
    re.IGNORECASE,
)
STANDALONE_API_PATH_PATTERN = re.compile(
    r"\b(/api/[a-zA-Z0-9_\-\.:<>{}/]+)\b",
    re.IGNORECASE,
)

# Regex patterns for code route declarations
FLASK_ROUTE_PATTERN = re.compile(
    r"@(?:app|bp|router|blueprint)\.(route|get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"'](?:[^)]*methods\s*=\s*\[([^\]]+)\])?",
    re.IGNORECASE,
)
EXPRESS_ROUTE_PATTERN = re.compile(
    r"(?:app|router)\.(get|post|put|delete|patch|all)\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
EXPRESS_USE_MOUNT_PATTERN = re.compile(
    r"(?:app|router)\.use\(\s*[\"']([^\"']+)[\"']\s*,\s*([a-zA-Z0-9_]+)",
    re.IGNORECASE,
)
SPRING_ROUTE_PATTERN = re.compile(
    r"@(GetMapping|PostMapping|DeleteMapping|PutMapping|PatchMapping|RequestMapping)\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"'](?:[^)]*method\s*=\s*RequestMethod\.([A-Z]+))?",
    re.IGNORECASE,
)
SPRING_CLASS_PREFIX_PATTERN = re.compile(
    r"@RequestMapping\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"'].*?\)\s*(?:@\w+\s*)*(?:public\s+|protected\s+)?(?:class|interface)\b",
    re.DOTALL | re.IGNORECASE,
)
FLASK_BP_PREFIX_PATTERN = re.compile(
    r"Blueprint\(\s*[\"'][^\"']+[\"'].*?url_prefix\s*=\s*[\"']([^\"']+)[\"']",
    re.DOTALL | re.IGNORECASE,
)
COMMENT_ROUTE_PATTERN = re.compile(
    r"(?:@route|Route:|Endpoint:)\s+(GET|POST|PUT|DELETE|PATCH)\s+([/a-zA-Z0-9_\-\.:<>{}\*]+)",
    re.IGNORECASE,
)


def normalize_path_segments(path: str) -> List[str]:
    """
    Normalizes URL path into lowercased segments, replacing parameter wildcards
    (:id, <id>, <int:id>, {id}) with unified '{param}'.
    """
    clean = path.split("?")[0].strip("/")
    if not clean:
        return []
    segments = clean.split("/")
    normalized = []
    for s in segments:
        if not s:
            continue
        # Check if route parameter: :param, {param}, <param>, <int:param>
        if re.match(r"^(:[a-zA-Z0-9_]+|\{[a-zA-Z0-9_]+\}|<[a-zA-Z0-9_:]+>)$", s):
            normalized.append("{param}")
        else:
            normalized.append(s.lower())
    return normalized


def extract_endpoint_from_query(query: str) -> Optional[EndpointTarget]:
    """
    Detects and extracts an API endpoint specification from a developer question.
    """
    # 1. Method + Path (e.g. "DELETE /api/v2/users/crypto_wallet")
    m = QUERY_METHOD_PATH_PATTERN.search(query)
    if m:
        method = m.group(1).upper()
        path = m.group(2)
        return EndpointTarget(
            method=method,
            path=path,
            raw_query_match=m.group(0),
            normalized_segments=normalize_path_segments(path),
        )

    # 2. Path followed or preceded by "endpoint" / "route"
    for pat in (QUERY_PATH_ENDPOINT_PATTERN, QUERY_TRAILING_ENDPOINT_PATTERN, STANDALONE_API_PATH_PATTERN):
        m = pat.search(query)
        if m:
            path = m.group(1)
            # Check if method is mentioned elsewhere in query
            meth_m = re.search(HTTP_METHOD_REGEX, query, re.IGNORECASE)
            method = meth_m.group(1).upper() if meth_m else None
            return EndpointTarget(
                method=method,
                path=path,
                raw_query_match=m.group(0),
                normalized_segments=normalize_path_segments(path),
            )

    return None


class DeclaredRoute(BaseModel):
    """A route declaration extracted from source code text."""
    methods: List[str]
    path: str
    normalized_segments: List[str]
    file_path: Optional[str] = None


def extract_declared_routes_from_code(source_code: str, file_path: Optional[str] = None) -> List[DeclaredRoute]:
    """
    Extracts route declarations from Python (Flask/FastAPI), TypeScript (Express),
    and Java (Spring Boot) source code text.
    """
    routes: List[DeclaredRoute] = []

    # 1. Python Flask/FastAPI
    for m in FLASK_ROUTE_PATTERN.finditer(source_code):
        route_func = m.group(1).upper()
        route_path = m.group(2)
        methods_str = m.group(3)
        if route_func in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            methods = [route_func]
        elif methods_str:
            methods = [meth.strip("'\" ").upper() for meth in methods_str.split(",") if meth.strip("'\" ")]
        else:
            methods = ["GET"]
        routes.append(
            DeclaredRoute(
                methods=methods,
                path=route_path,
                normalized_segments=normalize_path_segments(route_path),
                file_path=file_path,
            )
        )

    # 2. TypeScript Express
    for m in EXPRESS_ROUTE_PATTERN.finditer(source_code):
        method = m.group(1).upper()
        route_path = m.group(2)
        methods = [method] if method != "ALL" else ["GET", "POST", "PUT", "DELETE", "PATCH"]
        routes.append(
            DeclaredRoute(
                methods=methods,
                path=route_path,
                normalized_segments=normalize_path_segments(route_path),
                file_path=file_path,
            )
        )

    # 3. Java Spring Boot
    for m in SPRING_ROUTE_PATTERN.finditer(source_code):
        annotation = m.group(1)
        route_path = m.group(2)
        explicit_method = m.group(3)
        if explicit_method:
            methods = [explicit_method.upper()]
        elif "Get" in annotation:
            methods = ["GET"]
        elif "Post" in annotation:
            methods = ["POST"]
        elif "Delete" in annotation:
            methods = ["DELETE"]
        elif "Put" in annotation:
            methods = ["PUT"]
        elif "Patch" in annotation:
            methods = ["PATCH"]
        else:
            methods = ["GET"]
        routes.append(
            DeclaredRoute(
                methods=methods,
                path=route_path,
                normalized_segments=normalize_path_segments(route_path),
                file_path=file_path,
            )
        )

    # Detect prefix declarations (Spring @RequestMapping on class, Flask url_prefix, Express app.use)
    detected_prefix: Optional[str] = None
    m_spring_pfx = SPRING_CLASS_PREFIX_PATTERN.search(source_code)
    if m_spring_pfx:
        detected_prefix = m_spring_pfx.group(1).rstrip("/")
    else:
        m_flask_pfx = FLASK_BP_PREFIX_PATTERN.search(source_code)
        if m_flask_pfx:
            detected_prefix = m_flask_pfx.group(1).rstrip("/")
        else:
            m_exp_pfx = EXPRESS_USE_MOUNT_PATTERN.search(source_code)
            if m_exp_pfx:
                detected_prefix = m_exp_pfx.group(1).rstrip("/")

    # 4. Docstrings or comments declaring routes:
    for m in COMMENT_ROUTE_PATTERN.finditer(source_code):
        method = m.group(1).upper()
        route_path = m.group(2)
        routes.append(
            DeclaredRoute(
                methods=[method],
                path=route_path,
                normalized_segments=normalize_path_segments(route_path),
                file_path=file_path,
            )
        )

    # If prefix was detected, also generate composed full routes for each relative route
    if detected_prefix:
        composed_routes: List[DeclaredRoute] = []
        for r in routes:
            if not r.path.startswith(detected_prefix):
                full_path = f"{detected_prefix}/{r.path.lstrip('/')}"
                composed_routes.append(
                    DeclaredRoute(
                        methods=r.methods,
                        path=full_path,
                        normalized_segments=normalize_path_segments(full_path),
                        file_path=file_path,
                    )
                )
        routes.extend(composed_routes)

    return routes


def match_endpoint_against_chunks(
    target: EndpointTarget,
    chunks: List[Any],
) -> RouteMatchResult:
    """
    Performs structurally justified matching between a query EndpointTarget
    and retrieved source code chunks.
    Distinguishes EXACT_MATCH, METHOD_MISMATCH, PREFIX_ONLY, and NOT_FOUND.
    """
    target_segments = target.normalized_segments
    target_method = target.method

    if not target_segments:
        return RouteMatchResult(
            status=RouteMatchStatus.NOT_FOUND,
            target_method=target_method,
            target_path=target.path,
            explanation="Target endpoint path has no valid segments.",
        )

    # Extract all declared routes across all retrieved chunks
    all_declared_routes: List[DeclaredRoute] = []
    combined_source = ""
    for c in chunks:
        code = getattr(c, "source_code", "") or ""
        fp = getattr(c, "file_path", None)
        combined_source += "\n" + code
        all_declared_routes.extend(extract_declared_routes_from_code(code, fp))

    # Also check if target path is present as a literal string in code (e.g. config or url_for)
    target_path_lower = target.path.lower()
    has_exact_path_literal = (
        f'"{target_path_lower}"' in combined_source.lower()
        or f"'{target_path_lower}'" in combined_source.lower()
        or f"`{target_path_lower}`" in combined_source.lower()
    )

    best_prefix_len = 0
    method_mismatch_route: Optional[DeclaredRoute] = None

    for dr in all_declared_routes:
        dr_segs = dr.normalized_segments

        # Exact path segment match (accounting for {param} wildcards)
        if len(dr_segs) == len(target_segments):
            matches_all = True
            for d_seg, t_seg in zip(dr_segs, target_segments):
                if d_seg != t_seg and d_seg != "{param}" and t_seg != "{param}":
                    matches_all = False
                    break

            if matches_all:
                # Path matches! Now verify HTTP method
                if not target_method or target_method in dr.methods:
                    return RouteMatchResult(
                        status=RouteMatchStatus.EXACT_MATCH,
                        target_method=target_method,
                        target_path=target.path,
                        matched_method=",".join(dr.methods),
                        matched_path=dr.path,
                        matched_file=dr.file_path,
                        is_supported=True,
                        explanation=f"Exact route match found: {dr.path} with methods {dr.methods}.",
                    )
                else:
                    method_mismatch_route = dr

        # Check prefix overlap
        min_len = min(len(dr_segs), len(target_segments))
        matched_prefix = 0
        for i in range(min_len):
            if dr_segs[i] == target_segments[i] or dr_segs[i] == "{param}" or target_segments[i] == "{param}":
                matched_prefix += 1
            else:
                break
        if matched_prefix > best_prefix_len:
            best_prefix_len = matched_prefix

    if method_mismatch_route:
        return RouteMatchResult(
            status=RouteMatchStatus.METHOD_MISMATCH,
            target_method=target_method,
            target_path=target.path,
            matched_method=",".join(method_mismatch_route.methods),
            matched_path=method_mismatch_route.path,
            matched_file=method_mismatch_route.file_path,
            is_supported=False,
            explanation=(
                f"Route path '{method_mismatch_route.path}' exists, but declared methods "
                f"{method_mismatch_route.methods} do not match queried method '{target_method}'."
            ),
        )

    if has_exact_path_literal:
        return RouteMatchResult(
            status=RouteMatchStatus.EXACT_MATCH,
            target_method=target_method,
            target_path=target.path,
            matched_method=target_method or "ANY",
            matched_path=target.path,
            is_supported=True,
            explanation=f"Exact path literal '{target.path}' confirmed in source code.",
        )

    # If only an ancestor prefix matched (e.g. /api/ or /users/ while leaf is missing)
    if best_prefix_len > 0 and best_prefix_len < len(target_segments):
        matched_part = "/" + "/".join(target_segments[:best_prefix_len])
        return RouteMatchResult(
            status=RouteMatchStatus.PREFIX_ONLY,
            target_method=target_method,
            target_path=target.path,
            matched_path=matched_part,
            is_supported=False,
            explanation=(
                f"Prefix match only: '{matched_part}' matches repository routes, "
                f"but target sub-path '{target.path}' is absent."
            ),
        )

    return RouteMatchResult(
        status=RouteMatchStatus.NOT_FOUND,
        target_method=target_method,
        target_path=target.path,
        is_supported=False,
        explanation=f"No route declarations or path literals matching '{target.path}' found.",
    )
