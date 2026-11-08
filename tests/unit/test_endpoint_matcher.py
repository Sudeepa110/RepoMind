"""
Unit tests for API Endpoint Extractor and Matcher (Phase 9.4).
Verifies:
1. Exact route matching across Flask, Express, and Spring Boot.
2. HTTP method mismatch detection (e.g. DELETE vs POST).
3. Parameterized path matching (:id, <user_id>, {ownerId}).
4. Rejection of prefix-only overlap (never treating /api/ as sufficient for /api/v2/users/crypto_wallet).
5. Robust extraction of endpoints from developer queries.
"""

import pytest
from backend.app.retrieval.endpoint_matcher import (
    extract_endpoint_from_query,
    match_endpoint_against_chunks,
    RouteMatchStatus,
    EndpointTarget,
    DeclaredRoute,
    extract_declared_routes_from_code,
)
from backend.app.retrieval.retrieval_models import UnifiedSearchResult


class MockChunk:
    def __init__(self, source_code: str, file_path: str = "routes.py"):
        self.source_code = source_code
        self.file_path = file_path


def test_query_endpoint_extraction():
    # 1. Method + Path
    t1 = extract_endpoint_from_query("How is the DELETE /api/v2/users/crypto_wallet endpoint implemented?")
    assert t1 is not None
    assert t1.method == "DELETE"
    assert t1.path == "/api/v2/users/crypto_wallet"
    assert t1.normalized_segments == ["api", "v2", "users", "crypto_wallet"]

    # 2. Path followed by endpoint
    t2 = extract_endpoint_from_query("Where is the /api/internal/debug/coredump route handler defined?")
    assert t2 is not None
    assert t2.path == "/api/internal/debug/coredump"

    # 3. Spring style GET
    t3 = extract_endpoint_from_query("What does the GET /owners/{ownerId} route return?")
    assert t3 is not None
    assert t3.method == "GET"
    assert t3.normalized_segments == ["owners", "{param}"]


def test_flask_exact_and_method_mismatch():
    flask_code = """
@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    return {"token": "123"}

@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    return {"id": user_id}
"""
    chunks = [MockChunk(flask_code, "app.py")]

    # 1. Exact match (POST /api/v1/auth/login)
    target_exact = extract_endpoint_from_query("Show the POST /api/v1/auth/login endpoint")
    res_exact = match_endpoint_against_chunks(target_exact, chunks)
    assert res_exact.status == RouteMatchStatus.EXACT_MATCH
    assert res_exact.is_supported is True

    # 2. Method mismatch (DELETE /api/v1/auth/login)
    target_mismatch = extract_endpoint_from_query("Show the DELETE /api/v1/auth/login endpoint")
    res_mismatch = match_endpoint_against_chunks(target_mismatch, chunks)
    assert res_mismatch.status == RouteMatchStatus.METHOD_MISMATCH
    assert res_mismatch.is_supported is False

    # 3. Parameterized exact match
    target_param = extract_endpoint_from_query("What does GET /api/v1/users/{id} return?")
    res_param = match_endpoint_against_chunks(target_param, chunks)
    assert res_param.status == RouteMatchStatus.EXACT_MATCH
    assert res_param.is_supported is True


def test_rejection_of_prefix_only_match():
    """Crucial Phase 9.4 test: /api/v2/users/crypto_wallet must NOT match /api/v1/users."""
    flask_code = """
@app.route('/api/v1/users', methods=['GET'])
def list_users():
    return []
"""
    chunks = [MockChunk(flask_code, "app.py")]

    target_fake = extract_endpoint_from_query("DELETE /api/v2/users/crypto_wallet")
    res_fake = match_endpoint_against_chunks(target_fake, chunks)

    # Must be PREFIX_ONLY or NOT_FOUND, never EXACT_MATCH
    assert res_fake.status in (RouteMatchStatus.PREFIX_ONLY, RouteMatchStatus.NOT_FOUND)
    assert res_fake.is_supported is False


def test_express_route_matching():
    express_code = """
router.get('/health', (req, res) => res.send('OK'));
router.post('/login', authController.login);
router.delete('/users/:id', authController.deleteUser);
"""
    chunks = [MockChunk(express_code, "api.routes.ts")]

    # 1. Exact match Express
    target = extract_endpoint_from_query("What does DELETE /users/:id do in Express?")
    res = match_endpoint_against_chunks(target, chunks)
    assert res.status == RouteMatchStatus.EXACT_MATCH
    assert res.is_supported is True

    # 2. Nonexistent endpoint with similar prefix
    target_fake = extract_endpoint_from_query("Show POST /users/:id/webauthn/verify")
    res_fake = match_endpoint_against_chunks(target_fake, chunks)
    assert res_fake.status in (RouteMatchStatus.PREFIX_ONLY, RouteMatchStatus.NOT_FOUND)
    assert res_fake.is_supported is False


def test_spring_boot_route_matching():
    spring_code = """
@GetMapping("/owners/{ownerId}")
public String showOwner(@PathVariable("ownerId") int ownerId) {
    return "owners/ownerDetails";
}

@PostMapping("/pets/new")
public String processCreationForm(Pet pet) {
    return "redirect:/owners/";
}
"""
    chunks = [MockChunk(spring_code, "OwnerController.java")]

    # 1. Exact match Spring
    target = extract_endpoint_from_query("Show the GET /owners/{ownerId} handler")
    res = match_endpoint_against_chunks(target, chunks)
    assert res.status == RouteMatchStatus.EXACT_MATCH
    assert res.is_supported is True

    # 2. Method mismatch Spring
    target_mismatch = extract_endpoint_from_query("Show the DELETE /owners/{ownerId} handler")
    res_mismatch = match_endpoint_against_chunks(target_mismatch, chunks)
    assert res_mismatch.status == RouteMatchStatus.METHOD_MISMATCH
    assert res_mismatch.is_supported is False


def test_composed_class_prefix_matching():
    """Verify class-level @RequestMapping combined with method mapping."""
    petclinic_controller = """
@Controller
@RequestMapping("/owners/{ownerId}")
class PetController {
    @GetMapping("/pets/new")
    public String initCreationForm() { return "form"; }

    @PostMapping("/pets/{petId}/edit")
    public String processUpdateForm() { return "redirect:/"; }
}
"""
    chunks = [MockChunk(petclinic_controller, "PetController.java")]

    # 1. Composed exact match: GET /owners/{ownerId}/pets/new
    target_composed = extract_endpoint_from_query("Where is GET /owners/{ownerId}/pets/new handled?")
    res = match_endpoint_against_chunks(target_composed, chunks)
    assert res.status == RouteMatchStatus.EXACT_MATCH
    assert res.is_supported is True

    # 2. Composed method mismatch: DELETE /owners/{ownerId}/pets/new
    target_del = extract_endpoint_from_query("Where is DELETE /owners/{ownerId}/pets/new handled?")
    res_del = match_endpoint_against_chunks(target_del, chunks)
    assert res_del.status == RouteMatchStatus.METHOD_MISMATCH
    assert res_del.is_supported is False

    # 3. Composed nonexistent leaf: GET /owners/{ownerId}/pets/telehealth
    target_fake = extract_endpoint_from_query("Where is GET /owners/{ownerId}/pets/telehealth handled?")
    res_fake = match_endpoint_against_chunks(target_fake, chunks)
    assert res_fake.status in (RouteMatchStatus.PREFIX_ONLY, RouteMatchStatus.NOT_FOUND)
    assert res_fake.is_supported is False


def test_comment_route_matching():
    """Verify route declared in docstrings or comments."""
    code = """
# Route: POST /api/v1/auth/login
def login_endpoint(payload: dict) -> dict:
    \"\"\"Public login HTTP route handler for POST /api/v1/auth/login.\"\"\"
    return {"token": "123"}
"""
    chunks = [MockChunk(code, "routes.py")]

    target = extract_endpoint_from_query("How is POST /api/v1/auth/login implemented?")
    res = match_endpoint_against_chunks(target, chunks)
    assert res.status == RouteMatchStatus.EXACT_MATCH
    assert res.is_supported is True
