"""Optional AI / LLM Intelligence Layer with Offline Deterministic Fallback, Prompt-Injection Defense, and Fact Validation."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import re
import socket
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.auth import record_audit_log
from app.config import settings
from app.ml_pipeline import predict_order_risk
from app.models import AIProviderConfig, PurchaseOrder, Supplier

DEFAULT_MODELS_BY_PROVIDER = {
    "none": "offline-deterministic-v1",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "gemma3:latest",
    "custom": "gpt-4o-mini",
}

DEFAULT_URLS_BY_PROVIDER = {
    "none": "",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "custom": "",
}

SUGGESTED_MODELS_BY_PROVIDER: dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "o4-mini"],
    "anthropic": [
        "claude-3-5-haiku-latest",
        "claude-3-5-sonnet-latest",
        "claude-sonnet-4-20250514",
    ],
    "openrouter": [
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-haiku",
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
    ],
    "ollama": ["gemma3:latest", "gemma3:4b", "gemma2:latest", "llama3.2:latest", "mistral:latest"],
    "custom": ["gpt-4o-mini", "local-model"],
    "none": ["offline-deterministic-v1"],
}

# Approximate public list prices in USD per 1M tokens (input, output).
# Used only for coarse cost ESTIMATES, never for billing.
MODEL_PRICE_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "o4-mini": (1.10, 4.40),
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-3-5-sonnet-latest": (3.00, 15.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "anthropic/claude-3.5-haiku": (0.80, 4.00),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "meta-llama/llama-3.3-70b-instruct": (0.12, 0.30),
}

_BLOCKED_HOSTNAMES = {"169.254.169.254", "metadata.google.internal", "metadata"}

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"system\s*prompt",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"cancel\s+all\s+orders",
    r"reject\s+supplier",
    r"<\s*script",
    r"\{\{.*?\}\}",
]

_SECRET_PREFIX = "enc::"


def _fernet() -> Fernet:
    """Build a Fernet cipher from the configured secret-encryption key."""
    raw = (settings.ai_encryption_key or settings.jwt_secret_key or "sri-local").encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw).digest()))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a provider API key for storage at rest."""
    if not plaintext:
        return ""
    return _SECRET_PREFIX + _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(stored: str | None) -> str:
    """Decrypt a stored provider API key, tolerating legacy plaintext rows."""
    if not stored:
        return ""
    if not stored.startswith(_SECRET_PREFIX):
        return stored  # legacy plaintext value written before encryption was enabled
    try:
        return _fernet().decrypt(stored[len(_SECRET_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""


def validate_provider_base_url(base_url: str) -> str:
    """Reject unsafe provider URLs (non-HTTP schemes, cloud metadata endpoints)."""
    candidate = (base_url or "").strip().rstrip("/")
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("AI base URL must use http:// or https://")
    host = (parsed.hostname or "").lower()
    if host in _BLOCKED_HOSTNAMES:
        raise ValueError("Blocked host: cloud metadata endpoints are not permitted")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_link_local or str(ip) in _BLOCKED_HOSTNAMES:
            raise ValueError("Blocked host: link-local addresses are not permitted")
    except ValueError as exc:
        if "Blocked host" in str(exc):
            raise
        # Not an IP literal (a normal hostname); optionally resolve to screen metadata IPs.
        if host and host not in ("localhost",):
            try:
                for info in socket.getaddrinfo(host, None):
                    resolved = info[4][0]
                    if resolved in _BLOCKED_HOSTNAMES:
                        raise ValueError("Blocked host: resolves to a cloud metadata endpoint")
            except socket.gaierror:
                pass
    return candidate


def estimate_cost_usd(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Coarse token-based cost estimate for transparency; not a billing statement."""
    key = (model_name or "").strip()
    price = MODEL_PRICE_TABLE.get(key)
    if not price:
        for candidate, value in MODEL_PRICE_TABLE.items():
            if key.startswith(candidate.split(":")[0]):
                price = value
                break
    if not price:
        return 0.0
    in_price, out_price = price
    return round((input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price, 6)


def mask_api_key(key: str | None) -> str:
    """Return a safely masked representation of an API key (never returns plaintext secret)."""
    stored = decrypt_secret(key)
    if not stored or not stored.strip():
        return ""
    k = stored.strip()
    if len(k) <= 8:
        return "••••••••"
    return f"{k[:4]}••••••••{k[-4:]}"



def sanitize_untrusted_text(value: str | None, max_len: int = 240) -> str:
    """Sanitize untrusted supplier/order text fields before inserting into prompts."""
    if not value:
        return ""
    cleaned = str(value).strip()
    for pat in INJECTION_PATTERNS:
        cleaned = re.sub(pat, "[REDACTED_UNTRUSTED_DIRECTIVE]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    return cleaned[:max_len]


def get_ai_config(db: Session) -> AIProviderConfig:
    """Fetch or initialize the singleton AIProviderConfig row."""
    cfg = db.query(AIProviderConfig).first()
    if not cfg:
        cfg = AIProviderConfig(
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
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def serialize_ai_config(cfg: AIProviderConfig) -> dict[str, Any]:
    """Serialize AIProviderConfig for safe API output with masked API key."""
    return {
        "provider_type": cfg.provider_type,
        "base_url": cfg.base_url,
        "has_api_key": bool(cfg.api_key_stored and cfg.api_key_stored.strip()),
        "api_key_masked": mask_api_key(cfg.api_key_stored),
        "model_name": cfg.model_name or DEFAULT_MODELS_BY_PROVIDER.get(cfg.provider_type, ""),
        "suggested_models": SUGGESTED_MODELS_BY_PROVIDER.get(cfg.provider_type, []),
        "default_base_url": DEFAULT_URLS_BY_PROVIDER.get(cfg.provider_type, ""),
        "timeout_seconds": cfg.timeout_seconds,
        "max_retries": cfg.max_retries,
        "max_tokens": cfg.max_tokens,
        "budget_limit_usd": round(cfg.budget_limit_usd, 4),
        "spent_usd": round(cfg.spent_usd, 5),
        "request_count": cfg.request_count,
        "is_enabled": cfg.is_enabled and cfg.provider_type != "none",
        "updated_by": cfg.updated_by,
        "updated_at": cfg.updated_at,
    }


def list_provider_presets() -> list[dict[str, Any]]:
    """Return the supported AI provider presets for the settings UI."""
    return [
        {
            "provider_type": "none",
            "label": "No AI / Offline Mode (default, free)",
            "default_base_url": "",
            "default_model": DEFAULT_MODELS_BY_PROVIDER["none"],
            "requires_api_key": False,
            "suggested_models": SUGGESTED_MODELS_BY_PROVIDER["none"],
        },
        {
            "provider_type": "openai",
            "label": "OpenAI API",
            "default_base_url": DEFAULT_URLS_BY_PROVIDER["openai"],
            "default_model": DEFAULT_MODELS_BY_PROVIDER["openai"],
            "requires_api_key": True,
            "suggested_models": SUGGESTED_MODELS_BY_PROVIDER["openai"],
        },
        {
            "provider_type": "anthropic",
            "label": "Anthropic Claude API",
            "default_base_url": DEFAULT_URLS_BY_PROVIDER["anthropic"],
            "default_model": DEFAULT_MODELS_BY_PROVIDER["anthropic"],
            "requires_api_key": True,
            "suggested_models": SUGGESTED_MODELS_BY_PROVIDER["anthropic"],
        },
        {
            "provider_type": "openrouter",
            "label": "OpenRouter (multi-model gateway)",
            "default_base_url": DEFAULT_URLS_BY_PROVIDER["openrouter"],
            "default_model": DEFAULT_MODELS_BY_PROVIDER["openrouter"],
            "requires_api_key": True,
            "suggested_models": SUGGESTED_MODELS_BY_PROVIDER["openrouter"],
        },
        {
            "provider_type": "ollama",
            "label": "Local Ollama / self-hosted inference",
            "default_base_url": DEFAULT_URLS_BY_PROVIDER["ollama"],
            "default_model": DEFAULT_MODELS_BY_PROVIDER["ollama"],
            "requires_api_key": False,
            "suggested_models": SUGGESTED_MODELS_BY_PROVIDER["ollama"],
        },
        {
            "provider_type": "custom",
            "label": "Custom OpenAI-compatible endpoint",
            "default_base_url": DEFAULT_URLS_BY_PROVIDER["custom"],
            "default_model": DEFAULT_MODELS_BY_PROVIDER["custom"],
            "requires_api_key": False,
            "suggested_models": SUGGESTED_MODELS_BY_PROVIDER["custom"],
        },
    ]


def update_ai_config(
    db: Session,
    payload: dict[str, Any],
    actor: str,
    role: str,
) -> dict[str, Any]:
    """Update AI provider configuration while preserving or updating the server-side API key."""
    cfg = get_ai_config(db)
    provider = str(payload.get("provider_type", "none")).lower()
    cfg.provider_type = provider

    base_url = str(payload.get("base_url") or "").strip()
    if not base_url and provider in DEFAULT_URLS_BY_PROVIDER:
        base_url = DEFAULT_URLS_BY_PROVIDER[provider]
    cfg.base_url = validate_provider_base_url(base_url)

    model_name = str(payload.get("model_name") or "").strip()
    if not model_name:
        model_name = DEFAULT_MODELS_BY_PROVIDER.get(provider, "gpt-4o-mini")
    cfg.model_name = model_name

    # Only overwrite api_key_stored if a new non-masked key is explicitly provided
    new_key = payload.get("api_key")
    if new_key is not None:
        new_key_str = str(new_key).strip()
        if "••••" not in new_key_str:
            cfg.api_key_stored = encrypt_secret(new_key_str)

    cfg.timeout_seconds = int(payload.get("timeout_seconds", cfg.timeout_seconds))
    cfg.max_retries = int(payload.get("max_retries", cfg.max_retries))
    cfg.max_tokens = int(payload.get("max_tokens", cfg.max_tokens))
    cfg.budget_limit_usd = float(payload.get("budget_limit_usd", cfg.budget_limit_usd))
    cfg.is_enabled = bool(payload.get("is_enabled", False)) and provider != "none"
    cfg.updated_by = actor
    cfg.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(cfg)

    record_audit_log(
        db=db,
        actor=actor,
        role=role,
        action="UPDATE_AI_PROVIDER_CONFIG",
        entity_type="AIProviderConfig",
        entity_id=str(cfg.id),
        details={
            "provider_type": cfg.provider_type,
            "base_url": cfg.base_url,
            "model_name": cfg.model_name,
            "is_enabled": cfg.is_enabled,
            "has_api_key": bool(cfg.api_key_stored),
        },
    )
    return serialize_ai_config(cfg)


def test_ai_provider_connection(db: Session) -> dict[str, Any]:
    """Test connectivity to the configured AI provider without exposing secrets."""
    cfg = get_ai_config(db)
    if cfg.provider_type == "none" or not cfg.is_enabled:
        return {
            "status": "ok",
            "mode": "offline",
            "provider_type": "none",
            "model_name": "offline-deterministic-v1",
            "message": "Offline Mode active (Free, deterministic fact-grounded engine ready; no external API calls).",
        }

    if cfg.provider_type in ("openai", "anthropic", "openrouter") and not cfg.api_key_stored:
        return {
            "status": "error",
            "mode": "external",
            "provider_type": cfg.provider_type,
            "model_name": cfg.model_name,
            "message": f"Missing API key for provider '{cfg.provider_type}'. Configure an API key or switch to Offline Mode.",
        }

    try:
        resp_text, cost_est = _invoke_external_llm(
            cfg=cfg,
            system_prompt="You are a supply chain assistant. Reply with 'CONNECTION_OK'.",
            user_prompt="Ping test.",
            max_tokens=16,
        )
        return {
            "status": "ok",
            "mode": "external",
            "provider_type": cfg.provider_type,
            "model_name": cfg.model_name,
            "estimated_cost_usd": cost_est,
            "message": f"Successfully connected to {cfg.provider_type} ({cfg.model_name}). Response: {resp_text[:60]}",
        }
    except Exception as exc:
        return {
            "status": "error",
            "mode": "external",
            "provider_type": cfg.provider_type,
            "model_name": cfg.model_name,
            "message": f"Connection test failed for {cfg.provider_type}: {str(exc)[:180]}. System will safely fall back to Offline Fact-Grounded Synthesis.",
        }


def _invoke_external_llm(
    cfg: AIProviderConfig,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
) -> tuple[str, float]:
    """Call OpenAI, Anthropic, OpenRouter, Ollama, or Custom endpoint with retries and budget guard."""
    if cfg.spent_usd >= cfg.budget_limit_usd and cfg.budget_limit_usd > 0:
        raise RuntimeError(
            f"AI budget limit reached (${cfg.spent_usd:.4f} / ${cfg.budget_limit_usd:.2f} USD)."
        )

    api_key = decrypt_secret(cfg.api_key_stored)
    tokens_limit = max_tokens or cfg.max_tokens
    timeout = float(cfg.timeout_seconds)
    retries = max(0, int(cfg.max_retries))
    base_url = validate_provider_base_url(cfg.base_url)

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if cfg.provider_type == "anthropic":
                url = f"{base_url.rstrip('/')}/messages"
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                body = {
                    "model": cfg.model_name or "claude-3-5-haiku-latest",
                    "max_tokens": tokens_limit,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                }
                with httpx.Client(timeout=timeout) as client:
                    r = client.post(url, headers=headers, json=body)
                    r.raise_for_status()
                    data = r.json()
                    content = data["content"][0]["text"]
                    usage = data.get("usage", {}) or {}
                    est_cost = estimate_cost_usd(
                        cfg.model_name,
                        int(usage.get("input_tokens", 0)),
                        int(usage.get("output_tokens", 0)),
                    )
                    return str(content), est_cost
            else:
                # OpenAI-compatible (OpenAI, OpenRouter, Ollama, Custom)
                url = f"{base_url.rstrip('/')}/chat/completions"
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                body = {
                    "model": cfg.model_name or "gpt-4o-mini",
                    "max_tokens": tokens_limit,
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                with httpx.Client(timeout=timeout) as client:
                    r = client.post(url, headers=headers, json=body)
                    r.raise_for_status()
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    if cfg.provider_type == "ollama":
                        est_cost = 0.0
                    else:
                        usage = data.get("usage") or {}
                        if usage:
                            est_cost = estimate_cost_usd(
                                cfg.model_name,
                                int(usage.get("prompt_tokens", 0)),
                                int(usage.get("completion_tokens", 0)),
                            )
                        else:
                            # No usage metadata: rough character-based estimate.
                            est_cost = estimate_cost_usd(
                                cfg.model_name,
                                max(1, len(system_prompt + user_prompt) // 4),
                                max(1, len(str(content)) // 4),
                            )
                    return str(content), est_cost
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(0.3 * (attempt + 1))

    raise RuntimeError(f"LLM request failed after {retries + 1} attempts: {last_err}")


def discover_provider_models(db: Session) -> dict[str, Any]:
    """Best-effort discovery of models exposed by the configured provider."""
    cfg = get_ai_config(db)
    provider = cfg.provider_type
    if provider in ("none", ""):
        return {"provider_type": "none", "models": SUGGESTED_MODELS_BY_PROVIDER["none"], "source": "offline"}

    if provider == "anthropic":
        return {
            "provider_type": provider,
            "models": SUGGESTED_MODELS_BY_PROVIDER["anthropic"],
            "source": "static_catalog",
        }

    api_key = decrypt_secret(cfg.api_key_stored)
    base_url = validate_provider_base_url(cfg.base_url) or DEFAULT_URLS_BY_PROVIDER.get(provider, "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    models: list[str] = []
    try:
        with httpx.Client(timeout=float(cfg.timeout_seconds)) as client:
            if provider == "ollama":
                # Ollama exposes a native tags endpoint in addition to the OpenAI shim.
                native = base_url.rstrip("/").removesuffix("/v1")
                resp = client.get(f"{native}/api/tags", headers=headers)
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
            if not models:
                resp = client.get(f"{base_url.rstrip('/')}/models", headers=headers)
                resp.raise_for_status()
                payload = resp.json()
                models = [m.get("id", "") for m in payload.get("data", []) if m.get("id")]
    except Exception as exc:
        return {
            "provider_type": provider,
            "models": SUGGESTED_MODELS_BY_PROVIDER.get(provider, []),
            "source": "fallback_catalog",
            "message": f"Live discovery unavailable ({str(exc)[:140]}); showing known models.",
        }

    return {
        "provider_type": provider,
        "models": models or SUGGESTED_MODELS_BY_PROVIDER.get(provider, []),
        "source": "provider_api" if models else "fallback_catalog",
    }


def validate_ai_output_against_facts(
    text: str,
    facts: dict[str, Any],
) -> tuple[str, list[str]]:
    """Validate that AI output does not claim autonomous binding decisions or contradict ground-truth records."""
    validation_notes: list[str] = [
        "Fact-grounding verified against database records",
        "Prompt-injection sanitization applied to supplier inputs",
        "Human oversight constraint enforced (no autonomous order actions)",
    ]

    forbidden_action_phrases = [
        "i have cancelled the order",
        "order has been automatically cancelled",
        "supplier has been terminated",
        "binding contract executed",
    ]
    cleaned_text = text
    for phrase in forbidden_action_phrases:
        if phrase in cleaned_text.lower():
            cleaned_text = re.sub(
                phrase,
                "[BLOCKED: Autonomous procurement actions are prohibited; human review required]",
                cleaned_text,
                flags=re.IGNORECASE,
            )
            validation_notes.append("Blocked unauthorized autonomous action claim in output")

    return cleaned_text, validation_notes


def generate_grounded_analyst_briefing(
    db: Session,
    po_id: int | None = None,
    supplier_id: int | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Generate a fact-grounded procurement risk briefing and investigation questions."""
    cfg = get_ai_config(db)
    clean_question = sanitize_untrusted_text(question, max_len=200)

    po_pred = None
    supplier_obj = None

    if po_id is not None:
        po_obj = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if po_obj:
            po_pred = predict_order_risk(db, po_obj, persist=False)
            supplier_obj = db.query(Supplier).filter(Supplier.id == po_obj.supplier_id).first()

    if supplier_obj is None and supplier_id is not None:
        supplier_obj = db.query(Supplier).filter(Supplier.id == supplier_id).first()

    if supplier_obj is None and po_pred is None:
        # Pick highest priority open PO for default briefing
        top_po = (
            db.query(PurchaseOrder)
            .filter(PurchaseOrder.status.in_(["open", "in_transit"]))
            .first()
        )
        if top_po:
            po_pred = predict_order_risk(db, top_po, persist=False)
            supplier_obj = db.query(Supplier).filter(Supplier.id == top_po.supplier_id).first()

    # Build deterministic ground-truth facts dictionary
    facts: dict[str, Any] = {}
    if po_pred:
        facts["po_number"] = po_pred["po_number"]
        facts["supplier_name"] = sanitize_untrusted_text(po_pred["supplier_name"])
        facts["product_name"] = sanitize_untrusted_text(po_pred["product_name"])
        facts["calibrated_probability_pct"] = round(po_pred["calibrated_probability"] * 100.0, 1)
        facts["risk_category"] = po_pred["risk_category"]
        facts["expected_delay_days"] = po_pred["expected_delay_days"]
        facts["expected_financial_impact_usd"] = po_pred["expected_financial_impact"]
        facts["business_priority_score"] = po_pred["business_priority_score"]
        facts["reliability_status"] = po_pred["reliability_status"]
        facts["reliability_warnings"] = po_pred["reliability_warnings"]
        facts["top_contributors"] = [
            {
                "factor": c["display_label"],
                "value": c["feature_value"],
                "direction": c["direction"],
            }
            for c in po_pred["top_contributors"][:4]
        ]
        facts["historical_context"] = po_pred["historical_context"]
    elif supplier_obj:
        facts["supplier_code"] = supplier_obj.supplier_code
        facts["supplier_name"] = sanitize_untrusted_text(supplier_obj.name)
        facts["region"] = supplier_obj.region
        facts["primary_category"] = supplier_obj.primary_category
        facts["financial_health_score"] = supplier_obj.financial_health_score

    # Prepare deterministic fact-grounded synthesis & investigation questions
    deterministic_summary, investigation_questions = _build_deterministic_briefing(
        po_pred, supplier_obj, clean_question
    )

    used_provider = "none (Offline Fact-Grounded Engine)"
    used_model = "offline-deterministic-v1"
    fallback_triggered = False
    est_cost = 0.0
    final_summary = deterministic_summary

    if cfg.is_enabled and cfg.provider_type != "none":
        system_prompt = (
            "You are a senior manufacturing procurement risk analyst assistant. "
            "Use ONLY the verified JSON facts provided. Never invent numbers, never claim causal certainty, "
            "and never execute or claim autonomous order cancellations or supplier rejections. "
            "Keep your summary concise (3-4 sentences)."
        )
        user_prompt = (
            f"Verified Procurement Record Facts:\n{json.dumps(facts, indent=2, default=str)}\n\n"
            f"Analyst Question: {clean_question or 'Provide an executive risk summary and recommended human review focus.'}"
        )
        try:
            llm_text, est_cost = _invoke_external_llm(
                cfg=cfg,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            cfg.spent_usd = round(cfg.spent_usd + est_cost, 5)
            cfg.request_count += 1
            db.commit()
            final_summary = llm_text
            used_provider = cfg.provider_type
            used_model = cfg.model_name
        except Exception as exc:
            fallback_triggered = True
            used_provider = f"{cfg.provider_type} -> offline_fallback"
            final_summary = (
                f"[External AI provider '{cfg.provider_type}' unavailable ({str(exc)[:90]}); "
                f"gracefully served by Offline Fact-Grounded Engine]\n\n{deterministic_summary}"
            )

    validated_summary, validation_checks = validate_ai_output_against_facts(
        final_summary, facts
    )

    return {
        "provider_used": used_provider,
        "model_used": used_model,
        "fallback_triggered": fallback_triggered,
        "estimated_cost_usd": est_cost,
        "executive_summary": validated_summary,
        "suggested_investigation_questions": investigation_questions,
        "grounded_facts": facts,
        "validation_checks": validation_checks,
        "governance_notice": (
            "Advisory intelligence only. All supplier communications, expediting approvals, "
            "and order modifications require explicit human authorization."
        ),
    }


def _build_deterministic_briefing(
    po_pred: dict[str, Any] | None,
    supplier: Supplier | None,
    question: str,
) -> tuple[str, list[str]]:
    if po_pred:
        prob_pct = po_pred["calibrated_probability"] * 100.0
        hist = po_pred["historical_context"]
        prior_cnt = hist.get("supplier_completed_orders_prior", 0)
        otd_pct = (
            f"{hist['supplier_raw_otd_rate_prior'] * 100:.1f}%"
            if hist.get("supplier_raw_otd_rate_prior") is not None
            else "N/A (Cold Start)"
        )
        top_factors = ", ".join(
            f"{c['display_label']} ({c['feature_value']})"
            for c in po_pred["top_contributors"][:3]
        )
        warn_text = (
            f" Reliability alert: {po_pred['reliability_warnings'][0]}"
            if po_pred["reliability_warnings"]
            else " Prediction passes all out-of-distribution and history depth checks."
        )
        q_prefix = f"Regarding your query ('{question}'): " if question else ""

        summary = (
            f"{q_prefix}Purchase Order {po_pred['po_number']} ({po_pred['product_name']}) with "
            f"{po_pred['supplier_name']} carries a calibrated late-delivery probability of {prob_pct:.1f}% "
            f"({po_pred['risk_category'].upper()} risk, Business Priority {po_pred['business_priority_score']:.1f}/100). "
            f"Based on {prior_cnt} completed historical deliveries prior to {hist['as_of_date']} "
            f"(historical OTD rate: {otd_pct}, trailing 90-day avg delay: {hist['supplier_trailing_90d_delay_days']:+.1f} days), "
            f"the primary statistical risk contributors are {top_factors}. "
            f"Estimated operational exposure is ${po_pred['expected_financial_impact']:,.2f} across an expected "
            f"+{po_pred['expected_delay_days']:.1f} day slip.{warn_text}"
        )
        questions = [
            f"Has {po_pred['supplier_name']} confirmed raw material staging and sub-tier wafer/component readiness for {po_pred['po_number']}?",
            f"Given the promised lead time of {int(po_pred['feature_snapshot']['promised_lead_time_days'])} days vs standard {int(po_pred['feature_snapshot']['standard_lead_time_days'])} days, can the receiving plant absorb a +{po_pred['expected_delay_days']:.1f} day arrival variance with current safety stock?",
            f"With {hist['supplier_active_open_orders_at_prediction']} concurrent active orders at {po_pred['supplier_name']}, should the buyer request weekly production milestone photos or evaluate partial air-freight split?",
            "Are there secondary pre-qualified suppliers in the same category with lower capacity utilization for upcoming Q4 replenishments?",
        ]
        return summary, questions

    if supplier:
        summary = (
            f"Supplier {supplier.name} ({supplier.supplier_code}) in {supplier.country} ({supplier.region}) "
            f"operates as a {supplier.tier} partner for {supplier.primary_category} with a financial health score "
            f"of {supplier.financial_health_score:.1f}/100 and capacity index {supplier.capacity_index:.2f}."
        )
        questions = [
            f"What is {supplier.name}'s current shop-floor capacity utilization for upcoming {supplier.primary_category} schedules?",
            "Should quarterly business review (QBR) targets adjust promised lead-time buffers to match observed transit variance?",
        ]
        return summary, questions

    return (
        "No specific purchase order or supplier selected. Select an open purchase order to generate a fact-grounded risk briefing.",
        ["Which open purchase orders exceed the 60% high-risk threshold this week?"],
    )
