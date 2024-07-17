import React, { Suspense, lazy, useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Building2,
  ClipboardCheck,
  Cpu,
  FileText,
  GitCompare,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Settings,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react';
import { LoginPage } from './components/LoginPage';
import {
  apiFetch,
  clearSession,
  getStoredUser,
  getToken,
  type AuthUser,
} from './api';

// Tab panels are code-split so the initial shell loads fast; each chart-heavy
// workspace is fetched on first visit instead of inflating the entry bundle.
const OverviewTab = lazy(() =>
  import('./components/OverviewAndOrders').then((m) => ({ default: m.OverviewTab }))
);
const OrdersTab = lazy(() =>
  import('./components/OverviewAndOrders').then((m) => ({ default: m.OrdersTab }))
);
const SuppliersTab = lazy(() =>
  import('./components/OverviewAndOrders').then((m) => ({ default: m.SuppliersTab }))
);
const PredictionsTab = lazy(() =>
  import('./components/RiskAndWorkflows').then((m) => ({ default: m.PredictionsTab }))
);
const EarlyWarningsTab = lazy(() =>
  import('./components/RiskAndWorkflows').then((m) => ({ default: m.EarlyWarningsTab }))
);
const ReviewQueueTab = lazy(() =>
  import('./components/RiskAndWorkflows').then((m) => ({ default: m.ReviewQueueTab }))
);
const SupplierAnalyticsTab = lazy(() =>
  import('./components/AnalyticsAndML').then((m) => ({ default: m.SupplierAnalyticsTab }))
);
const ModelEvaluationTab = lazy(() =>
  import('./components/AnalyticsAndML').then((m) => ({ default: m.ModelEvaluationTab }))
);
const ScenarioAnalysisTab = lazy(() =>
  import('./components/AnalyticsAndML').then((m) => ({ default: m.ScenarioAnalysisTab }))
);
const ReportsTab = lazy(() =>
  import('./components/OpsAndSettings').then((m) => ({ default: m.ReportsTab }))
);
const DataImportTab = lazy(() =>
  import('./components/OpsAndSettings').then((m) => ({ default: m.DataImportTab }))
);
const SettingsTab = lazy(() =>
  import('./components/OpsAndSettings').then((m) => ({ default: m.SettingsTab }))
);

const TabLoading: React.FC = () => (
  <div className="flex h-64 items-center justify-center text-sm text-slate-400">
    <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />
    <span className="ml-3">Loading workspace…</span>
  </div>
);

interface NavItem {
  id: string;
  label: string;
  icon: React.FC<{ className?: string }>;
  group: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard, group: 'Operations' },
  { id: 'orders', label: 'Purchase Orders', icon: Package, group: 'Operations' },
  { id: 'suppliers', label: 'Suppliers', icon: Building2, group: 'Operations' },
  { id: 'predictions', label: 'Risk Predictions', icon: Activity, group: 'Risk & Oversight' },
  { id: 'alerts', label: 'Early Warnings', icon: AlertTriangle, group: 'Risk & Oversight' },
  { id: 'reviews', label: 'Human Review Queue', icon: ClipboardCheck, group: 'Risk & Oversight' },
  { id: 'analytics', label: 'Supplier Analytics', icon: BarChart3, group: 'Intelligence & ML' },
  { id: 'models', label: 'Model Evaluation', icon: Cpu, group: 'Intelligence & ML' },
  { id: 'scenarios', label: 'Scenario Analysis', icon: GitCompare, group: 'Intelligence & ML' },
  { id: 'reports', label: 'Reports & Audit', icon: FileText, group: 'Governance & Data' },
  { id: 'import', label: 'Data Import', icon: Upload, group: 'Governance & Data' },
  { id: 'settings', label: 'Settings & AI Config', icon: Settings, group: 'Governance & Data' },
];

const ROLE_LABEL: Record<string, string> = {
  admin: 'Administrator',
  procurement_lead: 'Procurement Lead',
  reviewer: 'Reviewer',
  viewer: 'Read-only Viewer',
};

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [selectedPoIdForPrediction, setSelectedPoIdForPrediction] = useState<number | null>(null);
  const [user, setUser] = useState<AuthUser | null>(() => (getToken() ? getStoredUser() : null));
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener('sri:unauthorized', onUnauthorized);
    return () => window.removeEventListener('sri:unauthorized', onUnauthorized);
  }, []);

  useEffect(() => {
    if (!user) return;
    apiFetch('/api/health', {}, user.role)
      .then(setHealth)
      .catch(() => setHealth(null));
  }, [user]);

  if (!user) {
    return (
      <LoginPage
        onAuthenticated={(_token, authenticatedUser) => {
          setUser(authenticatedUser);
          setActiveTab('overview');
        }}
      />
    );
  }

  const role = user.role;

  const handleNavigate = (tab: string, poId?: number) => {
    if (poId !== undefined) setSelectedPoIdForPrediction(poId);
    setActiveTab(tab);
    setMobileNavOpen(false);
  };

  const handleSignOut = () => {
    clearSession();
    setUser(null);
  };

  const sidebar = (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col shrink-0 h-full">
      <div className="p-4 border-b border-slate-800 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-black text-base shadow-lg shadow-blue-900/50">
          SR
        </div>
        <div className="min-w-0">
          <h1 className="text-sm font-bold text-white leading-tight">Supplier Risk IQ</h1>
          <p className="text-[11px] text-slate-400">Predictive Procurement ML</p>
        </div>
        <button
          onClick={() => setMobileNavOpen(false)}
          className="ml-auto rounded p-1 text-slate-400 hover:text-white lg:hidden"
          aria-label="Close navigation"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-5">
        {['Operations', 'Risk & Oversight', 'Intelligence & ML', 'Governance & Data'].map((group) => (
          <div key={group}>
            <div className="px-2.5 mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              {group}
            </div>
            <div className="space-y-1">
              {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    data-testid={`nav-${item.id}`}
                    onClick={() => handleNavigate(item.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition ${
                      isActive
                        ? 'bg-blue-600 text-white shadow-md shadow-blue-950/60'
                        : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                    }`}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="p-3 border-t border-slate-800 bg-slate-950/60 space-y-2.5 text-[11px]">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 shrink-0 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-blue-300">
            {user.full_name
              .split(' ')
              .map((part) => part[0])
              .slice(0, 2)
              .join('')}
          </div>
          <div className="min-w-0">
            <div className="truncate font-semibold text-slate-200" title={user.full_name}>
              {user.full_name}
            </div>
            <div className="truncate text-slate-500">
              {ROLE_LABEL[user.role] || user.role}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
          <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
          <span>Human-in-the-Loop Enforced</span>
        </div>
        <button
          onClick={handleSignOut}
          data-testid="sign-out-btn"
          className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-700 px-2 py-1.5 text-slate-300 transition hover:bg-slate-800 hover:text-white"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign out
        </button>
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex">
      <div className="hidden lg:flex">{sidebar}</div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          <div className="relative z-50 h-full">{sidebar}</div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-slate-900/80 backdrop-blur border-b border-slate-800 px-4 md:px-6 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 text-xs text-slate-300 min-w-0">
            <button
              onClick={() => setMobileNavOpen(true)}
              className="rounded p-1 text-slate-300 hover:text-white lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="px-2 py-0.5 rounded bg-blue-950/90 border border-blue-800 text-blue-300 font-semibold whitespace-nowrap">
              Advisory Decision Support
            </span>
            <span className="hidden xl:inline text-slate-400 truncate">
              No autonomous order cancellations or supplier rejections • Point-in-time leakage-free features
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs whitespace-nowrap">
            {health?.demo_mode && (
              <span className="hidden sm:inline rounded border border-amber-800 bg-amber-950/60 px-2 py-0.5 text-amber-300">
                Demo mode
              </span>
            )}
            <span className="text-slate-400">
              Ref Date:{' '}
              <strong className="text-slate-200">{health?.reference_date || '—'}</strong>
            </span>
          </div>
        </header>

        <main className="flex-1 p-4 md:p-6 overflow-y-auto max-w-[1600px] w-full mx-auto">
          <Suspense fallback={<TabLoading />}>
            {activeTab === 'overview' && <OverviewTab role={role} onNavigate={handleNavigate} />}
            {activeTab === 'orders' && (
              <OrdersTab
                role={role}
                onInspectPrediction={(poId) => handleNavigate('predictions', poId)}
              />
            )}
            {activeTab === 'suppliers' && <SuppliersTab role={role} />}
            {activeTab === 'predictions' && (
              <PredictionsTab role={role} initialPoId={selectedPoIdForPrediction} />
            )}
            {activeTab === 'alerts' && (
              <EarlyWarningsTab
                role={role}
                onInspectPo={(poId) => handleNavigate('predictions', poId)}
              />
            )}
            {activeTab === 'reviews' && (
              <ReviewQueueTab
                role={role}
                onInspectPo={(poId) => handleNavigate('predictions', poId)}
              />
            )}
            {activeTab === 'analytics' && <SupplierAnalyticsTab role={role} />}
            {activeTab === 'models' && <ModelEvaluationTab role={role} />}
            {activeTab === 'scenarios' && <ScenarioAnalysisTab role={role} />}
            {activeTab === 'reports' && <ReportsTab role={role} />}
            {activeTab === 'import' && <DataImportTab role={role} />}
            {activeTab === 'settings' && (
              <SettingsTab role={role} username={user.username} onSignOut={handleSignOut} />
            )}
          </Suspense>
        </main>
      </div>
    </div>
  );
};

export default App;
