"""Point-in-time (as-of) feature engineering engine preventing future data leakage."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models import Product, PurchaseOrder, Supplier

# Strictly forbidden outcome columns that must NEVER appear in model input features
FORBIDDEN_LEAKAGE_COLUMNS = {
    "actual_delivery_date",
    "actual_lead_time_days",
    "delay_days",
    "is_delayed",
    "final_status",
}

NUMERIC_FEATURES = [
    "promised_lead_time_days",
    "standard_lead_time_days",
    "lead_time_compression_ratio",
    "order_quantity_log",
    "order_value_log",
    "quantity_vs_supplier_avg_ratio",
    "supplier_prior_order_count",
    "supplier_prior_otd_rate_smoothed",
    "supplier_trailing_90d_delay_avg",
    "supplier_prior_delay_std",
    "supplier_active_open_orders",
    "supplier_capacity_utilization",
    "supplier_financial_health",
    "supplier_geopolitical_risk",
    "product_criticality_score",
    "urgency_numeric",
    "order_month_sin",
    "order_month_cos",
    "is_q4_peak",
]

CATEGORICAL_FEATURES = [
    "product_category",
    "supplier_region",
    "shipping_mode",
    "supplier_tier",
]

ALL_MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

FEATURE_DISPLAY_NAMES = {
    "promised_lead_time_days": "Promised Lead Time (Days)",
    "standard_lead_time_days": "Product Standard Lead Time (Days)",
    "lead_time_compression_ratio": "Lead Time vs Standard Ratio",
    "order_quantity_log": "Order Quantity (Log Scale)",
    "order_value_log": "Total Order Value (Log USD)",
    "quantity_vs_supplier_avg_ratio": "Order Volume vs Supplier Typical Size",
    "supplier_prior_order_count": "Supplier Completed Order History Count",
    "supplier_prior_otd_rate_smoothed": "Supplier Historical On-Time Rate",
    "supplier_trailing_90d_delay_avg": "Supplier 90-Day Trailing Avg Delay (Days)",
    "supplier_prior_delay_std": "Supplier Historical Lead-Time Volatility (Days)",
    "supplier_active_open_orders": "Supplier Concurrent Active Orders",
    "supplier_capacity_utilization": "Supplier Estimated Capacity Utilization",
    "supplier_financial_health": "Supplier Financial Health Score",
    "supplier_geopolitical_risk": "Regional Geopolitical Risk Index",
    "product_criticality_score": "Component Criticality Score",
    "urgency_numeric": "Order Urgency Level",
    "order_month_sin": "Seasonal Cycle (Sine)",
    "order_month_cos": "Seasonal Cycle (Cosine)",
    "is_q4_peak": "Q4 Peak Freight Season",
    "product_category": "Product Category",
    "supplier_region": "Supplier Region",
    "shipping_mode": "Shipping Mode",
    "supplier_tier": "Supplier Tier",
}

URGENCY_MAP = {
    "low": 0.2,
    "standard": 0.5,
    "high": 0.8,
    "critical": 1.0,
}


def compute_point_in_time_features_for_order(
    target_order: dict[str, Any],
    supplier: dict[str, Any],
    product: dict[str, Any],
    prior_supplier_orders: list[dict[str, Any]],
    as_of_date: date,
    global_prior_otd: float = 0.76,
     global_prior_delay: float = 1.2,
) -> dict[str, Any]:
    """Compute point-in-time features for a single order strictly as of `as_of_date`.

    CRITICAL PREDICTION-TIME CORRECTNESS GUARANTEE:
    1. Only orders placed on or before `as_of_date` (`order_date <= as_of_date`) are visible.
    2. Delivery outcomes (`is_delayed`, `delay_days`, `actual_delivery_date`) of a prior order
       are ONLY used if `actual_delivery_date < as_of_date` and `status == 'delivered'`.
    3. Any order placed on or before `as_of_date` that was still in flight at `as_of_date`
       (`actual_delivery_date is None` or `actual_delivery_date >= as_of_date`) is treated
       purely as an active open order (congestion signal), never leaking its future outcome.
    """
    # Filter strictly completed orders where outcome was known BEFORE as_of_date
    completed_prior: list[dict[str, Any]] = []
    active_at_as_of = 0

    for po in prior_supplier_orders:
        po_id = po.get("id")
        if po_id is not None and po_id == target_order.get("id"):
            continue
        ord_d: Optional[date] = po.get("order_date")
        if ord_d is None or ord_d > as_of_date:
            # Future order placed after as_of_date — invisible!
            continue

        act_d: Optional[date] = po.get("actual_delivery_date")
        st = po.get("status", "open")

        if st == "delivered" and act_d is not None and act_d < as_of_date:
            completed_prior.append(po)
        elif st in ("open", "in_transit") or (act_d is not None and act_d >= as_of_date):
            # Order was placed on or before as_of_date and had not arrived by as_of_date
            if st != "cancelled":
                active_at_as_of += 1

    prior_count = len(completed_prior)

    # Bayesian-smoothed historical On-Time Delivery (OTD) rate (m-estimate with m=5)
    m_prior = 5.0
    if prior_count > 0:
        on_time_count = sum(1 for p in completed_prior if not bool(p.get("is_delayed")))
        raw_otd_rate = on_time_count / prior_count
        smoothed_otd = (on_time_count + m_prior * global_prior_otd) / (prior_count + m_prior)
        delays = [float(p.get("delay_days") or 0.0) for p in completed_prior]
        delay_std = float(np.std(delays)) if len(delays) >= 2 else 3.0
        avg_delay_all = float(np.mean(delays))
        avg_qty = float(np.mean([float(p.get("quantity") or 250.0) for p in completed_prior]))
    else:
        raw_otd_rate = global_prior_otd
        smoothed_otd = global_prior_otd
        delay_std = 3.5
        avg_delay_all = global_prior_delay
        avg_qty = 450.0 * float(supplier.get("capacity_index") or 1.0)

    # Trailing 90-day delay average based on actual_delivery_date within [as_of_date - 90d, as_of_date)
    window_90d_start = as_of_date - timedelta(days=90)
    recent_90d = [
        float(p.get("delay_days") or 0.0)
        for p in completed_prior
        if p.get("actual_delivery_date") and p["actual_delivery_date"] >= window_90d_start
    ]
    trailing_90d_delay = float(np.mean(recent_90d)) if recent_90d else avg_delay_all

    # Trailing 30-day OTD rate for historical context
    window_30d_start = as_of_date - timedelta(days=30)
    recent_30d = [
        p
        for p in completed_prior
        if p.get("actual_delivery_date") and p["actual_delivery_date"] >= window_30d_start
    ]
    trailing_30d_otd = (
        sum(1 for p in recent_30d if not bool(p.get("is_delayed"))) / len(recent_30d)
        if recent_30d
        else raw_otd_rate
    )

    promised_lead = max(1, int(target_order.get("promised_lead_time_days") or 21))
    std_lead = max(1, int(product.get("standard_lead_time_days") or 21))
    lead_compression_ratio = round(promised_lead / float(std_lead), 4)

    qty = max(1, int(target_order.get("quantity") or 100))
    unit_price = max(0.01, float(target_order.get("unit_price") or product.get("unit_cost") or 100.0))
    total_val = float(target_order.get("total_value") or (qty * unit_price))

    qty_vs_avg = round(qty / max(10.0, avg_qty), 4)
    cap_index = max(0.1, float(supplier.get("capacity_index") or 1.0))
    cap_utilization = round((active_at_as_of + 1) / (cap_index * 6.0), 4)

    ord_date: date = target_order.get("order_date") or as_of_date
    month = ord_date.month
    month_sin = round(math.sin(2.0 * math.pi * month / 12.0), 4)
    month_cos = round(math.cos(2.0 * math.pi * month / 12.0), 4)
    is_q4 = 1.0 if month in (10, 11, 12) else 0.0

    urgency_str = str(target_order.get("urgency_level") or "standard").lower()
    urgency_num = URGENCY_MAP.get(urgency_str, 0.5)

    features = {
        "promised_lead_time_days": float(promised_lead),
        "standard_lead_time_days": float(std_lead),
        "lead_time_compression_ratio": float(lead_compression_ratio),
        "order_quantity_log": round(math.log1p(qty), 4),
        "order_value_log": round(math.log1p(total_val), 4),
        "quantity_vs_supplier_avg_ratio": float(qty_vs_avg),
        "supplier_prior_order_count": float(prior_count),
        "supplier_prior_otd_rate_smoothed": round(float(smoothed_otd), 4),
        "supplier_trailing_90d_delay_avg": round(float(trailing_90d_delay), 4),
        "supplier_prior_delay_std": round(float(delay_std), 4),
        "supplier_active_open_orders": float(active_at_as_of),
        "supplier_capacity_utilization": float(cap_utilization),
        "supplier_financial_health": float(supplier.get("financial_health_score") or 75.0),
        "supplier_geopolitical_risk": float(supplier.get("geopolitical_risk_index") or 0.25),
        "product_criticality_score": float(product.get("criticality_score") or 0.5),
        "urgency_numeric": float(urgency_num),
        "order_month_sin": float(month_sin),
        "order_month_cos": float(month_cos),
        "is_q4_peak": float(is_q4),
        "product_category": str(product.get("category") or supplier.get("primary_category") or "General"),
        "supplier_region": str(supplier.get("region") or "Global"),
        "shipping_mode": str(target_order.get("shipping_mode") or "Ocean Freight"),
        "supplier_tier": str(supplier.get("tier") or "Tier 1"),
    }

    # Explicit assertion that no forbidden outcome column leaked into features
    leaked = FORBIDDEN_LEAKAGE_COLUMNS.intersection(features.keys())
    if leaked:
        raise RuntimeError(f"Data leakage detected! Forbidden columns in features: {leaked}")

    historical_context = {
        "as_of_date": as_of_date.isoformat(),
        "supplier_completed_orders_prior": prior_count,
        "supplier_raw_otd_rate_prior": round(float(raw_otd_rate), 4) if prior_count > 0 else None,
        "supplier_smoothed_otd_rate": round(float(smoothed_otd), 4),
        "supplier_trailing_30d_otd_rate": round(float(trailing_30d_otd), 4) if recent_30d else None,
        "supplier_trailing_90d_delay_days": round(float(trailing_90d_delay), 2),
        "supplier_delay_volatility_days": round(float(delay_std), 2),
        "supplier_active_open_orders_at_prediction": active_at_as_of,
        "supplier_typical_order_qty": round(float(avg_qty), 1),
        "is_cold_start_supplier": prior_count < 5,
    }

    return {
        "features": features,
        "historical_context": historical_context,
    }


def build_point_in_time_training_dataframe(
    db: Session,
) -> pd.DataFrame:
    """Build a strictly point-in-time feature dataset for all delivered historical orders.

    For each historical order `i`, `as_of_date = order_i.order_date`, meaning only
    prior orders from that supplier with `actual_delivery_date < order_i.order_date`
    are used to compute historical supplier statistics.
    """
    suppliers = {
        s.id: {
            "id": s.id,
            "supplier_code": s.supplier_code,
            "name": s.name,
            "region": s.region,
            "primary_category": s.primary_category,
            "tier": s.tier,
            "capacity_index": s.capacity_index,
            "financial_health_score": s.financial_health_score,
            "geopolitical_risk_index": s.geopolitical_risk_index,
        }
        for s in db.query(Supplier).all()
    }
    products = {
        p.id: {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "unit_cost": p.unit_cost,
            "criticality_score": p.criticality_score,
            "standard_lead_time_days": p.standard_lead_time_days,
        }
        for p in db.query(Product).all()
    }

    all_orders = (
        db.query(PurchaseOrder)
        .order_by(PurchaseOrder.order_date.asc(), PurchaseOrder.id.asc())
        .all()
    )

    orders_by_supplier: dict[int, list[dict[str, Any]]] = {}
    all_order_dicts: list[dict[str, Any]] = []

    for po in all_orders:
        d = {
            "id": po.id,
            "po_number": po.po_number,
            "supplier_id": po.supplier_id,
            "product_id": po.product_id,
            "order_date": po.order_date,
            "promised_delivery_date": po.promised_delivery_date,
            "actual_delivery_date": po.actual_delivery_date,
            "quantity": po.quantity,
            "unit_price": po.unit_price,
            "total_value": po.total_value,
            "promised_lead_time_days": po.promised_lead_time_days,
            "actual_lead_time_days": po.actual_lead_time_days,
            "delay_days": po.delay_days,
            "is_delayed": po.is_delayed,
            "status": po.status,
            "shipping_mode": po.shipping_mode,
            "urgency_level": po.urgency_level,
        }
        all_order_dicts.append(d)
        orders_by_supplier.setdefault(po.supplier_id, []).append(d)

    rows: list[dict[str, Any]] = []
    for po_dict in all_order_dicts:
        # Only delivered orders have uncensored ground-truth binary delay labels for supervised learning
        if po_dict["status"] != "delivered" or po_dict["is_delayed"] is None:
            continue

        sup_dict = suppliers.get(po_dict["supplier_id"], {})
        prod_dict = products.get(po_dict["product_id"], {})
        sup_orders = orders_by_supplier.get(po_dict["supplier_id"], [])

        pit = compute_point_in_time_features_for_order(
            target_order=po_dict,
            supplier=sup_dict,
            product=prod_dict,
            prior_supplier_orders=sup_orders,
            as_of_date=po_dict["order_date"],
        )

        row = {
            "po_id": po_dict["id"],
            "po_number": po_dict["po_number"],
            "supplier_id": po_dict["supplier_id"],
            "order_date": po_dict["order_date"],
            "promised_delivery_date": po_dict["promised_delivery_date"],
            "target_is_delayed": int(bool(po_dict["is_delayed"])),
            "target_delay_days": float(po_dict["delay_days"] or 0.0),
            **pit["features"],
        }
        rows.append(row)

    return pd.DataFrame(rows)
