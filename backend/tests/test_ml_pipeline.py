"""Tests for ML pipeline evaluation, SHA-256 artifact integrity, and cold-start reliability warnings."""

from __future__ import annotations

import json

import pytest

from app.database import SessionLocal
from app.explainability import evaluate_prediction_reliability
from app.ml_pipeline import (
    SecurityError,
    load_verified_model_artifact,
    predict_order_risk,
)
from app.models import ModelRegistry, PurchaseOrder


def test_all_three_algorithms_and_baselines_registered() -> None:
    """Verify Logistic Regression, Random Forest, and HistGradientBoosting are trained and evaluated."""
    db = SessionLocal()
    try:
        models = db.query(ModelRegistry).all()
        algos = {m.algorithm_name for m in models}
        assert "logistic_regression" in algos
        assert "random_forest" in algos
        assert "hist_gradient_boosting" in algos

        champ = (
            db.query(ModelRegistry)
            .filter(ModelRegistry.is_champion.is_(True))
            .first()
        )
        assert champ is not None
        metrics = json.loads(champ.metrics_json)
        assert "validation" in metrics
        assert "test" in metrics
        assert "baselines" in metrics
        assert metrics["test"]["roc_auc"] >= 0.72
        assert metrics["test"]["pr_auc"] >= 0.60
        assert metrics["test"]["brier_score"] <= 0.25
        assert "precision_at_25" in metrics["test"]["review_capacity_metrics"]
    finally:
        db.close()


def test_sha256_integrity_check_blocks_tampered_artifact() -> None:
    """Verify that tampering with the expected SHA-256 hash raises SecurityError."""
    db = SessionLocal()
    try:
        champ = (
            db.query(ModelRegistry)
            .filter(ModelRegistry.is_champion.is_(True))
            .first()
        )
        assert champ is not None
        original_sha = champ.artifact_sha256
        champ.artifact_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
        db.commit()

        with pytest.raises(SecurityError, match="Artifact integrity check failed"):
            load_verified_model_artifact(db, model_version=champ.model_version)

        champ.artifact_sha256 = original_sha
        db.commit()
    finally:
        db.close()


def test_cold_start_and_ood_reliability_warnings() -> None:
    """Verify explicit reliability warnings for sparse supplier history and OOD inputs."""
    features_cold = {
        "supplier_prior_order_count": 0.0,
        "quantity_vs_supplier_avg_ratio": 4.2,
        "lead_time_compression_ratio": 0.55,
        "supplier_prior_delay_std": 8.0,
        "product_category": "Semiconductors",
    }
    status, warnings = evaluate_prediction_reliability(
        features=features_cold,
        historical_context={"supplier_completed_orders_prior": 0},
        training_stats={"known_categories": {"product_category": ["Semiconductors"]}},
    )
    assert status == "unreliable_cold_start"
    assert any(
        "Insufficient supplier history — manual review recommended" in w
        for w in warnings
    )
    assert any("Out-of-distribution order volume" in w for w in warnings)
    assert any("Extreme lead-time compression" in w for w in warnings)


def test_single_order_prediction_and_explainability() -> None:
    """Verify single order prediction outputs calibrated probabilities and non-causal attributions."""
    db = SessionLocal()
    try:
        open_po = (
            db.query(PurchaseOrder)
            .filter(PurchaseOrder.status.in_(["open", "in_transit"]))
            .first()
        )
        assert open_po is not None
        res = predict_order_risk(db=db, po=open_po, persist=False)
        assert 0.0 <= res["calibrated_probability"] <= 1.0
        assert res["risk_category"] in ("low", "moderate", "high", "critical")
        assert len(res["top_contributors"]) == 6
        assert "do not establish causal effects" in res["explanation_limitations"]
    finally:
        db.close()


def test_batch_inference_performance_smoke() -> None:
    """Performance smoke test: batch scoring all 140+ open orders must complete within 10 seconds."""
    import time

    from app.decision_engine import refresh_predictions_and_queues

    db = SessionLocal()
    try:
        t0 = time.perf_counter()
        res = refresh_predictions_and_queues(db=db)
        elapsed = time.perf_counter() - t0
        assert res["open_orders_scored"] >= 140
        assert elapsed < 10.0, f"Batch inference took too long: {elapsed:.2f}s"
    finally:
        db.close()

