"""End-to-End Playwright Browser Tests and Real Application Screenshot Capture."""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = Path(os.environ.get("SRI_IMAGES_DIR", PROJECT_ROOT / "docs" / "images"))
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
APP_URL = os.environ.get("SRI_BASE_URL", "http://127.0.0.1:5173")
API_URL = os.environ.get("SRI_API_URL", "http://127.0.0.1:8000")


def test_full_user_journey_and_capture_screenshots() -> None:
    """Exercise all 12 modules end-to-end in headless Chromium and capture genuine screenshots."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()

        # 1. Overview Dashboard
        page.goto(APP_URL, wait_until="networkidle")

        # Authenticate with a seeded demo account (the app is JWT-gated).
        page.wait_for_selector('[data-testid="login-page"]', timeout=15000)
        page.wait_for_timeout(600)
        page.screenshot(path=str(IMAGES_DIR / "00_login_page.png"), full_page=True)
        page.fill('input[autocomplete="username"]', "marcus.chen")
        page.fill('input[autocomplete="current-password"]', "Analyst2026!")
        page.click('button[type="submit"]')
        page.wait_for_selector('[data-testid="overview-dashboard"]', timeout=20000)
        assert "Manufacturing & Procurement Risk Command Center" in page.inner_text("body")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(IMAGES_DIR / "01_overview_dashboard.png"), full_page=True)

        # 2. Suppliers Management
        page.click('[data-testid="nav-suppliers"]')
        page.wait_for_selector('[data-testid="suppliers-page"]', timeout=10000)
        assert "Global Manufacturing Supplier Directory" in page.inner_text("body")
        page.wait_for_timeout(600)
        page.screenshot(path=str(IMAGES_DIR / "02_supplier_management.png"), full_page=False)

        # 3. Purchase Orders & Risk Predictions
        page.click('[data-testid="nav-orders"]')
        page.wait_for_selector('[data-testid="orders-page"]', timeout=10000)
        assert "Purchase Orders & Delivery Promises" in page.inner_text("body")
        page.wait_for_timeout(600)
        page.screenshot(
            path=str(IMAGES_DIR / "03_purchase_order_risk_predictions.png"),
            full_page=False,
        )

        # 4. Individual Prediction Explainability & Reliability Warnings
        page.click('[data-testid="nav-predictions"]')
        page.wait_for_selector('[data-testid="predictions-page"]', timeout=10000)
        page.wait_for_selector('[data-testid="prediction-explanation-panel"]', timeout=10000)
        # Click "Generate Grounded Briefing" button and wait for synthesis result
        page.click('button:has-text("Generate Grounded Briefing")')
        page.wait_for_selector('text=Suggested Buyer Investigation Questions:', timeout=10000)
        page.wait_for_timeout(500)
        assert "Top Contributing Risk Factors" in page.inner_text("body")
        page.screenshot(
            path=str(IMAGES_DIR / "05_individual_prediction_explanation.png"),
            full_page=True,
        )

        # 5. Early Warning Center
        page.click('[data-testid="nav-alerts"]')
        page.wait_for_selector('[data-testid="early-warnings-page"]', timeout=10000)
        assert "Early-Warning Alert Center" in page.inner_text("body")
        page.wait_for_timeout(600)
        page.screenshot(path=str(IMAGES_DIR / "11_early_warnings_center.png"), full_page=False)

        # 6. Human Review Queue & Authoritative Decision Recording
        page.click('[data-testid="nav-reviews"]')
        page.wait_for_selector('[data-testid="review-queue-page"]', timeout=10000)
        assert "Human-in-the-Loop Procurement Review Queue" in page.inner_text("body")
        # Open decision modal on top ranked item and submit decision
        decide_btn = page.locator('button:has-text("Record Decision")').first
        decide_btn.click()
        page.wait_for_selector('[data-testid="submit-review-decision-btn"]', timeout=5000)
        page.click('[data-testid="submit-review-decision-btn"]')
        page.wait_for_timeout(600)
        page.screenshot(path=str(IMAGES_DIR / "06_human_review_queue.png"), full_page=False)

        # 7. Supplier Analytics
        page.click('[data-testid="nav-analytics"]')
        page.wait_for_selector('[data-testid="supplier-analytics-page"]', timeout=10000)
        assert "Supplier Performance & Lead-Time Variability Analytics" in page.inner_text("body")
        page.wait_for_timeout(700)
        page.screenshot(path=str(IMAGES_DIR / "07_supplier_analytics.png"), full_page=True)

        # 8. Model Evaluation & Comparison
        page.click('[data-testid="nav-models"]')
        page.wait_for_selector('[data-testid="model-evaluation-page"]', timeout=10000)
        body_text = page.inner_text("body")
        assert "Machine Learning Evaluation, Calibration & Drift Governance" in body_text
        assert "Logistic Regression" in body_text
        assert "Random Forest" in body_text
        assert "HistGradientBoosting" in body_text
        page.wait_for_timeout(700)
        page.screenshot(
            path=str(IMAGES_DIR / "04_model_comparison_evaluation.png"),
            full_page=True,
        )

        # 9. Scenario Analysis (What-If Simulator)
        page.click('[data-testid="nav-scenarios"]')
        page.wait_for_selector('[data-testid="scenario-analysis-page"]', timeout=10000)
        page.click('[data-testid="run-scenario-btn"]')
        page.wait_for_timeout(700)
        assert "NON-CAUSAL SCENARIO PROJECTION" in page.inner_text("body")
        page.screenshot(path=str(IMAGES_DIR / "08_scenario_analysis.png"), full_page=True)

        # 10. Data Import & Schema Validation Preview
        page.click('[data-testid="nav-import"]')
        page.wait_for_selector('[data-testid="data-import-page"]', timeout=10000)
        page.click('[data-testid="load-sample-batch-btn"]')
        page.wait_for_timeout(800)
        assert "DRY-RUN PREVIEW" in page.inner_text("body")
        page.screenshot(
            path=str(IMAGES_DIR / "10_data_import_validation.png"),
            full_page=True,
        )

        # 11. Reports & Governance Audit
        page.click('[data-testid="nav-reports"]')
        page.wait_for_selector('[data-testid="reports-page"]', timeout=10000)
        assert "Executive Procurement Risk & Model Quality Report (PDF)" in page.inner_text("body")
        page.wait_for_timeout(600)
        page.screenshot(path=str(IMAGES_DIR / "12_reports_and_audit_trail.png"), full_page=False)

        # 12. Settings & AI Provider Configuration (Secrets Hidden)
        page.click('[data-testid="nav-settings"]')
        page.wait_for_selector('[data-testid="settings-page"]', timeout=10000)
        page.click('[data-testid="test-ai-connection-btn"]')
        page.wait_for_timeout(600)
        assert "Optional AI / LLM Intelligence Provider Settings" in page.inner_text("body")
        page.screenshot(
            path=str(IMAGES_DIR / "09_ai_provider_configuration.png"),
            full_page=True,
        )

        browser.close()

    # Verify all 10 screenshot files exist and are non-empty PNGs
    expected_files = [
        "00_login_page.png",
        "01_overview_dashboard.png",
        "02_supplier_management.png",
        "03_purchase_order_risk_predictions.png",
        "04_model_comparison_evaluation.png",
        "05_individual_prediction_explanation.png",
        "06_human_review_queue.png",
        "07_supplier_analytics.png",
        "08_scenario_analysis.png",
        "09_ai_provider_configuration.png",
        "10_data_import_validation.png",
        "11_early_warnings_center.png",
        "12_reports_and_audit_trail.png",
    ]
    for fname in expected_files:
        fpath = IMAGES_DIR / fname
        assert fpath.exists(), f"Missing screenshot {fpath}"
        assert fpath.stat().st_size > 20_000, f"Screenshot {fpath} appears empty"
