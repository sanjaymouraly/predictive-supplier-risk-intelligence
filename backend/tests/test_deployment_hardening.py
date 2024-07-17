"""Tests for deployment hardening: portable artifacts, auth modes and stale queue cleanup."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.ml_pipeline import load_verified_model_artifact, resolve_artifact_path
from app.models import ModelRegistry

client = TestClient(app)


def test_registry_artifact_paths_are_portable_filenames() -> None:
    """Newly trained models must not bake machine-specific absolute paths into the DB."""
    db = SessionLocal()
    try:
        for model in db.query(ModelRegistry).all():
            assert model.artifact_path is not None
            assert "/" not in model.artifact_path and "\\" not in model.artifact_path, (
                f"Artifact path for {model.model_version} is not portable: {model.artifact_path}"
            )
            resolved = resolve_artifact_path(model.artifact_path)
            assert resolved is not None and resolved.exists()
    finally:
        db.close()


def test_resolve_artifact_path_rejects_traversal() -> None:
    """A malicious registry entry must never escape the trusted artifacts directory."""
    resolved = resolve_artifact_path("../../../../etc/passwd")
    assert resolved is None or str(resolved).startswith(str(settings.artifacts_dir.resolve()))


def test_legacy_absolute_path_is_recovered_by_basename() -> None:
    """Older DBs containing another host's absolute path still resolve via the filename."""
    db = SessionLocal()
    try:
        champ = db.query(ModelRegistry).filter(ModelRegistry.is_champion.is_(True)).first()
        assert champ is not None
        original = champ.artifact_path
        champ.artifact_path = f"/home/user/backend/artifacts/{original}"
        db.commit()

        resolved = resolve_artifact_path(champ.artifact_path)
        assert resolved is not None and resolved.exists()
        _, bundle = load_verified_model_artifact(db, model_version=champ.model_version)
        assert bundle["model_version"] == champ.model_version

        champ.artifact_path = original
        db.commit()
    finally:
        db.close()


def test_demo_mode_can_be_disabled_for_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """With ALLOW_DEMO_MODE=false, unauthenticated role headers must be rejected."""
    from app.auth import get_current_user

    monkeypatch.setattr(settings, "allow_demo_mode", False)
    db = SessionLocal()
    try:
        with pytest.raises(Exception) as exc_info:
            get_current_user(
                credentials=None,
                x_demo_role="admin",
                x_demo_user=None,
                db=db,
            )
        assert "401" in str(exc_info.value) or "Authentication required" in str(exc_info.value)
    finally:
        db.close()

    # A real JWT must still work when demo mode is off.
    token = client.post(
        "/api/auth/login",
        json={"username": "priya.nair", "password": "Reviewer2026!"},
    ).json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "reviewer"


def test_review_queue_exposes_resolved_bucket() -> None:
    payload = client.get("/api/reviews").json()
    assert "resolved" in payload["summary"]
    assert payload["summary"]["total_in_queue"] >= payload["summary"]["pending"]
