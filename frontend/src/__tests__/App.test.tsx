import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from '../App';
import { apiFetch } from '../api';

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', MockResizeObserver);
  localStorage.setItem('sri_access_token', 'test-token');
  localStorage.setItem(
    'sri_current_user',
    JSON.stringify({
      id: 2,
      username: 'marcus.chen',
      email: 'marcus.chen@manufacturing.local',
      full_name: 'Marcus Chen',
      role: 'procurement_lead',
      is_active: true,
    })
  );
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/api/dashboard/overview')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            kpis: {
              total_suppliers: 55,
              active_open_orders: 140,
              high_or_critical_open_orders: 42,
              open_orders_total_value_usd: 28500000,
              expected_risk_exposure_usd: 3650000,
              total_historical_orders: 2344,
              historical_otd_rate_pct: 62.5,
              avg_delay_when_late_days: 15.2,
              pending_human_reviews: 105,
              active_early_warnings: 47,
              champion_model_version: 'logistic_regression-v1-test',
              champion_model_name: 'Logistic Regression (Calibrated)',
              champion_test_roc_auc: 0.816,
              champion_test_pr_auc: 0.717,
            },
            risk_breakdown: [
              { key: 'low', category: 'Low (<35%)', count: 50 },
              { key: 'high', category: 'High (60-80%)', count: 25 },
            ],
            monthly_trends: [],
            regional_risk: [],
            top_priority_reviews: [],
          }),
        };
      }
      if (url.includes('/api/suppliers')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [
            {
              id: 1,
              supplier_code: 'SUP-1001',
              name: 'Apex Microelectronics',
              country: 'Taiwan',
              region: 'East Asia',
              category_specialty: 'Semiconductors',
              tier_level: 1,
              is_cold_start: true,
              completed_orders_count: 1,
              historical_otd_rate: 0.5,
              avg_delay_days: 4.2,
              financial_health_score: 72.0,
              capacity_utilization: 0.78,
              lead_time_std_days: 3.1,
              open_orders_count: 2,
            },
          ],
        };
      }
      if (url.includes('/api/predictions')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [
            {
              id: 1,
              po_id: 101,
              po_number: 'PO-2026-OPEN-2001',
              supplier_id: 1,
              supplier_name: 'Apex Microelectronics',
              supplier_code: 'SUP-1001',
              supplier_region: 'East Asia',
              product_id: 1,
              product_name: 'Semiconductors Module Type-A1',
              product_category: 'Semiconductors',
              order_value_usd: 85000,
              promised_delivery_date: '2026-11-05',
              urgency_level: 'critical',
              model_version: 'logistic_regression-v1-test',
              as_of_date: '2026-10-17',
              raw_probability: 0.78,
              calibrated_probability: 0.74,
              risk_category: 'high',
              decision_threshold: 0.6,
              business_priority_score: 84.5,
              expected_delay_days: 9.4,
              expected_financial_impact: 14200,
              reliability_status: 'unreliable_cold_start',
              reliability_warnings: [
                'Insufficient supplier history — manual review recommended',
              ],
              top_contributors: [
                {
                  feature_name: 'lead_time_compression_ratio',
                  display_label: 'Lead Time vs Standard Ratio',
                  feature_value: 0.65,
                  contribution_score: 0.42,
                  direction: 'increases_risk',
                  human_explanation: 'Compressed lead time elevates delay risk.',
                },
              ],
              historical_context: {
                supplier_completed_orders_before_po: 1,
                supplier_prior_otd_rate: 0.5,
              },
              explanation_method: 'SHAP Linear Log-Odds Attribution',
              explanation_limitations: 'Observational correlation only.',
            },
          ],
        };
      }
      if (url.includes('/api/ai/config')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            provider_type: 'none',
            base_url: '',
            model_name: 'offline-deterministic-v1',
            has_api_key: false,
            masked_api_key: '',
            timeout_seconds: 20,
            max_retries: 2,
            max_tokens: 600,
            budget_limit_usd: 10.0,
            spent_usd: 0.0,
            is_enabled: false,
            last_test_status: 'untested',
            last_test_message: 'Using built-in Offline Fact-Grounded Engine.',
          }),
        };
      }
      if (url.includes('/api/health')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            status: 'healthy',
            service: 'Predictive Supplier Risk Intelligence',
            version: '1.0.0',
            reference_date: '2026-10-17',
            database_connected: true,
            suppliers_count: 55,
            purchase_orders_count: 2540,
            champion_model: 'logistic_regression-v1-test',
          }),
        };
      }
      return {
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => [],
      };
    })
  );
});

describe('Supplier Risk IQ Frontend Governance & Navigation', () => {
  it('renders advisory decision support governance header and 12 navigation items', async () => {
    render(<App />);
    await screen.findByTestId('overview-dashboard');
    expect(screen.getByText('Advisory Decision Support')).toBeDefined();
    expect(screen.getByTestId('nav-overview')).toBeDefined();
    expect(screen.getByTestId('nav-orders')).toBeDefined();
    expect(screen.getByTestId('nav-suppliers')).toBeDefined();
    expect(screen.getByTestId('nav-predictions')).toBeDefined();
    expect(screen.getByTestId('nav-alerts')).toBeDefined();
    expect(screen.getByTestId('nav-reviews')).toBeDefined();
    expect(screen.getByTestId('nav-analytics')).toBeDefined();
    expect(screen.getByTestId('nav-models')).toBeDefined();
    expect(screen.getByTestId('nav-scenarios')).toBeDefined();
    expect(screen.getByTestId('nav-reports')).toBeDefined();
    expect(screen.getByTestId('nav-import')).toBeDefined();
    expect(screen.getByTestId('nav-settings')).toBeDefined();
  });

  it('navigates to Suppliers, Risk Predictions (SHAP + Cold-Start Warning), and AI Settings', async () => {
    render(<App />);
    await screen.findByTestId('overview-dashboard');

    // Navigate to Suppliers tab
    fireEvent.click(screen.getByTestId('nav-suppliers'));
    await screen.findByTestId('suppliers-page');
    await screen.findByText('Apex Microelectronics');
    expect(screen.getByText(/Cold-Start/i)).toBeDefined();

    // Navigate to Risk Predictions tab and verify reliability warning & SHAP attribution
    fireEvent.click(screen.getByTestId('nav-predictions'));
    await screen.findByTestId('predictions-page');
    await screen.findByText(/Insufficient supplier history — manual review recommended/i);
    expect(screen.getByText('Compressed lead time elevates delay risk.')).toBeDefined();

    // Navigate to Settings & AI Config tab
    fireEvent.click(screen.getByTestId('nav-settings'));
    await screen.findByTestId('settings-page');
    await screen.findByText('Optional AI / LLM Intelligence Provider Settings');
  });

  it('signs the user out back to the login screen', async () => {
    render(<App />);
    await screen.findByTestId('overview-dashboard');
    fireEvent.click(screen.getByTestId('sign-out-btn'));
    await screen.findByTestId('login-page');
    expect(localStorage.getItem('sri_access_token')).toBeNull();
  });

  it('sends a Bearer token when authenticated and falls back to demo role otherwise', async () => {
    await apiFetch('/api/health', { method: 'GET' }, 'reviewer');
    const authedHeaders = (globalThis.fetch as any).mock.calls[0][1].headers as Headers;
    expect(authedHeaders.get('Authorization')).toBe('Bearer test-token');
    expect(authedHeaders.get('X-Demo-Role')).toBeNull();
    expect(authedHeaders.get('Content-Type')).toBe('application/json');

    localStorage.removeItem('sri_access_token');
    await apiFetch('/api/health', { method: 'GET' }, 'reviewer');
    const demoHeaders = (globalThis.fetch as any).mock.calls[1][1].headers as Headers;
    expect(demoHeaders.get('Authorization')).toBeNull();
    expect(demoHeaders.get('X-Demo-Role')).toBe('reviewer');
  });
});
