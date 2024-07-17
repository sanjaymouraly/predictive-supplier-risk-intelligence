"""Reproducible synthetic manufacturing procurement dataset generator and validator."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.auth import seed_default_users
from app.config import settings
from app.models import (
    AIProviderConfig,
    DeliveryEvent,
    Product,
    PurchaseOrder,
    Supplier,
    SystemRuleConfig,
)

REGIONS = [
    ("East Asia", ["China", "Taiwan", "South Korea", "Japan"], ["Shanghai", "Kaohsiung", "Busan", "Yokohama"], 0.30),
    ("North America", ["United States", "Mexico", "Canada"], ["Los Angeles", "Monterrey", "Toronto"], 0.15),
    ("Central Europe", ["Germany", "Poland", "Czechia", "Italy"], ["Hamburg", "Gdansk", "Prague", "Genoa"], 0.18),
    ("Southeast Asia", ["Vietnam", "Malaysia", "Thailand"], ["Haiphong", "Penang", "Laem Chabang"], 0.28),
    ("South Asia", ["India"], ["Chennai", "Mundra"], 0.25),
    ("Latin America", ["Brazil", "Colombia"], ["Santos", "Cartagena"], 0.32),
]

CATEGORIES = [
    ("Semiconductors", 35, 145.0, 0.90),
    ("Battery Cells & Packs", 30, 420.0, 0.88),
    ("Power Electronics", 24, 210.0, 0.78),
    ("Precision Machining", 18, 85.0, 0.65),
    ("Industrial Sensors", 21, 115.0, 0.72),
    ("Hydraulic Assemblies", 25, 310.0, 0.70),
    ("Structural Castings", 28, 165.0, 0.60),
]

SHIPPING_MODES = ["Ocean Freight", "Air Freight", "Air Express", "Ground Freight", "Rail Intermodal"]
PLANTS = ["Detroit Assembly", "Austin Gigafactory", "Stuttgart Plant 2", "Pune Powertrain", "Guadalajara Ops"]

SUPPLIER_PREFIXES = [
    "Apex", "Vanguard", "Precision", "Nexus", "Aether", "Titan", "Kinetix", "Nova",
    "Quantum", "Helios", "Vertex", "Stratos", "Dynatek", "CyberCore", "Omni", "Atlas",
    "Hyperion", "Zephyr", "Chronos", "Vectra", "Synapse", "Meridian", "Polaris", "Orion",
    "Covalent", "Valiant", "Boreal", "Solstice", "Pinnacle", "Aegis", "Axis", "Crest",
    "Cobalt", "Forge", "Pulse", "Matrix", "Lumen", "Arc", "Prime", "Catalyst",
    "Horizon", "Summit", "Delta", "Omega", "ferroTech", "VoltEdge", "SiliconWave", "MechaFlow",
    "AeroCast", "HydroForce", "Sensoria", "OptiFab", "MicroGrid", "ThermalCore", "TerraMetals",
]

SUPPLIER_SUFFIXES = [
    "Microelectronics", "Industrial Systems", "Manufacturing Ltd", "Precision Corp",
    "Components GmbH", "Semiconductor Co", "Dynamics", "Foundry Works", "Technologies",
    "Assemblies Inc", "Metals & Alloys", "Power Solutions", "Automation",
]


def validate_dataset_records(
    orders: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run comprehensive data quality checks over order records.

    Checks for:
    - Missing required fields
    - Duplicate PO numbers
    - Invalid dates (promised < order, or actual < order)
    - Impossible quantities (<= 0) or negative prices
    - Inconsistent statuses (e.g. open order with actual_delivery_date present)
    - Categorical anomalies (unknown status or shipping mode)
    - Extreme numeric outliers (quantity > 5,000,000 or lead time > 365 days)
    """
    valid_statuses = {"open", "in_transit", "delivered", "cancelled"}
    valid_shipping = set(SHIPPING_MODES)

    errors: list[dict[str, Any]] = []
    seen_po_numbers: set[str] = set()
    valid_rows: list[dict[str, Any]] = []

    counts = {
        "missing_values": 0,
        "duplicates": 0,
        "invalid_dates": 0,
        "impossible_quantities": 0,
        "inconsistent_statuses": 0,
        "categorical_anomalies": 0,
        "extreme_outliers": 0,
    }

    for idx, row in enumerate(orders):
        row_errors: list[str] = []
        po_num = str(row.get("po_number") or "").strip()

        # 1. Missing values check
        for req_field in ("po_number", "supplier_id", "product_id", "order_date", "promised_delivery_date", "quantity", "unit_price"):
            if row.get(req_field) in (None, ""):
                counts["missing_values"] += 1
                row_errors.append(f"Missing required field '{req_field}'")

        # 2. Duplicate PO check
        if po_num:
            if po_num in seen_po_numbers:
                counts["duplicates"] += 1
                row_errors.append(f"Duplicate po_number '{po_num}'")
            seen_po_numbers.add(po_num)

        # 3. Date checks
        ord_d = row.get("order_date")
        prom_d = row.get("promised_delivery_date")
        act_d = row.get("actual_delivery_date")
        if isinstance(ord_d, date) and isinstance(prom_d, date):
            if prom_d < ord_d:
                counts["invalid_dates"] += 1
                row_errors.append("promised_delivery_date is earlier than order_date")
            lead_days = (prom_d - ord_d).days
            if lead_days > 365:
                counts["extreme_outliers"] += 1
                row_errors.append(f"Extreme promised lead time ({lead_days} days > 365)")
        if isinstance(ord_d, date) and isinstance(act_d, date):
            if act_d < ord_d:
                counts["invalid_dates"] += 1
                row_errors.append("actual_delivery_date is earlier than order_date")

        # 4. Quantity & Price checks
        qty = row.get("quantity")
        price = row.get("unit_price")
        if isinstance(qty, (int, float)):
            if qty <= 0:
                counts["impossible_quantities"] += 1
                row_errors.append(f"Impossible quantity ({qty} <= 0)")
            elif qty > 5_000_000:
                counts["extreme_outliers"] += 1
                row_errors.append(f"Extreme quantity outlier ({qty} > 5,000,000)")
        if isinstance(price, (int, float)) and price <= 0:
            counts["impossible_quantities"] += 1
            row_errors.append(f"Invalid unit_price ({price} <= 0)")

        # 5. Status consistency & categorical anomaly checks
        st = str(row.get("status") or "open")
        if st not in valid_statuses:
            counts["categorical_anomalies"] += 1
            row_errors.append(f"Unknown status '{st}'")
        if st in ("open", "in_transit") and act_d is not None:
            counts["inconsistent_statuses"] += 1
            row_errors.append(f"Inconsistent status: '{st}' order cannot have actual_delivery_date")
        if st == "delivered" and act_d is None:
            counts["inconsistent_statuses"] += 1
            row_errors.append("Inconsistent status: 'delivered' order missing actual_delivery_date")

        ship = row.get("shipping_mode")
        if ship and ship not in valid_shipping:
            counts["categorical_anomalies"] += 1
            row_errors.append(f"Categorical anomaly in shipping_mode '{ship}'")

        if row_errors:
            errors.append({"row_index": idx, "po_number": po_num, "errors": row_errors})
        else:
            valid_rows.append(row)

    return {
        "total_checked": len(orders),
        "valid_count": len(valid_rows),
        "invalid_count": len(errors),
        "anomaly_counts": counts,
        "errors": errors,
        "valid_rows": valid_rows,
    }


def _compute_latent_delay_Outcome(
    rng: np.random.Generator,
    supplier: Supplier,
    product: Product,
    order_date: date,
    promised_lead_time: int,
    quantity: int,
    shipping_mode: str,
    urgency_level: str,
    active_supplier_orders: int,
) -> tuple[bool, int]:
    """Simulate realistic non-linear manufacturing & logistics delay mechanics."""
    # Base log-odds from supplier intrinsic reliability
    # E.g. reliability 0.88 -> base late prob 0.12 -> logit(-1.99)
    base_late_prob = np.clip(1.0 - supplier.reliability_baseline, 0.04, 0.85)
    logit = math.log(base_late_prob / (1.0 - base_late_prob))

    # 1. Lead time compression pressure (if buyer requests tighter lead time than standard)
    lead_ratio = promised_lead_time / max(1.0, float(product.standard_lead_time_days))
    if lead_ratio < 0.78:
        logit += 1.65 * (0.85 - lead_ratio) * 3.0
    elif lead_ratio < 0.92:
        logit += 0.65
    elif lead_ratio > 1.25:
        logit -= 0.55

    # 2. Supplier congestion / capacity overload
    utilization = active_supplier_orders / max(1.0, supplier.capacity_index * 6.0)
    if utilization > 0.85:
        logit += 0.95 * (utilization - 0.70)

    # 3. Order quantity spike
    typical_qty = 450.0 * supplier.capacity_index
    qty_ratio = quantity / max(50.0, typical_qty)
    if qty_ratio > 1.8:
        logit += 0.55 * min(2.5, qty_ratio - 1.5)

    # 4. Seasonality (Q4 freight peak + late summer port typhoons in East/SE Asia)
    if order_date.month in (10, 11, 12):
        logit += 0.48
    if order_date.month in (8, 9) and supplier.region in ("East Asia", "Southeast Asia"):
        logit += 0.38

    # 5. Category complexity
    if product.category in ("Semiconductors", "Battery Cells & Packs"):
        logit += 0.32
    elif product.category == "Power Electronics":
        logit += 0.18

    # 6. Shipping mode
    if shipping_mode == "Ocean Freight":
        logit += 0.35
    elif shipping_mode == "Air Express":
        logit -= 0.65
    elif shipping_mode == "Air Freight":
        logit -= 0.30

    # 7. Geopolitical & financial distress interaction
    if supplier.financial_health_score < 58.0:
        logit += 0.60
    logit += (supplier.geopolitical_risk_index - 0.25) * 1.1

    # 8. Urgency interaction (rush orders with compressed lead times often slip)
    if urgency_level == "critical" and lead_ratio < 0.90:
        logit += 0.40

    # Convert logit to probability with modest idiosyncratic noise
    noisy_logit = logit + float(rng.normal(0.0, 0.32))
    prob_late = 1.0 / (1.0 + math.exp(-noisy_logit))

    is_delayed = bool(rng.random() < prob_late)
    if is_delayed:
        # Delay duration in days (1 to 35 days, correlated with lead_time_std_days & probability)
        mean_delay = max(2.0, supplier.lead_time_std_days * (1.2 + 2.2 * prob_late))
        if shipping_mode == "Ocean Freight":
            mean_delay += 3.5
        delay_days = max(1, int(round(rng.gamma(shape=2.2, scale=mean_delay / 2.2))))
        delay_days = min(delay_days, 48)
    else:
        # Early or exact on-time (-4 to 0 days)
        delay_days = -int(rng.integers(0, 4))

    return is_delayed, delay_days


def generate_synthetic_dataset(
    db: Session,
    num_suppliers: int = 55,
    num_historical_orders: int = 2400,
    num_open_orders: int = 140,
    seed: int = 42,
    force_reset: bool = False,
) -> dict[str, Any]:
    """Populate database with reproducible, realistic multi-year procurement data."""
    seed_default_users(db)

    # Ensure default business rule configuration exists
    if not db.query(SystemRuleConfig).filter_by(config_key="prioritization_rules").first():
        import json
        default_rules = {
            "moderate_risk_threshold": settings.moderate_risk_threshold,
            "high_risk_threshold": settings.high_risk_threshold,
            "critical_risk_threshold": settings.critical_risk_threshold,
            "reviewer_capacity": settings.default_reviewer_capacity,
            "weight_ml_probability": 0.45,
            "weight_financial_impact": 0.25,
            "weight_urgency": 0.15,
            "weight_criticality": 0.15,
        }
        db.add(
            SystemRuleConfig(
                config_key="prioritization_rules",
                config_value_json=json.dumps(default_rules),
                updated_by="system",
            )
        )
        db.commit()

    # Ensure default AI provider config row exists (Offline Mode default)
    if not db.query(AIProviderConfig).first():
        db.add(
            AIProviderConfig(
                provider_type="none",
                base_url="",
                api_key_stored="",
                model_name="offline-deterministic-v1",
                timeout_seconds=20,
                max_retries=2,
                max_tokens=600,
                budget_limit_usd=10.0,
                spent_usd=0.0,
                request_count=0,
                is_enabled=False,
                updated_by="system",
            )
        )
        db.commit()

    existing_po_count = db.query(PurchaseOrder).count()
    if existing_po_count > 0 and not force_reset:
        return {
            "status": "already_seeded",
            "suppliers": db.query(Supplier).count(),
            "products": db.query(Product).count(),
            "purchase_orders": existing_po_count,
        }

    if force_reset:
        db.query(DeliveryEvent).delete()
        db.query(PurchaseOrder).delete()
        db.query(Product).delete()
        db.query(Supplier).delete()
        db.commit()

    rng = np.random.default_rng(seed)
    ref_date = date.fromisoformat(settings.reference_date)  # 2026-10-17

    # 1. Create Suppliers (including 5 recently onboarded cold-start suppliers)
    suppliers: list[Supplier] = []
    supplier_ports: dict[int, str] = {}
    for i in range(num_suppliers):
        reg_name, countries, ports, base_geo = REGIONS[i % len(REGIONS)]
        country = countries[int(rng.integers(0, len(countries)))]
        port = ports[int(rng.integers(0, len(ports)))]
        cat_name, _, _, _ = CATEGORIES[i % len(CATEGORIES)]

        is_cold_start = i >= (num_suppliers - 5)
        if is_cold_start:
            onboarding = ref_date - timedelta(days=int(rng.integers(10, 45)))
            tier = "Tier 2"
        else:
            onboarding = date(2022, 1, 1) + timedelta(days=int(rng.integers(0, 650)))
            tier = "Tier 1" if i % 3 != 0 else "Tier 2"

        # Assign realistic supplier reliability regimes:
        # ~25% high-risk suppliers (reliability 0.45 - 0.68)
        # ~35% moderate reliability (0.70 - 0.84)
        # ~40% reliable partners (0.86 - 0.96)
        bucket = i % 10
        if bucket in (0, 1, 2):
            reliability = float(rng.uniform(0.42, 0.68))
            std_days = float(rng.uniform(4.5, 9.5))
            fin_health = float(rng.uniform(44.0, 68.0))
        elif bucket in (3, 4, 5):
            reliability = float(rng.uniform(0.71, 0.84))
            std_days = float(rng.uniform(2.5, 5.2))
            fin_health = float(rng.uniform(65.0, 82.0))
        else:
            reliability = float(rng.uniform(0.86, 0.96))
            std_days = float(rng.uniform(1.0, 2.8))
            fin_health = float(rng.uniform(78.0, 96.0))

        prefix = SUPPLIER_PREFIXES[i % len(SUPPLIER_PREFIXES)]
        suffix = SUPPLIER_SUFFIXES[(i * 3) % len(SUPPLIER_SUFFIXES)]
        sup = Supplier(
            supplier_code=f"SUP-{1001 + i}",
            name=f"{prefix} {suffix}",
            country=country,
            region=reg_name,
            primary_category=cat_name,
            tier=tier,
            capacity_index=round(float(rng.uniform(0.6, 1.6)), 2),
            reliability_baseline=round(reliability, 3),
            lead_time_std_days=round(std_days, 2),
            financial_health_score=round(fin_health, 1),
            geopolitical_risk_index=round(
                float(np.clip(base_geo + rng.normal(0, 0.08), 0.05, 0.85)), 2
            ),
            contact_email=f"ops@{prefix.lower().replace(' ', '')}-{1001+i}.example.com",
            status="active",
            onboarding_date=onboarding,
            notes=(
                "Newly onboarded supplier — limited historical delivery baseline."
                if is_cold_start
                else f"Primary {cat_name} supplier operating out of {port}, {country}."
            ),
        )
        suppliers.append(sup)

    db.add_all(suppliers)
    db.commit()
    for idx, sup in enumerate(suppliers):
        db.refresh(sup)
        reg_name, _, ports, _ = REGIONS[idx % len(REGIONS)]
        supplier_ports[sup.id] = ports[0]

    # 2. Create Products (2 to 3 products per supplier)
    products: list[Product] = []
    sku_counter = 100
    for sup in suppliers:
        cat_info = next(
            (c for c in CATEGORIES if c[0] == sup.primary_category), CATEGORIES[0]
        )
        cat_name, std_lead, base_cost, base_crit = cat_info
        num_prods = 2 if sup.tier == "Tier 2" else 3
        for p_idx in range(num_prods):
            sku_counter += 1
            unit_cost = round(float(base_cost * rng.uniform(0.65, 1.55)), 2)
            crit = round(float(np.clip(base_crit + rng.normal(0, 0.10), 0.2, 0.99)), 2)
            lead = max(7, int(round(std_lead * rng.uniform(0.85, 1.20))))
            prod = Product(
                sku=f"SKU-{cat_name[:3].upper()}-{sku_counter}",
                name=f"{cat_name} Module Type-{chr(65 + p_idx)}{sku_counter % 10}",
                category=cat_name,
                unit_cost=unit_cost,
                criticality_score=crit,
                standard_lead_time_days=lead,
                safety_stock_days=max(3, int(lead * 0.3)),
                supplier_id=sup.id,
            )
            products.append(prod)

    db.add_all(products)
    db.commit()
    for prod in products:
        db.refresh(prod)

    sup_by_id = {s.id: s for s in suppliers}
    prods_by_sup: dict[int, list[Product]] = {}
    for p in products:
        prods_by_sup.setdefault(p.supplier_id, []).append(p)

    # Separate established suppliers from the 5 cold-start suppliers
    established_suppliers = suppliers[:-5]
    cold_start_suppliers = suppliers[-5:]

    # 3. Generate Historical Orders (2024-01-01 to 2026-09-25)
    start_hist_date = date(2024, 1, 1)
    end_hist_date = ref_date - timedelta(days=22)
    total_hist_span_days = (end_hist_date - start_hist_date).days

    # Generate chronological order dates
    day_offsets = sorted(
        int(x) for x in rng.integers(0, total_hist_span_days, size=num_historical_orders)
    )

    purchase_orders: list[PurchaseOrder] = []
    delivery_events: list[DeliveryEvent] = []

    # Track active orders per supplier by completion date for realistic congestion simulation
    active_end_dates_by_sup: dict[int, list[date]] = {s.id: [] for s in suppliers}

    for idx, offset in enumerate(day_offsets):
        ord_date = start_hist_date + timedelta(days=offset)
        # In the final test window (last 120 days), include a couple of orders from 2 cold-start suppliers
        # so unseen-supplier evaluation has test samples while leaving 3 completely unseen until open orders
        if offset > total_hist_span_days - 40 and idx % 25 == 0:
            sup = cold_start_suppliers[idx % 2]
        else:
            sup = established_suppliers[int(rng.integers(0, len(established_suppliers)))]

        sup_prods = prods_by_sup[sup.id]
        prod = sup_prods[int(rng.integers(0, len(sup_prods)))]

        # Promised lead time around standard lead time
        lead_multiplier = float(rng.choice([0.68, 0.80, 0.95, 1.0, 1.05, 1.15, 1.30], p=[0.10, 0.16, 0.24, 0.22, 0.14, 0.08, 0.06]))
        promised_lead = max(5, int(round(prod.standard_lead_time_days * lead_multiplier)))
        promised_date = ord_date + timedelta(days=promised_lead)

        # Count active orders for this supplier at ord_date
        active_list = [d for d in active_end_dates_by_sup[sup.id] if d > ord_date]
        active_end_dates_by_sup[sup.id] = active_list
        active_count = len(active_list)

        qty = int(round(rng.lognormal(mean=5.8, sigma=0.65) * sup.capacity_index))
        qty = max(25, min(qty, 25000))
        unit_price = round(prod.unit_cost * float(rng.uniform(0.95, 1.06)), 2)
        total_val = round(qty * unit_price, 2)

        shipping_mode = str(
            rng.choice(
                SHIPPING_MODES,
                p=[0.48, 0.20, 0.10, 0.14, 0.08],
            )
        )
        urgency = str(
            rng.choice(["low", "standard", "high", "critical"], p=[0.12, 0.55, 0.23, 0.10])
        )
        plant = str(rng.choice(PLANTS))

        is_delayed, delay_days = _compute_latent_delay_Outcome(
            rng=rng,
            supplier=sup,
            product=prod,
            order_date=ord_date,
            promised_lead_time=promised_lead,
            quantity=qty,
            shipping_mode=shipping_mode,
            urgency_level=urgency,
            active_supplier_orders=active_count,
        )

        actual_lead = max(2, promised_lead + delay_days)
        actual_date = ord_date + timedelta(days=actual_lead)

        # Ensure historical completed orders actually finished before reference_date
        if actual_date >= ref_date:
            actual_date = ref_date - timedelta(days=int(rng.integers(1, 5)))
            actual_lead = max(1, (actual_date - ord_date).days)
            delay_days = actual_lead - promised_lead
            is_delayed = delay_days > 0

        active_end_dates_by_sup[sup.id].append(actual_date)

        # ~2.5% cancelled orders (censored outcome)
        is_cancelled = bool(rng.random() < 0.025)
        status_str = "cancelled" if is_cancelled else "delivered"

        po = PurchaseOrder(
            po_number=f"PO-{ord_date.year}-{10001 + idx}",
            supplier_id=sup.id,
            product_id=prod.id,
            order_date=ord_date,
            promised_delivery_date=promised_date,
            actual_delivery_date=None if is_cancelled else actual_date,
            quantity=qty,
            unit_price=unit_price,
            total_value=total_val,
            promised_lead_time_days=promised_lead,
            actual_lead_time_days=None if is_cancelled else actual_lead,
            delay_days=None if is_cancelled else delay_days,
            is_delayed=None if is_cancelled else is_delayed,
            status=status_str,
            shipping_mode=shipping_mode,
            origin_port=supplier_ports[sup.id],
            destination_plant=plant,
            urgency_level=urgency,
            notes="Completed historical order" if not is_cancelled else "Cancelled prior to shipment",
        )
        purchase_orders.append(po)

    # 4. Generate Active Open / In-Transit Orders (around ref_date 2026-10-17)
    for j in range(num_open_orders):
        # Include orders from cold-start suppliers to showcase cold-start warnings in live queue
        if j < 14:
            sup = cold_start_suppliers[j % len(cold_start_suppliers)]
        else:
            sup = suppliers[int(rng.integers(0, len(suppliers)))]

        sup_prods = prods_by_sup[sup.id]
        prod = sup_prods[int(rng.integers(0, len(sup_prods)))]

        days_ago = int(rng.integers(1, 18))
        ord_date = ref_date - timedelta(days=days_ago)

        lead_multiplier = float(
            rng.choice([0.62, 0.74, 0.85, 0.95, 1.0, 1.15], p=[0.18, 0.22, 0.20, 0.18, 0.12, 0.10])
        )
        promised_lead = max(6, int(round(prod.standard_lead_time_days * lead_multiplier)))
        promised_date = ord_date + timedelta(days=promised_lead)
        if promised_date <= ref_date:
            promised_date = ref_date + timedelta(days=int(rng.integers(2, 28)))
            promised_lead = (promised_date - ord_date).days

        qty = int(round(rng.lognormal(mean=6.0, sigma=0.75) * sup.capacity_index))
        qty = max(40, min(qty, 30000))
        unit_price = round(prod.unit_cost * float(rng.uniform(0.96, 1.05)), 2)
        total_val = round(qty * unit_price, 2)

        shipping_mode = str(
            rng.choice(SHIPPING_MODES, p=[0.52, 0.18, 0.08, 0.14, 0.08])
        )
        urgency = str(
            rng.choice(["low", "standard", "high", "critical"], p=[0.08, 0.44, 0.30, 0.18])
        )
        status_str = "in_transit" if days_ago > 8 else "open"

        po = PurchaseOrder(
            po_number=f"PO-2026-OPEN-{2001 + j}",
            supplier_id=sup.id,
            product_id=prod.id,
            order_date=ord_date,
            promised_delivery_date=promised_date,
            actual_delivery_date=None,
            quantity=qty,
            unit_price=unit_price,
            total_value=total_val,
            promised_lead_time_days=promised_lead,
            actual_lead_time_days=None,
            delay_days=None,
            is_delayed=None,
            status=status_str,
            shipping_mode=shipping_mode,
            origin_port=supplier_ports[sup.id],
            destination_plant=str(rng.choice(PLANTS)),
            urgency_level=urgency,
            notes="Active open purchase order awaiting delivery",
        )
        purchase_orders.append(po)

    db.add_all(purchase_orders)
    db.commit()

    # Add realistic delivery milestone events for open/in-transit orders and recent delivered orders
    recent_pos = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.status.in_(["open", "in_transit"]))
        .limit(60)
        .all()
    )
    for po in recent_pos:
        sup = sup_by_id[po.supplier_id]
        ev_time = datetime.combine(po.order_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=14)
        delivery_events.append(
            DeliveryEvent(
                po_id=po.id,
                event_type="PO_ACKNOWLEDGED",
                event_timestamp=ev_time,
                location=f"{sup.country} Factory",
                delay_days_reported=0,
                severity="info",
                notes=f"Order confirmed by {sup.name}.",
            )
        )
        if po.status == "in_transit":
            transit_time = ev_time + timedelta(days=4)
            is_congested = sup.reliability_baseline < 0.72
            delivery_events.append(
                DeliveryEvent(
                    po_id=po.id,
                    event_type="PORT_DEPARTURE_DELAY" if is_congested else "DEPARTED_ORIGIN_PORT",
                    event_timestamp=transit_time,
                    location=po.origin_port,
                    delay_days_reported=4 if is_congested else 0,
                    severity="warning" if is_congested else "info",
                    notes=(
                        f"Vessel berth congestion reported at {po.origin_port}; +4d slip estimated."
                        if is_congested
                        else f"Shipment departed {po.origin_port} via {po.shipping_mode}."
                    ),
                )
            )

    db.add_all(delivery_events)
    db.commit()

    return {
        "status": "seeded",
        "suppliers": len(suppliers),
        "products": len(products),
        "purchase_orders": len(purchase_orders),
        "historical_orders": num_historical_orders,
        "open_orders": num_open_orders,
    }
