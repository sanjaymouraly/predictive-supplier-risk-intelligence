"""SQLAlchemy ORM models for Predictive Supplier Risk Intelligence."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """System user with role-based access control."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    hashed_password: Mapped[str] = mapped_column(String(256))
    # Roles: admin, procurement_lead, reviewer, viewer
    role: Mapped[str] = mapped_column(String(32), default="reviewer", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Supplier(Base):
    """Manufacturing supplier master record."""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    supplier_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    country: Mapped[str] = mapped_column(String(64), index=True)
    region: Mapped[str] = mapped_column(String(64), index=True)
    primary_category: Mapped[str] = mapped_column(String(64), index=True)
    tier: Mapped[str] = mapped_column(String(16), default="Tier 1")
    capacity_index: Mapped[float] = mapped_column(Float, default=1.0)
    reliability_baseline: Mapped[float] = mapped_column(Float, default=0.85)
    lead_time_std_days: Mapped[float] = mapped_column(Float, default=2.5)
    financial_health_score: Mapped[float] = mapped_column(Float, default=75.0)
    geopolitical_risk_index: Mapped[float] = mapped_column(Float, default=0.25)
    contact_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    onboarding_date: Mapped[date] = mapped_column(Date, default=date(2023, 1, 1))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    products: Mapped[list[Product]] = relationship(
        "Product", back_populates="supplier", cascade="all, delete-orphan"
    )
    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        "PurchaseOrder", back_populates="supplier", cascade="all, delete-orphan"
    )


class Product(Base):
    """Manufactured component or raw material SKU."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    unit_cost: Mapped[float] = mapped_column(Float)
    criticality_score: Mapped[float] = mapped_column(Float, default=0.5)
    standard_lead_time_days: Mapped[int] = mapped_column(Integer, default=21)
    safety_stock_days: Mapped[int] = mapped_column(Integer, default=7)
    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    supplier: Mapped[Supplier] = relationship("Supplier", back_populates="products")
    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        "PurchaseOrder", back_populates="product"
    )


class PurchaseOrder(Base):
    """Purchase order with delivery promise and actual outcome (if completed)."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("ix_po_supplier_order_date", "supplier_id", "order_date"),
        Index("ix_po_status_promised_date", "status", "promised_delivery_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    po_number: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    order_date: Mapped[date] = mapped_column(Date, index=True)
    promised_delivery_date: Mapped[date] = mapped_column(Date, index=True)
    actual_delivery_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    total_value: Mapped[float] = mapped_column(Float)
    promised_lead_time_days: Mapped[int] = mapped_column(Integer)
    actual_lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delay_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_delayed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, index=True)
    # Status: open, in_transit, delivered, cancelled
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    shipping_mode: Mapped[str] = mapped_column(String(32), default="Ocean Freight")
    origin_port: Mapped[str] = mapped_column(String(64), default="Shanghai")
    destination_plant: Mapped[str] = mapped_column(String(64), default="Detroit Assembly")
    urgency_level: Mapped[str] = mapped_column(String(24), default="standard")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    supplier: Mapped[Supplier] = relationship(
        "Supplier", back_populates="purchase_orders"
    )
    product: Mapped[Product] = relationship(
        "Product", back_populates="purchase_orders"
    )
    delivery_events: Mapped[list[DeliveryEvent]] = relationship(
        "DeliveryEvent", back_populates="purchase_order", cascade="all, delete-orphan"
    )
    predictions: Mapped[list[RiskPrediction]] = relationship(
        "RiskPrediction", back_populates="purchase_order", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[EarlyWarningAlert]] = relationship(
        "EarlyWarningAlert", back_populates="purchase_order", cascade="all, delete-orphan"
    )
    review_items: Mapped[list[ReviewQueueItem]] = relationship(
        "ReviewQueueItem", back_populates="purchase_order", cascade="all, delete-orphan"
    )


class DeliveryEvent(Base):
    """Milestone or exception event along a PO's fulfillment lifecycle."""

    __tablename__ = "delivery_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    po_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    event_timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    location: Mapped[str] = mapped_column(String(128))
    delay_days_reported: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[str] = mapped_column(String(24), default="info")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    purchase_order: Mapped[PurchaseOrder] = relationship(
        "PurchaseOrder", back_populates="delivery_events"
    )


class ModelRegistry(Base):
    """Trained ML model artifact metadata, evaluation metrics, and champion state."""

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_version: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    algorithm_name: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    is_champion: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="evaluated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    training_window_start: Mapped[date] = mapped_column(Date)
    training_window_end: Mapped[date] = mapped_column(Date)
    validation_window_end: Mapped[date] = mapped_column(Date)
    test_window_end: Mapped[date] = mapped_column(Date)
    train_row_count: Mapped[int] = mapped_column(Integer)
    val_row_count: Mapped[int] = mapped_column(Integer)
    test_row_count: Mapped[int] = mapped_column(Integer)
    random_seed: Mapped[int] = mapped_column(Integer, default=42)
    metrics_json: Mapped[str] = mapped_column(Text)
    calibration_json: Mapped[str] = mapped_column(Text)
    feature_importance_json: Mapped[str] = mapped_column(Text)
    hyperparameters_json: Mapped[str] = mapped_column(Text)
    unseen_supplier_metrics_json: Mapped[str] = mapped_column(Text)
    segment_analysis_json: Mapped[str] = mapped_column(Text)
    selection_rationale: Mapped[str] = mapped_column(Text)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    artifact_sha256: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class RiskPrediction(Base):
    """Point-in-time risk prediction and explainability record for a PO."""

    __tablename__ = "risk_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    po_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    algorithm_name: Mapped[str] = mapped_column(String(64))
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    raw_probability: Mapped[float] = mapped_column(Float)
    calibrated_probability: Mapped[float] = mapped_column(Float, index=True)
    risk_category: Mapped[str] = mapped_column(String(32), index=True)
    threshold_used: Mapped[float] = mapped_column(Float)
    expected_delay_days: Mapped[float] = mapped_column(Float)
    expected_financial_impact: Mapped[float] = mapped_column(Float)
    business_priority_score: Mapped[float] = mapped_column(Float, index=True)
    reliability_status: Mapped[str] = mapped_column(String(32), default="reliable")
    reliability_warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    top_contributors_json: Mapped[str] = mapped_column(Text, default="[]")
    historical_context_json: Mapped[str] = mapped_column(Text, default="{}")
    feature_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    explanation_method: Mapped[str] = mapped_column(
        String(64), default="SHAP / Calibrated Additive Attribution"
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(
        "PurchaseOrder", back_populates="predictions"
    )


class EarlyWarningAlert(Base):
    """Actionable early warning alert for upcoming high-risk deliveries."""

    __tablename__ = "early_warning_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    po_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    prediction_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("risk_predictions.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    review_priority: Mapped[int] = mapped_column(Integer, default=1, index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    # Status: open, acknowledged, escalated, resolved
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    purchase_order: Mapped[PurchaseOrder] = relationship(
        "PurchaseOrder", back_populates="alerts"
    )


class ReviewQueueItem(Base):
    """Human-in-the-loop review queue item separating ML risk from business priority."""

    __tablename__ = "review_queue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    po_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    prediction_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("risk_predictions.id", ondelete="SET NULL"), nullable=True
    )
    priority_rank: Mapped[int] = mapped_column(Integer, index=True)
    within_reviewer_capacity: Mapped[bool] = mapped_column(Boolean, default=True)
    business_priority_score: Mapped[float] = mapped_column(Float, index=True)
    ml_calibrated_probability: Mapped[float] = mapped_column(Float)
    operational_impact_score: Mapped[float] = mapped_column(Float)
    urgency_score: Mapped[float] = mapped_column(Float)
    prioritization_rationale: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(String(200))
    # Status: pending, accepted, dismissed, investigating, deferred, escalated
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    assigned_reviewer: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    purchase_order: Mapped[PurchaseOrder] = relationship(
        "PurchaseOrder", back_populates="review_items"
    )


class SystemRuleConfig(Base):
    """Configurable business rules, thresholds, and prioritization weights."""

    __tablename__ = "system_rule_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    config_value_json: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AIProviderConfig(Base):
    """Persisted AI/LLM provider configuration with masked secrets."""

    __tablename__ = "ai_provider_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # provider_type: none, openai, anthropic, openrouter, ollama, custom
    provider_type: Mapped[str] = mapped_column(String(32), default="none")
    base_url: Mapped[str] = mapped_column(String(256), default="")
    api_key_stored: Mapped[str] = mapped_column(String(512), default="")
    model_name: Mapped[str] = mapped_column(String(128), default="")
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=20)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=600)
    budget_limit_usd: Mapped[float] = mapped_column(Float, default=10.0)
    spent_usd: Mapped[float] = mapped_column(Float, default=0.0)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    """Immutable audit log for human review actions, threshold edits, and model promotions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32), default="reviewer")
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
