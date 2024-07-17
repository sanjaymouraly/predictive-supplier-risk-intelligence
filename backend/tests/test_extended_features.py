"""Tests for extended features: exports, AI provider hardening and order lifecycle."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.ai_service import (
    decrypt_secret,
    encrypt_secret,
    estimate_cost_usd,
    mask_api_key,
    validate_provider_base_url,
)
from app.main import app

client = TestClient(app)


def test_ai_secret_encryption_roundtrip_and_masking() -> None:
    secret = "sk-test-1234567890abcdef"
    stored = encrypt_secret(secret)
    assert stored.startswith("enc::")
    assert secret not in stored
    assert decrypt_secret(stored) == secret
    masked = mask_api_key(stored)
    assert secret not in masked
    assert masked.startswith("sk-t")
    # Legacy plaintext rows remain readable.
    assert decrypt_secret("legacy-plaintext-key") == "legacy-plaintext-key"


def test_provider_base_url_blocks_cloud_metadata() -> None:
    assert validate_provider_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert validate_provider_base_url("http://localhost:11434/v1") == "http://localhost:11434/v1"
    with pytest.raises(ValueError):
        validate_provider_base_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        validate_provider_base_url("http://169.254.169.254/latest/meta-data")


def test_cost_estimation_is_token_based() -> None:
    assert estimate_cost_usd("gpt-4o-mini", 1_000_000, 0) == pytest.approx(0.15, abs=1e-6)
    assert estimate_cost_usd("gemma3:latest", 10_000, 10_000) == 0.0
    assert estimate_cost_usd("unknown-model-xyz", 1000, 1000) == 0.0


def test_ai_provider_presets_and_offline_model_discovery() -> None:
    presets = client.get("/api/ai/providers")
    assert presets.status_code == 200
    provider_types = {p["provider_type"] for p in presets.json()}
    assert {
        "none",
        "openai",
        "anthropic",
        "openrouter",
        "ollama",
        "custom",
    }.issubset(provider_types)
    ollama = next(p for p in presets.json() if p["provider_type"] == "ollama")
    assert any("gemma" in m for m in ollama["suggested_models"])

    models = client.get("/api/ai/models")
    assert models.status_code == 200
    assert models.json()["provider_type"] == "none"


def test_csv_exports_include_real_rows() -> None:
    for path, expected_header in [
        ("/api/reports/predictions.csv", "po_number"),
        ("/api/reports/orders.csv", "po_number"),
        ("/api/reports/suppliers.csv", "supplier_code"),
    ]:
        resp = client.get(path)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        lines = resp.text.strip().splitlines()
        assert expected_header in lines[0]
        assert len(lines) > 5


def test_order_lifecycle_prediction_created_then_cleared_on_delivery() -> None:
    suppliers = client.get("/api/suppliers").json()
    supplier_id = suppliers[0]["id"]
    products = client.get("/api/products").json()
    product = next(p for p in products if p["supplier_id"] == supplier_id)

    po_number = f"PO-2026-TEST-{uuid.uuid4().hex[:6].upper()}"
    created = client.post(
        "/api/orders",
        json={
            "po_number": po_number,
            "supplier_id": supplier_id,
            "product_id": product["id"],
            "order_date": "2026-10-16",
            "promised_delivery_date": "2026-12-01",
            "quantity": 100,
            "unit_price": 120.0,
            "status": "open",
            "shipping_mode": "Ocean Freight",
            "urgency_level": "standard",
        },
    )
    assert created.status_code == 201, created.text
    po_id = created.json()["id"]
    assert created.json()["latest_prediction"] is not None

    # Recording an actual delivery must close the order and clear stale predictions.
    updated = client.put(
        f"/api/orders/{po_id}",
        json={"status": "delivered", "actual_delivery_date": "2026-11-20"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["status"] == "delivered"
    assert body["is_delayed"] is False

    preds = client.get("/api/predictions").json()
    assert all(p["po_id"] != po_id for p in preds)


def test_health_reports_demo_mode_flag() -> None:
    payload = client.get("/api/health").json()
    assert payload["demo_mode"] is True
