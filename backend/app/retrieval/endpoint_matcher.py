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
    r"@([a-zA-Z_][a-zA-Z0-9_]*)\.(route|get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"'](?:[^)]*methods\s*=\s*\[([^\]]+)\])?",
    re.IGNORECASE,
)
EXPRESS_ROUTE_PATTERN = re.compile(
    r"\b([a-zA-Z_$][a-zA-Z0-9_$]*)\.(get|post|put|delete|patch|all)\(\s*[\"'](/[^\"']*)[\"']",
    re.IGNORECASE,
)
EXPRESS_USE_MOUNT_PATTERN = re.compile(
    r"\b([a-zA-Z_$][a-zA-Z0-9_$]*)\.use\(\s*[\"'](/[^\"']*)[\"']\s*,\s*([a-zA-Z_$][a-zA-Z0-9_$]*)",
    re.IGNORECASE,
)
SPRING_ROUTE_PATTERN = re.compile(
    r"@(GetMapping|PostMapping|DeleteMapping|PutMapping|PatchMapping|RequestMapping)\(\s*(?:(?:value|path)\s*=\s*)?[\"']([^\"']*)[\"'](?:[^)]*method\s*=\s*RequestMethod\.([A-Z]+))?",
    re.IGNORECASE,
)
SPRING_EMPTY_ROUTE_PATTERN = re.compile(
    r"@(GetMapping|PostMapping|DeleteMapping|PutMapping|PatchMapping)(?:\(\s*\))?(?!\s*\([^)]*[\"'])",
    re.IGNORECASE,
)
SPRING_CLASS_PREFIX_PATTERN = re.compile(
    r"@RequestMapping\(\s*(?:(?:value|path)\s*=\s*)?[\"']([^\"']+)[\"'][^)]*\)\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:public\s+|protected\s+|private\s+)?(?:class|interface)\b",
    re.DOTALL | re.IGNORECASE,
)
FLASK_BP_PREFIX_PATTERN = re.compile(
    r"Blueprint\(\s*[\"'][^\"']+[\"'].*?url_prefix\s*=\s*[\"']([^\"']+)[\"']",
    re.DOTALL | re.IGNORECASE,
)
FASTAPI_ROUTER_PREFIX_PATTERN = re.compile(
    r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)[\"']",
    re.DOTALL | re.IGNORECASE,
)
FLASK_REG_BP_PATTERN = re.compile(
    r"register_blueprint\(\s*([a-zA-Z_][a-zA-Z0-9_]*)[^)]*url_prefix\s*=\s*[\"']([^\"']+)[\"']",
    re.DOTALL | re.IGNORECASE,
)
FASTAPI_INC_ROUTER_PATTERN = re.compile(
    r"include_router\(\s*([a-zA-Z_][a-zA-Z0-9_]*)[^)]*prefix\s*=\s*[\"']([^\"']+)[\"']",
    re.DOTALL | re.IGNORECASE,
)
COMMENT_ROUTE_PATTERN = re.compile(
    r"(?:@route|Route:|Endpoint:)\s+(GET|POST|PUT|DELETE|PATCH)\s+([/a-zA-Z0-9_\-\.:<>{}\*]+)",
    re.IGNORECASE,
)

# Import discovery patterns for cross-file router mounting
JS_IMPORT_PATTERN = re.compile(
    r"import\s+(?:\{\s*([a-zA-Z_$][a-zA-Z0-9_$]*)(?:\s+as\s+[a-zA-Z_$][a-zA-Z0-9_$]*)?\s*\}|([a-zA-Z_$][a-zA-Z0-9_$]*))\s+from\s+[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
JS_REQUIRE_PATTERN = re.compile(
    r"(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*require\(\s*[\"']([^\"']+)[\"']\s*\)",
    re.IGNORECASE,
)
PY_FROM_IMPORT_PATTERN = re.compile(
    r"from\s+([a-zA-Z0-9_.]+)\s+import\s+([a-zA-Z0-9_, \t*]+(?:\s+as\s+[a-zA-Z0-9_]+)?)",
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
    and Java (Spring Boot) source code text, composing intra-file class or blueprint prefixes.
    """
    routes: List[DeclaredRoute] = []

    # 1. Python Flask / FastAPI
    for m in FLASK_ROUTE_PATTERN.finditer(source_code):
        route_func = m.group(2).upper()
        route_path = m.group(3)
        methods_str = m.group(4)
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

    # 2. TypeScript / JavaScript Express
    for m in EXPRESS_ROUTE_PATTERN.finditer(source_code):
        method = m.group(2).upper()
        route_path = m.group(3)
        methods = [method] if method != "ALL" else ["GET", "POST", "PUT", "DELETE", "PATCH"]
        routes.append(
            DeclaredRoute(
                methods=methods,
                path=route_path,
                normalized_segments=normalize_path_segments(route_path),
                file_path=file_path,
            )
        )

    # 3. Java Spring Boot: identify class-level prefixes first so they compose cleanly
    spring_class_prefixes: List[str] = []
    class_prefix_positions: set[int] = set()
    for m_cls in SPRING_CLASS_PREFIX_PATTERN.finditer(source_code):
        spring_class_prefixes.append(m_cls.group(1).rstrip("/"))
        class_prefix_positions.add(m_cls.start())

    for m in SPRING_ROUTE_PATTERN.finditer(source_code):
        if m.start() in class_prefix_positions:
            # Class-level @RequestMapping acts as a prefix for handler methods, not a method endpoint itself
            continue
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

    for m in SPRING_EMPTY_ROUTE_PATTERN.finditer(source_code):
        annotation = m.group(1)
        if "Get" in annotation:
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
                path="",
                normalized_segments=[],
                file_path=file_path,
            )
        )

    # Detect intra-file prefix declarations
    detected_prefixes: List[str] = list(spring_class_prefixes)
    for m_flask_pfx in FLASK_BP_PREFIX_PATTERN.finditer(source_code):
        detected_prefixes.append(m_flask_pfx.group(1).rstrip("/"))
    for m_fa_pfx in FASTAPI_ROUTER_PREFIX_PATTERN.finditer(source_code):
        detected_prefixes.append(m_fa_pfx.group(1).rstrip("/"))
    if not detected_prefixes:
        for m_exp_pfx in EXPRESS_USE_MOUNT_PATTERN.finditer(source_code):
            detected_prefixes.append(m_exp_pfx.group(2).rstrip("/"))

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

    # If prefix(es) were detected in this file, generate composed full routes
    if detected_prefixes:
        composed_routes: List[DeclaredRoute] = []
        for pfx in detected_prefixes:
            for r in routes:
                if not pfx:
                    continue
                if not r.path or not r.path.startswith(pfx):
                    joined = f"{pfx}/{r.path.lstrip('/')}" if r.path else pfx
                    composed_routes.append(
                        DeclaredRoute(
                            methods=r.methods,
                            path=joined,
                            normalized_segments=normalize_path_segments(joined),
                            file_path=file_path,
                        )
                    )
        routes.extend(composed_routes)

    # Filter out bare empty paths unless composed with a prefix
    return [r for r in routes if r.path or r.normalized_segments]


def _chunk_field(chunk: Any, field: str, default: Any = None) -> Any:
    if isinstance(chunk, dict):
        return chunk.get(field, default)
    return getattr(chunk, field, default)


def _resolve_module_to_file(
    source_file: str,
    import_spec: str,
    all_files: List[str],
) -> Optional[str]:
    """Resolves a relative/dotted import specifier to an indexed file path."""
    if not import_spec or not all_files:
        return None

    # Normalize JS/TS relative path (e.g. './routes/users.js' -> 'routes/users')
    spec_clean = import_spec.strip()
    if spec_clean.startswith("."):
        # Handle JS/TS './foo', '../foo' or Python '.foo', '..pkg.mod'
        if "/" in spec_clean:
            base_dir = "/".join(source_file.replace("\\", "/").split("/")[:-1])
            parts = (base_dir.split("/") if base_dir else []) + spec_clean.split("/")
            resolved_parts: List[str] = []
            for p in parts:
                if p in ("", "."):
                    continue
                elif p == "..":
                    if resolved_parts:
                        resolved_parts.pop()
                else:
                    resolved_parts.append(p)
            candidate_stem = "/".join(resolved_parts)
            # Strip .js/.ts extension if TypeScript uses ESM .js imports
            candidate_stem = re.sub(r"\.(?:js|ts|jsx|tsx|py)$", "", candidate_stem)
        else:
            # Python relative import like '.users'
            dots = len(spec_clean) - len(spec_clean.lstrip("."))
            mod_part = spec_clean.lstrip(".").replace(".", "/")
            dir_parts = source_file.replace("\\", "/").split("/")[:-dots]
            candidate_stem = "/".join(dir_parts + ([mod_part] if mod_part else []))
    else:
        candidate_stem = spec_clean.replace(".", "/")

    candidate_stem = candidate_stem.strip("/").lower()
    if not candidate_stem:
        return None

    for fp in all_files:
        fp_norm = fp.replace("\\", "/").lower()
        fp_no_ext = re.sub(r"\.(?:py|ts|tsx|js|jsx|java)$", "", fp_norm)
        if fp_no_ext == candidate_stem or fp_no_ext.endswith(f"/{candidate_stem}"):
            return fp
        if fp_no_ext.endswith(f"/{candidate_stem}/index") or fp_no_ext.endswith(f"/{candidate_stem}/__init__"):
            return fp
    return None


def extract_declared_routes_from_repository(chunks: List[Any]) -> Tuple[List[DeclaredRoute], str]:
    """
    Reconstructs file-level sources across all chunks (handling class/method chunk splits)
    and resolves cross-file router mounts (Express app.use, Flask register_blueprint,
    FastAPI include_router).
    """
    grouped: Dict[str, List[Tuple[int, str]]] = {}
    for idx, c in enumerate(chunks):
        code = _chunk_field(c, "source_code", "") or ""
        fp = _chunk_field(c, "file_path", None) or f"_chunk_{idx}"
        start_line = _chunk_field(c, "start_line", idx)
        if start_line is None:
            start_line = idx
        grouped.setdefault(fp, []).append((int(start_line), code))

    file_sources: Dict[str, str] = {}
    for fp, items in grouped.items():
        items.sort(key=lambda x: x[0])
        seen_blocks = set()
        ordered_blocks = []
        for _, code in items:
            if code and code not in seen_blocks:
                seen_blocks.add(code)
                ordered_blocks.append(code)
        file_sources[fp] = "\n".join(ordered_blocks)

    all_files = list(file_sources.keys())
    combined_source = "\n".join(file_sources.values())

    # 1. Extract intra-file routes per reconstructed file
    file_routes: Dict[str, List[DeclaredRoute]] = {}
    all_routes: List[DeclaredRoute] = []
    for fp, code in file_sources.items():
        f_routes = extract_declared_routes_from_code(code, fp)
        file_routes[fp] = f_routes
        all_routes.extend(f_routes)

    # 2. Extract cross-file router/blueprint mounts
    # Map target_file -> list of mount prefixes
    cross_mounts: List[Tuple[str, str]] = []  # (target_file, mount_prefix)
    for src_fp, code in file_sources.items():
        # Collect variable -> module path imports in src_fp
        var_to_module: Dict[str, str] = {}
        for m in JS_IMPORT_PATTERN.finditer(code):
            var_name = m.group(1) or m.group(2)
            mod_spec = m.group(3)
            if var_name and mod_spec:
                var_to_module[var_name] = mod_spec
        for m in JS_REQUIRE_PATTERN.finditer(code):
            var_to_module[m.group(1)] = m.group(2)
        for m in PY_FROM_IMPORT_PATTERN.finditer(code):
            mod_spec = m.group(1)
            for item in m.group(2).split(","):
                item = item.strip()
                if " as " in item:
                    alias = item.split(" as ")[-1].strip()
                    var_to_module[alias] = mod_spec
                elif item and item != "*":
                    var_to_module[item] = mod_spec

        # Express: host.use('/prefix', childRouter)
        for m in EXPRESS_USE_MOUNT_PATTERN.finditer(code):
            prefix = m.group(2).rstrip("/")
            child_var = m.group(3)
            if prefix and child_var in var_to_module:
                target_fp = _resolve_module_to_file(src_fp, var_to_module[child_var], all_files)
                if target_fp and target_fp != src_fp:
                    cross_mounts.append((target_fp, prefix))

        # Flask: app.register_blueprint(bp_var, url_prefix='/prefix')
        for m in FLASK_REG_BP_PATTERN.finditer(code):
            child_var = m.group(1)
            prefix = m.group(2).rstrip("/")
            if prefix and child_var in var_to_module:
                target_fp = _resolve_module_to_file(src_fp, var_to_module[child_var], all_files)
                if target_fp and target_fp != src_fp:
                    cross_mounts.append((target_fp, prefix))

        # FastAPI: app.include_router(router_var, prefix='/prefix')
        for m in FASTAPI_INC_ROUTER_PATTERN.finditer(code):
            child_var = m.group(1)
            prefix = m.group(2).rstrip("/")
            if prefix and child_var in var_to_module:
                target_fp = _resolve_module_to_file(src_fp, var_to_module[child_var], all_files)
                if target_fp and target_fp != src_fp:
                    cross_mounts.append((target_fp, prefix))

    # Apply cross-file mount prefixes (propagate across chained sub-routers up to 2 passes)
    composed_all: List[DeclaredRoute] = list(all_routes)
    applied_pairs = set()
    for target_fp, prefix in cross_mounts:
        for r in file_routes.get(target_fp, []):
            full_path = f"{prefix}/{r.path.lstrip('/')}" if r.path and r.path != "/" else prefix or "/"
            key = (tuple(r.methods), full_path, target_fp)
            if key not in applied_pairs:
                applied_pairs.add(key)
                composed_all.append(
                    DeclaredRoute(
                        methods=r.methods,
                        path=full_path,
                        normalized_segments=normalize_path_segments(full_path),
                        file_path=target_fp,
                    )
                )

    return composed_all, combined_source


def match_endpoint_against_chunks(
    target: EndpointTarget,
    chunks: List[Any],
) -> RouteMatchResult:
    """
    Performs structurally justified matching between a query EndpointTarget
    and source code chunks (supports both full-repository chunk scans and top-k subsets).
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

    # Extract all declared routes with per-file reconstruction and cross-file router mounting
    all_declared_routes, combined_source = extract_declared_routes_from_repository(chunks)

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
