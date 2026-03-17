"""
KGKB Test Configuration

Shared fixtures for API and E2E tests.
Uses a temporary database for each test session to avoid polluting real data.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def temp_data_dir():
    """Create a temporary data directory for the entire test session.

    Sets KGKB_DATA_DIR so all services use temp storage.
    Cleaned up after all tests complete.
    """
    tmpdir = tempfile.mkdtemp(prefix="kgkb_test_")
    os.environ["KGKB_DATA_DIR"] = tmpdir
    yield Path(tmpdir)
    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("KGKB_DATA_DIR", None)


@pytest.fixture(scope="session")
def test_client(temp_data_dir):
    """Create a FastAPI TestClient for the KGKB app.

    Uses the temp data directory so tests don't affect real data.
    Session-scoped for performance — the app is created once.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def knowledge_service(temp_data_dir):
    """Create a fresh KnowledgeService pointing at the temp database.

    Function-scoped — each test gets the same DB but can create its own data.
    """
    from backend.app.services.knowledge import KnowledgeService

    db_path = temp_data_dir / "data.db"
    return KnowledgeService(db_path)
