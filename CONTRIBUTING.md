# Contributing to Predictive Supplier Risk Intelligence

Thank you for your interest in contributing to **Predictive Supplier Risk Intelligence**!

## Development Workflow

1. **Fork & Clone** the repository.
2. **Create a Feature Branch**: `git checkout -b feat/your-feature-name`.
3. **Follow Point-in-Time ML Integrity Rules**:
   - Any new feature added to `backend/app/feature_engineering.py` **must** strictly use `as_of_date` and only aggregate prior orders where `actual_delivery_date < as_of_date`.
   - Never expose ground-truth arrival outcomes (`actual_delivery_date`, `delay_days`, `is_delayed`) in model input features.
4. **Preserve Human-in-the-Loop Governance**:
   - Never introduce automated order cancellation, automated supplier blacklisting, or unapproved binding procurement actions.
5. **Run Quality & Test Checks Before Submitting a PR**:
   ```bash
   cd backend
   ruff check app/ tests/
   mypy app/
   PYTHONPATH=. pytest tests/ -v

   cd ../frontend
   npm run lint
   npm test
   npm run build

   # Optional: full end-to-end journey + screenshot regeneration
   # (requires the backend on :8000 and the frontend dev server on :5173)
   cd ..
   .venv/bin/pytest e2e/test_e2e_playwright.py -v
   ```

6. **Keep Migrations in Sync**: after changing SQLAlchemy models in `backend/app/models.py`, generate a revision — `cd backend && alembic revision --autogenerate -m "describe change"` — and commit it under `backend/migrations/versions/`.
