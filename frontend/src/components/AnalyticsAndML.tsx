import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Play,
  RefreshCw,
  Sliders,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { apiFetch } from '../api';
import { RiskBadge } from './OverviewAndOrders';

// ============================================================================
// 7. SUPPLIER ANALYTICS TAB
// ============================================================================
export const SupplierAnalyticsTab: React.FC<{ role: string }> = ({ role }) => {
  const [data, setData] = useState<any>(null);
  const [regionFilter, setRegionFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const loadAnalytics = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (regionFilter) params.set('region', regionFilter);
      if (categoryFilter) params.set('category', categoryFilter);
      const res = await apiFetch(
        `/api/analytics/suppliers?${params.toString()}`,
        {},
        role
      );
      setData(res);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnalytics();
  }, [regionFilter, categoryFilter, role]);

  if (loading || !data) {
    return (
      <div className="p-8 text-slate-400 text-xs">
        Loading supplier performance analytics...
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="supplier-analytics-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">
            Supplier Performance & Lead-Time Variability Analytics
          </h2>
          <p className="text-sm text-slate-400">
            Historical on-time delivery rates, delay frequency, delay duration distributions, and breakdowns across {data.total_delivered_analyzed.toLocaleString()} delivered orders
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <select
            value={regionFilter}
            onChange={(e) => setRegionFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-200"
          >
            <option value="">All Regions</option>
            <option value="East Asia">East Asia</option>
            <option value="North America">North America</option>
            <option value="Central Europe">Central Europe</option>
            <option value="Southeast Asia">Southeast Asia</option>
            <option value="South Asia">South Asia</option>
            <option value="Latin America">Latin America</option>
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-200"
          >
            <option value="">All Categories</option>
            <option value="Semiconductors">Semiconductors</option>
            <option value="Battery Cells & Packs">Battery Cells & Packs</option>
            <option value="Power Electronics">Power Electronics</option>
            <option value="Precision Machining">Precision Machining</option>
            <option value="Industrial Sensors">Industrial Sensors</option>
            <option value="Hydraulic Assemblies">Hydraulic Assemblies</option>
            <option value="Structural Castings">Structural Castings</option>
          </select>
        </div>
      </div>

      {/* Category & Region Breakdown Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-bold text-white mb-1">
            On-Time Delivery Rate vs Delay Frequency by Product Category
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Persisted historical delivery outcomes across component families
          </p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.by_category}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="category" stroke="#94a3b8" fontSize={10} />
                <YAxis stroke="#94a3b8" fontSize={11} unit="%" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Bar
                  dataKey="otd_rate_pct"
                  name="On-Time Rate (%)"
                  fill="#10b981"
                  radius={[3, 3, 0, 0]}
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="delay_frequency_pct"
                  name="Delay Frequency (%)"
                  fill="#ef4444"
                  radius={[3, 3, 0, 0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-bold text-white mb-1">
            Regional Delivery Performance & Average Delay Duration
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Comparing regional OTD (%) with mean arrival slip when delayed (days)
          </p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data.by_region}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="region" stroke="#94a3b8" fontSize={10} />
                <YAxis yAxisId="left" stroke="#94a3b8" fontSize={11} unit="%" />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke="#f59e0b"
                  fontSize={11}
                  unit="d"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Bar
                  yAxisId="left"
                  dataKey="otd_rate_pct"
                  name="On-Time Rate (%)"
                  fill="#3b82f6"
                  radius={[3, 3, 0, 0]}
                  isAnimationActive={false}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="avg_delay_when_late_days"
                  name="Avg Delay Duration (Days)"
                  stroke="#f59e0b"
                  strokeWidth={2.5}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Delay Duration Distribution & Supplier Scorecards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-bold text-white mb-1">
            Historical Delay Duration Distribution
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Arrival offset buckets across completed orders
          </p>
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.delay_distribution} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis type="number" stroke="#94a3b8" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="bucket"
                  stroke="#cbd5e1"
                  fontSize={10}
                  width={130}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Bar
                  dataKey="count"
                  name="Orders"
                  fill="#8b5cf6"
                  radius={[0, 4, 4, 0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-2 bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-bold text-white mb-3">
            Supplier Lead-Time Variability & Reliability Scorecard
          </h3>
          <div className="overflow-x-auto max-h-64">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-2">Supplier</th>
                  <th className="pb-2">Region / Category</th>
                  <th className="pb-2">Orders</th>
                  <th className="pb-2">OTD Rate</th>
                  <th className="pb-2">Avg Offset</th>
                  <th className="pb-2">Volatility (σ)</th>
                  <th className="pb-2">Fin. Health</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data.supplier_scorecards.slice(0, 25).map((sc: any) => (
                  <tr key={sc.supplier_id} className="hover:bg-slate-800/40">
                    <td className="py-2 font-medium text-white">
                      {sc.supplier_code} — {sc.supplier_name}
                    </td>
                    <td className="py-2 text-slate-400">
                      {sc.region} • {sc.category}
                    </td>
                    <td className="py-2 text-slate-300">{sc.completed_orders}</td>
                    <td className="py-2">
                      {sc.otd_rate_pct !== null ? (
                        <span
                          className={`font-semibold ${
                            sc.otd_rate_pct >= 80
                              ? 'text-emerald-400'
                              : sc.otd_rate_pct >= 65
                              ? 'text-amber-400'
                              : 'text-rose-400'
                          }`}
                        >
                          {sc.otd_rate_pct}%
                        </span>
                      ) : (
                        <span className="text-amber-400">Cold Start</span>
                      )}
                    </td>
                    <td className="py-2 text-slate-300">
                      {sc.avg_delay_days !== null ? `${sc.avg_delay_days}d` : '—'}
                    </td>
                    <td className="py-2 text-slate-300">
                      {sc.lead_time_std_days !== null
                        ? `±${sc.lead_time_std_days}d`
                        : '—'}
                    </td>
                    <td className="py-2 text-slate-200">
                      {sc.financial_health_score}/100
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
// 8. MODEL EVALUATION, CALIBRATION & DRIFT MONITORING TAB
// ============================================================================
export const ModelEvaluationTab: React.FC<{ role: string }> = ({ role }) => {
  const [modelsData, setModelsData] = useState<any>(null);
  const [monitoring, setMonitoring] = useState<any>(null);
  const [selectedModel, setSelectedModel] = useState<any>(null);
  const [training, setTraining] = useState(false);

  const loadModels = async () => {
    const [mRes, monRes] = await Promise.all([
      apiFetch('/api/models', {}, role),
      apiFetch('/api/models/monitoring', {}, role),
    ]);
    setModelsData(mRes);
    setMonitoring(monRes);
    if (mRes.models.length > 0) {
      const champ =
        mRes.models.find((m: any) => m.is_champion) || mRes.models[0];
      setSelectedModel(champ);
    }
  };

  useEffect(() => {
    loadModels();
  }, [role]);

  const handleRetrain = async () => {
    setTraining(true);
    try {
      await apiFetch('/api/models/train', { method: 'POST' }, role);
      await loadModels();
    } finally {
      setTraining(false);
    }
  };

  const handlePromote = async (modelVersion: string) => {
    await apiFetch(
      `/api/models/${modelVersion}/promote`,
      { method: 'POST' },
      role
    );
    await loadModels();
  };

  if (!modelsData || !selectedModel) {
    return (
      <div className="p-8 text-slate-400 text-xs">
        Loading ML model evaluation and calibration benchmarks...
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="model-evaluation-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">
            Machine Learning Evaluation, Calibration & Drift Governance
          </h2>
          <p className="text-sm text-slate-400">
            Chronological Train (70%) / Validation (15%) / Unseen Final Test (15%) comparison across 3 ML architectures + 2 Operational Baselines
          </p>
        </div>
        <button
          onClick={handleRetrain}
          disabled={training}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${training ? 'animate-spin' : ''}`} />
          {training ? 'Training & Calibrating...' : 'Re-Run Full Training Pipeline'}
        </button>
      </div>

      {/* Model Comparison Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-bold text-white">
          Model & Baseline Benchmark Comparison (Unseen Chronological Test Split)
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="pb-2.5">Algorithm / Baseline</th>
                <th className="pb-2.5">Status</th>
                <th className="pb-2.5">Test ROC-AUC (95% CI)</th>
                <th className="pb-2.5">Test PR-AUC (95% CI)</th>
                <th className="pb-2.5">Brier Score ↓</th>
                <th className="pb-2.5">Calib ECE ↓</th>
                <th className="pb-2.5">Precision@25</th>
                <th className="pb-2.5">F1 Score</th>
                <th className="pb-2.5 text-right">Governance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {modelsData.models.map((m: any) => {
                const tm = m.test_metrics;
                const isSel = selectedModel.model_version === m.model_version;
                return (
                  <tr
                    key={m.model_version}
                    onClick={() => setSelectedModel(m)}
                    className={`cursor-pointer transition ${
                      isSel ? 'bg-blue-950/30' : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="py-3 font-semibold text-white">
                      <div>{m.display_name}</div>
                      <div className="text-[11px] font-mono text-slate-400">
                        {m.model_version} • SHA256: {m.artifact_sha256?.slice(0, 12)}...
                      </div>
                    </td>
                    <td className="py-3">
                      {m.is_champion ? (
                        <span className="px-2.5 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700 text-[11px] font-bold">
                          CHAMPION
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px]">
                          Candidate
                        </span>
                      )}
                    </td>
                    <td className="py-3 font-mono text-slate-200">
                      <span className="font-bold text-white">
                        {tm.roc_auc.toFixed(3)}
                      </span>{' '}
                      <span className="text-slate-500 text-[11px]">
                        [{tm.roc_auc_ci_95[0].toFixed(2)}–{tm.roc_auc_ci_95[1].toFixed(2)}]
                      </span>
                    </td>
                    <td className="py-3 font-mono text-slate-200">
                      <span className="font-bold text-blue-400">
                        {tm.pr_auc.toFixed(3)}
                      </span>{' '}
                      <span className="text-slate-500 text-[11px]">
                        [{tm.pr_auc_ci_95[0].toFixed(2)}–{tm.pr_auc_ci_95[1].toFixed(2)}]
                      </span>
                    </td>
                    <td className="py-3 font-mono text-emerald-400">
                      {tm.brier_score.toFixed(4)}
                    </td>
                    <td className="py-3 font-mono text-slate-300">
                      {tm.expected_calibration_error.toFixed(4)}
                    </td>
                    <td className="py-3 font-mono font-bold text-amber-300">
                      {(tm.review_capacity_metrics.precision_at_25 * 100).toFixed(0)}%
                    </td>
                    <td className="py-3 font-mono text-slate-300">
                      {tm.f1_score.toFixed(3)}
                    </td>
                    <td className="py-3 text-right">
                      {!m.is_champion && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePromote(m.model_version);
                          }}
                          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-blue-600 text-slate-200 hover:text-white text-[11px] font-medium transition"
                        >
                          Promote to Champion
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}

              {/* Operational Baselines */}
              {modelsData.baselines &&
                Object.entries(modelsData.baselines).map(
                  ([bKey, bVal]: [string, any]) => {
                    const bm = bVal.test;
                    return (
                      <tr key={bKey} className="bg-slate-950/50 text-slate-400">
                        <td className="py-2.5 font-medium text-slate-300">
                          {bVal.display_name}
                        </td>
                        <td className="py-2.5">
                          <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px]">
                            Heuristic Baseline
                          </span>
                        </td>
                        <td className="py-2.5 font-mono">{bm.roc_auc.toFixed(3)}</td>
                        <td className="py-2.5 font-mono">{bm.pr_auc.toFixed(3)}</td>
                        <td className="py-2.5 font-mono">{bm.brier_score.toFixed(4)}</td>
                        <td className="py-2.5 font-mono">
                          {bm.expected_calibration_error.toFixed(4)}
                        </td>
                        <td className="py-2.5 font-mono">
                          {(bm.review_capacity_metrics.precision_at_25 * 100).toFixed(0)}%
                        </td>
                        <td className="py-2.5 font-mono">{bm.f1_score.toFixed(3)}</td>
                        <td className="py-2.5 text-right text-[11px]">Reference</td>
                      </tr>
                    );
                  }
                )}
            </tbody>
          </table>
        </div>
        <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300">
          <strong>Champion Selection Rationale:</strong> {selectedModel.selection_rationale}
        </div>
      </div>

      {/* Selected Model Deep-Dive: ROC Curve, Calibration Curve & Feature Importance */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Calibration Curve */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <h4 className="text-sm font-bold text-white mb-1">
            Probability Calibration Curve ({selectedModel.algorithm_name})
          </h4>
          <p className="text-xs text-slate-400 mb-3">
            Predicted probability bin vs observed actual late-delivery rate
          </p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={selectedModel.calibration_curve}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="mean_predicted_prob"
                  stroke="#94a3b8"
                  fontSize={11}
                />
                <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Line
                  type="monotone"
                  dataKey="observed_delay_rate"
                  name="Observed Delay Rate"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="mean_predicted_prob"
                  name="Ideal Diagonal"
                  stroke="#64748b"
                  strokeDasharray="4 4"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ROC Curve */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <h4 className="text-sm font-bold text-white mb-1">
            Unseen Test ROC Curve (AUC = {selectedModel.test_metrics.roc_auc.toFixed(3)})
          </h4>
          <p className="text-xs text-slate-400 mb-3">
            True Positive Rate vs False Positive Rate across thresholds
          </p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={selectedModel.test_metrics.roc_curve}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="fpr" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="tpr"
                  name="True Positive Rate"
                  stroke="#3b82f6"
                  strokeWidth={2.5}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Global Permutation Feature Importance */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
          <h4 className="text-sm font-bold text-white mb-1">
            Global Feature Importance (Permutation ROC-AUC)
          </h4>
          <p className="text-xs text-slate-400 mb-3">
            Top predictive signals on chronological holdout split
          </p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={selectedModel.feature_importance.slice(0, 7)}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis type="number" stroke="#94a3b8" fontSize={10} />
                <YAxis
                  type="category"
                  dataKey="display_label"
                  stroke="#cbd5e1"
                  fontSize={10}
                  width={155}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                  }}
                />
                <Bar
                  dataKey="importance"
                  name="AUC Drop"
                  fill="#f59e0b"
                  radius={[0, 4, 4, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Confusion Matrix, Unseen Supplier Performance & Live Feature Drift Monitoring */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
          <h4 className="text-sm font-bold text-white">
            Confusion Matrix & Segment Error Analysis ({selectedModel.display_name})
          </h4>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded bg-emerald-950/40 border border-emerald-800/60">
              <div className="text-slate-400">True Negatives (On-Time Correct)</div>
              <div className="text-xl font-bold text-emerald-300">
                {selectedModel.test_metrics.confusion_matrix.tn}
              </div>
            </div>
            <div className="p-3 rounded bg-amber-950/40 border border-amber-800/60">
              <div className="text-slate-400">False Positives (Early Caution)</div>
              <div className="text-xl font-bold text-amber-300">
                {selectedModel.test_metrics.confusion_matrix.fp}
              </div>
            </div>
            <div className="p-3 rounded bg-rose-950/40 border border-rose-800/60">
              <div className="text-slate-400">False Negatives (Missed Slip)</div>
              <div className="text-xl font-bold text-rose-300">
                {selectedModel.test_metrics.confusion_matrix.fn}
              </div>
            </div>
            <div className="p-3 rounded bg-blue-950/40 border border-blue-800/60">
              <div className="text-slate-400">True Positives (Caught Late POs)</div>
              <div className="text-xl font-bold text-blue-300">
                {selectedModel.test_metrics.confusion_matrix.tp}
              </div>
            </div>
          </div>

          <div className="text-xs space-y-2">
            <div className="font-semibold text-slate-300">
              Segment Calibration & Error Analysis by Region:
            </div>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-1.5">Region Segment</th>
                  <th className="pb-1.5">Samples</th>
                  <th className="pb-1.5">Observed Late Rate</th>
                  <th className="pb-1.5">Mean Predicted</th>
                  <th className="pb-1.5">Segment Brier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {selectedModel.segment_analysis?.by_region?.map((seg: any) => (
                  <tr key={seg.segment}>
                    <td className="py-1.5 text-white">{seg.segment}</td>
                    <td className="py-1.5 text-slate-300">{seg.count}</td>
                    <td className="py-1.5 text-slate-300">
                      {(seg.observed_delay_rate * 100).toFixed(1)}%
                    </td>
                    <td className="py-1.5 text-blue-300">
                      {(seg.mean_predicted_prob * 100).toFixed(1)}%
                    </td>
                    <td className="py-1.5 font-mono text-emerald-400">
                      {seg.brier_score.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Live Feature Drift Monitoring */}
        {monitoring && (
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-white">
                  Live Feature Drift & Prediction Shift Monitoring
                </h4>
                <p className="text-xs text-slate-400">
                  Comparing active open orders ({monitoring.total_live_predictions}) against training baseline
                </p>
              </div>
              <span className="text-xs font-mono text-blue-400">
                Mean Prob Shift: {(monitoring.prediction_rate_shift * 100).toFixed(1)}%
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="pb-2">Feature</th>
                    <th className="pb-2">Train Mean</th>
                    <th className="pb-2">Live Mean</th>
                    <th className="pb-2">Shift (|Z|)</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {monitoring.feature_drift?.slice(0, 7).map((fd: any) => (
                    <tr key={fd.feature_name}>
                      <td className="py-2 text-slate-200">{fd.display_label}</td>
                      <td className="py-2 font-mono text-slate-400">
                        {fd.training_mean}
                      </td>
                      <td className="py-2 font-mono text-white">{fd.live_mean}</td>
                      <td className="py-2 font-mono text-blue-300">
                        {fd.standardized_shift_z}σ
                      </td>
                      <td className="py-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            fd.drift_status === 'stable'
                              ? 'bg-emerald-950 text-emerald-300'
                              : fd.drift_status === 'minor_shift'
                              ? 'bg-amber-950 text-amber-300'
                              : 'bg-rose-950 text-rose-300'
                          }`}
                        >
                          {fd.drift_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// 9. SCENARIO ANALYSIS (WHAT-IF SIMULATOR) TAB
// ============================================================================
export const ScenarioAnalysisTab: React.FC<{ role: string }> = ({ role }) => {
  const [openOrders, setOpenOrders] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [_products, setProducts] = useState<any[]>([]);
  const [simResult, setSimResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    po_id: 0,
    supplier_id: 1,
    product_id: 1,
    quantity: 600,
    promised_lead_time_days: 28,
    shipping_mode: 'Air Freight',
    urgency_level: 'standard',
  });

  useEffect(() => {
    Promise.all([
      apiFetch('/api/orders?status=active&page_size=50', {}, role),
      apiFetch('/api/suppliers', {}, role),
      apiFetch('/api/products', {}, role),
    ]).then(([ordRes, supRes, prodRes]) => {
      setOpenOrders(ordRes.items);
      setSuppliers(supRes);
      setProducts(prodRes);
      if (ordRes.items.length > 0) {
        const first = ordRes.items[0];
        const initialForm = {
          po_id: first.id,
          supplier_id: first.supplier_id,
          product_id: first.product_id,
          quantity: first.quantity,
          promised_lead_time_days: first.promised_lead_time_days + 7,
          shipping_mode: 'Air Freight',
          urgency_level: first.urgency_level,
        };
        setForm(initialForm);
        apiFetch(
          '/api/scenarios/simulate',
          {
            method: 'POST',
            body: JSON.stringify(initialForm),
          },
          role
        ).then(setSimResult);
      }
    });
  }, [role]);

  const handleSelectBaselinePo = (poId: number) => {
    const po = openOrders.find((o) => o.id === poId);
    if (!po) return;
    setForm({
      po_id: po.id,
      supplier_id: po.supplier_id,
      product_id: po.product_id,
      quantity: po.quantity,
      promised_lead_time_days: po.promised_lead_time_days,
      shipping_mode: po.shipping_mode,
      urgency_level: po.urgency_level,
    });
  };

  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await apiFetch(
        '/api/scenarios/simulate',
        {
          method: 'POST',
          body: JSON.stringify(form),
        },
        role
      );
      setSimResult(res);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="scenario-analysis-page">
      <div>
        <h2 className="text-xl font-bold text-white">
          Procurement What-If Scenario Simulator
        </h2>
        <p className="text-sm text-slate-400">
          Explore how adjusting order quantity, promised lead time, shipping mode, or supplier selection shifts model-projected delivery risk
        </p>
      </div>

      {/* Prominent Non-Causal Caveat Banner */}
      <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-700/70 text-amber-200 text-xs flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold uppercase tracking-wide text-amber-300">
            Methodological Distinction — Associative Model Projection vs. Proven Causal Prediction:
          </span>{' '}
          {simResult?.methodology_disclaimer ||
            'Scenario projections evaluate how the calibrated ML model responds to altered planning inputs based on historical correlations. Always verify contractual supplier capacity and logistics readiness before modifying orders.'}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Scenario Controls */}
        <form
          onSubmit={handleRunSimulation}
          className="lg:col-span-4 bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4 text-xs"
        >
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Sliders className="w-4 h-4 text-blue-400" />
            Configure Planning Variables
          </h3>

          <div>
            <label className="block text-slate-400 mb-1">
              Baseline Open Purchase Order
            </label>
            <select
              value={form.po_id}
              onChange={(e) => handleSelectBaselinePo(Number(e.target.value))}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
            >
              {openOrders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.po_number} — {o.supplier_name} ({o.promised_lead_time_days}d)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Candidate Supplier (Test Re-Allocation)
            </label>
            <select
              value={form.supplier_id}
              onChange={(e) =>
                setForm({ ...form, supplier_id: Number(e.target.value) })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
            >
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.supplier_code} — {s.name} ({s.region})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Order Quantity (Units): <strong className="text-white">{form.quantity}</strong>
            </label>
            <input
              type="range"
              min={50}
              max={15000}
              step={50}
              value={form.quantity}
              onChange={(e) =>
                setForm({ ...form, quantity: Number(e.target.value) })
              }
              className="w-full accent-blue-500"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Promised Lead Time (Days):{' '}
              <strong className="text-white">
                {form.promised_lead_time_days} days
              </strong>
            </label>
            <input
              type="range"
              min={5}
              max={75}
              step={1}
              value={form.promised_lead_time_days}
              onChange={(e) =>
                setForm({
                  ...form,
                  promised_lead_time_days: Number(e.target.value),
                })
              }
              className="w-full accent-blue-500"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Shipping Mode</label>
            <select
              value={form.shipping_mode}
              onChange={(e) =>
                setForm({ ...form, shipping_mode: e.target.value })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
            >
              <option value="Ocean Freight">Ocean Freight</option>
              <option value="Air Freight">Air Freight</option>
              <option value="Air Express">Air Express</option>
              <option value="Ground Freight">Ground Freight</option>
              <option value="Rail Intermodal">Rail Intermodal</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Order Urgency</label>
            <select
              value={form.urgency_level}
              onChange={(e) =>
                setForm({ ...form, urgency_level: e.target.value })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
            >
              <option value="low">Low</option>
              <option value="standard">Standard</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={loading}
            data-testid="run-scenario-btn"
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4" />
            {loading ? 'Simulating...' : 'Evaluate Scenario Projection'}
          </button>
        </form>

        {/* Right: Baseline vs Scenario Comparison */}
        <div className="lg:col-span-8 space-y-5">
          {simResult && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {/* Baseline Card */}
                {simResult.baseline && (
                  <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2">
                    <div className="text-xs font-semibold text-slate-400 uppercase">
                      Current Baseline Order
                    </div>
                    <div className="text-2xl font-bold text-white">
                      {(simResult.baseline.calibrated_probability * 100).toFixed(1)}%
                    </div>
                    <RiskBadge
                      category={simResult.baseline.risk_category}
                      prob={simResult.baseline.calibrated_probability}
                    />
                    <div className="text-xs text-slate-400 pt-2 space-y-1">
                      <div>Supplier: {simResult.baseline.supplier_name}</div>
                      <div>
                        Est. Delay: +{simResult.baseline.expected_delay_days} days
                      </div>
                      <div>
                        Risk Exposure: $
                        {simResult.baseline.expected_financial_impact.toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}

                {/* Modified Scenario Card */}
                <div className="bg-slate-900/90 border border-blue-700/80 rounded-xl p-4 space-y-2">
                  <div className="text-xs font-semibold text-blue-400 uppercase">
                    Simulated Scenario
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {(simResult.scenario.calibrated_probability * 100).toFixed(1)}%
                  </div>
                  <RiskBadge
                    category={simResult.scenario.risk_category}
                    prob={simResult.scenario.calibrated_probability}
                  />
                  <div className="text-xs text-slate-300 pt-2 space-y-1">
                    <div>Supplier: {simResult.scenario.supplier_name}</div>
                    <div>
                      Est. Delay: +{simResult.scenario.expected_delay_days} days
                    </div>
                    <div>
                      Risk Exposure: $
                      {simResult.scenario.expected_financial_impact.toLocaleString()}
                    </div>
                  </div>
                </div>

                {/* Net Impact Delta Card */}
                {simResult.deltas && (
                  <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2">
                    <div className="text-xs font-semibold text-slate-400 uppercase">
                      Projected Scenario Delta
                    </div>
                    <div
                      className={`text-2xl font-bold ${
                        simResult.deltas.probability_delta <= 0
                          ? 'text-emerald-400'
                          : 'text-rose-400'
                      }`}
                    >
                      {simResult.deltas.probability_delta_pct_points > 0 ? '+' : ''}
                      {simResult.deltas.probability_delta_pct_points}% pts
                    </div>
                    <div className="text-xs text-slate-300 pt-2 space-y-1">
                      <div>
                        Delay Shift:{' '}
                        {simResult.deltas.expected_delay_days_delta > 0 ? '+' : ''}
                        {simResult.deltas.expected_delay_days_delta} days
                      </div>
                      <div>
                        Exposure Delta: $
                        {simResult.deltas.expected_financial_impact_delta.toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Alternative Pre-Qualified Suppliers in Category */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
                <h4 className="text-sm font-bold text-white mb-1">
                  Alternative Pre-Qualified Suppliers in Same Category
                </h4>
                <p className="text-xs text-slate-400 mb-3">
                  Model-projected late-delivery probability under identical quantity ({form.quantity} units) & lead time ({form.promised_lead_time_days}d)
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400">
                        <th className="pb-2">Supplier</th>
                        <th className="pb-2">Region / Tier</th>
                        <th className="pb-2">Prior Completed Orders</th>
                        <th className="pb-2">Historical OTD Rate</th>
                        <th className="pb-2">Projected Scenario Delay Prob</th>
                        <th className="pb-2 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {simResult.alternative_suppliers?.map((alt: any) => (
                        <tr key={alt.supplier_id}>
                          <td className="py-2.5 font-medium text-white">
                            {alt.supplier_code} — {alt.supplier_name}
                          </td>
                          <td className="py-2.5 text-slate-300">
                            {alt.region} ({alt.tier})
                          </td>
                          <td className="py-2.5 text-slate-300">
                            {alt.prior_completed_orders}
                          </td>
                          <td className="py-2.5 text-emerald-400 font-semibold">
                            {alt.historical_otd_rate !== null
                              ? `${(alt.historical_otd_rate * 100).toFixed(1)}%`
                              : 'Cold-Start'}
                          </td>
                          <td className="py-2.5 font-bold text-blue-400">
                            {(alt.projected_delay_probability * 100).toFixed(1)}%
                          </td>
                          <td className="py-2.5 text-right">
                            <button
                              onClick={() =>
                                setForm({ ...form, supplier_id: alt.supplier_id })
                              }
                              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-blue-600 text-slate-200 hover:text-white text-[11px]"
                            >
                              Select in Simulator
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
