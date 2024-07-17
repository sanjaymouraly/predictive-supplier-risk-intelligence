"""CSV/Excel Bulk Import with Column Mapping, Preview, Validation, Duplicate Handling, and CSV/PDF Report Generation."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.data_generator import SHIPPING_MODES
from app.models import (
    ModelRegistry,
    Product,
    PurchaseOrder,
    ReviewQueueItem,
    RiskPrediction,
    Supplier,
)


def parse_uploaded_tabular_file(
    file_bytes: bytes,
    filename: str,
) -> pd.DataFrame:
    """Parse uploaded CSV or Excel (.xlsx) file safely into a DataFrame."""
    lower = filename.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return pd.read_excel(io.BytesIO(file_bytes))
    if lower.endswith(".csv"):
        text = file_bytes.decode("utf-8-sig", errors="replace")
        return pd.read_csv(io.StringIO(text))
    raise ValueError("Unsupported file format. Please upload a .csv or .xlsx file.")


def preview_or_commit_order_import(
    db: Session,
    df_raw: pd.DataFrame,
    column_mapping: dict[str, str] | None = None,
    duplicate_strategy: str = "skip",  # "skip" | "update" | "error"
    dry_run: bool = True,
) -> dict[str, Any]:
    """Validate, map columns, preview, and optionally commit bulk purchase order imports."""
    df = df_raw.copy()
    if column_mapping:
        # column_mapping maps target_schema_column -> uploaded_file_column
        rename_dict = {
            src_col: target_col
            for target_col, src_col in column_mapping.items()
            if src_col in df.columns
        }
        df = df.rename(columns=rename_dict)

    suppliers_by_code = {s.supplier_code: s for s in db.query(Supplier).all()}
    suppliers_by_id = {s.id: s for s in suppliers_by_code.values()}
    products_by_sku = {p.sku: p for p in db.query(Product).all()}
    products_by_id = {p.id: p for p in products_by_sku.values()}
    existing_pos = {po.po_number: po for po in db.query(PurchaseOrder).all()}

    seen_in_file: set[str] = set()
    valid_records: list[dict[str, Any]] = []
    validation_errors: list[dict[str, Any]] = []
    duplicate_count = 0
    created_count = 0
    updated_count = 0
    skipped_count = 0

    for idx, row in df.iterrows():
        row_num = int(idx) + 1
        row_errs: list[str] = []

        po_number = str(row.get("po_number", "")).strip()
        if not po_number or po_number == "nan":
            row_errs.append("Missing required field 'po_number'")

        # Resolve supplier by supplier_code or supplier_id
        sup = None
        sup_code = str(row.get("supplier_code", "")).strip()
        sup_id_raw = row.get("supplier_id")
        if sup_code and sup_code in suppliers_by_code:
            sup = suppliers_by_code[sup_code]
        elif pd.notna(sup_id_raw):
            try:
                sup = suppliers_by_id.get(int(sup_id_raw))
            except Exception:
                pass
        if not sup:
            row_errs.append(f"Unknown supplier (code='{sup_code}', id='{sup_id_raw}')")

        # Resolve product by product_sku or product_id
        prod = None
        sku = str(row.get("product_sku", "")).strip()
        prod_id_raw = row.get("product_id")
        if sku and sku in products_by_sku:
            prod = products_by_sku[sku]
        elif pd.notna(prod_id_raw):
            try:
                prod = products_by_id.get(int(prod_id_raw))
            except Exception:
                pass
        if not prod and sup:
            # Fallback to first product of supplier if not specified
            sup_prods = [p for p in products_by_id.values() if p.supplier_id == sup.id]
            if sup_prods and not sku and pd.isna(prod_id_raw):
                prod = sup_prods[0]
        if not prod:
            row_errs.append(f"Unknown product (sku='{sku}', id='{prod_id_raw}')")

        # Parse dates
        ord_date = _parse_date_safe(row.get("order_date"))
        prom_date = _parse_date_safe(row.get("promised_delivery_date"))
        act_date = _parse_date_safe(row.get("actual_delivery_date"))

        if not ord_date:
            row_errs.append("Invalid or missing 'order_date' (expected YYYY-MM-DD)")
        if not prom_date:
            row_errs.append("Invalid or missing 'promised_delivery_date' (expected YYYY-MM-DD)")
        if ord_date and prom_date and prom_date < ord_date:
            row_errs.append("Invalid date range: promised_delivery_date < order_date")
        if ord_date and act_date and act_date < ord_date:
            row_errs.append("Invalid date range: actual_delivery_date < order_date")

        # Parse quantity & unit_price
        qty = _parse_int_safe(row.get("quantity"))
        if qty is None or qty <= 0:
            row_errs.append(f"Impossible quantity '{row.get('quantity')}' (must be > 0)")
        elif qty > 5_000_000:
            row_errs.append(f"Extreme quantity outlier ({qty} > 5,000,000)")

        unit_price = _parse_float_safe(row.get("unit_price"))
        if unit_price is None or unit_price <= 0:
            unit_price = prod.unit_cost if prod else None
        if unit_price is None or unit_price <= 0:
            row_errs.append("Invalid or missing 'unit_price' (must be > 0)")

        status_str = str(row.get("status", "open") or "open").strip().lower()
        if status_str in ("nan", ""):
            status_str = "open"
        if status_str not in ("open", "in_transit", "delivered", "cancelled"):
            row_errs.append(f"Categorical anomaly: invalid status '{status_str}'")
        if status_str in ("open", "in_transit") and act_date is not None:
            row_errs.append(f"Inconsistent status: '{status_str}' order cannot have actual_delivery_date")

        shipping_mode = str(row.get("shipping_mode", "Ocean Freight") or "Ocean Freight").strip()
        if shipping_mode in ("nan", ""):
            shipping_mode = "Ocean Freight"
        if shipping_mode not in SHIPPING_MODES:
            row_errs.append(f"Categorical anomaly: unsupported shipping_mode '{shipping_mode}'")

        urgency_level = str(row.get("urgency_level", "standard") or "standard").strip().lower()
        if urgency_level in ("nan", ""):
            urgency_level = "standard"

        # Duplicate check within file or against existing DB
        is_duplicate = False
        if po_number in seen_in_file:
            is_duplicate = True
            duplicate_count += 1
            row_errs.append(f"Duplicate po_number '{po_number}' within uploaded file")
        elif po_number in existing_pos:
            is_duplicate = True
            duplicate_count += 1
            if duplicate_strategy == "error":
                row_errs.append(f"Duplicate po_number '{po_number}' already exists in database")

        if po_number:
            seen_in_file.add(po_number)

        if row_errs:
            validation_errors.append(
                {
                    "row_number": row_num,
                    "po_number": po_number,
                    "errors": row_errs,
                }
            )
            continue

        assert sup is not None and prod is not None and ord_date is not None and prom_date is not None and qty is not None and unit_price is not None
        promised_lead = max(1, (prom_date - ord_date).days)
        actual_lead = (act_date - ord_date).days if act_date else None
        delay_days = (actual_lead - promised_lead) if actual_lead is not None else None
        is_delayed = (delay_days > 0) if delay_days is not None else None

        clean_rec = {
            "row_number": row_num,
            "po_number": po_number,
            "supplier_id": sup.id,
            "supplier_code": sup.supplier_code,
            "supplier_name": sup.name,
            "product_id": prod.id,
            "product_sku": prod.sku,
            "order_date": ord_date.isoformat(),
            "promised_delivery_date": prom_date.isoformat(),
            "actual_delivery_date": act_date.isoformat() if act_date else None,
            "quantity": qty,
            "unit_price": round(unit_price, 2),
            "total_value": round(qty * unit_price, 2),
            "promised_lead_time_days": promised_lead,
            "status": status_str,
            "shipping_mode": shipping_mode,
            "urgency_level": urgency_level,
            "is_duplicate": is_duplicate,
        }
        valid_records.append(clean_rec)

        if not dry_run:
            if po_number in existing_pos:
                if duplicate_strategy == "skip":
                    skipped_count += 1
                    continue
                if duplicate_strategy == "update":
                    ex = existing_pos[po_number]
                    ex.supplier_id = sup.id
                    ex.product_id = prod.id
                    ex.order_date = ord_date
                    ex.promised_delivery_date = prom_date
                    ex.actual_delivery_date = act_date
                    ex.quantity = qty
                    ex.unit_price = round(unit_price, 2)
                    ex.total_value = round(qty * unit_price, 2)
                    ex.promised_lead_time_days = promised_lead
                    ex.actual_lead_time_days = actual_lead
                    ex.delay_days = delay_days
                    ex.is_delayed = is_delayed
                    ex.status = status_str
                    ex.shipping_mode = shipping_mode
                    ex.urgency_level = urgency_level
                    updated_count += 1
            else:
                new_po = PurchaseOrder(
                    po_number=po_number,
                    supplier_id=sup.id,
                    product_id=prod.id,
                    order_date=ord_date,
                    promised_delivery_date=prom_date,
                    actual_delivery_date=act_date,
                    quantity=qty,
                    unit_price=round(unit_price, 2),
                    total_value=round(qty * unit_price, 2),
                    promised_lead_time_days=promised_lead,
                    actual_lead_time_days=actual_lead,
                    delay_days=delay_days,
                    is_delayed=is_delayed,
                    status=status_str,
                    shipping_mode=shipping_mode,
                    urgency_level=urgency_level,
                )
                db.add(new_po)
                created_count += 1

    if not dry_run:
        db.commit()

    return {
        "dry_run": dry_run,
        "duplicate_strategy": duplicate_strategy,
        "detected_columns": list(df_raw.columns),
        "total_rows": len(df_raw),
        "valid_rows_count": len(valid_records),
        "error_rows_count": len(validation_errors),
        "duplicate_count": duplicate_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "preview_rows": valid_records[:25],
        "errors": validation_errors[:50],
    }


def _parse_date_safe(val: Any) -> date | None:
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        try:
            return pd.to_datetime(s).date()
        except Exception:
            return None


def _parse_int_safe(val: Any) -> int | None:
    if val is None or pd.isna(val):
        return None
    try:
        return int(float(val))
    except Exception:
        return None


def _parse_float_safe(val: Any) -> float | None:
    if val is None or pd.isna(val):
        return None
    try:
        return float(val)
    except Exception:
        return None


def generate_sample_import_template_csv() -> str:
    """Return a ready-to-use CSV template with valid sample purchase orders."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "po_number",
            "supplier_code",
            "product_sku",
            "order_date",
            "promised_delivery_date",
            "quantity",
            "unit_price",
            "status",
            "shipping_mode",
            "urgency_level",
        ]
    )
    writer.writerow(
        [
            "PO-2026-IMP-9001",
            "SUP-1001",
            "",
            "2026-10-14",
            "2026-11-04",
            "850",
            "142.50",
            "open",
            "Ocean Freight",
            "high",
        ]
    )
    writer.writerow(
        [
            "PO-2026-IMP-9002",
            "SUP-1004",
            "",
            "2026-10-15",
            "2026-10-29",
            "1200",
            "95.00",
            "open",
            "Air Freight",
            "critical",
        ]
    )
    writer.writerow(
        [
            "PO-2026-IMP-9003",
            "SUP-1008",
            "",
            "2026-10-16",
            "2026-11-18",
            "400",
            "210.00",
            "open",
            "Ground Freight",
            "standard",
        ]
    )
    return buf.getvalue()


def export_predictions_csv(db: Session) -> str:
    """Export all open order risk predictions and review priorities as CSV."""
    preds = (
        db.query(RiskPrediction)
        .order_by(RiskPrediction.business_priority_score.desc())
        .all()
    )
    pos = {p.id: p for p in db.query(PurchaseOrder).all()}
    sups = {s.id: s for s in db.query(Supplier).all()}
    prods = {pr.id: pr for pr in db.query(Product).all()}

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "po_number",
            "supplier_code",
            "supplier_name",
            "region",
            "product_sku",
            "product_category",
            "order_date",
            "promised_delivery_date",
            "order_value_usd",
            "calibrated_delay_probability",
            "risk_category",
            "business_priority_score",
            "expected_delay_days",
            "expected_financial_impact_usd",
            "reliability_status",
            "model_version",
            "predicted_at",
        ]
    )

    for pred in preds:
        po = pos.get(pred.po_id)
        if not po:
            continue
        sup = sups.get(po.supplier_id)
        prod = prods.get(po.product_id)
        writer.writerow(
            [
                po.po_number,
                sup.supplier_code if sup else "",
                sup.name if sup else "",
                sup.region if sup else "",
                prod.sku if prod else "",
                prod.category if prod else "",
                po.order_date.isoformat(),
                po.promised_delivery_date.isoformat(),
                po.total_value,
                pred.calibrated_probability,
                pred.risk_category,
                pred.business_priority_score,
                pred.expected_delay_days,
                pred.expected_financial_impact,
                pred.reliability_status,
                pred.model_version,
                pred.predicted_at.isoformat(),
            ]
        )
    return buf.getvalue()


def export_orders_csv(db: Session) -> str:
    """Export the full purchase order ledger with outcomes and latest risk scores."""
    orders = db.query(PurchaseOrder).order_by(PurchaseOrder.order_date.desc()).all()
    sups = {s.id: s for s in db.query(Supplier).all()}
    prods = {p.id: p for p in db.query(Product).all()}
    preds = {p.po_id: p for p in db.query(RiskPrediction).all()}

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "po_number",
            "supplier_code",
            "supplier_name",
            "supplier_region",
            "product_sku",
            "product_category",
            "order_date",
            "promised_delivery_date",
            "actual_delivery_date",
            "quantity",
            "unit_price",
            "total_value",
            "promised_lead_time_days",
            "actual_lead_time_days",
            "delay_days",
            "is_delayed",
            "status",
            "shipping_mode",
            "origin_port",
            "destination_plant",
            "urgency_level",
            "calibrated_delay_probability",
            "risk_category",
            "business_priority_score",
            "reliability_status",
        ]
    )
    for po in orders:
        sup = sups.get(po.supplier_id)
        prod = prods.get(po.product_id)
        pred = preds.get(po.id)
        writer.writerow(
            [
                po.po_number,
                sup.supplier_code if sup else "",
                sup.name if sup else "",
                sup.region if sup else "",
                prod.sku if prod else "",
                prod.category if prod else "",
                po.order_date.isoformat(),
                po.promised_delivery_date.isoformat(),
                po.actual_delivery_date.isoformat() if po.actual_delivery_date else "",
                po.quantity,
                po.unit_price,
                po.total_value,
                po.promised_lead_time_days,
                po.actual_lead_time_days if po.actual_lead_time_days is not None else "",
                po.delay_days if po.delay_days is not None else "",
                "" if po.is_delayed is None else int(po.is_delayed),
                po.status,
                po.shipping_mode,
                po.origin_port,
                po.destination_plant,
                po.urgency_level,
                pred.calibrated_probability if pred else "",
                pred.risk_category if pred else "",
                pred.business_priority_score if pred else "",
                pred.reliability_status if pred else "",
            ]
        )
    return buf.getvalue()


def export_suppliers_csv(db: Session) -> str:
    """Export supplier master data enriched with historical delivery performance."""
    suppliers = db.query(Supplier).order_by(Supplier.supplier_code.asc()).all()
    orders_by_sup: dict[int, list[PurchaseOrder]] = {}
    for po in db.query(PurchaseOrder).all():
        orders_by_sup.setdefault(po.supplier_id, []).append(po)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "supplier_code",
            "name",
            "country",
            "region",
            "primary_category",
            "tier",
            "status",
            "onboarding_date",
            "capacity_index",
            "reliability_baseline",
            "lead_time_std_days",
            "financial_health_score",
            "geopolitical_risk_index",
            "contact_email",
            "completed_orders",
            "open_orders",
            "historical_otd_rate",
            "avg_delay_days",
            "is_cold_start",
        ]
    )
    for sup in suppliers:
        delivered = [
            o
            for o in orders_by_sup.get(sup.id, [])
            if o.status == "delivered" and o.is_delayed is not None
        ]
        open_count = sum(
            1 for o in orders_by_sup.get(sup.id, []) if o.status in ("open", "in_transit")
        )
        otd = (
            round(sum(1 for o in delivered if not o.is_delayed) / len(delivered), 4)
            if delivered
            else ""
        )
        avg_delay = (
            round(sum(o.delay_days or 0 for o in delivered) / len(delivered), 2)
            if delivered
            else ""
        )
        writer.writerow(
            [
                sup.supplier_code,
                sup.name,
                sup.country,
                sup.region,
                sup.primary_category,
                sup.tier,
                sup.status,
                sup.onboarding_date.isoformat(),
                sup.capacity_index,
                sup.reliability_baseline,
                sup.lead_time_std_days,
                sup.financial_health_score,
                sup.geopolitical_risk_index,
                sup.contact_email or "",
                len(delivered),
                open_count,
                otd,
                avg_delay,
                int(len(delivered) < 5),
            ]
        )
    return buf.getvalue()


def generate_executive_pdf_report(db: Session) -> bytes:
    """Generate a formatted PDF Executive Procurement Risk & Model Governance Report."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph(
            "<b>Predictive Supplier Risk Intelligence — Executive Report</b>",
            styles["Title"],
        )
    )
    story.append(
        Paragraph(
            f"Generated UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Human-in-the-Loop Decision Support",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 14))

    # 1. KPI Summary
    total_sups = db.query(Supplier).count()
    total_pos = db.query(PurchaseOrder).count()
    open_pos = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.status.in_(["open", "in_transit"]))
        .count()
    )
    high_risk_preds = (
        db.query(RiskPrediction)
        .filter(RiskPrediction.risk_category.in_(["high", "critical"]))
        .count()
    )
    pending_reviews = (
        db.query(ReviewQueueItem)
        .filter(ReviewQueueItem.status == "pending")
        .count()
    )

    story.append(Paragraph("<b>1. Operational Risk Overview</b>", styles["Heading2"]))
    kpi_data = [
        ["Metric", "Value", "Operational Notes"],
        ["Active Suppliers Monitored", str(total_sups), "Across 6 global regions & 7 categories"],
        ["Total Purchase Orders", str(total_pos), f"{open_pos} currently open / in-transit"],
        ["High / Critical Risk Open Orders", str(high_risk_preds), "Flagged above calibrated risk threshold"],
        ["Pending Human Review Queue Items", str(pending_reviews), "Ranked by composite business priority"],
    ]
    t_kpi = Table(kpi_data, colWidths=[180, 90, 240])
    t_kpi.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t_kpi)
    story.append(Spacer(1, 16))

    # 2. Champion Model Summary
    champ = (
        db.query(ModelRegistry)
        .filter(ModelRegistry.is_champion.is_(True))
        .first()
    )
    story.append(Paragraph("<b>2. ML Model Evaluation & Governance</b>", styles["Heading2"]))
    if champ:
        metrics = json.loads(champ.metrics_json)
        test_m = metrics.get("test", {})
        story.append(
            Paragraph(
                f"<b>Champion Model:</b> {champ.display_name} ({champ.model_version})<br/>"
                f"<b>Unseen Test ROC-AUC:</b> {test_m.get('roc_auc', 0):.3f} | "
                f"<b>Test PR-AUC:</b> {test_m.get('pr_auc', 0):.3f} | "
                f"<b>Brier Calibration Score:</b> {test_m.get('brier_score', 0):.4f}<br/>"
                f"<b>Selection Rationale:</b> {champ.selection_rationale}",
                styles["Normal"],
            )
        )
    story.append(Spacer(1, 16))

    # 3. Top Prioritized High-Risk Open Orders
    story.append(
        Paragraph("<b>3. Top Prioritized Open Orders Requiring Human Review</b>", styles["Heading2"])
    )
    top_items = (
        db.query(ReviewQueueItem)
        .order_by(ReviewQueueItem.priority_rank.asc())
        .limit(12)
        .all()
    )
    pos_map = {p.id: p for p in db.query(PurchaseOrder).all()}
    sups_map = {s.id: s for s in db.query(Supplier).all()}

    q_rows = [["Rank", "PO Number", "Supplier", "ML Delay Prob", "Priority Score", "Review Status"]]
    for item in top_items:
        po = pos_map.get(item.po_id)
        sup = sups_map.get(po.supplier_id) if po else None
        q_rows.append(
            [
                f"#{item.priority_rank}",
                po.po_number if po else str(item.po_id),
                (sup.name[:26] if sup else "Unknown"),
                f"{item.ml_calibrated_probability * 100:.1f}%",
                f"{item.business_priority_score:.1f}",
                item.status.upper(),
            ]
        )
    t_queue = Table(q_rows, colWidths=[45, 110, 140, 75, 75, 75])
    t_queue.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t_queue)
    story.append(Spacer(1, 16))

    story.append(
        Paragraph(
            "<i>Governance Notice: Predictions are generated from historical point-in-time statistical models. "
            "No order cancellations or supplier actions are executed automatically. Human review is mandatory.</i>",
            styles["Normal"],
        )
    )

    doc.build(story)
    return buf.getvalue()
