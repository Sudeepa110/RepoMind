import pytest
from backend.app.database.session import init_db

@pytest.fixture(autouse=True)
async def setup_database():
    """Initializes database schema for tests."""
    await init_db()
    yield

