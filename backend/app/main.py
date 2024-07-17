"""FastAPI application entry point and REST API endpoints for Supplier Risk Intelligence."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.ai_service import (
    discover_provider_models,
    generate_grounded_analyst_briefing,
    get_ai_config,
    list_provider_presets,
    serialize_ai_config,
    test_ai_provider_connection,
    update_ai_config,
)
from app.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    record_audit_log,
    require_min_role,
    seed_default_users,
    verify_password,
)
from app.config import settings
from app.data_generator import generate_synthetic_dataset
from app.database import SessionLocal, get_db, init_db
from app.decision_engine import (
    refresh_predictions_and_queues,
    update_business_rules,
)
from app.import_export import (
    export_orders_csv,
    export_predictions_csv,
    export_suppliers_csv,
    generate_executive_pdf_report,
    generate_sample_import_template_csv,
    parse_uploaded_tabular_file,
    preview_or_commit_order_import,
)
from app.ml_pipeline import (
    get_business_rules,
    predict_order_risk,
    resolve_artifact_path,
    train_and_evaluate_all_models,
)
from app.models import (
    AuditLog,
    DeliveryEvent,
    EarlyWarningAlert,
    ModelRegistry,
    Product,
    PurchaseOrder,
    ReviewQueueItem,
    RiskPrediction,
    Supplier,
    User,
)
from app.monitoring import compute_monitoring_diagnostics
from app.scenario_engine import run_scenario_simulation
from app.schemas import (
    AIExplanationRequest,
    AIProviderConfigOut,
    AIProviderConfigUpdate,
    AlertActionRequest,
    BusinessRuleConfigSchema,
    LoginRequest,
    ProductCreate,
    ProductOut,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderUpdate,
    ReviewDecisionRequest,
    ScenarioRequest,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
    TokenResponse,
    UserOut,
)


def bootstrap_application_state() -> None:
    """Ensure DB tables exist, demo dataset is seeded, and champion model & queue are ready."""
    init_db()
    db = SessionLocal()
    try:
        seed_default_users(db)
        if settings.seed_demo_data and db.query(Supplier).count() == 0:
            generate_synthetic_dataset(db)
        champ = (
            db.query(ModelRegistry)
            .filter(ModelRegistry.is_champion.is_(True))
            .first()
        )
        artifact_ok = False
        if champ and champ.artifact_path:
            resolved = resolve_artifact_path(champ.artifact_path)
            artifact_ok = bool(resolved and resolved.exists())
        if not artifact_ok and settings.auto_train_on_startup:
            train_and_evaluate_all_models(db)
            refresh_predictions_and_queues(db)
        elif db.query(RiskPrediction).count() == 0:
            refresh_predictions_and_queues(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    bootstrap_application_state()
    yield


app = FastAPI(
    title="Predictive Supplier Risk Intelligence API",
    description=(
        "Enterprise ML & Human-in-the-Loop Procurement Decision Support System "
        "for anticipating delayed deliveries, calibrating supplier risk, and prioritizing reviews."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_PUBLIC_API_PATHS = {"/api/health", "/api/auth/login"}


@app.middleware("http")
async def require_authentication_in_production(request, call_next):  # type: ignore[no-untyped-def]
    """Reject unauthenticated API traffic when demo mode is disabled.

    URI-level dependencies alone are not sufficient because several read
    endpoints intentionally do not require a specific role. This guard makes
    ``ALLOW_DEMO_MODE=false`` a genuine deployment boundary.
    """
    path = request.url.path
    if (
        not settings.allow_demo_mode
        and path.startswith("/api/")
        and path not in _PUBLIC_API_PATHS
        and request.method != "OPTIONS"
    ):
        auth_header = request.headers.get("authorization", "")
        token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
        try:
            payload = decode_access_token(token) if token else None
            if not payload or not payload.get("sub"):
                raise ValueError("missing subject")
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required: provide a valid Bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
    return await call_next(request)


# ============================================================================
# 1. Health & Operational Diagnostics
# ============================================================================
@app.get("/api/health", tags=["System"])
def health_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    champ = (
        db.query(ModelRegistry)
        .filter(ModelRegistry.is_champion.is_(True))
        .first()
    )
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
        "reference_date": settings.reference_date,
        "database_connected": True,
        "suppliers_count": db.query(Supplier).count(),
        "purchase_orders_count": db.query(PurchaseOrder).count(),
        "champion_model": champ.model_version if champ else None,
        "demo_mode": settings.allow_demo_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# 2. Authentication & Role Management
# ============================================================================
@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@app.get("/api/auth/me", response_model=UserOut, tags=["Auth"])
def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)


@app.get("/api/auth/users", response_model=list[UserOut], tags=["Auth"])
def list_users(
    current_user: User = Depends(require_min_role("admin")),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    users = db.query(User).order_by(User.id.asc()).all()
    return [UserOut.model_validate(u) for u in users]


@app.get("/api/auth/demo-accounts", tags=["Auth"])
def list_demo_accounts() -> list[dict[str, str]]:
    """Return seeded demonstration credentials. Disabled outside demo mode."""
    if not settings.allow_demo_mode:
        raise HTTPException(status_code=404, detail="Not available")
    return [
        {
            "username": "elena.vance",
            "password": "Procurement2026!",
            "full_name": "Elena Vance",
            "title": "VP Procurement",
            "role": "admin",
        },
        {
            "username": "marcus.chen",
            "password": "Analyst2026!",
            "full_name": "Marcus Chen",
            "title": "Lead Supply Risk Analyst",
            "role": "procurement_lead",
        },
        {
            "username": "priya.nair",
            "password": "Reviewer2026!",
            "full_name": "Priya Nair",
            "title": "Senior Buyer / Reviewer",
            "role": "reviewer",
        },
        {
            "username": "david.miller",
            "password": "Viewer2026!",
            "full_name": "David Miller",
            "title": "Plant Operations Viewer",
            "role": "viewer",
        },
    ]


# ============================================================================
# 3. Overview Dashboard
# ============================================================================
@app.get("/api/dashboard/overview", tags=["Dashboard"])
def get_dashboard_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    total_suppliers = db.query(Supplier).count()
    all_orders = db.query(PurchaseOrder).all()
    delivered_orders = [o for o in all_orders if o.status == "delivered"]
    open_orders = [o for o in all_orders if o.status in ("open", "in_transit")]

    hist_otd_rate = (
        sum(1 for o in delivered_orders if not o.is_delayed) / len(delivered_orders)
        if delivered_orders
        else 0.0
    )
    avg_hist_delay = (
        float(np.mean([o.delay_days for o in delivered_orders if o.delay_days and o.delay_days > 0]))
        if any(o.delay_days and o.delay_days > 0 for o in delivered_orders)
        else 0.0
    )

    preds = db.query(RiskPrediction).all()
    high_crit_preds = [
        p for p in preds if p.risk_category in ("high", "critical")
    ]
    total_at_risk_value = sum(p.expected_financial_impact for p in preds)
    total_open_value = sum(o.total_value for o in open_orders)

    pending_reviews = (
        db.query(ReviewQueueItem)
        .filter(ReviewQueueItem.status == "pending")
        .count()
    )
    open_alerts = (
        db.query(EarlyWarningAlert)
        .filter(EarlyWarningAlert.status == "open")
        .count()
    )

    champ = (
        db.query(ModelRegistry)
        .filter(ModelRegistry.is_champion.is_(True))
        .first()
    )
    champ_metrics = json.loads(champ.metrics_json)["test"] if champ else {}

    # Monthly historical OTD & Delay Rate Trend (last 12 months)
    monthly_buckets: dict[str, dict[str, int]] = {}
    for o in delivered_orders:
        ym = o.order_date.strftime("%Y-%m")
        b = monthly_buckets.setdefault(ym, {"total": 0, "delayed": 0})
        b["total"] += 1
        if o.is_delayed:
            b["delayed"] += 1

    sorted_months = sorted(monthly_buckets.keys())[-12:]
    monthly_trend = []
    for ym in sorted_months:
        tot = monthly_buckets[ym]["total"]
        dly = monthly_buckets[ym]["delayed"]
        monthly_trend.append(
            {
                "month": ym,
                "total_orders": tot,
                "delayed_orders": dly,
                "otd_rate_pct": round((1.0 - dly / max(1, tot)) * 100.0, 1),
                "delay_rate_pct": round((dly / max(1, tot)) * 100.0, 1),
            }
        )

    # Risk category breakdown of open orders
    risk_breakdown = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
    for p in preds:
        risk_breakdown[p.risk_category] = risk_breakdown.get(p.risk_category, 0) + 1

    # Regional risk exposure
    sups_by_id = {s.id: s for s in db.query(Supplier).all()}
    pos_by_id = {o.id: o for o in open_orders}
    region_stats: dict[str, dict[str, Any]] = {}
    for p in preds:
        po = pos_by_id.get(p.po_id)
        if not po:
            continue
        sup = sups_by_id.get(po.supplier_id)
        reg_name = sup.region if sup else "Global"
        st = region_stats.setdefault(
            reg_name, {"region": reg_name, "open_orders": 0, "high_risk_orders": 0, "prob_sum": 0.0, "exposure_usd": 0.0}
        )
        st["open_orders"] += 1
        if p.risk_category in ("high", "critical"):
            st["high_risk_orders"] += 1
        st["prob_sum"] += p.calibrated_probability
        st["exposure_usd"] += p.expected_financial_impact

    regional_breakdown = []
    for reg_name, st in region_stats.items():
        regional_breakdown.append(
            {
                "region": reg_name,
                "open_orders": st["open_orders"],
                "high_risk_orders": st["high_risk_orders"],
                "avg_delay_prob_pct": round((st["prob_sum"] / max(1, st["open_orders"])) * 100.0, 1),
                "exposure_usd": round(st["exposure_usd"], 2),
            }
        )
    regional_breakdown.sort(key=lambda x: x["avg_delay_prob_pct"], reverse=True)

    # Top 6 urgent review items
    top_reviews_orm = (
        db.query(ReviewQueueItem)
        .order_by(ReviewQueueItem.priority_rank.asc())
        .limit(6)
        .all()
    )
    prods_by_id = {pr.id: pr for pr in db.query(Product).all()}
    top_reviews = []
    for r in top_reviews_orm:
        po = pos_by_id.get(r.po_id) or db.query(PurchaseOrder).filter_by(id=r.po_id).first()
        sup = sups_by_id.get(po.supplier_id) if po else None
        prod = prods_by_id.get(po.product_id) if po else None
        top_reviews.append(
            {
                "id": r.id,
                "priority_rank": r.priority_rank,
                "po_id": r.po_id,
                "po_number": po.po_number if po else "",
                "supplier_name": sup.name if sup else "",
                "product_name": prod.name if prod else "",
                "promised_delivery_date": po.promised_delivery_date.isoformat() if po else "",
                "order_value": po.total_value if po else 0.0,
                "ml_calibrated_probability": r.ml_calibrated_probability,
                "business_priority_score": r.business_priority_score,
                "status": r.status,
                "recommended_action": r.recommended_action,
            }
        )

    return {
        "kpis": {
            "total_suppliers": total_suppliers,
            "total_historical_orders": len(delivered_orders),
            "active_open_orders": len(open_orders),
            "historical_otd_rate_pct": round(hist_otd_rate * 100.0, 1),
            "avg_delay_when_late_days": round(avg_hist_delay, 1),
            "high_or_critical_open_orders": len(high_crit_preds),
            "total_open_order_value_usd": round(total_open_value, 2),
            "expected_risk_exposure_usd": round(total_at_risk_value, 2),
            "pending_human_reviews": pending_reviews,
            "active_early_warnings": open_alerts,
            "champion_model_version": champ.model_version if champ else "None",
            "champion_algorithm": champ.display_name if champ else "None",
            "champion_test_roc_auc": champ_metrics.get("roc_auc", 0.0),
            "champion_test_pr_auc": champ_metrics.get("pr_auc", 0.0),
        },
        "monthly_trend": monthly_trend,
        "risk_breakdown": [
            {"category": "Low (<35%)", "key": "low", "count": risk_breakdown["low"]},
            {"category": "Moderate (35-60%)", "key": "moderate", "count": risk_breakdown["moderate"]},
            {"category": "High (60-80%)", "key": "high", "count": risk_breakdown["high"]},
            {"category": "Critical (>=80%)", "key": "critical", "count": risk_breakdown["critical"]},
        ],
        "regional_breakdown": regional_breakdown,
        "top_priority_reviews": top_reviews,
    }


# ============================================================================
# 4. Suppliers & Products Management + Supplier Performance Analytics
# ============================================================================
@app.get("/api/suppliers", response_model=list[SupplierOut], tags=["Suppliers"])
def list_suppliers(
    search: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[SupplierOut]:
    q = db.query(Supplier)
    if search:
        like_str = f"%{search.strip()}%"
        q = q.filter(
            (Supplier.name.ilike(like_str))
            | (Supplier.supplier_code.ilike(like_str))
            | (Supplier.country.ilike(like_str))
        )
    if region:
        q = q.filter(Supplier.region == region)
    if category:
        q = q.filter(Supplier.primary_category == category)
    if tier:
        q = q.filter(Supplier.tier == tier)

    suppliers = q.order_by(Supplier.supplier_code.asc()).all()

    # Pre-aggregate order metrics per supplier
    all_pos = db.query(PurchaseOrder).all()
    by_sup: dict[int, list[PurchaseOrder]] = {}
    for po in all_pos:
        by_sup.setdefault(po.supplier_id, []).append(po)

    results: list[SupplierOut] = []
    for s in suppliers:
        s_pos = by_sup.get(s.id, [])
        delivered = [o for o in s_pos if o.status == "delivered" and o.is_delayed is not None]
        open_cnt = sum(1 for o in s_pos if o.status in ("open", "in_transit"))
        otd = (
            round(sum(1 for o in delivered if not o.is_delayed) / len(delivered), 4)
            if delivered
            else None
        )
        avg_delay = (
            round(float(np.mean([o.delay_days or 0 for o in delivered])), 2)
            if delivered
            else None
        )
        out = SupplierOut.model_validate(s)
        out.historical_order_count = len(delivered)
        out.on_time_delivery_rate = otd
        out.avg_delay_days = avg_delay
        out.active_open_orders = open_cnt
        results.append(out)
    return results


@app.post("/api/suppliers", response_model=SupplierOut, status_code=201, tags=["Suppliers"])
def create_supplier(
    payload: SupplierCreate,
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> SupplierOut:
    existing = (
        db.query(Supplier)
        .filter(Supplier.supplier_code == payload.supplier_code)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Supplier with code '{payload.supplier_code}' already exists.",
        )
    sup = Supplier(**payload.model_dump())
    db.add(sup)
    db.commit()
    db.refresh(sup)

    # Also create a default Product for the new supplier so orders can immediately be placed
    prod = Product(
        sku=f"SKU-{sup.primary_category[:3].upper()}-{sup.id}01",
        name=f"{sup.primary_category} Assembly Unit",
        category=sup.primary_category,
        unit_cost=150.0,
        criticality_score=0.70,
        standard_lead_time_days=21,
        safety_stock_days=7,
        supplier_id=sup.id,
    )
    db.add(prod)
    db.commit()

    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action="CREATE_SUPPLIER",
        entity_type="Supplier",
        entity_id=str(sup.id),
        details={"supplier_code": sup.supplier_code, "name": sup.name},
    )
    out = SupplierOut.model_validate(sup)
    out.historical_order_count = 0
    return out


@app.put("/api/suppliers/{supplier_id}", response_model=SupplierOut, tags=["Suppliers"])
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> SupplierOut:
    sup = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not sup:
        raise HTTPException(status_code=404, detail="Supplier not found")
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(sup, k, v)
    db.commit()
    db.refresh(sup)
    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action="UPDATE_SUPPLIER",
        entity_type="Supplier",
        entity_id=str(sup.id),
        details=update_data,
    )
    return SupplierOut.model_validate(sup)


@app.get("/api/suppliers/{supplier_id}", tags=["Suppliers"])
def get_supplier_detail(supplier_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    sup = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not sup:
        raise HTTPException(status_code=404, detail="Supplier not found")

    pos = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.supplier_id == sup.id)
        .order_by(PurchaseOrder.order_date.desc())
        .all()
    )
    delivered = [o for o in pos if o.status == "delivered" and o.is_delayed is not None]
    open_orders = [o for o in pos if o.status in ("open", "in_transit")]
    otd_rate = (
        sum(1 for o in delivered if not o.is_delayed) / len(delivered)
        if delivered
        else None
    )
    delays = [o.delay_days or 0 for o in delivered]

    # Quarterly OTD history for this supplier
    q_buckets: dict[str, dict[str, int]] = {}
    for o in reversed(delivered):
        q_label = f"{o.order_date.year}-Q{(o.order_date.month - 1) // 3 + 1}"
        b = q_buckets.setdefault(q_label, {"total": 0, "on_time": 0})
        b["total"] += 1
        if not o.is_delayed:
            b["on_time"] += 1

    quarterly_trend = [
        {
            "quarter": q,
            "orders": vals["total"],
            "otd_rate_pct": round((vals["on_time"] / max(1, vals["total"])) * 100.0, 1),
        }
        for q, vals in q_buckets.items()
    ]

    prods = db.query(Product).filter(Product.supplier_id == sup.id).all()
    return {
        "supplier": SupplierOut.model_validate(sup),
        "metrics": {
            "completed_orders": len(delivered),
            "open_orders": len(open_orders),
            "on_time_delivery_rate": round(otd_rate, 4) if otd_rate is not None else None,
            "avg_delay_days": round(float(np.mean(delays)), 2) if delays else None,
            "lead_time_volatility_days": round(float(np.std(delays)), 2) if len(delays) >= 2 else None,
            "max_delay_days": int(max(delays)) if delays else 0,
            "is_cold_start": len(delivered) < 5,
        },
        "quarterly_trend": quarterly_trend,
        "products": [ProductOut.model_validate(p) for p in prods],
        "recent_orders": [
            {
                "id": o.id,
                "po_number": o.po_number,
                "order_date": o.order_date.isoformat(),
                "promised_delivery_date": o.promised_delivery_date.isoformat(),
                "actual_delivery_date": o.actual_delivery_date.isoformat() if o.actual_delivery_date else None,
                "quantity": o.quantity,
                "total_value": o.total_value,
                "delay_days": o.delay_days,
                "is_delayed": o.is_delayed,
                "status": o.status,
            }
            for o in pos[:25]
        ],
    }


@app.get("/api/analytics/suppliers", tags=["Analytics"])
def get_supplier_analytics(
    region: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Comprehensive historical supplier performance analytics by category, region, and time period."""
    q_sup = db.query(Supplier)
    if region:
        q_sup = q_sup.filter(Supplier.region == region)
    if category:
        q_sup = q_sup.filter(Supplier.primary_category == category)
    suppliers = {s.id: s for s in q_sup.all()}

    pos = [
        o
        for o in db.query(PurchaseOrder).filter(PurchaseOrder.status == "delivered").all()
        if o.supplier_id in suppliers and o.is_delayed is not None
    ]

    # 1. Breakdown by Product Category
    cat_map: dict[str, list[PurchaseOrder]] = {}
    for o in pos:
        sup = suppliers[o.supplier_id]
        cat_map.setdefault(sup.primary_category, []).append(o)

    by_category: list[dict[str, Any]] = []
    for cat_name, orders_list in cat_map.items():
        delays = [o.delay_days or 0 for o in orders_list]
        late_only = [d for d in delays if d > 0]
        otd = sum(1 for o in orders_list if not o.is_delayed) / max(1, len(orders_list))
        by_category.append(
            {
                "category": cat_name,
                "total_orders": len(orders_list),
                "otd_rate_pct": round(otd * 100.0, 1),
                "delay_frequency_pct": round((1.0 - otd) * 100.0, 1),
                "avg_delay_when_late_days": round(float(np.mean(late_only)), 1) if late_only else 0.0,
                "lead_time_std_days": round(float(np.std(delays)), 2) if len(delays) >= 2 else 0.0,
            }
        )
    by_category.sort(key=lambda x: float(x["otd_rate_pct"]))

    # 2. Breakdown by Region
    reg_map: dict[str, list[PurchaseOrder]] = {}
    for o in pos:
        sup = suppliers[o.supplier_id]
        reg_map.setdefault(sup.region, []).append(o)

    by_region: list[dict[str, Any]] = []
    for reg_name, orders_list in reg_map.items():
        delays = [o.delay_days or 0 for o in orders_list]
        late_only = [d for d in delays if d > 0]
        otd = sum(1 for o in orders_list if not o.is_delayed) / max(1, len(orders_list))
        by_region.append(
            {
                "region": reg_name,
                "total_orders": len(orders_list),
                "otd_rate_pct": round(otd * 100.0, 1),
                "delay_frequency_pct": round((1.0 - otd) * 100.0, 1),
                "avg_delay_when_late_days": round(float(np.mean(late_only)), 1) if late_only else 0.0,
                "lead_time_std_days": round(float(np.std(delays)), 2) if len(delays) >= 2 else 0.0,
            }
        )
    by_region.sort(key=lambda x: float(x["otd_rate_pct"]))

    # 3. Supplier Leaderboard / Scorecard (OTD vs Lead-Time Variability)
    sup_orders: dict[int, list[PurchaseOrder]] = {}
    for o in pos:
        sup_orders.setdefault(o.supplier_id, []).append(o)

    scorecards = []
    for sup_id, sup in suppliers.items():
        s_list = sup_orders.get(sup_id, [])
        if not s_list:
            scorecards.append(
                {
                    "supplier_id": sup.id,
                    "supplier_code": sup.supplier_code,
                    "supplier_name": sup.name,
                    "region": sup.region,
                    "category": sup.primary_category,
                    "tier": sup.tier,
                    "completed_orders": 0,
                    "otd_rate_pct": None,
                    "avg_delay_days": None,
                    "lead_time_std_days": None,
                    "financial_health_score": sup.financial_health_score,
                    "is_cold_start": True,
                }
            )
            continue
        delays = [o.delay_days or 0 for o in s_list]
        otd = sum(1 for o in s_list if not o.is_delayed) / len(s_list)
        scorecards.append(
            {
                "supplier_id": sup.id,
                "supplier_code": sup.supplier_code,
                "supplier_name": sup.name,
                "region": sup.region,
                "category": sup.primary_category,
                "tier": sup.tier,
                "completed_orders": len(s_list),
                "otd_rate_pct": round(otd * 100.0, 1),
                "avg_delay_days": round(float(np.mean(delays)), 2),
                "lead_time_std_days": round(float(np.std(delays)), 2) if len(delays) >= 2 else 0.0,
                "financial_health_score": sup.financial_health_score,
                "is_cold_start": len(s_list) < 5,
            }
        )

    # 4. Delay Duration Distribution Histogram
    delay_bins = [
        ("On-Time / Early (<=0d)", -999, 0),
        ("Minor Slip (1-3d)", 1, 3),
        ("Moderate Delay (4-7d)", 4, 7),
        ("Severe Delay (8-14d)", 8, 14),
        ("Critical Disruption (15d+)", 15, 999),
    ]
    all_delays = [o.delay_days or 0 for o in pos]
    delay_distribution = []
    for label, lo, hi in delay_bins:
        cnt = sum(1 for d in all_delays if lo <= d <= hi)
        delay_distribution.append(
            {
                "bucket": label,
                "count": cnt,
                "percentage": round((cnt / max(1, len(all_delays))) * 100.0, 1),
            }
        )

    return {
        "total_delivered_analyzed": len(pos),
        "by_category": by_category,
        "by_region": by_region,
        "delay_distribution": delay_distribution,
        "supplier_scorecards": scorecards,
    }


@app.get("/api/products", response_model=list[ProductOut], tags=["Products"])
def list_products(
    supplier_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ProductOut]:
    q = db.query(Product)
    if supplier_id is not None:
        q = q.filter(Product.supplier_id == supplier_id)
    return [ProductOut.model_validate(p) for p in q.order_by(Product.sku.asc()).all()]


@app.post("/api/products", response_model=ProductOut, status_code=201, tags=["Products"])
def create_product(
    payload: ProductCreate,
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> ProductOut:
    prod = Product(**payload.model_dump())
    db.add(prod)
    db.commit()
    db.refresh(prod)
    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action="CREATE_PRODUCT",
        entity_type="Product",
        entity_id=str(prod.id),
        details={"sku": prod.sku, "name": prod.name},
    )
    return ProductOut.model_validate(prod)


# ============================================================================
# 5. Purchase Orders CRUD, Filtering, Pagination & Events
# ============================================================================
@app.get("/api/orders", tags=["Purchase Orders"])
def list_purchase_orders(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    supplier_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
    risk_category: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=250),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    q = db.query(PurchaseOrder)
    if status_filter:
        if status_filter == "active":
            q = q.filter(PurchaseOrder.status.in_(["open", "in_transit"]))
        else:
            q = q.filter(PurchaseOrder.status == status_filter)
    if supplier_id is not None:
        q = q.filter(PurchaseOrder.supplier_id == supplier_id)
    if search:
        like_str = f"%{search.strip()}%"
        q = q.filter(PurchaseOrder.po_number.ilike(like_str))

    if risk_category:
        pred_po_ids = [
            r.po_id
            for r in db.query(RiskPrediction.po_id)
            .filter(RiskPrediction.risk_category == risk_category)
            .all()
        ]
        q = q.filter(PurchaseOrder.id.in_(pred_po_ids))

    total = q.count()
    orders = (
        q.order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    sups = {s.id: s for s in db.query(Supplier).all()}
    prods = {p.id: p for p in db.query(Product).all()}
    preds_by_po = {
        pr.po_id: pr
        for pr in db.query(RiskPrediction)
        .filter(RiskPrediction.po_id.in_([o.id for o in orders]))
        .all()
    }

    items: list[PurchaseOrderOut] = []
    for o in orders:
        sup = sups.get(o.supplier_id)
        prod = prods.get(o.product_id)
        pred = preds_by_po.get(o.id)
        out = PurchaseOrderOut.model_validate(o)
        if sup:
            out.supplier_name = sup.name
            out.supplier_code = sup.supplier_code
            out.supplier_region = sup.region
        if prod:
            out.product_name = prod.name
            out.product_sku = prod.sku
            out.product_category = prod.category
        if pred:
            out.latest_prediction = {
                "calibrated_probability": pred.calibrated_probability,
                "risk_category": pred.risk_category,
                "business_priority_score": pred.business_priority_score,
                "expected_delay_days": pred.expected_delay_days,
                "reliability_status": pred.reliability_status,
            }
        items.append(out)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@app.post("/api/orders", response_model=PurchaseOrderOut, status_code=201, tags=["Purchase Orders"])
def create_purchase_order(
    payload: PurchaseOrderCreate,
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> PurchaseOrderOut:
    existing = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.po_number == payload.po_number)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Purchase order '{payload.po_number}' already exists.",
        )

    sup = db.query(Supplier).filter(Supplier.id == payload.supplier_id).first()
    prod = db.query(Product).filter(Product.id == payload.product_id).first()
    if not sup or not prod:
        raise HTTPException(status_code=400, detail="Invalid supplier_id or product_id")

    promised_lead = max(1, (payload.promised_delivery_date - payload.order_date).days)
    actual_lead = (
        (payload.actual_delivery_date - payload.order_date).days
        if payload.actual_delivery_date
        else None
    )
    delay_days = (
        actual_lead - promised_lead if actual_lead is not None else None
    )
    is_delayed = (delay_days > 0) if delay_days is not None else None
    total_val = round(payload.quantity * payload.unit_price, 2)

    po = PurchaseOrder(
        po_number=payload.po_number,
        supplier_id=payload.supplier_id,
        product_id=payload.product_id,
        order_date=payload.order_date,
        promised_delivery_date=payload.promised_delivery_date,
        actual_delivery_date=payload.actual_delivery_date,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total_value=total_val,
        promised_lead_time_days=promised_lead,
        actual_lead_time_days=actual_lead,
        delay_days=delay_days,
        is_delayed=is_delayed,
        status=payload.status,
        shipping_mode=payload.shipping_mode,
        origin_port=payload.origin_port,
        destination_plant=payload.destination_plant,
        urgency_level=payload.urgency_level,
        notes=payload.notes,
    )
    db.add(po)
    db.commit()
    db.refresh(po)

    # Automatically score newly created open order and update review queue
    pred_dict = None
    if po.status in ("open", "in_transit"):
        pred_dict = predict_order_risk(db=db, po=po, persist=True)
        refresh_predictions_and_queues(db=db)

    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action="CREATE_PURCHASE_ORDER",
        entity_type="PurchaseOrder",
        entity_id=str(po.id),
        details={"po_number": po.po_number, "total_value": po.total_value},
    )

    out = PurchaseOrderOut.model_validate(po)
    out.supplier_name = sup.name
    out.supplier_code = sup.supplier_code
    out.product_name = prod.name
    out.product_sku = prod.sku
    if pred_dict:
        out.latest_prediction = {
            "calibrated_probability": pred_dict["calibrated_probability"],
            "risk_category": pred_dict["risk_category"],
            "business_priority_score": pred_dict["business_priority_score"],
            "expected_delay_days": pred_dict["expected_delay_days"],
            "reliability_status": pred_dict["reliability_status"],
        }
    return out


@app.put("/api/orders/{po_id}", response_model=PurchaseOrderOut, tags=["Purchase Orders"])
def update_purchase_order(
    po_id: int,
    payload: PurchaseOrderUpdate,
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> PurchaseOrderOut:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(po, k, v)

    po.promised_lead_time_days = max(1, (po.promised_delivery_date - po.order_date).days)
    po.total_value = round(po.quantity * po.unit_price, 2)
    if po.actual_delivery_date:
        po.actual_lead_time_days = (po.actual_delivery_date - po.order_date).days
        po.delay_days = po.actual_lead_time_days - po.promised_lead_time_days
        po.is_delayed = po.delay_days > 0
        # Preserve the operational milestone as an auditable delivery event.
        if "actual_delivery_date" in update_data:
            db.add(
                DeliveryEvent(
                    po_id=po.id,
                    event_type="delivered",
                    event_timestamp=datetime.now(timezone.utc),
                    location=po.destination_plant,
                    delay_days_reported=max(0, po.delay_days or 0),
                    severity="info" if not po.is_delayed else "warning",
                    notes=(
                        "Actual delivery recorded by "
                        f"{current_user.username} ({po.actual_delivery_date.isoformat()})."
                    ),
                )
            )
    else:
        po.actual_lead_time_days = None
        po.delay_days = None
        po.is_delayed = None

    db.commit()
    db.refresh(po)

    if po.status in ("open", "in_transit"):
        predict_order_risk(db=db, po=po, persist=True)
    else:
        # Closed orders are no longer actionable: remove stale predictions and let the
        # queue/alerts engine resolve their review items.
        db.query(RiskPrediction).filter(RiskPrediction.po_id == po.id).delete()
        db.commit()
    refresh_predictions_and_queues(db=db)

    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action="UPDATE_PURCHASE_ORDER",
        entity_type="PurchaseOrder",
        entity_id=str(po.id),
        details=update_data,
    )
    return PurchaseOrderOut.model_validate(po)


@app.get("/api/orders/{po_id}/events", tags=["Purchase Orders"])
def list_order_events(
    po_id: int, db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    events = (
        db.query(DeliveryEvent)
        .filter(DeliveryEvent.po_id == po_id)
        .order_by(DeliveryEvent.event_timestamp.asc())
        .all()
    )
    return [
        {
            "id": ev.id,
            "po_id": ev.po_id,
            "event_type": ev.event_type,
            "event_timestamp": ev.event_timestamp.isoformat(),
            "location": ev.location,
            "delay_days_reported": ev.delay_days_reported,
            "severity": ev.severity,
            "notes": ev.notes,
        }
        for ev in events
    ]


# ============================================================================
# 6. Risk Predictions & Local Explainability
# ============================================================================
@app.get("/api/predictions", tags=["Risk Predictions"])
def list_risk_predictions(
    risk_category: Optional[str] = Query(default=None),
    reliability_status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    q = db.query(RiskPrediction)
    if risk_category:
        q = q.filter(RiskPrediction.risk_category == risk_category)
    if reliability_status:
        q = q.filter(RiskPrediction.reliability_status == reliability_status)

    preds = q.order_by(RiskPrediction.business_priority_score.desc()).all()
    pos = {p.id: p for p in db.query(PurchaseOrder).all()}
    sups = {s.id: s for s in db.query(Supplier).all()}
    prods = {pr.id: pr for pr in db.query(Product).all()}

    results = []
    for pred in preds:
        po = pos.get(pred.po_id)
        if not po:
            continue
        sup = sups.get(po.supplier_id)
        prod = prods.get(po.product_id)
        if search:
            s_lower = search.strip().lower()
            haystack = f"{po.po_number} {sup.name if sup else ''} {prod.name if prod else ''}".lower()
            if s_lower not in haystack:
                continue

        results.append(
            {
                "id": pred.id,
                "po_id": po.id,
                "po_number": po.po_number,
                "supplier_id": po.supplier_id,
                "supplier_name": sup.name if sup else "",
                "supplier_code": sup.supplier_code if sup else "",
                "supplier_region": sup.region if sup else "",
                "product_id": po.product_id,
                "product_name": prod.name if prod else "",
                "product_category": prod.category if prod else "",
                "order_date": po.order_date.isoformat(),
                "promised_delivery_date": po.promised_delivery_date.isoformat(),
                "order_value": po.total_value,
                "urgency_level": po.urgency_level,
                "shipping_mode": po.shipping_mode,
                "model_version": pred.model_version,
                "algorithm_name": pred.algorithm_name,
                "predicted_at": pred.predicted_at.isoformat(),
                "as_of_date": pred.as_of_date.isoformat(),
                "raw_probability": pred.raw_probability,
                "calibrated_probability": pred.calibrated_probability,
                "risk_category": pred.risk_category,
                "threshold_used": pred.threshold_used,
                "expected_delay_days": pred.expected_delay_days,
                "expected_financial_impact": pred.expected_financial_impact,
                "business_priority_score": pred.business_priority_score,
                "reliability_status": pred.reliability_status,
                "reliability_warnings": json.loads(pred.reliability_warnings_json),
                "top_contributors": json.loads(pred.top_contributors_json),
                "historical_context": json.loads(pred.historical_context_json),
                "feature_snapshot": json.loads(pred.feature_snapshot_json),
                "explanation_method": pred.explanation_method,
                "explanation_limitations": (
                    "Feature contributions reflect associative statistical patterns learned from historical "
                    "orders prior to the prediction date. They do not establish causal effects."
                ),
            }
        )
    return results


@app.get("/api/predictions/order/{po_id}", tags=["Risk Predictions"])
def get_or_compute_order_prediction(
    po_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return predict_order_risk(db=db, po=po, persist=po.status in ("open", "in_transit"))


@app.post("/api/predictions/refresh", tags=["Risk Predictions"])
def refresh_all_open_predictions(
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    res = refresh_predictions_and_queues(db=db)
    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action="BATCH_REFRESH_PREDICTIONS",
        entity_type="RiskPrediction",
        entity_id="all_open",
        details=res,
    )
    return res


# ============================================================================
# 7. Early Warning Center
# ============================================================================
@app.get("/api/alerts", tags=["Early Warnings"])
def list_early_warning_alerts(
    severity: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    q = db.query(EarlyWarningAlert)
    if severity:
        q = q.filter(EarlyWarningAlert.severity == severity)
    if status_filter:
        q = q.filter(EarlyWarningAlert.status == status_filter)

    alerts = q.order_by(EarlyWarningAlert.review_priority.asc()).all()
    pos = {p.id: p for p in db.query(PurchaseOrder).all()}
    sups = {s.id: s for s in db.query(Supplier).all()}
    preds = {pr.id: pr for pr in db.query(RiskPrediction).all()}

    out = []
    for al in alerts:
        po = pos.get(al.po_id)
        sup = sups.get(po.supplier_id) if po else None
        pred = preds.get(al.prediction_id) if al.prediction_id else None

        if search:
            s_low = search.strip().lower()
            if s_low not in f"{al.title} {al.description} {sup.name if sup else ''}".lower():
                continue

        out.append(
            {
                "id": al.id,
                "po_id": al.po_id,
                "po_number": po.po_number if po else "",
                "supplier_name": sup.name if sup else "",
                "supplier_region": sup.region if sup else "",
                "severity": al.severity,
                "title": al.title,
                "description": al.description,
                "review_priority": al.review_priority,
                "due_date": al.due_date.isoformat(),
                "status": al.status,
                "acknowledged_by": al.acknowledged_by,
                "acknowledged_at": al.acknowledged_at.isoformat() if al.acknowledged_at else None,
                "resolution_notes": al.resolution_notes,
                "calibrated_probability": pred.calibrated_probability if pred else None,
                "expected_financial_impact": pred.expected_financial_impact if pred else None,
                "historical_context": json.loads(pred.historical_context_json) if pred else {},
            }
        )
    return out


@app.post("/api/alerts/{alert_id}/action", tags=["Early Warnings"])
def update_alert_status(
    alert_id: int,
    payload: AlertActionRequest,
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    al = db.query(EarlyWarningAlert).filter(EarlyWarningAlert.id == alert_id).first()
    if not al:
        raise HTTPException(status_code=404, detail="Alert not found")

    al.status = payload.status
    al.acknowledged_by = current_user.username
    al.acknowledged_at = datetime.now(timezone.utc)
    if payload.resolution_notes is not None:
        al.resolution_notes = payload.resolution_notes
    db.commit()
    db.refresh(al)

    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action=f"ALERT_{payload.status.upper()}",
        entity_type="EarlyWarningAlert",
        entity_id=str(al.id),
        details={"po_id": al.po_id, "status": payload.status, "notes": payload.resolution_notes},
    )
    return {
        "id": al.id,
        "status": al.status,
        "acknowledged_by": al.acknowledged_by,
        "acknowledged_at": al.acknowledged_at.isoformat() if al.acknowledged_at else None,
        "resolution_notes": al.resolution_notes,
    }


# ============================================================================
# 8. Human Review Queue, Business Rules & Audit History
# ============================================================================
@app.get("/api/reviews", tags=["Human Review Queue"])
def list_review_queue(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    within_capacity_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    q = db.query(ReviewQueueItem)
    if status_filter:
        q = q.filter(ReviewQueueItem.status == status_filter)
    if within_capacity_only:
        q = q.filter(ReviewQueueItem.within_reviewer_capacity.is_(True))

    items_orm = q.order_by(ReviewQueueItem.priority_rank.asc()).all()
    pos = {p.id: p for p in db.query(PurchaseOrder).all()}
    sups = {s.id: s for s in db.query(Supplier).all()}
    prods = {pr.id: pr for pr in db.query(Product).all()}
    preds = {pr.id: pr for pr in db.query(RiskPrediction).all()}
    rules = get_business_rules(db)

    items = []
    for r in items_orm:
        po = pos.get(r.po_id)
        sup = sups.get(po.supplier_id) if po else None
        prod = prods.get(po.product_id) if po else None
        pred = preds.get(r.prediction_id) if r.prediction_id else None
        items.append(
            {
                "id": r.id,
                "po_id": r.po_id,
                "po_number": po.po_number if po else "",
                "supplier_id": po.supplier_id if po else None,
                "supplier_name": sup.name if sup else "",
                "supplier_region": sup.region if sup else "",
                "product_name": prod.name if prod else "",
                "product_category": prod.category if prod else "",
                "promised_delivery_date": po.promised_delivery_date.isoformat() if po else "",
                "order_value": po.total_value if po else 0.0,
                "urgency_level": po.urgency_level if po else "standard",
                "priority_rank": r.priority_rank,
                "within_reviewer_capacity": r.within_reviewer_capacity,
                "business_priority_score": r.business_priority_score,
                "ml_calibrated_probability": r.ml_calibrated_probability,
                "operational_impact_score": r.operational_impact_score,
                "urgency_score": r.urgency_score,
                "prioritization_rationale": r.prioritization_rationale,
                "recommended_action": r.recommended_action,
                "reliability_status": pred.reliability_status if pred else "reliable",
                "reliability_warnings": json.loads(pred.reliability_warnings_json) if pred else [],
                "status": r.status,
                "assigned_reviewer": r.assigned_reviewer,
                "decision": r.decision,
                "decision_reason": r.decision_reason,
                "decision_notes": r.decision_notes,
                "decided_by": r.decided_by,
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            }
        )

    all_items = db.query(ReviewQueueItem).all()
    summary = {
        "total_in_queue": len(all_items),
        "within_capacity": sum(1 for x in all_items if x.within_reviewer_capacity),
        "pending": sum(1 for x in all_items if x.status == "pending"),
        "accepted": sum(1 for x in all_items if x.status == "accepted"),
        "investigating": sum(1 for x in all_items if x.status == "investigating"),
        "deferred": sum(1 for x in all_items if x.status == "deferred"),
        "dismissed": sum(1 for x in all_items if x.status == "dismissed"),
        "escalated": sum(1 for x in all_items if x.status == "escalated"),
        "resolved": sum(1 for x in all_items if x.status == "resolved"),
    }

    return {
        "rules": rules,
        "summary": summary,
        "items": items,
    }


@app.post("/api/reviews/{review_id}/decision", tags=["Human Review Queue"])
def record_review_decision(
    review_id: int,
    payload: ReviewDecisionRequest,
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.query(ReviewQueueItem).filter(ReviewQueueItem.id == review_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review queue item not found")

    now = datetime.now(timezone.utc)
    if payload.decision != "annotated":
        item.status = payload.decision
    item.decision = payload.decision
    item.decision_reason = payload.decision_reason
    item.decision_notes = payload.decision_notes
    if payload.assigned_reviewer:
        item.assigned_reviewer = payload.assigned_reviewer
    item.decided_by = current_user.username
    item.decided_at = now
    item.updated_at = now

    db.commit()
    db.refresh(item)

    audit = record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action=f"REVIEW_DECISION_{payload.decision.upper()}",
        entity_type="ReviewQueueItem",
        entity_id=str(item.id),
        details={
            "po_id": item.po_id,
            "decision": payload.decision,
            "reason": payload.decision_reason,
            "notes": payload.decision_notes,
            "ml_calibrated_probability": item.ml_calibrated_probability,
            "business_priority_score": item.business_priority_score,
        },
    )

    return {
        "id": item.id,
        "po_id": item.po_id,
        "status": item.status,
        "decision": item.decision,
        "decision_reason": item.decision_reason,
        "decision_notes": item.decision_notes,
        "decided_by": item.decided_by,
        "decided_at": item.decided_at.isoformat(),
        "audit_log_id": audit.id,
    }


@app.get("/api/rules", response_model=BusinessRuleConfigSchema, tags=["Human Review Queue"])
def get_prioritization_rules_endpoint(db: Session = Depends(get_db)) -> BusinessRuleConfigSchema:
    rules = get_business_rules(db)
    return BusinessRuleConfigSchema(**rules)


@app.put("/api/rules", response_model=BusinessRuleConfigSchema, tags=["Human Review Queue"])
def update_prioritization_rules_endpoint(
    payload: BusinessRuleConfigSchema,
    current_user: User = Depends(require_min_role("procurement_lead")),
    db: Session = Depends(get_db),
) -> BusinessRuleConfigSchema:
    updated = update_business_rules(
        db=db,
        new_rules=payload.model_dump(),
        actor=current_user.username,
        role=current_user.role,
    )
    return BusinessRuleConfigSchema(**updated)


@app.get("/api/audit-logs", tags=["Human Review Queue"])
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_min_role("viewer")),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log_item.id,
            "timestamp": log_item.timestamp.isoformat(),
            "actor": log_item.actor,
            "role": log_item.role,
            "action": log_item.action,
            "entity_type": log_item.entity_type,
            "entity_id": log_item.entity_id,
            "details": json.loads(log_item.details_json),
        }
        for log_item in logs
    ]


# ============================================================================
# 9. Model Evaluation, Training, Promotion & Monitoring
# ============================================================================
@app.get("/api/models", tags=["Machine Learning"])
def list_models(db: Session = Depends(get_db)) -> dict[str, Any]:
    models = (
        db.query(ModelRegistry)
        .order_by(ModelRegistry.id.desc())
        .all()
    )
    # Return the latest evaluation cohort (the most recent run of the 3 algorithms)
    latest_by_algo: dict[str, ModelRegistry] = {}
    for m in models:
        if m.algorithm_name not in latest_by_algo:
            latest_by_algo[m.algorithm_name] = m

    cohort = list(latest_by_algo.values())
    cohort.sort(key=lambda x: (not x.is_champion, x.algorithm_name))

    serialized = []
    baselines: dict[str, Any] = {}
    for m in cohort:
        m_bundle = json.loads(m.metrics_json)
        if not baselines and "baselines" in m_bundle:
            baselines = m_bundle["baselines"]
        serialized.append(
            {
                "id": m.id,
                "model_version": m.model_version,
                "algorithm_name": m.algorithm_name,
                "display_name": m.display_name,
                "is_champion": m.is_champion,
                "status": m.status,
                "created_at": m.created_at.isoformat(),
                "training_window": {
                    "train_start": m.training_window_start.isoformat(),
                    "train_end": m.training_window_end.isoformat(),
                    "val_end": m.validation_window_end.isoformat(),
                    "test_end": m.test_window_end.isoformat(),
                    "train_rows": m.train_row_count,
                    "val_rows": m.val_row_count,
                    "test_rows": m.test_row_count,
                },
                "composite_selection_score": m_bundle.get("composite_selection_score"),
                "validation_metrics": m_bundle.get("validation"),
                "test_metrics": m_bundle.get("test"),
                "calibration_curve": json.loads(m.calibration_json),
                "feature_importance": json.loads(m.feature_importance_json),
                "hyperparameters": json.loads(m.hyperparameters_json),
                "unseen_supplier_metrics": json.loads(m.unseen_supplier_metrics_json),
                "segment_analysis": json.loads(m.segment_analysis_json),
                "selection_rationale": m.selection_rationale,
                "artifact_sha256": m.artifact_sha256,
            }
        )

    return {
        "models": serialized,
        "baselines": baselines,
        "leakage_safeguards": [
            "Point-in-time feature calculation strictly restricts supplier history to actual_delivery_date < order_date",
            "Forbidden outcome columns (actual_delivery_date, delay_days, is_delayed) structurally excluded from model pipeline",
            "Chronological 70% Train / 15% Validation / 15% Unseen Test split with zero temporal overlap",
            "SHA-256 cryptographic hash verified prior to loading any serialized joblib artifact",
        ],
    }


@app.post("/api/models/train", tags=["Machine Learning"])
def trigger_model_training(
    current_user: User = Depends(require_min_role("procurement_lead")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    train_res = train_and_evaluate_all_models(db=db, random_seed=settings.random_seed)
    queue_res = refresh_predictions_and_queues(db=db)
    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action="TRAIN_EVALUATE_MODELS",
        entity_type="ModelRegistry",
        entity_id=train_res["champion_model_version"],
        details=train_res,
    )
    return {
        "training": train_res,
        "queue_sync": queue_res,
    }


@app.post("/api/models/{model_version}/promote", tags=["Machine Learning"])
def promote_model_to_champion(
    model_version: str,
    current_user: User = Depends(require_min_role("procurement_lead")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    target = (
        db.query(ModelRegistry)
        .filter(ModelRegistry.model_version == model_version)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Model version not found")

    db.query(ModelRegistry).update({"is_champion": False, "status": "evaluated"})
    target.is_champion = True
    target.status = "champion"
    db.commit()

    sync_res = refresh_predictions_and_queues(db=db, model_version=target.model_version)
    record_audit_log(
        db=db,
        actor=current_user.username,
        role=current_user.role,
        action="PROMOTE_CHAMPION_MODEL",
        entity_type="ModelRegistry",
        entity_id=target.model_version,
        details={"promoted_model": target.model_version, "algorithm": target.algorithm_name},
    )
    return {
        "status": "promoted",
        "champion_model_version": target.model_version,
        "algorithm_name": target.algorithm_name,
        "queue_sync": sync_res,
    }


@app.get("/api/models/monitoring", tags=["Machine Learning"])
def get_model_monitoring(db: Session = Depends(get_db)) -> dict[str, Any]:
    return compute_monitoring_diagnostics(db=db)


# ============================================================================
# 10. Scenario Analysis (What-If Simulator)
# ============================================================================
@app.post("/api/scenarios/simulate", tags=["Scenario Analysis"])
def simulate_scenario_endpoint(
    payload: ScenarioRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return run_scenario_simulation(
            db=db,
            po_id=payload.po_id,
            supplier_id=payload.supplier_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            promised_lead_time_days=payload.promised_lead_time_days,
            shipping_mode=payload.shipping_mode,
            urgency_level=payload.urgency_level,
            order_date=payload.order_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ============================================================================
# 11. Data Import (CSV/Excel) & Report Exports (CSV/PDF)
# ============================================================================
@app.post("/api/import/orders", tags=["Data Import & Export"])
async def import_orders_endpoint(
    file: UploadFile = File(...),
    dry_run: bool = Form(default=True),
    duplicate_strategy: str = Form(default="skip"),
    column_mapping_json: Optional[str] = Form(default=None),
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 15MB upload limit")

    try:
        df_raw = parse_uploaded_tabular_file(content, file.filename or "upload.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    col_map = None
    if column_mapping_json:
        try:
            col_map = json.loads(column_mapping_json)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid column_mapping_json") from exc

    result = preview_or_commit_order_import(
        db=db,
        df_raw=df_raw,
        column_mapping=col_map,
        duplicate_strategy=duplicate_strategy,
        dry_run=dry_run,
    )

    if not dry_run and (result["created_count"] > 0 or result["updated_count"] > 0):
        refresh_predictions_and_queues(db=db)
        record_audit_log(
            db=db,
            actor=current_user.username,
            role=current_user.role,
            action="BULK_IMPORT_ORDERS",
            entity_type="PurchaseOrder",
            entity_id=file.filename or "upload",
            details={
                "created": result["created_count"],
                "updated": result["updated_count"],
                "skipped": result["skipped_count"],
                "errors": result["error_rows_count"],
            },
        )
    return result


@app.get("/api/import/template", tags=["Data Import & Export"])
def download_import_template() -> Response:
    csv_text = generate_sample_import_template_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=purchase_orders_import_template.csv"
        },
    )


@app.get("/api/reports/predictions.csv", tags=["Data Import & Export"])
def download_predictions_csv(db: Session = Depends(get_db)) -> Response:
    csv_text = export_predictions_csv(db)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=supplier_risk_predictions.csv"
        },
    )


@app.get("/api/reports/orders.csv", tags=["Data Import & Export"])
def download_orders_csv(db: Session = Depends(get_db)) -> Response:
    return Response(
        content=export_orders_csv(db),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=purchase_order_ledger.csv"
        },
    )


@app.get("/api/reports/suppliers.csv", tags=["Data Import & Export"])
def download_suppliers_csv(db: Session = Depends(get_db)) -> Response:
    return Response(
        content=export_suppliers_csv(db),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=supplier_scorecards.csv"
        },
    )


@app.get("/api/reports/executive.pdf", tags=["Data Import & Export"])
def download_executive_pdf(db: Session = Depends(get_db)) -> Response:
    pdf_bytes = generate_executive_pdf_report(db)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=executive_supplier_risk_report.pdf"
        },
    )


# ============================================================================
# 12. Optional AI / LLM Provider Settings & Grounded Analyst Assistant
# ============================================================================
@app.get("/api/ai/config", response_model=AIProviderConfigOut, tags=["AI Intelligence"])
def get_ai_provider_settings(db: Session = Depends(get_db)) -> AIProviderConfigOut:
    cfg = get_ai_config(db)
    return AIProviderConfigOut(**serialize_ai_config(cfg))


@app.get("/api/ai/providers", tags=["AI Intelligence"])
def get_ai_providers() -> list[dict[str, Any]]:
    """List supported provider presets so the UI can offer one-click setup."""
    return list_provider_presets()


@app.get("/api/ai/models", tags=["AI Intelligence"])
def get_ai_models(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Discover models available from the currently configured provider."""
    return discover_provider_models(db)


@app.put("/api/ai/config", response_model=AIProviderConfigOut, tags=["AI Intelligence"])
def update_ai_provider_settings(
    payload: AIProviderConfigUpdate,
    current_user: User = Depends(require_min_role("procurement_lead")),
    db: Session = Depends(get_db),
) -> AIProviderConfigOut:
    try:
        updated = update_ai_config(
            db=db,
            payload=payload.model_dump(),
            actor=current_user.username,
            role=current_user.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AIProviderConfigOut(**updated)


@app.post("/api/ai/test-connection", tags=["AI Intelligence"])
def test_ai_connection_endpoint(
    current_user: User = Depends(require_min_role("reviewer")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return test_ai_provider_connection(db=db)


@app.post("/api/ai/briefing", tags=["AI Intelligence"])
def generate_ai_briefing_endpoint(
    payload: AIExplanationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return generate_grounded_analyst_briefing(
        db=db,
        po_id=payload.po_id,
        supplier_id=payload.supplier_id,
        question=payload.question,
    )


# ============================================================================
# 13. Optional Production Static SPA Hosting (when frontend/dist is built)
# ============================================================================
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (_FRONTEND_DIST / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="frontend-assets",
    )

    @app.get("/", include_in_schema=False)
    def serve_spa_index() -> FileResponse:
        return FileResponse(str(_FRONTEND_DIST / "index.html"))

