# Security Policy & Governance Architecture

## 1. Model Artifact Integrity & Deserialization Safety
- All trained `joblib` artifacts are stored strictly inside `backend/artifacts/` and registered with a cryptographic **SHA-256 digest** in the `model_registry` table.
- Prior to loading any model artifact (`load_verified_model_artifact` in `backend/app/ml_pipeline.py`), the system verifies:
  1. Path traversal protection (`resolved_path` must reside inside the trusted `artifacts_dir`).
  2. Exact SHA-256 digest match against the registered hash. Any mismatch raises `SecurityError` and blocks deserialization.
- Arbitrary untrusted model uploads are prohibited.

## 2. API Key & Secret Protection
- External AI provider keys (`AI_API_KEY`) are **encrypted at rest** with Fernet (symmetric authenticated encryption). The key is derived from `AI_ENCRYPTION_KEY`, falling back to `JWT_SECRET_KEY` when unset; rotate it to invalidate stored secrets.
- All API responses (`/api/ai/config`) mask stored secrets (`sk-t••••••••cdef`) via `mask_api_key()`. Decryption happens only inside the backend process at request time.
- Legacy rows written before encryption was enabled (plaintext) remain readable and are transparently re-encrypted on the next save.
- Secrets are never logged, never included in audit log payloads, and never bundled into the frontend build.

## 2.1 Provider Endpoint (SSRF) Guard
- Provider base URLs must use `http://` or `https://`; other schemes (e.g. `file://`) are rejected.
- Cloud-metadata and link-local endpoints (`169.254.169.254`, `metadata.google.internal`, any link-local IP) are blocked, including when reached via DNS resolution.

## 2.2 Authentication Boundary
- `ALLOW_DEMO_MODE=false` activates an HTTP middleware that rejects any `/api/*` request lacking a valid `Authorization: Bearer <JWT>`. Only `/api/health` and `/api/auth/login` stay public. The demo quick-login accounts and `GET /api/auth/demo-accounts` are disabled.
- With demo mode on (local evaluation only), `X-Demo-Role`/`X-Demo-User` headers are accepted for convenience but never elevate beyond a seeded, active user.

## 3. Prompt-Injection Defense & Fact Grounding
- Supplier names, notes, and user questions are treated as **untrusted input** and sanitized via `sanitize_untrusted_text()` before prompt construction.
- AI outputs are validated via `validate_ai_output_against_facts()` to block any claim of autonomous order cancellation or supplier termination.

## 4. Role-Based Access Control (RBAC)
- Four privilege levels are enforced via JWT bearer tokens (`Authorization: Bearer <token>`) and role dependencies (`require_min_role`):
  - `viewer`: Read-only access to dashboards, analytics, and predictions.
  - `reviewer`: Can create/import orders, acknowledge alerts, and record human review decisions.
  - `procurement_lead`: Can edit business prioritization rules/weights, trigger model training, and promote champion models.
  - `admin`: Full system & AI provider configuration access.

## 5. Reporting a Vulnerability
Please report suspected security issues privately to the maintainers rather than opening a public issue.
