import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  DollarSign,
  Filter,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { apiFetch } from '../api';

const RISK_COLORS: Record<string, string> = {
  low: '#10b981',
  moderate: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
};

export const RiskBadge: React.FC<{ category?: string; prob?: number }> = ({
  category = 'low',
  prob,
}) => {
  const cat = category.toLowerCase();
  const styles: Record<string, string> = {
    low: 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60',
    moderate: 'bg-amber-950/80 text-amber-300 border-amber-700/60',
    high: 'bg-orange-950/80 text-orange-300 border-orange-700/60',
    critical: 'bg-rose-950/80 text-rose-300 border-rose-700/60',
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
        styles[cat] || styles.low
      }`}
    >
      <span className="uppercase">{cat}</span>
      {prob !== undefined && <span>({(prob * 100).toFixed(1)}%)</span>}
    </span>
  );
};

// ============================================================================
// 1. OVERVIEW DASHBOARD TAB
// ============================================================================
export const OverviewTab: React.FC<{
  role: string;
  onNavigate: (tab: string, poId?: number) => void;
}> = ({ role, onNavigate }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('/api/dashboard/overview', {}, role);
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard overview');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [role]);

  if (loading) {
    return (
      <div className="p-8 text-slate-400 flex items-center gap-3">
        <RefreshCw className="w-5 h-5 animate-spin text-blue-400" />
        Loading real-time procurement intelligence overview...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300">
        Error: {error}
      </div>
    );
  }

  const { kpis, monthly_trend, risk_breakdown, regional_breakdown, top_priority_reviews } = data;

  return (
    <div className="space-y-6" data-testid="overview-dashboard">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-blue-950/40 to-slate-900 border border-slate-800 rounded-xl p-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-blue-400 uppercase tracking-wider">
            <span>Point-in-Time Calibrated ML Engine</span>
            <span>•</span>
            <span>Active Champion: {kpis.champion_model_version}</span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1">
            Manufacturing & Procurement Risk Command Center
          </h2>
          <p className="text-sm text-slate-400 mt-0.5">
            Monitoring {kpis.active_open_orders} open purchase orders (${(kpis.total_open_order_value_usd / 1_000_000).toFixed(2)}M total committed value) across {kpis.total_suppliers} global suppliers.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => onNavigate('reviews')}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium flex items-center gap-2 shadow-lg shadow-blue-950/50 transition"
          >
            <ShieldAlert className="w-4 h-4" />
            Open Review Queue ({kpis.pending_human_reviews})
          </button>
          <button
            onClick={() => onNavigate('scenarios')}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium border border-slate-700 transition"
          >
            Run Scenario Simulation
          </button>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase">
            <span>High / Critical Risk Orders</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">
              {kpis.high_or_critical_open_orders}
            </span>
            <span className="text-xs text-slate-400">
              of {kpis.active_open_orders} open POs
            </span>
          </div>
          <div className="mt-2 text-xs text-rose-400">
            {kpis.active_early_warnings} active early-warning alerts
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase">
            <span>Expected Risk Exposure</span>
            <DollarSign className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">
              ${Math.round(kpis.expected_risk_exposure_usd).toLocaleString()}
            </span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Probability-weighted expedite & line-stop risk
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase">
            <span>Historical On-Time Rate</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">
              {kpis.historical_otd_rate_pct}%
            </span>
            <span className="text-xs text-slate-400">
              ({kpis.total_historical_orders.toLocaleString()} completed POs)
            </span>
          </div>
          <div className="mt-2 text-xs text-amber-300">
            Avg slip when delayed: +{kpis.avg_delay_when_late_days} days
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium uppercase">
            <span>Champion Model Quality</span>
            <TrendingUp className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-3">
            <div>
              <span className="text-2xl font-bold text-white">
                {kpis.champion_test_roc_auc.toFixed(3)}
              </span>
              <span className="text-xs text-slate-400 ml-1">ROC-AUC</span>
            </div>
            <div>
              <span className="text-xl font-semibold text-blue-400">
                {kpis.champion_test_pr_auc.toFixed(3)}
              </span>
              <span className="text-xs text-slate-400 ml-1">PR-AUC</span>
            </div>
          </div>
          <div className="mt-2 text-xs text-slate-400 truncate">
            {kpis.champion_algorithm} (Unseen Test Split)
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Monthly Historical OTD & Delay Trend */}
        <div className="lg:col-span-2 bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white">
                12-Month Historical Delivery Reliability & Delay Trend
              </h3>
              <p className="text-xs text-slate-400">
                Persisted historical delivered order outcomes by order month
              </p>
            </div>
            <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
              Source: SQLite/PostgreSQL purchase_orders
            </span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={monthly_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} />
                <YAxis yAxisId="left" stroke="#94a3b8" fontSize={11} unit="%" />
                <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar
                  yAxisId="right"
                  dataKey="delayed_orders"
                  name="Delayed Orders (Count)"
                  fill="#f97316"
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="otd_rate_pct"
                  name="On-Time Delivery Rate (%)"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Open Orders Risk Distribution */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-white">
              Open Orders by Calibrated Risk Tier
            </h3>
            <p className="text-xs text-slate-400">
              Distribution across {kpis.active_open_orders} active POs
            </p>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={risk_breakdown}
                  dataKey="count"
                  nameKey="category"
                  cx="50%"
                  cy="50%"
                  innerRadius={52}
                  outerRadius={82}
                  paddingAngle={3}
                  isAnimationActive={false}
                >
                  {risk_breakdown.map((entry: any, idx: number) => (
                    <Cell
                      key={entry.key || entry.category || idx}
                      fill={RISK_COLORS[entry.key] || '#3b82f6'}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Regional Breakdown & Top Priority Review Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-1">
            Regional Supply Chain Risk Exposure
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Mean predicted late-delivery probability by supplier region
          </p>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={regional_breakdown} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis type="number" stroke="#94a3b8" fontSize={11} unit="%" />
                <YAxis
                  type="category"
                  dataKey="region"
                  stroke="#cbd5e1"
                  fontSize={11}
                  width={105}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Bar
                  dataKey="avg_delay_prob_pct"
                  name="Avg Delay Prob (%)"
                  fill="#3b82f6"
                  radius={[0, 4, 4, 0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Priority Human Review Queue Preview */}
        <div className="lg:col-span-2 bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white">
                Highest-Priority Orders Requiring Human Oversight
              </h3>
              <p className="text-xs text-slate-400">
                Ranked by composite Business Priority (ML Probability + Financial Impact + Urgency)
              </p>
            </div>
            <button
              onClick={() => onNavigate('reviews')}
              className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1"
            >
              View Full Queue <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-2.5 font-medium">Rank</th>
                  <th className="pb-2.5 font-medium">PO Number</th>
                  <th className="pb-2.5 font-medium">Supplier & Component</th>
                  <th className="pb-2.5 font-medium">Promised Date</th>
                  <th className="pb-2.5 font-medium">ML Delay Prob</th>
                  <th className="pb-2.5 font-medium">Business Priority</th>
                  <th className="pb-2.5 font-medium">Status</th>
                  <th className="pb-2.5 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {top_priority_reviews.map((item: any) => (
                  <tr key={item.id} className="hover:bg-slate-800/40">
                    <td className="py-2.5 font-bold text-blue-400">
                      #{item.priority_rank}
                    </td>
                    <td className="py-2.5 font-mono text-white">
                      {item.po_number}
                    </td>
                    <td className="py-2.5">
                      <div className="font-medium text-slate-200">
                        {item.supplier_name}
                      </div>
                      <div className="text-slate-500 text-[11px]">
                        {item.product_name}
                      </div>
                    </td>
                    <td className="py-2.5 text-slate-300">
                      {item.promised_delivery_date}
                    </td>
                    <td className="py-2.5">
                      <span className="font-semibold text-rose-400">
                        {(item.ml_calibrated_probability * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2.5">
                      <span className="px-2 py-0.5 rounded bg-blue-950/80 border border-blue-700/50 text-blue-300 font-semibold">
                        {item.business_priority_score.toFixed(1)} / 100
                      </span>
                    </td>
                    <td className="py-2.5">
                      <span className="uppercase text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {item.status}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      <button
                        onClick={() => onNavigate('predictions', item.po_id)}
                        className="text-blue-400 hover:underline font-medium"
                      >
                        Inspect SHAP
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// 2. PURCHASE ORDERS MANAGEMENT TAB
// ============================================================================
export const OrdersTab: React.FC<{
  role: string;
  onInspectPrediction: (poId: number) => void;
}> = ({ role, onInspectPrediction }) => {
  const [ordersData, setOrdersData] = useState<any>({ total: 0, items: [] });
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('active');
  const [riskFilter, setRiskFilter] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState('');
  const [editingPo, setEditingPo] = useState<any>(null);
  const [poError, setPoError] = useState('');
  const [selectedPoEvents, setSelectedPoEvents] = useState<{
    poNumber: string;
    events: any[];
  } | null>(null);

  const [newPo, setNewPo] = useState({
    po_number: `PO-2026-MAN-${Math.floor(1000 + Math.random() * 9000)}`,
    supplier_id: 1,
    product_id: 1,
    order_date: '2026-10-16',
    promised_delivery_date: '2026-11-04',
    quantity: 750,
    unit_price: 145.0,
    status: 'open',
    shipping_mode: 'Ocean Freight',
    urgency_level: 'high',
  });

  const loadOrders = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      if (riskFilter) params.set('risk_category', riskFilter);
      if (search) params.set('search', search);
      params.set('page_size', '60');
      const res = await apiFetch(`/api/orders?${params.toString()}`, {}, role);
      setOrdersData(res);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, [statusFilter, riskFilter, role]);

  useEffect(() => {
    apiFetch('/api/suppliers', {}, role).then((s) => {
      setSuppliers(s);
      if (s.length > 0) {
        setNewPo((prev) => ({ ...prev, supplier_id: s[0].id }));
      }
    });
    apiFetch('/api/products', {}, role).then((p) => {
      setProducts(p);
    });
  }, [role]);

  const handleCreateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError('');
    try {
      await apiFetch(
        '/api/orders',
        {
          method: 'POST',
          body: JSON.stringify(newPo),
        },
        role
      );
      setShowCreateModal(false);
      loadOrders();
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create purchase order');
    }
  };

  const openEventsDrawer = async (po: any) => {
    const evs = await apiFetch(`/api/orders/${po.id}/events`, {}, role);
    setSelectedPoEvents({ poNumber: po.po_number, events: evs });
  };

  const handleUpdateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPo) return;
    setPoError('');
    try {
      const payload: Record<string, unknown> = {
        status: editingPo.status,
        promised_delivery_date: editingPo.promised_delivery_date,
        quantity: Number(editingPo.quantity),
        unit_price: Number(editingPo.unit_price),
        shipping_mode: editingPo.shipping_mode,
        urgency_level: editingPo.urgency_level,
        notes: editingPo.notes,
      };
      if (editingPo.actual_delivery_date) {
        payload.actual_delivery_date = editingPo.actual_delivery_date;
      }
      await apiFetch(
        `/api/orders/${editingPo.id}`,
        { method: 'PUT', body: JSON.stringify(payload) },
        role
      );
      setEditingPo(null);
      loadOrders();
    } catch (err: any) {
      setPoError(err.message || 'Failed to update purchase order');
    }
  };

  const supplierProducts = products.filter(
    (p) => p.supplier_id === Number(newPo.supplier_id)
  );

  return (
    <div className="space-y-5" data-testid="orders-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">
            Purchase Orders & Delivery Promises
          </h2>
          <p className="text-sm text-slate-400">
            Search, filter, create, and inspect open and completed purchase orders ({ordersData.total.toLocaleString()} matching records)
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          data-testid="create-order-btn"
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium flex items-center gap-2 transition"
        >
          <Plus className="w-4 h-4" />
          New Purchase Order
        </button>
      </div>

      {/* Filters Bar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadOrders()}
            placeholder="Search by PO number (e.g. PO-2026-OPEN-2001)..."
            className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
          />
        </div>
        <button
          onClick={loadOrders}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700"
        >
          Search
        </button>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
          >
            <option value="active">Active Open / In-Transit</option>
            <option value="open">Open Only</option>
            <option value="in_transit">In-Transit Only</option>
            <option value="delivered">Delivered (Historical)</option>
            <option value="cancelled">Cancelled</option>
            <option value="">All Statuses</option>
          </select>

          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
          >
            <option value="">All Risk Tiers</option>
            <option value="critical">Critical Risk (&gt;=80%)</option>
            <option value="high">High Risk (60-80%)</option>
            <option value="moderate">Moderate Risk (35-60%)</option>
            <option value="low">Low Risk (&lt;35%)</option>
          </select>
        </div>
      </div>

      {/* Orders Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-950/70 border-b border-slate-800 text-slate-400">
                <th className="p-3 font-medium">PO Number</th>
                <th className="p-3 font-medium">Supplier</th>
                <th className="p-3 font-medium">Product / Category</th>
                <th className="p-3 font-medium">Order Date</th>
                <th className="p-3 font-medium">Promised Date</th>
                <th className="p-3 font-medium">Qty / Value</th>
                <th className="p-3 font-medium">Shipping / Urgency</th>
                <th className="p-3 font-medium">Status / Outcome</th>
                <th className="p-3 font-medium">Predicted Risk</th>
                <th className="p-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={10} className="p-6 text-center text-slate-400">
                    Loading purchase orders...
                  </td>
                </tr>
              ) : ordersData.items.length === 0 ? (
                <tr>
                  <td colSpan={10} className="p-6 text-center text-slate-400">
                    No purchase orders match the selected filters.
                  </td>
                </tr>
              ) : (
                ordersData.items.map((po: any) => (
                  <tr key={po.id} className="hover:bg-slate-800/40">
                    <td className="p-3 font-mono font-semibold text-white">
                      {po.po_number}
                    </td>
                    <td className="p-3">
                      <div className="font-medium text-slate-200">
                        {po.supplier_name}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {po.supplier_code} • {po.supplier_region}
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="text-slate-200">{po.product_name}</div>
                      <div className="text-[11px] text-slate-500">
                        {po.product_category}
                      </div>
                    </td>
                    <td className="p-3 text-slate-300">{po.order_date}</td>
                    <td className="p-3 text-slate-300">
                      <div>{po.promised_delivery_date}</div>
                      <div className="text-[11px] text-slate-500">
                        {po.promised_lead_time_days}d lead time
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="text-slate-200 font-medium">
                        ${po.total_value.toLocaleString()}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {po.quantity.toLocaleString()} units
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="text-slate-300">{po.shipping_mode}</div>
                      <div className="text-[11px] uppercase font-semibold text-blue-400">
                        {po.urgency_level}
                      </div>
                    </td>
                    <td className="p-3">
                      <span className="uppercase text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-200">
                        {po.status}
                      </span>
                      {po.status === 'delivered' && po.delay_days !== null && (
                        <div
                          className={`text-[11px] mt-1 font-medium ${
                            po.is_delayed ? 'text-rose-400' : 'text-emerald-400'
                          }`}
                        >
                          {po.is_delayed
                            ? `Delayed +${po.delay_days}d`
                            : `On-Time (${po.delay_days}d)`}
                        </div>
                      )}
                    </td>
                    <td className="p-3">
                      {po.latest_prediction ? (
                        <div>
                          <RiskBadge
                            category={po.latest_prediction.risk_category}
                            prob={po.latest_prediction.calibrated_probability}
                          />
                          {po.latest_prediction.reliability_status !== 'reliable' && (
                            <div className="text-[10px] text-amber-400 mt-1 flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              Manual check advised
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="p-3 text-right space-x-2">
                      <button
                        onClick={() => onInspectPrediction(po.id)}
                        className="px-2.5 py-1 rounded bg-blue-950/80 hover:bg-blue-900 border border-blue-800 text-blue-300 font-medium"
                      >
                        Explain Risk
                      </button>
                      <button
                        onClick={() => {
                          setPoError('');
                          setEditingPo({
                            id: po.id,
                            po_number: po.po_number,
                            status: po.status,
                            promised_delivery_date: po.promised_delivery_date,
                            actual_delivery_date: po.actual_delivery_date || '',
                            quantity: po.quantity,
                            unit_price: po.unit_price,
                            shipping_mode: po.shipping_mode,
                            urgency_level: po.urgency_level,
                            notes: po.notes || '',
                          });
                        }}
                        data-testid={`update-order-${po.id}`}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 font-medium"
                      >
                        Update
                      </button>
                      <button
                        onClick={() => openEventsDrawer(po)}
                        className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                      >
                        Events
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Update PO / Record Delivery Modal */}
      {editingPo && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">
                Update Order & Record Delivery — {editingPo.po_number}
              </h3>
              <button
                onClick={() => setEditingPo(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                Close
              </button>
            </div>
            {poError && (
              <div className="p-3 rounded bg-rose-950/60 border border-rose-700 text-xs text-rose-200">
                {poError}
              </div>
            )}
            <form onSubmit={handleUpdateOrder} className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Status</label>
                <select
                  value={editingPo.status}
                  onChange={(e) => setEditingPo({ ...editingPo, status: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  <option value="open">open</option>
                  <option value="in_transit">in_transit</option>
                  <option value="delivered">delivered</option>
                  <option value="cancelled">cancelled</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Urgency</label>
                <select
                  value={editingPo.urgency_level}
                  onChange={(e) => setEditingPo({ ...editingPo, urgency_level: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  <option value="low">low</option>
                  <option value="standard">standard</option>
                  <option value="high">high</option>
                  <option value="critical">critical</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Promised Delivery Date</label>
                <input
                  type="date"
                  required
                  value={editingPo.promised_delivery_date}
                  onChange={(e) => setEditingPo({ ...editingPo, promised_delivery_date: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Actual Delivery Date (optional)</label>
                <input
                  type="date"
                  value={editingPo.actual_delivery_date}
                  onChange={(e) => setEditingPo({ ...editingPo, actual_delivery_date: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Quantity</label>
                <input
                  type="number"
                  min={1}
                  value={editingPo.quantity}
                  onChange={(e) => setEditingPo({ ...editingPo, quantity: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Unit Price (USD)</label>
                <input
                  type="number"
                  step="0.01"
                  min={0.01}
                  value={editingPo.unit_price}
                  onChange={(e) => setEditingPo({ ...editingPo, unit_price: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-slate-400 mb-1">Shipping Mode</label>
                <select
                  value={editingPo.shipping_mode}
                  onChange={(e) => setEditingPo({ ...editingPo, shipping_mode: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  <option value="Ocean Freight">Ocean Freight</option>
                  <option value="Air Freight">Air Freight</option>
                  <option value="Air Express">Air Express</option>
                  <option value="Ground Freight">Ground Freight</option>
                  <option value="Rail Intermodal">Rail Intermodal</option>
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="block text-slate-400 mb-1">Reviewer Notes</label>
                <textarea
                  rows={2}
                  value={editingPo.notes}
                  onChange={(e) => setEditingPo({ ...editingPo, notes: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div className="sm:col-span-2 flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingPo(null)}
                  className="px-4 py-2 rounded bg-slate-800 text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-blue-600 text-white font-semibold"
                >
                  Save & Re-Score
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create PO Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">
                Create New Purchase Order
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                Close
              </button>
            </div>
            {createError && (
              <div className="p-3 rounded bg-rose-950/60 border border-rose-700 text-xs text-rose-200">
                {createError}
              </div>
            )}
            <form onSubmit={handleCreateOrder} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">PO Number</label>
                  <input
                    type="text"
                    required
                    value={newPo.po_number}
                    onChange={(e) =>
                      setNewPo({ ...newPo, po_number: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Supplier</label>
                  <select
                    value={newPo.supplier_id}
                    onChange={(e) => {
                      const sid = Number(e.target.value);
                      const firstProd = products.find((p) => p.supplier_id === sid);
                      setNewPo({
                        ...newPo,
                        supplier_id: sid,
                        product_id: firstProd ? firstProd.id : newPo.product_id,
                        unit_price: firstProd ? firstProd.unit_cost : newPo.unit_price,
                      });
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  >
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.supplier_code} — {s.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Component SKU</label>
                <select
                  value={newPo.product_id}
                  onChange={(e) =>
                    setNewPo({ ...newPo, product_id: Number(e.target.value) })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  {(supplierProducts.length > 0 ? supplierProducts : products).map(
                    (p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} — {p.name} (Std Lead: {p.standard_lead_time_days}d)
                      </option>
                    )
                  )}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Order Date</label>
                  <input
                    type="date"
                    required
                    value={newPo.order_date}
                    onChange={(e) =>
                      setNewPo({ ...newPo, order_date: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">
                    Committed Delivery Date
                  </label>
                  <input
                    type="date"
                    required
                    value={newPo.promised_delivery_date}
                    onChange={(e) =>
                      setNewPo({
                        ...newPo,
                        promised_delivery_date: e.target.value,
                      })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Quantity</label>
                  <input
                    type="number"
                    min={1}
                    required
                    value={newPo.quantity}
                    onChange={(e) =>
                      setNewPo({ ...newPo, quantity: Number(e.target.value) })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">
                    Unit Price (USD)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min={0.01}
                    required
                    value={newPo.unit_price}
                    onChange={(e) =>
                      setNewPo({ ...newPo, unit_price: Number(e.target.value) })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Shipping Mode</label>
                  <select
                    value={newPo.shipping_mode}
                    onChange={(e) =>
                      setNewPo({ ...newPo, shipping_mode: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  >
                    <option value="Ocean Freight">Ocean Freight</option>
                    <option value="Air Freight">Air Freight</option>
                    <option value="Air Express">Air Express</option>
                    <option value="Ground Freight">Ground Freight</option>
                    <option value="Rail Intermodal">Rail Intermodal</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Urgency Level</label>
                  <select
                    value={newPo.urgency_level}
                    onChange={(e) =>
                      setNewPo({ ...newPo, urgency_level: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  >
                    <option value="low">Low</option>
                    <option value="standard">Standard</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded bg-slate-800 text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white font-semibold"
                >
                  Create & Score Order Risk
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delivery Events Modal */}
      {selectedPoEvents && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">
                Delivery Milestone Events — {selectedPoEvents.poNumber}
              </h3>
              <button
                onClick={() => setSelectedPoEvents(null)}
                className="text-slate-400 hover:text-white text-xs"
              >
                Close
              </button>
            </div>
            {selectedPoEvents.events.length === 0 ? (
              <p className="text-xs text-slate-400">
                No milestone exceptions recorded for this order yet.
              </p>
            ) : (
              <div className="space-y-3">
                {selectedPoEvents.events.map((ev: any) => (
                  <div
                    key={ev.id}
                    className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs"
                  >
                    <div className="flex items-center justify-between font-semibold text-white">
                      <span>{ev.event_type}</span>
                      <span className="text-slate-400 font-normal">
                        {ev.event_timestamp.slice(0, 16).replace('T', ' ')}
                      </span>
                    </div>
                    <div className="text-slate-400 mt-1">
                      Location: {ev.location} | Reported Offset: +{ev.delay_days_reported}d
                    </div>
                    <div className="text-slate-300 mt-1">{ev.notes}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// 3. SUPPLIERS DIRECTORY & 360 PROFILE TAB
// ============================================================================
export const SuppliersTab: React.FC<{ role: string }> = ({ role }) => {
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [regionFilter, setRegionFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedSupplierDetail, setSelectedSupplierDetail] = useState<any>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<any>(null);
  const [editError, setEditError] = useState('');
  const [newSup, setNewSup] = useState({
    supplier_code: `SUP-${Math.floor(2000 + Math.random() * 7000)}`,
    name: '',
    country: 'Germany',
    region: 'Central Europe',
    primary_category: 'Precision Machining',
    tier: 'Tier 1',
    capacity_index: 1.1,
    reliability_baseline: 0.88,
    lead_time_std_days: 2.2,
    financial_health_score: 82.0,
    geopolitical_risk_index: 0.18,
  });

  const loadSuppliers = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (regionFilter) params.set('region', regionFilter);
      const res = await apiFetch(`/api/suppliers?${params.toString()}`, {}, role);
      setSuppliers(res);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSuppliers();
  }, [regionFilter, role]);

  const openSupplier360 = async (supplierId: number) => {
    const res = await apiFetch(`/api/suppliers/${supplierId}`, {}, role);
    setSelectedSupplierDetail(res);
  };

  const handleCreateSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiFetch(
      '/api/suppliers',
      {
        method: 'POST',
        body: JSON.stringify(newSup),
      },
      role
    );
    setShowAddModal(false);
    loadSuppliers();
  };

  const handleUpdateSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSupplier) return;
    setEditError('');
    try {
      await apiFetch(
        `/api/suppliers/${editingSupplier.id}`,
        {
          method: 'PUT',
          body: JSON.stringify({
            name: editingSupplier.name,
            country: editingSupplier.country,
            region: editingSupplier.region,
            tier: editingSupplier.tier,
            status: editingSupplier.status,
            primary_category: editingSupplier.primary_category,
            capacity_index: Number(editingSupplier.capacity_index),
            reliability_baseline: Number(editingSupplier.reliability_baseline),
            lead_time_std_days: Number(editingSupplier.lead_time_std_days),
            financial_health_score: Number(editingSupplier.financial_health_score),
            geopolitical_risk_index: Number(editingSupplier.geopolitical_risk_index),
            contact_email: editingSupplier.contact_email,
          }),
        },
        role
      );
      setEditingSupplier(null);
      loadSuppliers();
    } catch (err: any) {
      setEditError(err.message || 'Failed to update supplier');
    }
  };

  return (
    <div className="space-y-5" data-testid="suppliers-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">
            Global Manufacturing Supplier Directory
          </h2>
          <p className="text-sm text-slate-400">
            Inspect historical on-time delivery performance, lead-time volatility, financial health, and cold-start status ({suppliers.length} suppliers)
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Supplier
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadSuppliers()}
            placeholder="Search supplier name, code, or country..."
            className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white"
          />
        </div>
        <button
          onClick={loadSuppliers}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700"
        >
          Search
        </button>
        <select
          value={regionFilter}
          onChange={(e) => setRegionFilter(e.target.value)}
          className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
        >
          <option value="">All Regions</option>
          <option value="East Asia">East Asia</option>
          <option value="North America">North America</option>
          <option value="Central Europe">Central Europe</option>
          <option value="Southeast Asia">Southeast Asia</option>
          <option value="South Asia">South Asia</option>
          <option value="Latin America">Latin America</option>
        </select>
      </div>

      {/* Suppliers Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-950/70 border-b border-slate-800 text-slate-400">
                <th className="p-3 font-medium">Code</th>
                <th className="p-3 font-medium">Supplier Name</th>
                <th className="p-3 font-medium">Region / Country</th>
                <th className="p-3 font-medium">Primary Category</th>
                <th className="p-3 font-medium">Tier</th>
                <th className="p-3 font-medium">Completed Orders</th>
                <th className="p-3 font-medium">Historical OTD Rate</th>
                <th className="p-3 font-medium">Avg Delay Offset</th>
                <th className="p-3 font-medium">Financial Health</th>
                <th className="p-3 font-medium text-right">Profile</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={10} className="p-6 text-center text-slate-400">
                    Loading suppliers...
                  </td>
                </tr>
              ) : (
                suppliers.map((s) => {
                  const isColdStart = s.historical_order_count < 5;
                  return (
                    <tr key={s.id} className="hover:bg-slate-800/40">
                      <td className="p-3 font-mono font-semibold text-blue-400">
                        {s.supplier_code}
                      </td>
                      <td className="p-3 font-medium text-white">
                        {s.name}
                        {isColdStart && (
                          <span className="ml-2 px-1.5 py-0.5 text-[10px] rounded bg-amber-950 border border-amber-700 text-amber-300">
                            Cold-Start (&lt;5 POs)
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-slate-300">
                        {s.region} ({s.country})
                      </td>
                      <td className="p-3 text-slate-300">{s.primary_category}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {s.tier}
                        </span>
                      </td>
                      <td className="p-3 text-slate-300">
                        {s.historical_order_count} delivered ({s.active_open_orders} open)
                      </td>
                      <td className="p-3">
                        {s.on_time_delivery_rate !== null ? (
                          <span
                            className={`font-semibold ${
                              s.on_time_delivery_rate >= 0.8
                                ? 'text-emerald-400'
                                : s.on_time_delivery_rate >= 0.65
                                ? 'text-amber-400'
                                : 'text-rose-400'
                            }`}
                          >
                            {(s.on_time_delivery_rate * 100).toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-slate-500">Insufficient History</span>
                        )}
                      </td>
                      <td className="p-3 text-slate-300">
                        {s.avg_delay_days !== null
                          ? `${s.avg_delay_days > 0 ? '+' : ''}${s.avg_delay_days}d`
                          : '—'}
                      </td>
                      <td className="p-3">
                        <span className="text-slate-200 font-medium">
                          {s.financial_health_score.toFixed(0)} / 100
                        </span>
                      </td>
                      <td className="p-3 text-right space-x-1.5">
                        <button
                          onClick={() => openSupplier360(s.id)}
                          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-blue-300 font-medium border border-slate-700"
                        >
                          360° Scorecard
                        </button>
                        <button
                          onClick={() => {
                            setEditError('');
                            setEditingSupplier({ ...s });
                          }}
                          data-testid={`edit-supplier-${s.id}`}
                          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Supplier 360 Modal */}
      {selectedSupplierDetail && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-3xl w-full p-6 space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-mono text-blue-400">
                  {selectedSupplierDetail.supplier.supplier_code} • {selectedSupplierDetail.supplier.tier}
                </span>
                <h3 className="text-lg font-bold text-white">
                  {selectedSupplierDetail.supplier.name}
                </h3>
                <p className="text-xs text-slate-400">
                  {selectedSupplierDetail.supplier.country} ({selectedSupplierDetail.supplier.region}) • Primary Category: {selectedSupplierDetail.supplier.primary_category}
                </p>
              </div>
              <button
                onClick={() => setSelectedSupplierDetail(null)}
                className="px-3 py-1 rounded bg-slate-800 text-slate-300 text-xs"
              >
                Close
              </button>
            </div>

            {selectedSupplierDetail.metrics.is_cold_start && (
              <div className="p-3 rounded-lg bg-amber-950/60 border border-amber-700 text-amber-200 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                <span>
                  <strong>Insufficient supplier history — manual review recommended:</strong> Only {selectedSupplierDetail.metrics.completed_orders} completed deliveries on record.
                </span>
              </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                <div className="text-slate-400">Historical OTD Rate</div>
                <div className="text-lg font-bold text-white mt-1">
                  {selectedSupplierDetail.metrics.on_time_delivery_rate !== null
                    ? `${(selectedSupplierDetail.metrics.on_time_delivery_rate * 100).toFixed(1)}%`
                    : 'N/A'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                <div className="text-slate-400">Avg Arrival Offset</div>
                <div className="text-lg font-bold text-white mt-1">
                  {selectedSupplierDetail.metrics.avg_delay_days !== null
                    ? `${selectedSupplierDetail.metrics.avg_delay_days} days`
                    : 'N/A'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                <div className="text-slate-400">Lead-Time Volatility (σ)</div>
                <div className="text-lg font-bold text-white mt-1">
                  {selectedSupplierDetail.metrics.lead_time_volatility_days !== null
                    ? `${selectedSupplierDetail.metrics.lead_time_volatility_days} days`
                    : 'N/A'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                <div className="text-slate-400">Completed / Open POs</div>
                <div className="text-lg font-bold text-white mt-1">
                  {selectedSupplierDetail.metrics.completed_orders} / {selectedSupplierDetail.metrics.open_orders}
                </div>
              </div>
            </div>

            {selectedSupplierDetail.quarterly_trend.length > 0 && (
              <div className="h-48 bg-slate-950 border border-slate-800 rounded-lg p-3">
                <div className="text-xs font-semibold text-slate-300 mb-2">
                  Quarterly On-Time Delivery Rate Trend (%)
                </div>
                <ResponsiveContainer width="100%" height="85%">
                  <BarChart data={selectedSupplierDetail.quarterly_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="quarter" stroke="#94a3b8" fontSize={10} />
                    <YAxis stroke="#94a3b8" fontSize={10} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        borderColor: '#334155',
                        fontSize: '11px',
                      }}
                    />
                    <Bar dataKey="otd_rate_pct" name="OTD %" fill="#10b981" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Add Supplier Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-base font-bold text-white">Onboard New Supplier</h3>
            <form onSubmit={handleCreateSupplier} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Supplier Code</label>
                <input
                  type="text"
                  required
                  value={newSup.supplier_code}
                  onChange={(e) =>
                    setNewSup({ ...newSup, supplier_code: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Supplier Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. RheinMetall Precision GmbH"
                  value={newSup.name}
                  onChange={(e) => setNewSup({ ...newSup, name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Region</label>
                  <select
                    value={newSup.region}
                    onChange={(e) =>
                      setNewSup({ ...newSup, region: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  >
                    <option value="East Asia">East Asia</option>
                    <option value="North America">North America</option>
                    <option value="Central Europe">Central Europe</option>
                    <option value="Southeast Asia">Southeast Asia</option>
                    <option value="South Asia">South Asia</option>
                    <option value="Latin America">Latin America</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Country</label>
                  <input
                    type="text"
                    required
                    value={newSup.country}
                    onChange={(e) =>
                      setNewSup({ ...newSup, country: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                  />
                </div>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Primary Category</label>
                <select
                  value={newSup.primary_category}
                  onChange={(e) =>
                    setNewSup({ ...newSup, primary_category: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  <option value="Semiconductors">Semiconductors</option>
                  <option value="Battery Cells & Packs">Battery Cells & Packs</option>
                  <option value="Power Electronics">Power Electronics</option>
                  <option value="Precision Machining">Precision Machining</option>
                  <option value="Industrial Sensors">Industrial Sensors</option>
                  <option value="Hydraulic Assemblies">Hydraulic Assemblies</option>
                  <option value="Structural Castings">Structural Castings</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded bg-slate-800 text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-blue-600 text-white font-semibold"
                >
                  Save Supplier
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Supplier Modal */}
      {editingSupplier && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-2xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">
                Edit Supplier — {editingSupplier.supplier_code}
              </h3>
              <button
                onClick={() => setEditingSupplier(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                Close
              </button>
            </div>
            {editError && (
              <div className="p-3 rounded bg-rose-950/60 border border-rose-700 text-xs text-rose-200">
                {editError}
              </div>
            )}
            <form onSubmit={handleUpdateSupplier} className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="sm:col-span-2">
                <label className="block text-slate-400 mb-1">Supplier Name</label>
                <input
                  type="text"
                  required
                  value={editingSupplier.name}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, name: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Region</label>
                <select
                  value={editingSupplier.region}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, region: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  {['East Asia', 'North America', 'Central Europe', 'Southeast Asia', 'South Asia', 'Latin America'].map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Country</label>
                <input
                  type="text"
                  value={editingSupplier.country}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, country: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Tier</label>
                <select
                  value={editingSupplier.tier}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, tier: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  <option value="Tier 1">Tier 1</option>
                  <option value="Tier 2">Tier 2</option>
                  <option value="Tier 3">Tier 3</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Status</label>
                <select
                  value={editingSupplier.status}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, status: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  <option value="active">active</option>
                  <option value="on_watchlist">on_watchlist</option>
                  <option value="suspended">suspended</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Primary Category</label>
                <input
                  type="text"
                  value={editingSupplier.primary_category}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, primary_category: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Contact Email</label>
                <input
                  type="email"
                  value={editingSupplier.contact_email || ''}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, contact_email: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Capacity Index</label>
                <input
                  type="number"
                  step="0.05"
                  value={editingSupplier.capacity_index}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, capacity_index: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Reliability Baseline (0-1)</label>
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  max={1}
                  value={editingSupplier.reliability_baseline}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, reliability_baseline: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Lead-Time Std Dev (days)</label>
                <input
                  type="number"
                  step="0.1"
                  value={editingSupplier.lead_time_std_days}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, lead_time_std_days: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Financial Health (0-100)</label>
                <input
                  type="number"
                  step="1"
                  value={editingSupplier.financial_health_score}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, financial_health_score: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Geopolitical Risk Index (0-1)</label>
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  max={1}
                  value={editingSupplier.geopolitical_risk_index}
                  onChange={(e) => setEditingSupplier({ ...editingSupplier, geopolitical_risk_index: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div className="sm:col-span-2 flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingSupplier(null)}
                  className="px-4 py-2 rounded bg-slate-800 text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded bg-blue-600 text-white font-semibold"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
