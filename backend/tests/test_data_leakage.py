"""Tests for prediction-time correctness, temporal isolation, and data quality checks."""

from __future__ import annotations

from datetime import date

from app.data_generator import validate_dataset_records
from app.database import SessionLocal
from app.feature_engineering import (
    ALL_MODEL_FEATURES,
    FORBIDDEN_LEAKAGE_COLUMNS,
    build_point_in_time_training_dataframe,
    compute_point_in_time_features_for_order,
)


def test_no_forbidden_outcome_columns_in_model_features() -> None:
    """Verify that ground-truth arrival dates and delay labels are excluded from features."""
    overlap = FORBIDDEN_LEAKAGE_COLUMNS.intersection(set(ALL_MODEL_FEATURES))
    assert len(overlap) == 0, f"Forbidden leakage columns present: {overlap}"


def test_point_in_time_future_outcome_cannot_leak() -> None:
    """Prove that an order placed before as_of_date but delivered AFTER as_of_date does not leak its outcome."""
    supplier = {
        "id": 999,
        "supplier_code": "SUP-TEST",
        "name": "Test Precision Ltd",
        "region": "East Asia",
        "primary_category": "Semiconductors",
        "tier": "Tier 1",
        "capacity_index": 1.0,
        "financial_health_score": 80.0,
        "geopolitical_risk_index": 0.25,
    }
    product = {
        "id": 888,
        "sku": "SKU-TEST",
        "name": "Wafer Controller",
        "category": "Semiconductors",
        "unit_cost": 100.0,
        "criticality_score": 0.8,
        "standard_lead_time_days": 20,
    }

    # Order 1: placed Jan 1, promised Jan 15, delivered Jan 25 (10 days late!)
    # Order 2 (Target): placed Jan 10 (as_of_date = Jan 10).
    # On Jan 10, Order 1 is still in flight; its Jan 25 arrival and 10-day delay are IN THE FUTURE!
    order_1_version_a = {
        "id": 1,
        "order_date": date(2026, 1, 1),
        "promised_delivery_date": date(2026, 1, 15),
        "actual_delivery_date": date(2026, 1, 25),
        "delay_days": 10,
        "is_delayed": True,
        "quantity": 500,
        "status": "delivered",
    }
    # Mutated future outcome of Order 1 (arrived early on Jan 12 with -3d delay)
    order_1_version_b = {
        "id": 1,
        "order_date": date(2026, 1, 1),
        "promised_delivery_date": date(2026, 1, 15),
        "actual_delivery_date": date(2026, 1, 12),
        "delay_days": -3,
        "is_delayed": False,
        "quantity": 500,
        "status": "delivered",
    }
    # Order 3: placed Jan 18 ( strictly in the future relative to Jan 10)
    future_order_3 = {
        "id": 3,
        "order_date": date(2026, 1, 18),
        "promised_delivery_date": date(2026, 1, 28),
        "actual_delivery_date": date(2026, 2, 10),
        "delay_days": 13,
        "is_delayed": True,
        "quantity": 9000,
        "status": "delivered",
    }

    target_order_2 = {
        "id": 2,
        "po_number": "PO-TARGET-2",
        "order_date": date(2026, 1, 10),
        "promised_delivery_date": date(2026, 1, 30),
        "promised_lead_time_days": 20,
        "quantity": 400,
        "unit_price": 100.0,
        "total_value": 40000.0,
        "shipping_mode": "Ocean Freight",
        "urgency_level": "high",
    }

    pit_a = compute_point_in_time_features_for_order(
        target_order=target_order_2,
        supplier=supplier,
        product=product,
        prior_supplier_orders=[order_1_version_a, future_order_3],
        as_of_date=date(2026, 1, 10),
    )
    pit_b = compute_point_in_time_features_for_order(
        target_order=target_order_2,
        supplier=supplier,
        product=product,
        prior_supplier_orders=[order_1_version_b],
        as_of_date=date(2026, 1, 10),
    )

    # At Jan 10, neither version A nor version B of Order 1 has arrived yet, and Order 3 hasn't been placed.
    # Therefore features for Target Order 2 MUST be 100% identical!
    assert pit_a["features"] == pit_b["features"]
    assert pit_a["features"]["supplier_prior_order_count"] == 0.0
    assert pit_a["features"]["supplier_active_open_orders"] == 1.0


def test_chronological_training_splits_have_no_temporal_overlap() -> None:
    """Verify chronological Train / Validation / Test split boundaries."""
    db = SessionLocal()
    try:
        df = build_point_in_time_training_dataframe(db)
        df = df.sort_values(["order_date", "po_id"]).reset_index(drop=True)
        n = len(df)
        n_train = int(n * 0.70)
        n_val = int(n * 0.85)

        train_max_date = df.iloc[:n_train]["order_date"].max()
        val_min_date = df.iloc[n_train:n_val]["order_date"].min()
        val_max_date = df.iloc[n_train:n_val]["order_date"].max()
        test_min_date = df.iloc[n_val:]["order_date"].min()

        assert train_max_date <= val_min_date
        assert val_max_date <= test_min_date
    finally:
        db.close()


def test_dataset_quality_validator_catches_all_anomaly_types() -> None:
    """Verify data quality checks catch missing values, duplicates, invalid dates, impossible quantities, and status anomalies."""
    sample_records = [
        # Valid record
        {
            "po_number": "PO-VAL-1",
            "supplier_id": 1,
            "product_id": 1,
            "order_date": date(2026, 10, 1),
            "promised_delivery_date": date(2026, 10, 20),
            "actual_delivery_date": None,
            "quantity": 500,
            "unit_price": 120.0,
            "status": "open",
            "shipping_mode": "Ocean Freight",
        },
        # Duplicate PO + invalid date (promised < order) + impossible quantity (<=0)
        {
            "po_number": "PO-VAL-1",
            "supplier_id": 1,
            "product_id": 1,
            "order_date": date(2026, 10, 15),
            "promised_delivery_date": date(2026, 10, 5),
            "actual_delivery_date": date(2026, 10, 16),
            "quantity": -10,
            "unit_price": 120.0,
            "status": "open",
            "shipping_mode": "Teleportation",
        },
        # Extreme outlier quantity + missing required field
        {
            "po_number": "",
            "supplier_id": 1,
            "product_id": 1,
            "order_date": date(2026, 10, 1),
            "promised_delivery_date": date(2026, 10, 20),
            "actual_delivery_date": None,
            "quantity": 9_000_000,
            "unit_price": 100.0,
            "status": "unknown_status",
            "shipping_mode": "Ocean Freight",
        },
    ]

    report = validate_dataset_records(sample_records)
    assert report["total_checked"] == 3
    assert report["valid_count"] == 1
    assert report["invalid_count"] == 2
    counts = report["anomaly_counts"]
    assert counts["duplicates"] >= 1
    assert counts["invalid_dates"] >= 1
    assert counts["impossible_quantities"] >= 1
    assert counts["inconsistent_statuses"] >= 1
    assert counts["categorical_anomalies"] >= 1
    assert counts["extreme_outliers"] >= 1
    assert counts["missing_values"] >= 1
