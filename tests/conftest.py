"""
LoopGrid Test Configuration

"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.database import Base, get_db

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///./test_loopgrid.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Test client with overridden DB."""
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_decision():
    """Standard test decision payload."""
    return {
        "service_name": "test-agent",
        "decision_type": "customer_support_reply",
        "input": {"message": "I was charged twice"},
        "model": {"provider": "openai", "name": "gpt-4"},
        "output": {"response": "Your account looks fine."}
    }
