"""
Benchmark Dataset Loader & Fixture Provisioner (Phase 9).
Constructs and provides access to reproducible benchmark repositories:
1. synthetic_auth_repo: Controlled multi-tier auth/payment codebase with deliberate patterns.
2. real_world_flask_subset: Open-source reference subset mirroring pallets/flask (commit e559fa7).
"""

import json
from pathlib import Path
from typing import Dict, Any, List


BENCHMARK_DATASETS_DIR = Path(__file__).parent
QUERIES_FILE = BENCHMARK_DATASETS_DIR / "benchmark_queries.json"


def load_benchmark_queries() -> List[Dict[str, Any]]:
    """Loads standardized 25-query ground truth evaluation suite."""
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_synthetic_auth_repo(target_dir: Path) -> Path:
    """Creates the synthetic_auth_repo fixture on disk."""
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. utils/hash.py
    u_dir = target_dir / "utils"
    u_dir.mkdir(parents=True, exist_ok=True)
    (u_dir / "hash.py").write_text(
        '''"""Password hashing utilities."""
import hashlib
import os

def generate_salt() -> str:
    """Generate cryptographic random salt."""
    return os.urandom(16).hex()

def compute_sha256(password: str, salt: str) -> str:
    """Compute salted SHA256 digest."""
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
''',
        encoding="utf-8",
    )

    # 2. database/session.py
    db_dir = target_dir / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "session.py").write_text(
        '''"""Database session management."""

class SessionManager:
    """Manages active database connection pooling."""
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.is_connected = False

    def connect(self):
        self.is_connected = True

    def close(self):
        self.is_connected = False

def get_db_session() -> SessionManager:
    """Acquires a database session."""
    mgr = SessionManager("sqlite:///auth.db")
    mgr.connect()
    return mgr
''',
        encoding="utf-8",
    )

    # 3. models/user.py
    m_dir = target_dir / "models"
    m_dir.mkdir(parents=True, exist_ok=True)
    (m_dir / "user.py").write_text(
        '''"""User domain models."""

class BaseEntity:
    """Base persistent entity."""
    def __init__(self, entity_id: int):
        self.id = entity_id

class UserAccount(BaseEntity):
    """User account entity model."""
    def __init__(self, user_id: int, username: str, password_hash: str, salt: str):
        super().__init__(user_id)
        self.username = username
        self.password_hash = password_hash
        self.salt = salt
        self.is_active = True
''',
        encoding="utf-8",
    )

    # 4. services/auth_service.py
    s_dir = target_dir / "services"
    s_dir.mkdir(parents=True, exist_ok=True)
    (s_dir / "auth_service.py").write_text(
        '''"""Core authentication business logic service."""
from utils.hash import compute_sha256, generate_salt
from database.session import get_db_session
from models.user import UserAccount

class AuthService:
    """Handles credential validation, password verification, and user authentication."""
    def __init__(self):
        self.session = get_db_session()

    def hash_password(self, password: str, salt: str = None) -> tuple:
        """Hashes a raw password with salt."""
        s = salt or generate_salt()
        hashed = compute_sha256(password, s)
        return hashed, s

    def verify_password(self, password: str, salt: str, expected_hash: str) -> bool:
        """Verifies if password matches expected hash."""
        computed, _ = self.hash_password(password, salt)
        return computed == expected_hash

    def get_user_by_username(self, username: str) -> UserAccount:
        """Retrieves user account record."""
        return UserAccount(1, username, "dummy_hash_123", "dummy_salt_456")

    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticates a user by username and password."""
        user = self.get_user_by_username(username)
        if not user or not user.is_active:
            return False
        return self.verify_password(password, user.salt, user.password_hash)
''',
        encoding="utf-8",
    )

    # 5. services/payment_service.py (Contains deliberate defect: unresolved call)
    (s_dir / "payment_service.py").write_text(
        '''"""Payment processing service with intentional defect."""

class PaymentService:
    def process_payment(self, amount: float, card_token: str) -> bool:
        """Processes transaction - calls unresolved external function."""
        # Intentionally unresolved call to external gateway function
        return execute_charge_gateway(amount, card_token)
''',
        encoding="utf-8",
    )

    # 6. api/routes.py
    a_dir = target_dir / "api"
    a_dir.mkdir(parents=True, exist_ok=True)
    (a_dir / "routes.py").write_text(
        '''"""API Route handlers."""
from services.auth_service import AuthService

auth_svc = AuthService()

def login_endpoint(payload: dict) -> dict:
    """Public login HTTP route handler."""
    username = payload.get("username", "")
    password = payload.get("password", "")
    is_valid = auth_svc.authenticate_user(username, password)
    if is_valid:
        return {"status": "success", "token": "jwt_token_abc"}
    return {"status": "error", "message": "Invalid credentials"}

def delete_account_endpoint(payload: dict) -> dict:
    """Unguarded route lacking exception handling."""
    uid = payload["user_id"] # Potential KeyError!
    return {"status": "deleted", "user_id": uid}
''',
        encoding="utf-8",
    )

    # 7. tests/test_auth.py
    t_dir = target_dir / "tests"
    t_dir.mkdir(parents=True, exist_ok=True)
    (t_dir / "test_auth.py").write_text(
        '''"""Unit test suite."""
from services.auth_service import AuthService

def test_authenticate_success():
    svc = AuthService()
    assert svc is not None
''',
        encoding="utf-8",
    )

    return target_dir


def build_real_world_flask_subset(target_dir: Path) -> Path:
    """
    Creates real_world_flask_subset mirroring pallets/flask commit e559fa7.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    flask_pkg = target_dir / "src" / "flask"
    flask_pkg.mkdir(parents=True, exist_ok=True)

    # 1. scaffold.py
    (flask_pkg / "scaffold.py").write_text(
        '''"""Flask Scaffold common endpoint registration base."""

class Scaffold:
    """Common base for Flask application and Blueprint."""
    def __init__(self, import_name: str, root_path: str = None):
        self.import_name = import_name
        self.root_path = root_path
        self._endpoints = {}

    def route(self, rule: str, **options):
        """Decorator to register a view function for a given URL rule."""
        def decorator(f):
            endpoint = options.pop("endpoint", f.__name__)
            self._endpoints[endpoint] = f
            return f
        return decorator
''',
        encoding="utf-8",
    )

    # 2. config.py
    (flask_pkg / "config.py").write_text(
        '''"""Flask configuration management."""
import os

class Config(dict):
    """Configuration dictionary subclass supporting environment loading."""
    def __init__(self, root_path: str, defaults: dict = None):
        super().__init__(defaults or {})
        self.root_path = root_path

    def from_envvar(self, variable_name: str, silent: bool = False) -> bool:
        """Loads configuration from environment variable path."""
        val = os.environ.get(variable_name)
        if not val:
            if silent:
                return False
            raise RuntimeError(f"The environment variable {variable_name!r} is not set.")
        return self.from_pyfile(val, silent=silent)

    def from_pyfile(self, filename: str, silent: bool = False) -> bool:
        """Loads configuration from python file."""
        return True
''',
        encoding="utf-8",
    )

    # 3. helpers.py
    (flask_pkg / "helpers.py").write_text(
        '''"""Flask helper utilities."""
import os

def get_debug_flag() -> bool:
    """Reads FLASK_DEBUG environment variable."""
    val = os.environ.get("FLASK_DEBUG")
    return val in ("1", "true", "True")

def url_for(endpoint: str, **values) -> str:
    """Generates a URL to the given endpoint."""
    return f"/{endpoint}"
''',
        encoding="utf-8",
    )

    # 4. app.py
    (flask_pkg / "app.py").write_text(
        '''"""Core Flask application class."""
from flask.scaffold import Scaffold
from flask.config import Config
from flask.helpers import get_debug_flag

class Flask(Scaffold):
    """The Flask object implements a WSGI application and acts as central registry."""
    default_config = {
        "DEBUG": None,
        "TESTING": False,
        "SECRET_KEY": None,
    }

    def __init__(self, import_name: str, root_path: str = None):
        super().__init__(import_name=import_name, root_path=root_path)
        self.config = self.make_config()

    def make_config(self) -> Config:
        """Instantiates the application Config object."""
        defaults = dict(self.default_config)
        defaults["DEBUG"] = get_debug_flag()
        return Config(self.root_path, defaults)

    def dispatch_request(self) -> str:
        """Does the request dispatching. Matches the URL and returns the view response."""
        return "HTTP 200 OK"

    def full_dispatch_request(self) -> str:
        """Dispatches the request and performs pre and post request processing."""
        return self.dispatch_request()

    def wsgi_app(self, environ: dict, start_response) -> list:
        """The actual WSGI application method."""
        response_body = self.full_dispatch_request()
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [response_body.encode("utf-8")]

    def __call__(self, environ: dict, start_response):
        """Shortcut for WSGI server entry."""
        return self.wsgi_app(environ, start_response)
''',
        encoding="utf-8",
    )

    # 5. tests/test_basic.py
    t_dir = target_dir / "tests"
    t_dir.mkdir(parents=True, exist_ok=True)
    (t_dir / "test_basic.py").write_text(
        '''"""Basic test for flask app."""
from flask.app import Flask

def test_create_app():
    app = Flask("test_app")
    assert app.config["TESTING"] is False
''',
        encoding="utf-8",
    )

    return target_dir



def build_synthetic_ts_express_repo(target_dir: Path) -> Path:
    """Creates the synthetic_ts_express_repo fixture on disk."""
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. src/models/user.interface.ts
    m_dir = target_dir / "src" / "models"
    m_dir.mkdir(parents=True, exist_ok=True)
    (m_dir / "user.interface.ts").write_text(
        '''export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: string;
}
''',
        encoding="utf-8",
    )

    # 2. src/services/jwt.service.ts
    s_dir = target_dir / "src" / "services"
    s_dir.mkdir(parents=True, exist_ok=True)
    (s_dir / "jwt.service.ts").write_text(
        '''export class TokenService {
  private secretKey: string = "repomind-jwt-secret";

  public generateAccessToken(userId: string): string {
    return `jwt-token-${userId}`;
  }

  public verifyJwtToken(token: string): boolean {
    return token.startsWith("jwt-token-");
  }
}
''',
        encoding="utf-8",
    )

    # 3. src/middleware/authenticate.middleware.ts
    mw_dir = target_dir / "src" / "middleware"
    mw_dir.mkdir(parents=True, exist_ok=True)
    (mw_dir / "authenticate.middleware.ts").write_text(
        '''import { TokenService } from "../services/jwt.service";

export function authenticateMiddleware(authHeader: string): boolean {
  const tokenService = new TokenService();
  return tokenService.verifyJwtToken(authHeader);
}
''',
        encoding="utf-8",
    )

    # 4. src/controllers/auth.controller.ts
    c_dir = target_dir / "src" / "controllers"
    c_dir.mkdir(parents=True, exist_ok=True)
    (c_dir / "auth.controller.ts").write_text(
        '''import { TokenService } from "../services/jwt.service";

export class AuthController {
  private tokenService: TokenService;

  constructor() {
    this.tokenService = new TokenService();
  }

  public login(username: string): string {
    return this.tokenService.generateAccessToken(username);
  }
}
''',
        encoding="utf-8",
    )

    # 5. src/routes/api.routes.ts
    r_dir = target_dir / "src" / "routes"
    r_dir.mkdir(parents=True, exist_ok=True)
    (r_dir / "api.routes.ts").write_text(
        '''import { AuthController } from "../controllers/auth.controller";
import { authenticateMiddleware } from "../middleware/authenticate.middleware";

export function registerRoutes(): void {
  const controller = new AuthController();
  controller.login("test-user");
  authenticateMiddleware("jwt-token-test");
}
''',
        encoding="utf-8",
    )

    return target_dir


def build_synthetic_java_petclinic_repo(target_dir: Path) -> Path:
    """Creates the synthetic_java_petclinic_repo fixture on disk."""
    target_dir.mkdir(parents=True, exist_ok=True)

    base_pkg = target_dir / "src" / "main" / "java" / "org" / "repomind"

    # 1. model/Pet.java
    pet_dir = base_pkg / "model"
    pet_dir.mkdir(parents=True, exist_ok=True)
    (pet_dir / "Pet.java").write_text(
        '''package org.repomind.model;

public class Pet {
    private String name;

    public String getName() {
        return this.name;
    }

    public void setName(String name) {
        this.name = name;
    }
}
''',
        encoding="utf-8",
    )

    # 2. model/Owner.java
    (pet_dir / "Owner.java").write_text(
        '''package org.repomind.model;

import java.util.List;

public class Owner {
    private Long id;
    private String lastName;
    private List<Pet> pets;

    public Long getId() {
        return this.id;
    }

    public String getLastName() {
        return this.lastName;
    }
}
''',
        encoding="utf-8",
    )

    # 3. repository/OwnerRepository.java
    repo_dir = base_pkg / "repository"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "OwnerRepository.java").write_text(
        '''package org.repomind.repository;

import org.repomind.model.Owner;
import java.util.Optional;

public interface OwnerRepository {
    Optional<Owner> findById(Long id);
    void save(Owner owner);
}
''',
        encoding="utf-8",
    )

    # 4. service/ClinicService.java
    svc_dir = base_pkg / "service"
    svc_dir.mkdir(parents=True, exist_ok=True)
    (svc_dir / "ClinicService.java").write_text(
        '''package org.repomind.service;

import org.repomind.model.Owner;
import org.repomind.repository.OwnerRepository;
import java.util.Optional;

public class ClinicService {
    private final OwnerRepository ownerRepository;

    public ClinicService(OwnerRepository repo) {
        this.ownerRepository = repo;
    }

    public Optional<Owner> findOwnerById(Long id) {
        return this.ownerRepository.findById(id);
    }
}
''',
        encoding="utf-8",
    )

    # 5. controller/OwnerController.java
    ctrl_dir = base_pkg / "controller"
    ctrl_dir.mkdir(parents=True, exist_ok=True)
    (ctrl_dir / "OwnerController.java").write_text(
        '''package org.repomind.controller;

import org.repomind.model.Owner;
import org.repomind.service.ClinicService;
import java.util.Optional;

public class OwnerController {
    private final ClinicService clinicService;

    public OwnerController(ClinicService clinicService) {
        this.clinicService = clinicService;
    }

    public Owner processFindForm(Long ownerId) {
        Optional<Owner> owner = this.clinicService.findOwnerById(ownerId);
        return owner.orElse(null);
    }
}
''',
        encoding="utf-8",
    )

    return target_dir


def build_real_world_ky_subset(target_dir: Path) -> Path:
    """Provisions authentic pinned subset of sindresorhus/ky (commit 3541888)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    cache_file = Path(__file__).parent / "real_world_ky_files.json"
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            files_dict = json.load(f)
        for rel_path, content in files_dict.items():
            dest = target_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
    return target_dir


def build_real_world_petclinic_subset(target_dir: Path) -> Path:
    """Provisions authentic pinned subset of spring-projects/spring-petclinic (commit 500158f)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    cache_file = Path(__file__).parent / "real_world_petclinic_files.json"
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            files_dict = json.load(f)
        for rel_path, content in files_dict.items():
            dest = target_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
    return target_dir

