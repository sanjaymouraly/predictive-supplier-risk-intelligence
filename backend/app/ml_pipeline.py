"""End-to-end Machine Learning training, evaluation, calibration, and inference pipeline."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy.orm import Session

from app.config import settings
from app.explainability import (
    compute_local_feature_contributions,
    evaluate_prediction_reliability,
)
from app.feature_engineering import (
    ALL_MODEL_FEATURES,
    CATEGORICAL_FEATURES,
    FEATURE_DISPLAY_NAMES,
    FORBIDDEN_LEAKAGE_COLUMNS,
    NUMERIC_FEATURES,
    build_point_in_time_training_dataframe,
    compute_point_in_time_features_for_order,
)
from app.models import (
    ModelRegistry,
    Product,
    PurchaseOrder,
    RiskPrediction,
    Supplier,
    SystemRuleConfig,
)


def _compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_artifact_path(stored_path: str | None) -> Path | None:
    """Resolve a registry artifact path in a portable, traversal-safe way.

    Newly trained models store only the artifact *filename*. Older databases may
    contain absolute paths from another machine, so a bare basename fallback is
    applied when the recorded location no longer exists. Any resolved path must
    remain inside ``settings.artifacts_dir``.
    """
    if not stored_path:
        return None

    raw = Path(stored_path)
    candidates = [raw] if raw.is_absolute() else [settings.artifacts_dir / raw]
    # Backwards compatibility: recover from absolute paths baked in on another host.
    candidates.append(settings.artifacts_dir / raw.name)

    allowed_dir = settings.artifacts_dir.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not str(resolved).startswith(str(allowed_dir)):
            continue
        if resolved.exists():
            return resolved

    # Nothing exists yet; return the safest expected location for error messaging.
    fallback = (settings.artifacts_dir / raw.name).resolve()
    return fallback if str(fallback).startswith(str(allowed_dir)) else None


def _expected_calibration_error(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> float:
    """Compute Expected Calibration Error (ECE) across uniform probability bins."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binids = np.digitize(y_prob, bins) - 1
    ece = 0.0
    n = len(y_true)
    if n == 0:
        return 0.0
    for b in range(n_bins):
        mask = binids == b
        if np.any(mask):
            bin_acc = float(np.mean(y_true[mask]))
            bin_conf = float(np.mean(y_prob[mask]))
            ece += (np.sum(mask) / n) * abs(bin_acc - bin_conf)
    return float(ece)


def _precision_recall_at_k(
    y_true: np.ndarray, y_prob: np.ndarray, k: int
) -> tuple[float, float]:
    """Compute Precision@K and Recall@K when reviewing the top K highest-risk orders."""
    n = len(y_true)
    if n == 0:
        return 0.0, 0.0
    k_eff = min(k, n)
    top_indices = np.argsort(y_prob)[::-1][:k_eff]
    true_in_top_k = float(np.sum(y_true[top_indices]))
    prec_at_k = true_in_top_k / k_eff
    total_positives = float(np.sum(y_true))
    rec_at_k = true_in_top_k / total_positives if total_positives > 0 else 0.0
    return round(prec_at_k, 4), round(rec_at_k, 4)


def _bootstrap_ci(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    metric_fn,
    n_bootstraps: int = 80,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute 95% bootstrap confidence interval for a ranking metric."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    if n < 20 or len(np.unique(y_true)) < 2:
        val = float(metric_fn(y_true, y_prob)) if len(np.unique(y_true)) >= 2 else 0.5
        return round(val, 4), round(val, 4)

    scores: list[float] = []
    for _ in range(n_bootstraps):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        if len(np.unique(yt)) < 2:
            continue
        scores.append(float(metric_fn(yt, y_prob[idx])))
    if not scores:
        val = float(metric_fn(y_true, y_prob))
        return round(val, 4), round(val, 4)
    low, high = np.percentile(scores, [2.5, 97.5])
    return round(float(low), 4), round(float(high), 4)


def _evaluate_predictions(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.50,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute comprehensive ML & operational review capacity metrics."""
    y_pred = (y_prob >= threshold).astype(int)
    has_both_classes = len(np.unique(y_true)) >= 2

    roc_auc = float(roc_auc_score(y_true, y_prob)) if has_both_classes else 0.5
    pr_auc = float(average_precision_score(y_true, y_prob)) if has_both_classes else 0.0
    roc_ci = _bootstrap_ci(y_true, y_prob, roc_auc_score, seed=seed)
    pr_ci = _bootstrap_ci(y_true, y_prob, average_precision_score, seed=seed)

    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    brier = float(brier_score_loss(y_true, y_prob))
    ece = _expected_calibration_error(y_true, y_prob, n_bins=8)

    tn, fp, fn, tp = (
        confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        if len(y_true) > 0
        else (0, 0, 0, 0)
    )

    p10, r10 = _precision_recall_at_k(y_true, y_prob, 10)
    p25, r25 = _precision_recall_at_k(y_true, y_prob, 25)
    p50, r50 = _precision_recall_at_k(y_true, y_prob, 50)

    # ROC curve points (downsampled to ~25 points for clean API/UI visualization)
    if has_both_classes:
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        step = max(1, len(fpr) // 25)
        roc_points = [
            {"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)}
            for i in range(0, len(fpr), step)
        ]
        if roc_points[-1]["fpr"] != 1.0:
            roc_points.append({"fpr": 1.0, "tpr": 1.0})

        prec_c, rec_c, _ = precision_recall_curve(y_true, y_prob)
        step_pr = max(1, len(prec_c) // 25)
        pr_points = [
            {"recall": round(float(rec_c[i]), 4), "precision": round(float(prec_c[i]), 4)}
            for i in range(0, len(prec_c), step_pr)
        ]
    else:
        roc_points = [{"fpr": 0.0, "tpr": 0.0}, {"fpr": 1.0, "tpr": 1.0}]
        pr_points = []

    return {
        "roc_auc": round(roc_auc, 4),
        "roc_auc_ci_95": list(roc_ci),
        "pr_auc": round(pr_auc, 4),
        "pr_auc_ci_95": list(pr_ci),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "brier_score": round(brier, 4),
        "expected_calibration_error": round(ece, 4),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "review_capacity_metrics": {
            "precision_at_10": p10,
            "recall_at_10": r10,
            "precision_at_25": p25,
            "recall_at_25": r25,
            "precision_at_50": p50,
            "recall_at_50": r50,
        },
        "roc_curve": roc_points,
        "pr_curve": pr_points,
        "positive_rate": round(float(np.mean(y_true)), 4) if len(y_true) > 0 else 0.0,
        "sample_count": int(len(y_true)),
    }


def _compute_calibration_bins(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 8
) -> list[dict[str, Any]]:
    if len(y_true) < 10 or len(np.unique(y_true)) < 2:
        return []
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="uniform")
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binids = np.digitize(y_prob, bins) - 1
    non_empty_counts = [int(np.sum(binids == b)) for b in range(n_bins) if np.any(binids == b)]

    result: list[dict[str, Any]] = []
    for idx in range(len(prob_pred)):
        result.append(
            {
                "bin_index": idx + 1,
                "mean_predicted_prob": round(float(prob_pred[idx]), 4),
                "observed_delay_rate": round(float(prob_true[idx]), 4),
                "count": non_empty_counts[idx] if idx < len(non_empty_counts) else 0,
            }
        )
    return result


def _compute_segment_analysis(
    df_test: pd.DataFrame, y_true: np.ndarray, y_prob: np.ndarray
) -> dict[str, Any]:
    """Evaluate calibration and error rates across operational segments."""
    df_seg = df_test.copy()
    df_seg["y_true"] = y_true
    df_seg["y_prob"] = y_prob
    df_seg["y_pred"] = (y_prob >= 0.50).astype(int)

    by_region: list[dict[str, Any]] = []
    for reg, grp in df_seg.groupby("supplier_region"):
        if len(grp) < 3:
            continue
        yt = grp["y_true"].to_numpy()
        yp = grp["y_prob"].to_numpy()
        by_region.append(
            {
                "segment": str(reg),
                "count": int(len(grp)),
                "observed_delay_rate": round(float(np.mean(yt)), 4),
                "mean_predicted_prob": round(float(np.mean(yp)), 4),
                "brier_score": round(float(brier_score_loss(yt, yp)), 4),
                "roc_auc": round(float(roc_auc_score(yt, yp)), 4)
                if len(np.unique(yt)) >= 2
                else None,
            }
        )

    by_category: list[dict[str, Any]] = []
    for cat, grp in df_seg.groupby("product_category"):
        if len(grp) < 3:
            continue
        yt = grp["y_true"].to_numpy()
        yp = grp["y_prob"].to_numpy()
        by_category.append(
            {
                "segment": str(cat),
                "count": int(len(grp)),
                "observed_delay_rate": round(float(np.mean(yt)), 4),
                "mean_predicted_prob": round(float(np.mean(yp)), 4),
                "brier_score": round(float(brier_score_loss(yt, yp)), 4),
            }
        )

    return {
        "by_region": by_region,
        "by_category": by_category,
    }


def _build_preprocessor() -> ColumnTransformer:
    num_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    cat_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", num_pipe, NUMERIC_FEATURES),
            ("cat", cat_pipe, CATEGORICAL_FEATURES),
        ]
    )


def train_and_evaluate_all_models(
    db: Session,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Train, tune, calibrate, and evaluate Logistic Regression, Random Forest, and HistGradientBoosting.

    Enforces chronological Train (70%) / Validation (15%) / Test (15%) splits and compares
    against two operational baselines. Persists artifacts with SHA-256 hashes and updates ModelRegistry.
    """
    df = build_point_in_time_training_dataframe(db)
    if len(df) < 50:
        raise ValueError(f"Insufficient delivered historical orders ({len(df)}) to train ML pipeline.")

    # Verify zero forbidden columns in feature list
    assert not FORBIDDEN_LEAKAGE_COLUMNS.intersection(ALL_MODEL_FEATURES)

    # Sort strictly chronologically by order_date, then po_id
    df = df.sort_values(["order_date", "po_id"]).reset_index(drop=True)

    n_total = len(df)
    n_train = int(n_total * 0.70)
    n_val = int(n_total * 0.85)

    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train:n_val].copy()
    df_test = df.iloc[n_val:].copy()

    # Assert strict chronological ordering across split boundaries
    assert df_train["order_date"].max() <= df_val["order_date"].min()
    assert df_val["order_date"].max() <= df_test["order_date"].min()

    X_train = df_train[ALL_MODEL_FEATURES]
    y_train = df_train["target_is_delayed"].to_numpy()
    X_val = df_val[ALL_MODEL_FEATURES]
    y_val = df_val["target_is_delayed"].to_numpy()
    X_test = df_test[ALL_MODEL_FEATURES]
    y_test = df_test["target_is_delayed"].to_numpy()

    # Identify unseen / cold-start supplier test subset (suppliers with < 3 prior orders or not in train)
    train_suppliers = set(df_train["supplier_id"].unique())
    cold_mask = (df_test["supplier_prior_order_count"] < 5) | (
        ~df_test["supplier_id"].isin(train_suppliers)
    )

    # Compute training distribution stats for OOD & explainability reference
    training_stats = {
        "numeric_means": {col: float(X_train[col].mean()) for col in NUMERIC_FEATURES},
        "numeric_stds": {col: float(X_train[col].std() or 1.0) for col in NUMERIC_FEATURES},
        "categorical_modes": {
            col: str(X_train[col].mode().iloc[0]) for col in CATEGORICAL_FEATURES
        },
        "known_categories": {
            col: [str(v) for v in X_train[col].unique()] for col in CATEGORICAL_FEATURES
        },
        "train_delay_rate": float(np.mean(y_train)),
    }

    # --- Operational Baselines (evaluated on Validation & Test) ---
    # Baseline 1: Naive Historical Supplier Delay Rate (1 - supplier_prior_otd_rate_smoothed)
    val_prob_base_sup = np.clip(
        1.0 - X_val["supplier_prior_otd_rate_smoothed"].to_numpy(), 0.02, 0.98
    )
    test_prob_base_sup = np.clip(
        1.0 - X_test["supplier_prior_otd_rate_smoothed"].to_numpy(), 0.02, 0.98
    )

    # Baseline 2: Lead-Time Compression Heuristic
    test_prob_base_lt = np.clip(
        0.55 - 0.35 * (X_test["lead_time_compression_ratio"].to_numpy() - 1.0), 0.05, 0.95
    )

    baselines_summary = {
        "supplier_history_heuristic": {
            "display_name": "Operational Baseline: Historical Supplier Delay Rate",
            "validation": _evaluate_predictions(y_val, val_prob_base_sup, seed=random_seed),
            "test": _evaluate_predictions(y_test, test_prob_base_sup, seed=random_seed),
        },
        "lead_time_compression_heuristic": {
            "display_name": "Operational Baseline: Lead-Time Compression Rule",
            "test": _evaluate_predictions(y_test, test_prob_base_lt, seed=random_seed),
        },
    }

    # --- Define the 3 Candidate ML Algorithms + Hyperparameter Grids ---
    candidate_specs: list[dict[str, Any]] = [
        {
            "algorithm_name": "logistic_regression",
            "display_name": "Logistic Regression (Calibrated Linear Baseline)",
            "interpretability_bonus": 0.02,
            "candidates": [
                {"C": 0.25, "class_weight": "balanced"},
                {"C": 1.0, "class_weight": "balanced"},
                {"C": 2.5, "class_weight": None},
            ],
            "builder": lambda params: LogisticRegression(
                C=params["C"],
                class_weight=params["class_weight"],
                max_iter=1000,
                random_state=random_seed,
            ),
        },
        {
            "algorithm_name": "random_forest",
            "display_name": "Random Forest (Calibrated Nonlinear Ensemble)",
            "interpretability_bonus": 0.01,
            "candidates": [
                {"n_estimators": 140, "max_depth": 8, "min_samples_leaf": 6},
                {"n_estimators": 180, "max_depth": 11, "min_samples_leaf": 4},
            ],
            "builder": lambda params: RandomForestClassifier(
                n_estimators=params["n_estimators"],
                max_depth=params["max_depth"],
                min_samples_leaf=params["min_samples_leaf"],
                class_weight="balanced_subsample",
                random_state=random_seed,
                n_jobs=-1,
            ),
        },
        {
            "algorithm_name": "hist_gradient_boosting",
            "display_name": "HistGradientBoosting (Calibrated Gradient-Boosted Trees)",
            "interpretability_bonus": 0.015,
            "candidates": [
                {"max_iter": 140, "learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 15, "l2_regularization": 1.5},
                {"max_iter": 180, "learning_rate": 0.07, "max_leaf_nodes": 23, "min_samples_leaf": 12, "l2_regularization": 0.8},
            ],
            "builder": lambda params: HistGradientBoostingClassifier(
                max_iter=params["max_iter"],
                learning_rate=params["learning_rate"],
                max_leaf_nodes=params["max_leaf_nodes"],
                min_samples_leaf=params["min_samples_leaf"],
                l2_regularization=params["l2_regularization"],
                random_state=random_seed,
            ),
        },
    ]

    trained_models_info: list[dict[str, Any]] = []
    timestamp_tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # Reset existing champion flags
    db.query(ModelRegistry).update({"is_champion": False})
    db.commit()

    for spec in candidate_specs:
        algo_name = spec["algorithm_name"]
        best_val_score = -1e9
        best_bundle = None
        best_params = None

        for params in spec["candidates"]:
            preprocessor = _build_preprocessor()
            X_train_trans = preprocessor.fit_transform(X_train)
            base_est = spec["builder"](params)
            base_est.fit(X_train_trans, y_train)

            full_pipe = Pipeline(
                steps=[
                    ("preprocessor", preprocessor),
                    ("classifier", base_est),
                ]
            )
            calibrated_model = CalibratedClassifierCV(
                estimator=full_pipe,
                method="sigmoid",
                cv=3,
            )
            calibrated_model.fit(X_train, y_train)

            val_probs = calibrated_model.predict_proba(X_val)[:, 1]
            val_metrics = _evaluate_predictions(y_val, val_probs, seed=random_seed)

            # Multi-objective validation selection score:
            # 0.35 * PR-AUC + 0.30 * ROC-AUC + 0.20 * Precision@25 - 0.15 * BrierScore + InterpretabilityBonus
            composite = (
                0.35 * val_metrics["pr_auc"]
                + 0.30 * val_metrics["roc_auc"]
                + 0.20 * val_metrics["review_capacity_metrics"]["precision_at_25"]
                - 0.15 * val_metrics["brier_score"]
                + spec["interpretability_bonus"]
            )
            if composite > best_val_score:
                best_val_score = composite
                best_params = params
                best_bundle = {
                    "preprocessor": preprocessor,
                    "base_estimator": base_est,
                    "calibrated_model": calibrated_model,
                    "val_metrics": val_metrics,
                    "val_probs": val_probs,
                    "composite_score": round(float(composite), 4),
                }

        assert best_bundle is not None and best_params is not None

        cal_model = best_bundle["calibrated_model"]
        test_probs = cal_model.predict_proba(X_test)[:, 1]
        test_metrics = _evaluate_predictions(y_test, test_probs, seed=random_seed)
        cal_bins = _compute_calibration_bins(y_test, test_probs, n_bins=8)
        seg_analysis = _compute_segment_analysis(df_test, y_test, test_probs)

        # Unseen / cold-start supplier evaluation on test split
        if int(np.sum(cold_mask)) >= 5:
            y_cold = y_test[cold_mask]
            p_cold = test_probs[cold_mask]
            unseen_metrics = _evaluate_predictions(y_cold, p_cold, seed=random_seed)
        else:
            unseen_metrics = {
                "sample_count": int(np.sum(cold_mask)),
                "note": "Evaluated on cold-start/sparse-history orders in test split",
                "brier_score": round(
                    float(brier_score_loss(y_test[cold_mask], test_probs[cold_mask])), 4
                )
                if int(np.sum(cold_mask)) > 0
                else None,
            }

        # Global Feature Importance via permutation importance on validation split
        perm = permutation_importance(
            cal_model,
            X_val,
            y_val,
            scoring="roc_auc",
            n_repeats=5,
            random_state=random_seed,
        )
        feat_imp_list: list[dict[str, Any]] = []
        for idx_f, fname in enumerate(ALL_MODEL_FEATURES):
            imp_val = max(0.0, float(perm.importances_mean[idx_f]))
            feat_imp_list.append(
                {
                    "feature_name": fname,
                    "display_label": FEATURE_DISPLAY_NAMES.get(fname, fname),
                    "importance": round(imp_val, 5),
                    "std": round(float(perm.importances_std[idx_f]), 5),
                }
            )
        feat_imp_list.sort(key=lambda x: float(x["importance"]), reverse=True)

        version_id = f"{algo_name}-v1-{timestamp_tag}"
        artifact_path = settings.artifacts_dir / f"{version_id}.joblib"

        artifact_payload = {
            "model_version": version_id,
            "algorithm_name": algo_name,
            "display_name": spec["display_name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "random_seed": random_seed,
            "features": ALL_MODEL_FEATURES,
            "preprocessor": best_bundle["preprocessor"],
            "base_estimator": best_bundle["base_estimator"],
            "calibrated_model": cal_model,
            "training_stats": training_stats,
            "hyperparameters": best_params,
        }
        joblib.dump(artifact_payload, artifact_path)
        sha256_hex = _compute_file_sha256(artifact_path)

        metrics_bundle = {
            "validation": best_bundle["val_metrics"],
            "test": test_metrics,
            "baselines": baselines_summary,
            "composite_selection_score": best_bundle["composite_score"],
        }

        trained_models_info.append(
            {
                "model_version": version_id,
                "algorithm_name": algo_name,
                "display_name": spec["display_name"],
                "composite_score": best_bundle["composite_score"],
                "metrics_bundle": metrics_bundle,
                "calibration_bins": cal_bins,
                "feature_importance": feat_imp_list,
                "hyperparameters": best_params,
                "unseen_supplier_metrics": unseen_metrics,
                "segment_analysis": seg_analysis,
                "artifact_path": artifact_path.name,
                "artifact_sha256": sha256_hex,
            }
        )

    # Select Champion Model with highest multi-objective composite validation score
    trained_models_info.sort(key=lambda m: m["composite_score"], reverse=True)
    champion_version = trained_models_info[0]["model_version"]

    registry_rows: list[ModelRegistry] = []
    for m_info in trained_models_info:
        is_champ = m_info["model_version"] == champion_version
        val_m = m_info["metrics_bundle"]["validation"]
        test_m = m_info["metrics_bundle"]["test"]
        rationale = (
            f"{'Selected as Champion Model' if is_champ else 'Candidate Model'}: "
            f"Validation Composite Score = {m_info['composite_score']:.4f} "
            f"(Val PR-AUC={val_m['pr_auc']:.3f}, Val ROC-AUC={val_m['roc_auc']:.3f}, "
            f"Val Brier={val_m['brier_score']:.3f}, Val P@25={val_m['review_capacity_metrics']['precision_at_25']:.2f}; "
            f"Unseen Test ROC-AUC={test_m['roc_auc']:.3f}, Test PR-AUC={test_m['pr_auc']:.3f})."
        )
        reg = ModelRegistry(
            model_version=m_info["model_version"],
            algorithm_name=m_info["algorithm_name"],
            display_name=m_info["display_name"],
            is_champion=is_champ,
            status="champion" if is_champ else "evaluated",
            training_window_start=df_train["order_date"].min(),
            training_window_end=df_train["order_date"].max(),
            validation_window_end=df_val["order_date"].max(),
            test_window_end=df_test["order_date"].max(),
            train_row_count=len(df_train),
            val_row_count=len(df_val),
            test_row_count=len(df_test),
            random_seed=random_seed,
            metrics_json=json.dumps(m_info["metrics_bundle"]),
            calibration_json=json.dumps(m_info["calibration_bins"]),
            feature_importance_json=json.dumps(m_info["feature_importance"]),
            hyperparameters_json=json.dumps(m_info["hyperparameters"]),
            unseen_supplier_metrics_json=json.dumps(m_info["unseen_supplier_metrics"]),
            segment_analysis_json=json.dumps(m_info["segment_analysis"]),
            selection_rationale=rationale,
            artifact_path=m_info["artifact_path"],
            artifact_sha256=m_info["artifact_sha256"],
        )
        db.add(reg)
        registry_rows.append(reg)

    db.commit()

    return {
        "champion_model_version": champion_version,
        "champion_algorithm": trained_models_info[0]["algorithm_name"],
        "models_evaluated": len(trained_models_info),
        "splits": {
            "train_rows": len(df_train),
            "val_rows": len(df_val),
            "test_rows": len(df_test),
            "train_start": df_train["order_date"].min().isoformat(),
            "train_end": df_train["order_date"].max().isoformat(),
            "val_end": df_val["order_date"].max().isoformat(),
            "test_end": df_test["order_date"].max().isoformat(),
        },
        "models": [
            {
                "model_version": m["model_version"],
                "algorithm_name": m["algorithm_name"],
                "display_name": m["display_name"],
                "is_champion": m["model_version"] == champion_version,
                "composite_score": m["composite_score"],
                "validation_metrics": m["metrics_bundle"]["validation"],
                "test_metrics": m["metrics_bundle"]["test"],
            }
            for m in trained_models_info
        ],
    }


_VERIFIED_ARTIFACT_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def load_verified_model_artifact(db: Session, model_version: str | None = None) -> tuple[ModelRegistry, dict[str, Any]]:
    """Load a registered model artifact only after verifying its SHA-256 cryptographic digest."""
    if model_version:
        reg = db.query(ModelRegistry).filter(ModelRegistry.model_version == model_version).first()
    else:
        reg = (
            db.query(ModelRegistry)
            .filter(ModelRegistry.is_champion.is_(True))
            .order_by(ModelRegistry.id.desc())
            .first()
        )
        if not reg:
            reg = db.query(ModelRegistry).order_by(ModelRegistry.id.desc()).first()

    if not reg or not reg.artifact_path:
        raise RuntimeError("No trained model artifact found in ModelRegistry. Run training first.")

    resolved_path = resolve_artifact_path(reg.artifact_path)
    # Security check: ensure artifact path resides strictly inside settings.artifacts_dir
    allowed_dir = settings.artifacts_dir.resolve()
    if resolved_path is None or not str(resolved_path).startswith(str(allowed_dir)):
        raise SecurityError(
            f"Refusing to load model outside trusted artifacts directory: {reg.artifact_path}"
        )

    if not resolved_path.exists():
        raise RuntimeError(f"Model artifact file missing on disk: {resolved_path}")

    actual_sha = _compute_file_sha256(resolved_path)
    if reg.artifact_sha256 and actual_sha != reg.artifact_sha256:
        raise SecurityError(
            f"Artifact integrity check failed for {reg.model_version}: expected SHA-256 {reg.artifact_sha256}, got {actual_sha}"
        )

    cache_key = (str(resolved_path), actual_sha)
    if cache_key not in _VERIFIED_ARTIFACT_CACHE:
        _VERIFIED_ARTIFACT_CACHE[cache_key] = joblib.load(resolved_path)
    bundle = _VERIFIED_ARTIFACT_CACHE[cache_key]
    return reg, bundle


class SecurityError(Exception):
    """Raised when model artifact integrity or path safety check fails."""


def get_business_rules(db: Session) -> dict[str, Any]:
    """Retrieve active configurable thresholds and prioritization weights."""
    row = (
        db.query(SystemRuleConfig)
        .filter(SystemRuleConfig.config_key == "prioritization_rules")
        .first()
    )
    if row:
        try:
            return json.loads(row.config_value_json)
        except Exception:
            pass
    return {
        "moderate_risk_threshold": settings.moderate_risk_threshold,
        "high_risk_threshold": settings.high_risk_threshold,
        "critical_risk_threshold": settings.critical_risk_threshold,
        "reviewer_capacity": settings.default_reviewer_capacity,
        "weight_ml_probability": 0.45,
        "weight_financial_impact": 0.25,
        "weight_urgency": 0.15,
        "weight_criticality": 0.15,
    }


def predict_order_risk(
    db: Session,
    po: PurchaseOrder,
    as_of_date: date | None = None,
    model_version: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Generate a calibrated, explainable point-in-time risk prediction for a PurchaseOrder."""
    reg, bundle = load_verified_model_artifact(db, model_version=model_version)
    rules = get_business_rules(db)

    ref_as_of = as_of_date or date.fromisoformat(settings.reference_date)
    # For historical completed orders inspected retroactively, evaluate as of their order_date
    if po.status in ("delivered", "cancelled") and as_of_date is None:
        ref_as_of = po.order_date

    supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
    product = db.query(Product).filter(Product.id == po.product_id).first()
    if not supplier or not product:
        raise ValueError(f"Missing supplier or product record for PO {po.po_number}")

    sup_orders_orm = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.supplier_id == supplier.id)
        .all()
    )
    prior_orders = [
        {
            "id": o.id,
            "order_date": o.order_date,
            "actual_delivery_date": o.actual_delivery_date,
            "is_delayed": o.is_delayed,
            "delay_days": o.delay_days,
            "quantity": o.quantity,
            "status": o.status,
        }
        for o in sup_orders_orm
    ]

    target_dict = {
        "id": po.id,
        "po_number": po.po_number,
        "order_date": po.order_date,
        "promised_delivery_date": po.promised_delivery_date,
        "promised_lead_time_days": po.promised_lead_time_days,
        "quantity": po.quantity,
        "unit_price": po.unit_price,
        "total_value": po.total_value,
        "shipping_mode": po.shipping_mode,
        "urgency_level": po.urgency_level,
    }
    sup_dict = {
        "id": supplier.id,
        "supplier_code": supplier.supplier_code,
        "name": supplier.name,
        "region": supplier.region,
        "primary_category": supplier.primary_category,
        "tier": supplier.tier,
        "capacity_index": supplier.capacity_index,
        "financial_health_score": supplier.financial_health_score,
        "geopolitical_risk_index": supplier.geopolitical_risk_index,
    }
    prod_dict = {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "category": product.category,
        "unit_cost": product.unit_cost,
        "criticality_score": product.criticality_score,
        "standard_lead_time_days": product.standard_lead_time_days,
    }

    pit = compute_point_in_time_features_for_order(
        target_order=target_dict,
        supplier=sup_dict,
        product=prod_dict,
        prior_supplier_orders=prior_orders,
        as_of_date=ref_as_of,
    )
    features = pit["features"]
    hist_ctx = pit["historical_context"]

    df_single = pd.DataFrame([{k: features[k] for k in ALL_MODEL_FEATURES}])
    X_trans = bundle["preprocessor"].transform(df_single)
    raw_prob = float(bundle["base_estimator"].predict_proba(X_trans)[0, 1])
    cal_prob = float(bundle["calibrated_model"].predict_proba(df_single)[0, 1])

    # Cold-start adjustment: blend with conservative prior if 0 prior orders
    if int(features["supplier_prior_order_count"]) == 0:
        cal_prob = round(0.65 * cal_prob + 0.35 * 0.45, 4)

    # Classify into risk category using configurable thresholds
    mod_t = float(rules.get("moderate_risk_threshold", 0.35))
    high_t = float(rules.get("high_risk_threshold", 0.60))
    crit_t = float(rules.get("critical_risk_threshold", 0.80))

    if cal_prob >= crit_t:
        risk_cat = "critical"
    elif cal_prob >= high_t:
        risk_cat = "high"
    elif cal_prob >= mod_t:
        risk_cat = "moderate"
    else:
        risk_cat = "low"

    # Expected delay days conditional on delay risk and supplier volatility
    trailing_delay = max(1.5, float(features["supplier_trailing_90d_delay_avg"]))
    vol = max(1.5, float(features["supplier_prior_delay_std"]))
    expected_delay_days = round(cal_prob * (trailing_delay + 0.85 * vol), 1)

    # Expected operational financial impact (expediting + line-stoppage risk exposure)
    # Bounded realistically as a fraction of order value + criticality multiplier
    impact_rate = 0.08 + 0.18 * float(product.criticality_score)
    expected_fin_impact = round(cal_prob * po.total_value * impact_rate, 2)

    # Compute transparent Business Priority Score (0 to 100 scale)
    norm_fin_impact = min(1.0, math.log1p(po.total_value) / math.log1p(500_000.0))
    urgency_score = float(features["urgency_numeric"])
    crit_score = float(product.criticality_score)

    w_prob = float(rules.get("weight_ml_probability", 0.45))
    w_fin = float(rules.get("weight_financial_impact", 0.25))
    w_urg = float(rules.get("weight_urgency", 0.15))
    w_crit = float(rules.get("weight_criticality", 0.15))
    total_w = max(0.01, w_prob + w_fin + w_urg + w_crit)

    priority_score = round(
        100.0
        * (
            w_prob * cal_prob
            + w_fin * norm_fin_impact
            + w_urg * urgency_score
            + w_crit * crit_score
        )
        / total_w,
        1,
    )

    reliability_status, reliability_warnings = evaluate_prediction_reliability(
        features=features,
        historical_context=hist_ctx,
        training_stats=bundle.get("training_stats", {}),
        model_created_at=reg.created_at,
    )

    contributors, explanation_method = compute_local_feature_contributions(
        artifact_bundle=bundle,
        features=features,
        top_k=6,
    )

    pred_record_id = 0
    predicted_at_dt = datetime.now(timezone.utc)

    if persist:
        # Remove older prediction for the same PO if re-scoring open orders
        existing = (
            db.query(RiskPrediction)
            .filter(RiskPrediction.po_id == po.id)
            .first()
        )
        if existing:
            existing.model_version = reg.model_version
            existing.algorithm_name = reg.algorithm_name
            existing.predicted_at = predicted_at_dt
            existing.as_of_date = ref_as_of
            existing.raw_probability = round(raw_prob, 4)
            existing.calibrated_probability = round(cal_prob, 4)
            existing.risk_category = risk_cat
            existing.threshold_used = high_t
            existing.expected_delay_days = expected_delay_days
            existing.expected_financial_impact = expected_fin_impact
            existing.business_priority_score = priority_score
            existing.reliability_status = reliability_status
            existing.reliability_warnings_json = json.dumps(reliability_warnings)
            existing.top_contributors_json = json.dumps(contributors)
            existing.historical_context_json = json.dumps(hist_ctx)
            existing.feature_snapshot_json = json.dumps(features)
            existing.explanation_method = explanation_method
            db.commit()
            db.refresh(existing)
            pred_record_id = existing.id
        else:
            new_pred = RiskPrediction(
                po_id=po.id,
                model_version=reg.model_version,
                algorithm_name=reg.algorithm_name,
                predicted_at=predicted_at_dt,
                as_of_date=ref_as_of,
                raw_probability=round(raw_prob, 4),
                calibrated_probability=round(cal_prob, 4),
                risk_category=risk_cat,
                threshold_used=high_t,
                expected_delay_days=expected_delay_days,
                expected_financial_impact=expected_fin_impact,
                business_priority_score=priority_score,
                reliability_status=reliability_status,
                reliability_warnings_json=json.dumps(reliability_warnings),
                top_contributors_json=json.dumps(contributors),
                historical_context_json=json.dumps(hist_ctx),
                feature_snapshot_json=json.dumps(features),
                explanation_method=explanation_method,
            )
            db.add(new_pred)
            db.commit()
            db.refresh(new_pred)
            pred_record_id = new_pred.id

    return {
        "id": pred_record_id,
        "po_id": po.id,
        "po_number": po.po_number,
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "product_name": product.name,
        "product_category": product.category,
        "order_date": po.order_date,
        "promised_delivery_date": po.promised_delivery_date,
        "order_value": po.total_value,
        "urgency_level": po.urgency_level,
        "model_version": reg.model_version,
        "algorithm_name": reg.algorithm_name,
        "predicted_at": predicted_at_dt,
        "as_of_date": ref_as_of,
        "raw_probability": round(raw_prob, 4),
        "calibrated_probability": round(cal_prob, 4),
        "risk_category": risk_cat,
        "threshold_used": high_t,
        "expected_delay_days": expected_delay_days,
        "expected_financial_impact": expected_fin_impact,
        "business_priority_score": priority_score,
        "reliability_status": reliability_status,
        "reliability_warnings": reliability_warnings,
        "top_contributors": contributors,
        "historical_context": hist_ctx,
        "feature_snapshot": features,
        "explanation_method": explanation_method,
        "explanation_limitations": (
            "Feature contributions reflect associative statistical patterns learned from historical "
            "orders prior to the prediction date. They do not establish causal effects and should "
            "be combined with supplier communication before purchasing action."
        ),
    }
