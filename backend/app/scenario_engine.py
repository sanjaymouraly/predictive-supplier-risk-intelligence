"""What-If Scenario Analysis Engine with explicit non-causal model caveats."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.explainability import (
    compute_local_feature_contributions,
    evaluate_prediction_reliability,
)
from app.feature_engineering import (
    ALL_MODEL_FEATURES,
    compute_point_in_time_features_for_order,
)
from app.ml_pipeline import (
    get_business_rules,
    load_verified_model_artifact,
    predict_order_risk,
)
from app.models import Product, PurchaseOrder, Supplier


def run_scenario_simulation(
    db: Session,
    po_id: int | None,
    supplier_id: int,
    product_id: int,
    quantity: int,
    promised_lead_time_days: int,
    shipping_mode: str = "Ocean Freight",
    urgency_level: str = "standard",
    order_date: date | None = None,
) -> dict[str, Any]:
    """Simulate a hypothetical procurement configuration and compare against baseline PO if provided."""
    reg, bundle = load_verified_model_artifact(db)
    rules = get_business_rules(db)
    ref_as_of = date.fromisoformat(settings.reference_date)

    baseline_result = None
    if po_id is not None:
        base_po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if base_po:
            baseline_result = predict_order_risk(
                db=db, po=base_po, as_of_date=ref_as_of, persist=False
            )

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    product = db.query(Product).filter(Product.id == product_id).first()
    if not supplier or not product:
        raise ValueError("Invalid supplier_id or product_id for scenario simulation")

    sim_order_date = order_date or ref_as_of
    sim_promised_date = sim_order_date + timedelta(days=promised_lead_time_days)
    unit_price = product.unit_cost
    total_value = round(quantity * unit_price, 2)

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
        "id": -1,
        "po_number": "SCENARIO-SIM",
        "order_date": sim_order_date,
        "promised_delivery_date": sim_promised_date,
        "promised_lead_time_days": promised_lead_time_days,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_value": total_value,
        "shipping_mode": shipping_mode,
        "urgency_level": urgency_level,
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
    cal_prob = float(bundle["calibrated_model"].predict_proba(df_single)[0, 1])
    if int(features["supplier_prior_order_count"]) == 0:
        cal_prob = round(0.65 * cal_prob + 0.35 * 0.45, 4)

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

    trailing_delay = max(1.5, float(features["supplier_trailing_90d_delay_avg"]))
    vol = max(1.5, float(features["supplier_prior_delay_std"]))
    expected_delay_days = round(cal_prob * (trailing_delay + 0.85 * vol), 1)
    impact_rate = 0.08 + 0.18 * float(product.criticality_score)
    expected_fin_impact = round(cal_prob * total_value * impact_rate, 2)

    norm_fin_impact = min(1.0, math.log1p(total_value) / math.log1p(500_000.0))
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

    scenario_result = {
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "supplier_region": supplier.region,
        "product_id": product.id,
        "product_name": product.name,
        "quantity": quantity,
        "promised_lead_time_days": promised_lead_time_days,
        "shipping_mode": shipping_mode,
        "urgency_level": urgency_level,
        "order_value": total_value,
        "calibrated_probability": round(cal_prob, 4),
        "risk_category": risk_cat,
        "expected_delay_days": expected_delay_days,
        "expected_financial_impact": expected_fin_impact,
        "business_priority_score": priority_score,
        "reliability_status": reliability_status,
        "reliability_warnings": reliability_warnings,
        "top_contributors": contributors,
        "historical_context": hist_ctx,
        "feature_snapshot": features,
        "explanation_method": explanation_method,
    }

    deltas = None
    if baseline_result is not None:
        prob_delta = round(
            scenario_result["calibrated_probability"]
            - baseline_result["calibrated_probability"],
            4,
        )
        delay_delta = round(
            scenario_result["expected_delay_days"]
            - baseline_result["expected_delay_days"],
            1,
        )
        impact_delta = round(
            scenario_result["expected_financial_impact"]
            - baseline_result["expected_financial_impact"],
            2,
        )
        deltas = {
            "probability_delta": prob_delta,
            "probability_delta_pct_points": round(prob_delta * 100.0, 2),
            "expected_delay_days_delta": delay_delta,
            "expected_financial_impact_delta": impact_delta,
            "risk_reduced": prob_delta < -0.005,
        }

    # Also evaluate top 3 alternative suppliers in the same product category for comparison
    alt_suppliers = (
        db.query(Supplier)
        .filter(
            Supplier.primary_category == product.category,
            Supplier.id != supplier.id,
            Supplier.status == "active",
        )
        .limit(4)
        .all()
    )
    alternatives: list[dict[str, Any]] = []
    for alt_sup in alt_suppliers:
        alt_orders_orm = (
            db.query(PurchaseOrder)
            .filter(PurchaseOrder.supplier_id == alt_sup.id)
            .all()
        )
        alt_prior = [
            {
                "id": o.id,
                "order_date": o.order_date,
                "actual_delivery_date": o.actual_delivery_date,
                "is_delayed": o.is_delayed,
                "delay_days": o.delay_days,
                "quantity": o.quantity,
                "status": o.status,
            }
            for o in alt_orders_orm
        ]
        alt_sup_dict = {
            "id": alt_sup.id,
            "supplier_code": alt_sup.supplier_code,
            "name": alt_sup.name,
            "region": alt_sup.region,
            "primary_category": alt_sup.primary_category,
            "tier": alt_sup.tier,
            "capacity_index": alt_sup.capacity_index,
            "financial_health_score": alt_sup.financial_health_score,
            "geopolitical_risk_index": alt_sup.geopolitical_risk_index,
        }
        alt_pit = compute_point_in_time_features_for_order(
            target_order=target_dict,
            supplier=alt_sup_dict,
            product=prod_dict,
            prior_supplier_orders=alt_prior,
            as_of_date=ref_as_of,
        )
        alt_df = pd.DataFrame([{k: alt_pit["features"][k] for k in ALL_MODEL_FEATURES}])
        alt_prob = float(bundle["calibrated_model"].predict_proba(alt_df)[0, 1])
        alternatives.append(
            {
                "supplier_id": alt_sup.id,
                "supplier_code": alt_sup.supplier_code,
                "supplier_name": alt_sup.name,
                "region": alt_sup.region,
                "tier": alt_sup.tier,
                "projected_delay_probability": round(alt_prob, 4),
                "historical_otd_rate": alt_pit["historical_context"]["supplier_raw_otd_rate_prior"],
                "prior_completed_orders": alt_pit["historical_context"]["supplier_completed_orders_prior"],
            }
        )
    alternatives.sort(key=lambda x: x["projected_delay_probability"])

    return {
        "model_version": reg.model_version,
        "algorithm_name": reg.algorithm_name,
        "baseline": baseline_result,
        "scenario": scenario_result,
        "deltas": deltas,
        "alternative_suppliers": alternatives[:3],
        "methodology_disclaimer": (
            "NON-CAUSAL SCENARIO PROJECTION: This simulation evaluates how the trained predictive "
            "model responds to modified input features based on historical observational correlations. "
            "It is NOT a proven causal counterfactual. Changing lead times, quantities, or suppliers in "
            "real-world operations requires verifying supplier contractual capacity, tooling readiness, "
            "and logistics availability."
        ),
    }
