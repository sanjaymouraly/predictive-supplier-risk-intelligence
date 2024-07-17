"""Pydantic v2 schemas for API requests, responses, and validation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Auth & Users ---
class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Suppliers ---
class SupplierCreate(BaseModel):
    supplier_code: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=160)
    country: str = Field(..., min_length=2, max_length=64)
    region: str = Field(..., min_length=2, max_length=64)
    primary_category: str = Field(..., min_length=2, max_length=64)
    tier: str = Field(default="Tier 1")
    capacity_index: float = Field(default=1.0, ge=0.1, le=2.0)
    reliability_baseline: float = Field(default=0.85, ge=0.05, le=0.999)
    lead_time_std_days: float = Field(default=2.5, ge=0.1, le=30.0)
    financial_health_score: float = Field(default=75.0, ge=1.0, le=100.0)
    geopolitical_risk_index: float = Field(default=0.25, ge=0.0, le=1.0)
    contact_email: Optional[str] = None
    status: str = Field(default="active")
    onboarding_date: date = Field(default=date(2023, 1, 1))
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    primary_category: Optional[str] = None
    tier: Optional[str] = None
    capacity_index: Optional[float] = Field(default=None, ge=0.1, le=2.0)
    reliability_baseline: Optional[float] = Field(default=None, ge=0.05, le=0.999)
    lead_time_std_days: Optional[float] = Field(default=None, ge=0.1, le=30.0)
    financial_health_score: Optional[float] = Field(default=None, ge=1.0, le=100.0)
    geopolitical_risk_index: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    contact_email: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    supplier_code: str
    name: str
    country: str
    region: str
    primary_category: str
    tier: str
    capacity_index: float
    reliability_baseline: float
    lead_time_std_days: float
    financial_health_score: float
    geopolitical_risk_index: float
    contact_email: Optional[str]
    status: str
    onboarding_date: date
    notes: Optional[str]
    created_at: datetime
    # Enriched metrics
    historical_order_count: int = 0
    on_time_delivery_rate: Optional[float] = None
    avg_delay_days: Optional[float] = None
    active_open_orders: int = 0


# --- Products ---
class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=2, max_length=48)
    name: str = Field(..., min_length=2, max_length=160)
    category: str = Field(..., min_length=2, max_length=64)
    unit_cost: float = Field(..., gt=0)
    criticality_score: float = Field(default=0.5, ge=0.0, le=1.0)
    standard_lead_time_days: int = Field(default=21, ge=1, le=365)
    safety_stock_days: int = Field(default=7, ge=0, le=180)
    supplier_id: int


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    name: str
    category: str
    unit_cost: float
    criticality_score: float
    standard_lead_time_days: int
    safety_stock_days: int
    supplier_id: int


# --- Purchase Orders ---
class PurchaseOrderCreate(BaseModel):
    po_number: str = Field(..., min_length=3, max_length=48)
    supplier_id: int
    product_id: int
    order_date: date
    promised_delivery_date: date
    actual_delivery_date: Optional[date] = None
    quantity: int = Field(..., gt=0, le=10_000_000)
    unit_price: float = Field(..., gt=0)
    status: str = Field(default="open")
    shipping_mode: str = Field(default="Ocean Freight")
    origin_port: str = Field(default="Shanghai")
    destination_plant: str = Field(default="Detroit Assembly")
    urgency_level: str = Field(default="standard")
    notes: Optional[str] = None

    @field_validator("promised_delivery_date")
    @classmethod
    def check_promised_after_order(cls, v: date, info) -> date:
        order_date = info.data.get("order_date")
        if order_date and v < order_date:
            raise ValueError("promised_delivery_date cannot be earlier than order_date")
        return v


class PurchaseOrderUpdate(BaseModel):
    promised_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    quantity: Optional[int] = Field(default=None, gt=0)
    unit_price: Optional[float] = Field(default=None, gt=0)
    status: Optional[str] = None
    shipping_mode: Optional[str] = None
    urgency_level: Optional[str] = None
    notes: Optional[str] = None


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    po_number: str
    supplier_id: int
    supplier_name: Optional[str] = None
    supplier_code: Optional[str] = None
    supplier_region: Optional[str] = None
    product_id: int
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    product_category: Optional[str] = None
    order_date: date
    promised_delivery_date: date
    actual_delivery_date: Optional[date]
    quantity: int
    unit_price: float
    total_value: float
    promised_lead_time_days: int
    actual_lead_time_days: Optional[int]
    delay_days: Optional[int]
    is_delayed: Optional[bool]
    status: str
    shipping_mode: str
    origin_port: str
    destination_plant: str
    urgency_level: str
    notes: Optional[str]
    latest_prediction: Optional[dict[str, Any]] = None


# --- Risk Prediction & Explainability ---
class FeatureContribution(BaseModel):
    feature_name: str
    display_label: str
    feature_value: Any
    contribution_score: float
    direction: str  # "increases_risk" | "decreases_risk"
    human_explanation: str


class RiskPredictionOut(BaseModel):
    id: int
    po_id: int
    po_number: str
    supplier_id: int
    supplier_name: str
    product_name: str
    product_category: str
    order_date: date
    promised_delivery_date: date
    order_value: float
    urgency_level: str
    model_version: str
    algorithm_name: str
    predicted_at: datetime
    as_of_date: date
    raw_probability: float
    calibrated_probability: float
    risk_category: str
    threshold_used: float
    expected_delay_days: float
    expected_financial_impact: float
    business_priority_score: float
    reliability_status: str
    reliability_warnings: list[str]
    top_contributors: list[FeatureContribution]
    historical_context: dict[str, Any]
    feature_snapshot: dict[str, Any]
    explanation_method: str
    explanation_limitations: str


# --- Human Review Queue & Early Warnings ---
class ReviewDecisionRequest(BaseModel):
    decision: str = Field(
        ...,
        pattern="^(accepted|dismissed|investigating|deferred|escalated|annotated)$",
    )
    decision_reason: str = Field(..., min_length=2, max_length=160)
    decision_notes: Optional[str] = None
    assigned_reviewer: Optional[str] = None


class BusinessRuleConfigSchema(BaseModel):
    moderate_risk_threshold: float = Field(default=0.35, ge=0.1, le=0.9)
    high_risk_threshold: float = Field(default=0.60, ge=0.2, le=0.95)
    critical_risk_threshold: float = Field(default=0.80, ge=0.4, le=0.99)
    reviewer_capacity: int = Field(default=25, ge=1, le=500)
    weight_ml_probability: float = Field(default=0.45, ge=0.0, le=1.0)
    weight_financial_impact: float = Field(default=0.25, ge=0.0, le=1.0)
    weight_urgency: float = Field(default=0.15, ge=0.0, le=1.0)
    weight_criticality: float = Field(default=0.15, ge=0.0, le=1.0)


class AlertActionRequest(BaseModel):
    status: str = Field(..., pattern="^(open|acknowledged|escalated|resolved)$")
    resolution_notes: Optional[str] = None


# --- Scenario Analysis ---
class ScenarioRequest(BaseModel):
    po_id: Optional[int] = None
    supplier_id: int
    product_id: int
    quantity: int = Field(..., gt=0, le=10_000_000)
    promised_lead_time_days: int = Field(..., ge=1, le=365)
    shipping_mode: str = Field(default="Ocean Freight")
    urgency_level: str = Field(default="standard")
    order_date: Optional[date] = None


# --- AI Provider Settings ---
class AIProviderConfigUpdate(BaseModel):
    provider_type: str = Field(
        default="none",
        pattern="^(none|openai|anthropic|openrouter|ollama|custom)$",
    )
    base_url: str = Field(default="")
    api_key: Optional[str] = Field(default=None)
    model_name: str = Field(default="")
    timeout_seconds: int = Field(default=20, ge=3, le=120)
    max_retries: int = Field(default=2, ge=0, le=5)
    max_tokens: int = Field(default=600, ge=64, le=4096)
    budget_limit_usd: float = Field(default=10.0, ge=0.0, le=10000.0)
    is_enabled: bool = Field(default=False)


class AIProviderConfigOut(BaseModel):
    provider_type: str
    base_url: str
    has_api_key: bool
    api_key_masked: str
    model_name: str
    suggested_models: list[str] = []
    default_base_url: str = ""
    timeout_seconds: int
    max_retries: int
    max_tokens: int
    budget_limit_usd: float
    spent_usd: float
    request_count: int
    is_enabled: bool
    updated_by: str
    updated_at: datetime


class AIExplanationRequest(BaseModel):
    po_id: Optional[int] = None
    supplier_id: Optional[int] = None
    question: Optional[str] = None
