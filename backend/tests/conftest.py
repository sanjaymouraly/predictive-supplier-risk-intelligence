"""Shared pytest configuration.

Tests run against an isolated, throwaway SQLite database and artifact directory so
that the reproducible demo database shipped with the project is never mutated by
a test run. The fixture is session-scoped because seeding + training the reference
model is intentionally expensive.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="sri-test-"))
_DATA_DIR = _TMP_ROOT / "data"
_ARTIFACTS_DIR = _TMP_ROOT / "artifacts"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# These must be set *before* app.config is imported by any test module.
os.environ["DATABASE_URL"] = f"sqlite:///{_DATA_DIR / 'test.db'}"
os.environ["ARTIFACTS_DIR"] = str(_ARTIFACTS_DIR)
os.environ["DATA_DIR"] = str(_DATA_DIR)
os.environ["RANDOM_SEED"] = "42"
os.environ["REFERENCE_DATE"] = "2026-10-17"
os.environ["ALLOW_DEMO_MODE"] = "true"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["AUTO_TRAIN_ON_STARTUP"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-not-for-production"


@pytest.fixture(scope="session", autouse=True)
def _isolated_application_state():
    """Bootstrap the isolated test database exactly once per test session."""
    from app.main import bootstrap_application_state

    bootstrap_application_state()
    yield
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)
