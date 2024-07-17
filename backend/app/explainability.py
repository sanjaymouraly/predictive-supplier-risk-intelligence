"""Explainability (SHAP / additive feature attributions) and Reliability Intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.feature_engineering import (
    ALL_MODEL_FEATURES,
    CATEGORICAL_FEATURES,
    FEATURE_DISPLAY_NAMES,
    NUMERIC_FEATURES,
)


def evaluate_prediction_reliability(
    features: dict[str, Any],
    historical_context: dict[str, Any],
    training_stats: dict[str, Any],
    model_created_at: datetime | None = None,
) -> tuple[str, list[str]]:
    """Run explicit uncertainty, out-of-distribution (OOD), and cold-start reliability checks.

    Returns:
        (reliability_status, list_of_warnings)
        where reliability_status is one of:
        - "reliable"
        - "caution_manual_review"
        - "unreliable_cold_start"
    """
    warnings: list[str] = []
    prior_count = int(features.get("supplier_prior_order_count", 0))

    # 1. Cold-start / sparse supplier history check
    if prior_count == 0:
        warnings.append(
            "Insufficient supplier history — manual review recommended (Cold-start supplier with 0 prior completed orders; Bayesian prior fallback applied)."
        )
    elif prior_count < 5:
        warnings.append(
            f"Insufficient supplier history — manual review recommended (Only {prior_count} prior completed orders recorded)."
        )

    # 2. Out-of-distribution (OOD) numeric checks against training distribution
    qty_ratio = float(features.get("quantity_vs_supplier_avg_ratio", 1.0))
    if qty_ratio > 3.0:
        warnings.append(
            f"Out-of-distribution order volume: quantity is {qty_ratio:.1f}x the supplier's historical average."
        )

    lead_ratio = float(features.get("lead_time_compression_ratio", 1.0))
    if lead_ratio < 0.65:
        warnings.append(
            f"Extreme lead-time compression: promised lead time is {int(lead_ratio * 100)}% of standard product lead time."
        )
    elif lead_ratio > 2.2:
        warnings.append(
            f"Unusually long lead-time horizon ({int(features.get('promised_lead_time_days', 0))} days) outside typical training range."
        )

    # 3. High supplier lead-time volatility / poorly calibrated segment check
    delay_std = float(features.get("supplier_prior_delay_std", 0.0))
    if delay_std > 6.5 and prior_count >= 5:
        warnings.append(
            f"High historical delivery volatility (σ = {delay_std:.1f} days) — point estimates carry elevated variance."
        )

    # 4. Unseen categorical value check
    known_cats = training_stats.get("known_categories", {})
    for cat_col in CATEGORICAL_FEATURES:
        val = str(features.get(cat_col, ""))
        allowed = known_cats.get(cat_col)
        if allowed and val not in allowed:
            warnings.append(
                f"Unseen categorical value '{val}' in '{cat_col}' not present during training."
            )

    # 5. Model freshness check
    if model_created_at is not None:
        now = datetime.now(timezone.utc)
        created_utc = (
            model_created_at
            if model_created_at.tzinfo is not None
            else model_created_at.replace(tzinfo=timezone.utc)
        )
        age_days = (now - created_utc).days
        if age_days > 90:
            warnings.append(
                f"Stale model artifact: trained {age_days} days ago (> 90 day threshold)."
            )

    if prior_count == 0:
        status = "unreliable_cold_start"
    elif warnings:
        status = "caution_manual_review"
    else:
        status = "reliable"

    return status, warnings


_TREE_EXPLAINER_CACHE: dict[str, Any] = {}


def compute_local_feature_contributions(
    artifact_bundle: dict[str, Any],
    features: dict[str, Any],
    top_k: int = 6,
) -> tuple[list[dict[str, Any]], str]:
    """Compute local feature attributions for a single prediction using SHAP or exact model attribution.

    Always phrases explanations as associative model contributions, never causal claims.
    """
    preprocessor = artifact_bundle["preprocessor"]
    base_estimator = artifact_bundle["base_estimator"]
    training_stats = artifact_bundle.get("training_stats", {})
    feature_means = training_stats.get("numeric_means", {})
    feature_stds = training_stats.get("numeric_stds", {})

    df_single = pd.DataFrame([{k: features[k] for k in ALL_MODEL_FEATURES}])
    X_trans = preprocessor.transform(df_single)
    if hasattr(X_trans, "toarray"):
        X_trans = X_trans.toarray()

    feature_names_out = list(preprocessor.get_feature_names_out())
    raw_contribs: dict[str, float] = {f: 0.0 for f in ALL_MODEL_FEATURES}
    method_used = "SHAP Additive Feature Attribution"

    try:
        import shap

        algo = artifact_bundle.get("algorithm_name", "")
        ver = artifact_bundle.get("model_version", algo)
        if algo in ("random_forest", "hist_gradient_boosting"):
            if ver not in _TREE_EXPLAINER_CACHE:
                _TREE_EXPLAINER_CACHE[ver] = shap.TreeExplainer(base_estimator)
            explainer = _TREE_EXPLAINER_CACHE[ver]
            shap_vals = explainer.shap_values(X_trans)
            if isinstance(shap_vals, list):
                sv = np.asarray(shap_vals[1])[0]
            elif getattr(shap_vals, "ndim", 0) == 3:
                sv = np.asarray(shap_vals)[0, :, 1]
            else:
                sv = np.asarray(shap_vals)[0]
        else:
            # Linear model exact log-odds contribution relative to standardized mean (0)
            coefs = base_estimator.coef_[0]
            sv = X_trans[0] * coefs
            method_used = "SHAP Linear Log-Odds Attribution"

        # Aggregate transformed one-hot / scaled columns back to original domain features
        for idx, trans_name in enumerate(feature_names_out):
            val = float(sv[idx])
            clean_name = trans_name.split("__", 1)[-1] if "__" in trans_name else trans_name
            matched_orig = None
            for orig_f in ALL_MODEL_FEATURES:
                if clean_name == orig_f or clean_name.startswith(orig_f + "_"):
                    matched_orig = orig_f
                    break
            if matched_orig:
                raw_contribs[matched_orig] += val
    except Exception:
        # Deterministic perturbation attribution fallback if SHAP tree explainer encounters version edge case
        method_used = "Calibrated Marginal Perturbation Attribution"
        base_prob = float(artifact_bundle["calibrated_model"].predict_proba(df_single)[0, 1])
        for orig_f in ALL_MODEL_FEATURES:
            perturbed = dict(features)
            if orig_f in NUMERIC_FEATURES:
                perturbed[orig_f] = float(feature_means.get(orig_f, features[orig_f]))
            else:
                perturbed[orig_f] = training_stats.get("categorical_modes", {}).get(
                    orig_f, features[orig_f]
                )
            df_p = pd.DataFrame([{k: perturbed[k] for k in ALL_MODEL_FEATURES}])
            p_prob = float(artifact_bundle["calibrated_model"].predict_proba(df_p)[0, 1])
            raw_contribs[orig_f] = base_prob - p_prob

    # Format top K contributors with human-readable explanations
    sorted_feats = sorted(
        raw_contribs.items(), key=lambda item: abs(item[1]), reverse=True
    )[:top_k]

    contributors: list[dict[str, Any]] = []
    for fname, score in sorted_feats:
        fval = features.get(fname)
        direction = "increases_risk" if score >= 0 else "decreases_risk"
        display_label = FEATURE_DISPLAY_NAMES.get(fname, fname)
        explanation = _build_human_explanation(
            fname, fval, score, features, feature_means, feature_stds
        )
        contributors.append(
            {
                "feature_name": fname,
                "display_label": display_label,
                "feature_value": _format_feature_value(fname, fval),
                "contribution_score": round(float(score), 4),
                "direction": direction,
                "human_explanation": explanation,
            }
        )

    return contributors, method_used


def _format_feature_value(fname: str, fval: Any) -> Any:
    if isinstance(fval, float):
        if "rate" in fname or "ratio" in fname or "utilization" in fname:
            return round(fval, 3)
        return round(fval, 2)
    return fval


def _build_human_explanation(
    fname: str,
    fval: Any,
    score: float,
    features: dict[str, Any],
    means: dict[str, float],
    stds: dict[str, float],
) -> str:
    verb = "elevates predicted delay risk" if score >= 0 else "reduces predicted delay risk"
    if fname == "supplier_prior_otd_rate_smoothed":
        pct = float(fval) * 100.0
        cnt = int(features.get("supplier_prior_order_count", 0))
        return f"Supplier historical on-time rate of {pct:.1f}% across {cnt} prior completed orders {verb}."
    if fname == "lead_time_compression_ratio":
        prom = int(features.get("promised_lead_time_days", 0))
        std = int(features.get("standard_lead_time_days", 0))
        return f"Promised lead time ({prom}d) is {float(fval):.2f}x the standard product lead time ({std}d), which {verb}."
    if fname == "supplier_trailing_90d_delay_avg":
        return f"Trailing 90-day average arrival offset of {float(fval):+.1f} days {verb}."
    if fname == "supplier_capacity_utilization":
        active = int(features.get("supplier_active_open_orders", 0))
        return f"Estimated supplier capacity utilization of {float(fval)*100:.0f}% ({active} concurrent active orders) {verb}."
    if fname == "quantity_vs_supplier_avg_ratio":
        return f"Order quantity is {float(fval):.2f}x the supplier's typical historical batch size, which {verb}."
    if fname == "supplier_financial_health":
        return f"Supplier financial health index ({float(fval):.1f}/100) {verb}."
    if fname == "shipping_mode":
        return f"Selected transit mode '{fval}' is associated with historical transit variance that {verb}."
    if fname == "is_q4_peak":
        season = "Q4 peak freight season" if float(fval) > 0.5 else "non-peak freight window"
        return f"Order placement during {season} {verb} based on historical seasonal patterns."
    return f"{FEATURE_DISPLAY_NAMES.get(fname, fname)} value ({_format_feature_value(fname, fval)}) {verb} (associative model contribution {score:+.3f})."
