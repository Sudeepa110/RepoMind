import pytest
from sqlalchemy import create_engine
from backend.app.config import settings
from backend.app.database.models import Base

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Initializes database schema synchronously once per test session."""
    settings.init_directories()
    db_path_str = str(settings.SQLITE_DB_PATH).replace("\\", "/")
    sync_engine = create_engine(f"sqlite:///{db_path_str}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    yield


