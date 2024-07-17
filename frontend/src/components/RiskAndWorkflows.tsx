import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle,
  Info,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { apiFetch } from '../api';
import { RiskBadge } from './OverviewAndOrders';

// ============================================================================
// 4. RISK PREDICTIONS & INDIVIDUAL EXPLAINABILITY TAB
// ============================================================================
export const PredictionsTab: React.FC<{
  role: string;
  initialPoId?: number | null;
}> = ({ role, initialPoId }) => {
  const [predictions, setPredictions] = useState<any[]>([]);
  const [selectedPred, setSelectedPred] = useState<any>(null);
  const [riskFilter, setRiskFilter] = useState('');
  const [relFilter, setRelFilter] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [aiBriefing, setAiBriefing] = useState<any>(null);
  const [aiQuestion, setAiQuestion] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  const loadPredictions = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (riskFilter) params.set('risk_category', riskFilter);
      if (relFilter) params.set('reliability_status', relFilter);
      if (search) params.set('search', search);
      const res = await apiFetch(`/api/predictions?${params.toString()}`, {}, role);
      setPredictions(res);
      if (initialPoId) {
        const matched = res.find((p: any) => p.po_id === initialPoId);
        if (matched) {
          setSelectedPred(matched);
          return;
        }
      }
      if (res.length > 0 && !selectedPred) {
        setSelectedPred(res[0]);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPredictions();
  }, [riskFilter, relFilter, initialPoId, role]);

  const handleGenerateBriefing = async (poId: number) => {
    setAiLoading(true);
    try {
      const res = await apiFetch(
        '/api/ai/briefing',
        {
          method: 'POST',
          body: JSON.stringify({ po_id: poId, question: aiQuestion || undefined }),
        },
        role
      );
      setAiBriefing(res);
    } finally {
      setAiLoading(false);
    }
  };

  useEffect(() => {
    setAiBriefing(null);
  }, [selectedPred?.po_id]);

  return (
    <div className="space-y-5" data-testid="predictions-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">
            Calibrated Delay Risk Predictions & SHAP Explainability
          </h2>
          <p className="text-sm text-slate-400">
            Point-in-time late-delivery probabilities, local feature attributions, and reliability intelligence
          </p>
        </div>
        <button
          onClick={async () => {
            await apiFetch('/api/predictions/refresh', { method: 'POST' }, role);
            loadPredictions();
          }}
          className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 flex items-center gap-2"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Recalculate Batch Predictions
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadPredictions()}
            placeholder="Filter by PO number, supplier, or component..."
            className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white"
          />
        </div>
        <select
          value={riskFilter}
          onChange={(e) => setRiskFilter(e.target.value)}
          className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
        >
          <option value="">All Risk Tiers</option>
          <option value="critical">Critical (&gt;=80%)</option>
          <option value="high">High (60-80%)</option>
          <option value="moderate">Moderate (35-60%)</option>
          <option value="low">Low (&lt;35%)</option>
        </select>
        <select
          value={relFilter}
          onChange={(e) => setRelFilter(e.target.value)}
          className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
        >
          <option value="">All Reliability Statuses</option>
          <option value="reliable">Reliable History</option>
          <option value="caution_manual_review">Caution — Manual Check</option>
          <option value="unreliable_cold_start">Cold-Start Supplier</option>
        </select>
      </div>

      {/* Master-Detail Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left List of Open Order Predictions */}
        <div className="lg:col-span-5 bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden flex flex-col max-h-[760px]">
          <div className="p-3 bg-slate-950/70 border-b border-slate-800 text-xs font-semibold text-slate-300 flex justify-between">
            <span>Open Purchase Orders ({predictions.length})</span>
            <span>Sorted by Business Priority</span>
          </div>
          <div className="overflow-y-auto divide-y divide-slate-800/60">
            {loading ? (
              <div className="p-6 text-center text-xs text-slate-400">
                Loading predictions...
              </div>
            ) : (
              predictions.map((pred) => {
                const isSelected = selectedPred?.po_id === pred.po_id;
                return (
                  <button
                    key={pred.id}
                    onClick={() => setSelectedPred(pred)}
                    className={`w-full text-left p-3.5 transition hover:bg-slate-800/50 ${
                      isSelected
                        ? 'bg-blue-950/40 border-l-4 border-l-blue-500'
                        : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-white">
                        {pred.po_number}
                      </span>
                      <RiskBadge
                        category={pred.risk_category}
                        prob={pred.calibrated_probability}
                      />
                    </div>
                    <div className="text-xs font-medium text-slate-200 mt-1">
                      {pred.supplier_name}
                    </div>
                    <div className="text-[11px] text-slate-400 flex items-center justify-between mt-1">
                      <span>{pred.product_name}</span>
                      <span>Due: {pred.promised_delivery_date}</span>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[11px]">
                      <span className="text-blue-400 font-medium">
                        Priority Score: {pred.business_priority_score.toFixed(1)}/100
                      </span>
                      {pred.reliability_status !== 'reliable' && (
                        <span className="text-amber-400 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          {pred.reliability_status === 'unreliable_cold_start'
                            ? 'Cold-Start'
                            : 'Reliability Warning'}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Detail: Individual Prediction Explainability & Reliability Dossier */}
        <div
          className="lg:col-span-7 space-y-5"
          data-testid="prediction-explanation-panel"
        >
          {!selectedPred ? (
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-8 text-center text-slate-400 text-sm">
              Select a purchase order on the left to inspect its calibrated prediction and SHAP feature attributions.
            </div>
          ) : (
            <>
              {/* Header Card */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-blue-400">
                        {selectedPred.po_number}
                      </span>
                      <RiskBadge
                        category={selectedPred.risk_category}
                        prob={selectedPred.calibrated_probability}
                      />
                    </div>
                    <h3 className="text-lg font-bold text-white mt-1">
                      {selectedPred.supplier_name} — {selectedPred.product_name}
                    </h3>
                    <p className="text-xs text-slate-400">
                      Model: <span className="text-slate-200 font-mono">{selectedPred.model_version}</span> | As-Of Date: {selectedPred.as_of_date} | Threshold: {(selectedPred.threshold_used * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-slate-400">
                      Calibrated Late Probability
                    </div>
                    <div className="text-3xl font-extrabold text-white">
                      {(selectedPred.calibrated_probability * 100).toFixed(1)}%
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Raw Uncalibrated: {(selectedPred.raw_probability * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                {/* Reliability Warnings Banner */}
                {selectedPred.reliability_warnings &&
                selectedPred.reliability_warnings.length > 0 ? (
                  <div
                    className="p-3.5 rounded-lg bg-amber-950/60 border border-amber-700/80 text-amber-200 text-xs space-y-1.5"
                    data-testid="reliability-warning-banner"
                  >
                    <div className="font-bold flex items-center gap-2 text-amber-300">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>
                        Reliability Status: {selectedPred.reliability_status.toUpperCase()}
                      </span>
                    </div>
                    <ul className="list-disc list-inside space-y-1">
                      {selectedPred.reliability_warnings.map(
                        (w: string, idx: number) => (
                          <li key={idx}>{w}</li>
                        )
                      )}
                    </ul>
                  </div>
                ) : (
                  <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 shrink-0" />
                    <span>
                      Prediction Reliability Verified: Sufficient supplier history ({selectedPred.historical_context.supplier_completed_orders_prior} prior completed orders) and within training feature distribution.
                    </span>
                  </div>
                )}

                {/* Key Operational Metrics Row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <div className="text-slate-400">Business Priority</div>
                    <div className="text-base font-bold text-blue-400 mt-0.5">
                      {selectedPred.business_priority_score.toFixed(1)} / 100
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <div className="text-slate-400">Expected Delay Slip</div>
                    <div className="text-base font-bold text-white mt-0.5">
                      +{selectedPred.expected_delay_days} days
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <div className="text-slate-400">Expected Risk Impact</div>
                    <div className="text-base font-bold text-amber-400 mt-0.5">
                      ${selectedPred.expected_financial_impact.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <div className="text-slate-400">Prior Supplier OTD</div>
                    <div className="text-base font-bold text-white mt-0.5">
                      {selectedPred.historical_context.supplier_raw_otd_rate_prior !== null
                        ? `${(
                            selectedPred.historical_context
                              .supplier_raw_otd_rate_prior * 100
                          ).toFixed(1)}%`
                        : 'Cold-Start'}
                    </div>
                  </div>
                </div>
              </div>

              {/* SHAP / Additive Feature Attribution Chart & Table */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-bold text-white">
                      Top Contributing Risk Factors ({selectedPred.explanation_method})
                    </h4>
                    <p className="text-xs text-slate-400">
                      Positive bars push late-delivery risk higher; negative bars reduce predicted risk
                    </p>
                  </div>
                </div>

                <div className="h-52">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={selectedPred.top_contributors}
                      layout="vertical"
                      margin={{ left: 20, right: 20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis type="number" stroke="#94a3b8" fontSize={11} />
                      <YAxis
                        type="category"
                        dataKey="display_label"
                        stroke="#e2e8f0"
                        fontSize={11}
                        width={185}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          borderColor: '#334155',
                          fontSize: '12px',
                        }}
                      />
                      <Bar dataKey="contribution_score" name="Attribution Score" isAnimationActive={false}>
                        {selectedPred.top_contributors.map(
                          (entry: any, index: number) => (
                            <Cell
                              key={index}
                              fill={
                                entry.contribution_score >= 0
                                  ? '#ef4444'
                                  : '#10b981'
                              }
                            />
                          )
                        )}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="space-y-2">
                  {selectedPred.top_contributors.map((c: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-slate-950/90 border border-slate-800/80 flex items-start justify-between gap-3 text-xs"
                    >
                      <div>
                        <span className="font-semibold text-white">
                          {c.display_label}:{' '}
                        </span>
                        <span className="font-mono text-blue-300">
                          {String(c.feature_value)}
                        </span>
                        <p className="text-slate-400 mt-0.5">
                          {c.human_explanation}
                        </p>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded font-mono font-semibold shrink-0 ${
                          c.contribution_score >= 0
                            ? 'bg-rose-950 text-rose-300 border border-rose-800'
                            : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        }`}
                      >
                        {c.contribution_score >= 0 ? '+' : ''}
                        {c.contribution_score.toFixed(3)}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="p-3 rounded bg-slate-950 border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
                  <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                  <span>{selectedPred.explanation_limitations}</span>
                </div>
              </div>

              {/* Optional Fact-Grounded AI Analyst Briefing Card */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bot className="w-4 h-4 text-blue-400" />
                    <h4 className="text-sm font-bold text-white">
                      Fact-Grounded Analyst Assistant & Investigation Guide
                    </h4>
                  </div>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    Works Offline by Default • Zero Hallucination Guard
                  </span>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={aiQuestion}
                    onChange={(e) => setAiQuestion(e.target.value)}
                    placeholder="Optional analyst focus question (e.g. Should we expedite or check safety stock?)..."
                    className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white"
                  />
                  <button
                    onClick={() => handleGenerateBriefing(selectedPred.po_id)}
                    disabled={aiLoading}
                    className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 shrink-0"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    {aiLoading ? 'Synthesizing...' : 'Generate Grounded Briefing'}
                  </button>
                </div>

                {aiBriefing && (
                  <div className="p-4 rounded-lg bg-slate-950 border border-blue-900/60 space-y-3 text-xs">
                    <div className="flex items-center justify-between text-[11px] text-blue-400">
                      <span>
                        Engine: {aiBriefing.provider_used} ({aiBriefing.model_used})
                      </span>
                      <span>Cost: ${aiBriefing.estimated_cost_usd.toFixed(4)}</span>
                    </div>
                    <p className="text-slate-200 leading-relaxed whitespace-pre-line">
                      {aiBriefing.executive_summary}
                    </p>
                    <div>
                      <div className="font-semibold text-slate-300 mb-1">
                        Suggested Buyer Investigation Questions:
                      </div>
                      <ul className="list-disc list-inside text-slate-400 space-y-1">
                        {aiBriefing.suggested_investigation_questions.map(
                          (q: string, i: number) => (
                            <li key={i}>{q}</li>
                          )
                        )}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// 5. EARLY WARNING CENTER TAB
// ============================================================================
export const EarlyWarningsTab: React.FC<{
  role: string;
  onInspectPo: (poId: number) => void;
}> = ({ role, onInspectPo }) => {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [severityFilter, setSeverityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (severityFilter) params.set('severity', severityFilter);
      if (statusFilter) params.set('status', statusFilter);
      if (search) params.set('search', search);
      const res = await apiFetch(`/api/alerts?${params.toString()}`, {}, role);
      setAlerts(res);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
  }, [severityFilter, statusFilter, role]);

  const handleAlertAction = async (alertId: number, statusVal: string) => {
    await apiFetch(
      `/api/alerts/${alertId}/action`,
      {
        method: 'POST',
        body: JSON.stringify({
          status: statusVal,
          resolution_notes: `Marked as ${statusVal} by procurement reviewer`,
        }),
      },
      role
    );
    loadAlerts();
  };

  return (
    <div className="space-y-5" data-testid="early-warnings-page">
      <div>
        <h2 className="text-xl font-bold text-white">
          Early-Warning Alert Center
        </h2>
        <p className="text-sm text-slate-400">
          Upcoming high-risk and critical deliveries requiring proactive buyer acknowledgement and supplier milestone tracking ({alerts.length} alerts)
        </p>
      </div>

      {/* Filters */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadAlerts()}
            placeholder="Search alerts by PO, supplier, or factor..."
            className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white"
          />
        </div>
        <button
          onClick={loadAlerts}
          className="px-3 py-1.5 rounded-lg bg-slate-800 text-xs text-slate-200 border border-slate-700"
        >
          Search
        </button>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical Severity</option>
          <option value="high">High Severity</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
        >
          <option value="">All Statuses</option>
          <option value="open">Open (Unacknowledged)</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="escalated">Escalated</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {/* Alert Cards */}
      <div className="space-y-3">
        {loading ? (
          <div className="p-6 text-center text-slate-400 text-xs">
            Loading early-warning alerts...
          </div>
        ) : (
          alerts.map((al) => (
            <div
              key={al.id}
              className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4"
            >
              <div className="space-y-1 max-w-3xl">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                      al.severity === 'critical'
                        ? 'bg-rose-950 text-rose-300 border border-rose-700'
                        : 'bg-orange-950 text-orange-300 border border-orange-700'
                    }`}
                  >
                    {al.severity}
                  </span>
                  <span className="text-xs font-mono text-blue-400 font-semibold">
                    Priority Rank #{al.review_priority}
                  </span>
                  <span className="text-xs text-slate-400">
                    • Promised Due: {al.due_date}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] uppercase font-semibold text-slate-300">
                    {al.status}
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white">{al.title}</h4>
                <p className="text-xs text-slate-300">{al.description}</p>
                {al.acknowledged_by && (
                  <p className="text-[11px] text-emerald-400">
                    Last action by {al.acknowledged_by} ({al.resolution_notes})
                  </p>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => onInspectPo(al.po_id)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-blue-300 font-medium border border-slate-700"
                >
                  Inspect SHAP
                </button>
                {al.status === 'open' && (
                  <button
                    onClick={() => handleAlertAction(al.id, 'acknowledged')}
                    className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs text-white font-medium"
                  >
                    Acknowledge
                  </button>
                )}
                {al.status !== 'escalated' && (
                  <button
                    onClick={() => handleAlertAction(al.id, 'escalated')}
                    className="px-3 py-1.5 rounded-lg bg-rose-950/80 hover:bg-rose-900 border border-rose-800 text-xs text-rose-200 font-medium"
                  >
                    Escalate
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

// ============================================================================
// 6. HUMAN-IN-THE-LOOP REVIEW QUEUE TAB
// ============================================================================
export const ReviewQueueTab: React.FC<{
  role: string;
  onInspectPo: (poId: number) => void;
}> = ({ role, onInspectPo }) => {
  const [queueData, setQueueData] = useState<any>({
    rules: {},
    summary: {},
    items: [],
  });
  const [statusFilter, setStatusFilter] = useState('');
  const [withinCapOnly, setWithinCapOnly] = useState(false);
  const [page, setPage] = useState(0);
  const pageSize = 20;
  const [showRulesEditor, setShowRulesEditor] = useState(false);
  const [rulesForm, setRulesForm] = useState<any>(null);
  const [rulesError, setRulesError] = useState('');
  const [selectedItemForDecision, setSelectedItemForDecision] =
    useState<any>(null);
  const [decisionForm, setDecisionForm] = useState({
    decision: 'accepted',
    decision_reason: 'Confirmed supplier milestone recovery & buffer allocation',
    decision_notes: '',
  });
  const [auditLogs, setAuditLogs] = useState<any[]>([]);

  const loadQueue = async () => {
    const params = new URLSearchParams();
    if (statusFilter) params.set('status', statusFilter);
    if (withinCapOnly) params.set('within_capacity_only', 'true');
    const res = await apiFetch(`/api/reviews?${params.toString()}`, {}, role);
    setQueueData(res);
    if (!rulesForm) {
      setRulesForm(res.rules);
    }
    const logs = await apiFetch('/api/audit-logs?limit=12', {}, role);
    setAuditLogs(logs);
  };

  useEffect(() => {
    loadQueue();
  }, [statusFilter, withinCapOnly, role]);

  useEffect(() => {
    setPage(0);
  }, [statusFilter, withinCapOnly]);

  const handleSaveRules = async (e: React.FormEvent) => {
    e.preventDefault();
    setRulesError('');
    try {
      await apiFetch(
        '/api/rules',
        {
          method: 'PUT',
          body: JSON.stringify(rulesForm),
        },
        role
      );
      setShowRulesEditor(false);
      loadQueue();
    } catch (err: any) {
      setRulesError(err.message || 'Failed to update prioritization rules');
    }
  };

  const handleSubmitDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItemForDecision) return;
    await apiFetch(
      `/api/reviews/${selectedItemForDecision.id}/decision`,
      {
        method: 'POST',
        body: JSON.stringify(decisionForm),
      },
      role
    );
    setSelectedItemForDecision(null);
    loadQueue();
  };

  const { summary, rules, items } = queueData;
  const totalItems = (items || []).length;
  const pageCount = Math.max(1, Math.ceil(totalItems / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const pageItems = (items || []).slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize
  );

  return (
    <div className="space-y-5" data-testid="review-queue-page">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">
            Human-in-the-Loop Procurement Review Queue
          </h2>
          <p className="text-sm text-slate-400">
            Transparent prioritization separating ML Calibrated Delay Probability from composite Business Priority Score. All purchasing actions require human authorization.
          </p>
        </div>
        <button
          onClick={() => setShowRulesEditor(!showRulesEditor)}
          className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-blue-300 border border-slate-700 flex items-center gap-2"
        >
          <Settings2 className="w-4 h-4" />
          Configure Thresholds & Priority Weights
        </button>
      </div>

      {/* Summary Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 text-xs">
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
          <div className="text-slate-400">Reviewer Capacity</div>
          <div className="text-lg font-bold text-blue-400 mt-0.5">
            Top {rules.reviewer_capacity || 25} POs
          </div>
        </div>
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
          <div className="text-slate-400">Pending Review</div>
          <div className="text-lg font-bold text-amber-400 mt-0.5">
            {summary.pending || 0}
          </div>
        </div>
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
          <div className="text-slate-400">Accepted Action</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">
            {summary.accepted || 0}
          </div>
        </div>
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
          <div className="text-slate-400">Investigating</div>
          <div className="text-lg font-bold text-blue-300 mt-0.5">
            {summary.investigating || 0}
          </div>
        </div>
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
          <div className="text-slate-400">Deferred</div>
          <div className="text-lg font-bold text-slate-300 mt-0.5">
            {summary.deferred || 0}
          </div>
        </div>
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
          <div className="text-slate-400">Dismissed Override</div>
          <div className="text-lg font-bold text-slate-400 mt-0.5">
            {summary.dismissed || 0}
          </div>
        </div>
      </div>

      {/* Collapsible Business Rules & Weights Editor */}
      {showRulesEditor && rulesForm && (
        <div className="bg-slate-900 border border-blue-800/70 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white">
                Inspect & Edit Prioritization Thresholds and Scoring Weights
              </h3>
              <p className="text-xs text-slate-400">
                Requires role `procurement_lead` or `admin`. Changes re-rank the queue and record an immutable audit entry.
              </p>
            </div>
          </div>
          {rulesError && (
            <div className="p-3 rounded bg-rose-950/70 border border-rose-700 text-xs text-rose-200">
              {rulesError}
            </div>
          )}
          <form onSubmit={handleSaveRules} className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <label className="block text-slate-400 mb-1">
                High Risk Threshold (0-1)
              </label>
              <input
                type="number"
                step="0.05"
                value={rulesForm.high_risk_threshold}
                onChange={(e) =>
                  setRulesForm({
                    ...rulesForm,
                    high_risk_threshold: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">
                Critical Risk Threshold (0-1)
              </label>
              <input
                type="number"
                step="0.05"
                value={rulesForm.critical_risk_threshold}
                onChange={(e) =>
                  setRulesForm({
                    ...rulesForm,
                    critical_risk_threshold: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">
                Daily Reviewer Capacity (Orders)
              </label>
              <input
                type="number"
                min={1}
                value={rulesForm.reviewer_capacity}
                onChange={(e) =>
                  setRulesForm({
                    ...rulesForm,
                    reviewer_capacity: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">
                Weight: ML Delay Prob
              </label>
              <input
                type="number"
                step="0.05"
                value={rulesForm.weight_ml_probability}
                onChange={(e) =>
                  setRulesForm({
                    ...rulesForm,
                    weight_ml_probability: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">
                Weight: Financial Impact
              </label>
              <input
                type="number"
                step="0.05"
                value={rulesForm.weight_financial_impact}
                onChange={(e) =>
                  setRulesForm({
                    ...rulesForm,
                    weight_financial_impact: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">
                Weight: Order Urgency
              </label>
              <input
                type="number"
                step="0.05"
                value={rulesForm.weight_urgency}
                onChange={(e) =>
                  setRulesForm({
                    ...rulesForm,
                    weight_urgency: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">
                Weight: SKU Criticality
              </label>
              <input
                type="number"
                step="0.05"
                value={rulesForm.weight_criticality}
                onChange={(e) =>
                  setRulesForm({
                    ...rulesForm,
                    weight_criticality: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                className="w-full px-4 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-semibold"
              >
                Save & Re-Rank Queue
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 text-xs">
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-slate-200"
          >
            <option value="">All Queue Items ({summary.total_in_queue || 0})</option>
            <option value="pending">Pending Review</option>
            <option value="accepted">Accepted</option>
            <option value="investigating">Investigating</option>
            <option value="deferred">Deferred</option>
            <option value="dismissed">Dismissed</option>
            <option value="resolved">Resolved (Order Closed)</option>
          </select>
          <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={withinCapOnly}
              onChange={(e) => setWithinCapOnly(e.target.checked)}
              className="rounded border-slate-700"
            />
            <span>
              Show only items within daily reviewer capacity (Top{' '}
              {rules.reviewer_capacity || 25})
            </span>
          </label>
        </div>
      </div>

      {/* Review Queue Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-950/70 border-b border-slate-800 text-slate-400">
                <th className="p-3 font-medium">Rank</th>
                <th className="p-3 font-medium">PO & Supplier</th>
                <th className="p-3 font-medium">ML Delay Prob</th>
                <th className="p-3 font-medium">Business Priority</th>
                <th className="p-3 font-medium">Why Prioritized & Recommended Action</th>
                <th className="p-3 font-medium">Review Status & Decision</th>
                <th className="p-3 font-medium text-right">Human Oversight</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {pageItems.map((item: any) => (
                <tr key={item.id} className="hover:bg-slate-800/40">
                  <td className="p-3">
                    <div className="font-bold text-blue-400">
                      #{item.priority_rank}
                    </div>
                    {item.within_reviewer_capacity ? (
                      <span className="inline-block mt-1 px-1.5 py-0.5 text-[10px] rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                        In Capacity
                      </span>
                    ) : (
                      <span className="inline-block mt-1 px-1.5 py-0.5 text-[10px] rounded bg-slate-800 text-slate-400">
                        Backlog
                      </span>
                    )}
                  </td>
                  <td className="p-3">
                    <div className="font-mono font-bold text-white">
                      {item.po_number}
                    </div>
                    <div className="text-slate-200 font-medium">
                      {item.supplier_name}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {item.product_name} • ${item.order_value.toLocaleString()}
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="text-base font-bold text-rose-400">
                      {(item.ml_calibrated_probability * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-slate-400">
                      Calibrated Model Output
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="text-base font-bold text-blue-400">
                      {item.business_priority_score.toFixed(1)} / 100
                    </div>
                    <div className="text-[10px] text-slate-400">
                      Impact: {item.operational_impact_score} | Urg: {item.urgency_score}
                    </div>
                  </td>
                  <td className="p-3 max-w-md">
                    <div className="text-slate-200">{item.prioritization_rationale}</div>
                    <div className="text-blue-300 text-[11px] mt-1 font-medium">
                      Recommendation: {item.recommended_action}
                    </div>
                  </td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-0.5 rounded uppercase text-[10px] font-bold ${
                        item.status === 'accepted'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-700'
                          : item.status === 'investigating'
                          ? 'bg-blue-950 text-blue-300 border border-blue-700'
                          : item.status === 'pending'
                          ? 'bg-amber-950 text-amber-300 border border-amber-700'
                          : 'bg-slate-800 text-slate-300'
                      }`}
                    >
                      {item.status}
                    </span>
                    {item.decision_reason && (
                      <div className="text-[11px] text-slate-300 mt-1">
                        <strong>{item.decided_by}:</strong> {item.decision_reason}
                      </div>
                    )}
                  </td>
                  <td className="p-3 text-right space-y-1.5">
                    <button
                      onClick={() => {
                        setSelectedItemForDecision(item);
                        setDecisionForm({
                          decision: 'accepted',
                          decision_reason:
                            item.decision_reason ||
                            'Confirmed supplier expedite & milestone plan',
                          decision_notes: item.decision_notes || '',
                        });
                      }}
                      data-testid={`review-decide-btn-${item.priority_rank}`}
                      className="block w-full px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-semibold text-center"
                    >
                      Record Decision
                    </button>
                    <button
                      onClick={() => onInspectPo(item.po_id)}
                      className="block w-full px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-center"
                    >
                      Inspect SHAP
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 bg-slate-950/50 px-3 py-2.5 text-xs text-slate-400">
          <span>
            Showing{' '}
            <strong className="text-slate-200">
              {totalItems === 0 ? 0 : currentPage * pageSize + 1}–
              {Math.min(totalItems, (currentPage + 1) * pageSize)}
            </strong>{' '}
            of <strong className="text-slate-200">{totalItems}</strong> queue items
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage(Math.max(0, currentPage - 1))}
              disabled={currentPage === 0}
              className="rounded border border-slate-700 px-2.5 py-1 font-medium text-slate-300 transition hover:bg-slate-800 disabled:opacity-40"
            >
              Previous
            </button>
            <span className="font-mono text-[11px]">
              Page {currentPage + 1} / {pageCount}
            </span>
            <button
              type="button"
              onClick={() => setPage(Math.min(pageCount - 1, currentPage + 1))}
              disabled={currentPage >= pageCount - 1}
              className="rounded border border-slate-700 px-2.5 py-1 font-medium text-slate-300 transition hover:bg-slate-800 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
        <h3 className="text-sm font-bold text-white mb-3">
          Recent Human Oversight & Governance Audit Trail
        </h3>
        <div className="space-y-2 text-xs">
          {auditLogs.slice(0, 6).map((log) => (
            <div
              key={log.id}
              className="p-2.5 rounded bg-slate-950 border border-slate-800 flex flex-wrap items-center justify-between gap-2"
            >
              <div>
                <span className="font-mono text-blue-400 font-semibold">
                  [{log.action}]
                </span>{' '}
                <span className="text-white font-medium">{log.actor}</span>{' '}
                <span className="text-slate-400">({log.role})</span> —{' '}
                <span className="text-slate-300">
                  {JSON.stringify(log.details).slice(0, 120)}
                </span>
              </div>
              <span className="text-slate-500 font-mono text-[11px]">
                {log.timestamp.slice(0, 19).replace('T', ' ')} UTC
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Record Decision Modal */}
      {selectedItemForDecision && (
        <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-base font-bold text-white">
              Record Human Review Decision — {selectedItemForDecision.po_number}
            </h3>
            <p className="text-xs text-slate-400">
              Supplier: {selectedItemForDecision.supplier_name} | ML Delay Prob:{' '}
              {(selectedItemForDecision.ml_calibrated_probability * 100).toFixed(1)}% | Business Priority:{' '}
              {selectedItemForDecision.business_priority_score.toFixed(1)}/100
            </p>
            <form onSubmit={handleSubmitDecision} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">
                  Human Disposition
                </label>
                <select
                  value={decisionForm.decision}
                  onChange={(e) =>
                    setDecisionForm({ ...decisionForm, decision: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                >
                  <option value="accepted">
                    Accept Recommendation (Initiate Expedite / Supplier Outreach)
                  </option>
                  <option value="investigating">
                    Investigate Further (Request Sub-Tier / Factory Verification)
                  </option>
                  <option value="deferred">
                    Defer Review (Covered by Plant Safety Stock Buffer)
                  </option>
                  <option value="dismissed">
                    Dismiss Alert (Carrier ASN Confirmed On-Schedule)
                  </option>
                  <option value="escalated">
                    Escalate to VP Procurement & Plant Manager
                  </option>
                </select>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">
                  Decision Reason (Required for Audit Log)
                </label>
                <input
                  type="text"
                  required
                  value={decisionForm.decision_reason}
                  onChange={(e) =>
                    setDecisionForm({
                      ...decisionForm,
                      decision_reason: e.target.value,
                    })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">
                  Detailed Reviewer Notes & Action Plan
                </label>
                <textarea
                  rows={3}
                  value={decisionForm.decision_notes}
                  onChange={(e) =>
                    setDecisionForm({
                      ...decisionForm,
                      decision_notes: e.target.value,
                    })
                  }
                  placeholder="Document supplier commitment, air-freight quote, or buffer stock verification..."
                  className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSelectedItemForDecision(null)}
                  className="px-4 py-2 rounded bg-slate-800 text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="submit-review-decision-btn"
                  className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white font-semibold"
                >
                  Commit Authoritative Decision
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
