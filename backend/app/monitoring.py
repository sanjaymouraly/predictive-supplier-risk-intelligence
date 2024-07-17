"""Model monitoring, feature drift detection, and operational metrics."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.feature_engineering import FEATURE_DISPLAY_NAMES, NUMERIC_FEATURES
from app.ml_pipeline import load_verified_model_artifact
from app.models import (
    ReviewQueueItem,
    RiskPrediction,
)


def compute_monitoring_diagnostics(db: Session) -> dict[str, Any]:
    """Compute live prediction distribution, feature drift, and review governance diagnostics."""
    preds = db.query(RiskPrediction).all()
    if not preds:
        return {
            "status": "no_predictions",
            "message": "No active predictions found.",
        }

    reg, bundle = load_verified_model_artifact(db)
    train_stats = bundle.get("training_stats", {})
    train_means = train_stats.get("numeric_means", {})
    train_stds = train_stats.get("numeric_stds", {})
    train_delay_rate = float(train_stats.get("train_delay_rate", 0.30))

    probs = np.array([p.calibrated_probability for p in preds], dtype=float)
    mean_live_prob = float(np.mean(probs))
    prob_shift = round(mean_live_prob - train_delay_rate, 4)

    # Prediction probability histogram across 5 buckets
    buckets = [
        ("0-20% (Low)", 0.0, 0.20),
        ("20-40% (Guarded)", 0.20, 0.40),
        ("40-60% (Moderate)", 0.40, 0.60),
        ("60-80% (High)", 0.60, 0.80),
        ("80-100% (Critical)", 0.80, 1.01),
    ]
    prob_distribution = []
    for label, lo, hi in buckets:
        cnt = int(np.sum((probs >= lo) & (probs < hi)))
        prob_distribution.append(
            {
                "bucket": label,
                "count": cnt,
                "share": round(cnt / len(probs), 4),
            }
        )

    # Feature Drift Analysis comparing live open-order feature snapshots vs training distribution
    snapshots = [json.loads(p.feature_snapshot_json) for p in preds if p.feature_snapshot_json]
    feature_drift_rows: list[dict[str, Any]] = []
    if snapshots:
        for col in NUMERIC_FEATURES[:10]:
            live_vals = np.array([float(s.get(col, 0.0)) for s in snapshots], dtype=float)
            live_mean = float(np.mean(live_vals))
            ref_mean = float(train_means.get(col, live_mean))
            ref_std = max(1e-4, float(train_stds.get(col, 1.0)))
            z_shift = abs(live_mean - ref_mean) / ref_std

            if z_shift > 0.75:
                drift_status = "drift_warning"
            elif z_shift > 0.40:
                drift_status = "minor_shift"
            else:
                drift_status = "stable"

            feature_drift_rows.append(
                {
                    "feature_name": col,
                    "display_label": FEATURE_DISPLAY_NAMES.get(col, col),
                    "training_mean": round(ref_mean, 3),
                    "live_mean": round(live_mean, 3),
                    "standardized_shift_z": round(float(z_shift), 3),
                    "drift_status": drift_status,
                }
            )
        feature_drift_rows.sort(key=lambda x: x["standardized_shift_z"], reverse=True)

    # Reliability warning breakdown
    rel_counts: dict[str, int] = {}
    for p in preds:
        rel_counts[p.reliability_status] = rel_counts.get(p.reliability_status, 0) + 1

    # Operational review queue metrics
    review_items = db.query(ReviewQueueItem).all()
    status_counts: dict[str, int] = {}
    for r in review_items:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    return {
        "champion_model_version": reg.model_version,
        "champion_algorithm": reg.algorithm_name,
        "total_live_predictions": len(preds),
        "training_baseline_delay_rate": round(train_delay_rate, 4),
        "live_mean_predicted_probability": round(mean_live_prob, 4),
        "prediction_rate_shift": prob_shift,
        "probability_distribution": prob_distribution,
        "feature_drift": feature_drift_rows,
        "reliability_breakdown": rel_counts,
        "review_workflow_breakdown": status_counts,
        "retraining_governance": (
            "Automatic model retraining and silent promotion are disabled by policy. "
            "New candidate models must be evaluated on chronological holdouts and explicitly promoted by an authorized lead."
        ),
    }
