import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Bot,
  Download,
  FileSpreadsheet,
  FileText,
  Server,
  Shield,
  Upload,
} from 'lucide-react';
import { apiFetch, downloadFile } from '../api';

// ============================================================================
// 10. REPORTS & AUDIT GOVERNANCE TAB
// ============================================================================
export const ReportsTab: React.FC<{ role: string }> = ({ role }) => {
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [_overview, setOverview] = useState<any>(null);

  useEffect(() => {
    apiFetch('/api/audit-logs?limit=60', {}, role).then(setAuditLogs);
    apiFetch('/api/dashboard/overview', {}, role).then(setOverview);
  }, [role]);

  return (
    <div className="space-y-6" data-testid="reports-page">
      <div>
        <h2 className="text-xl font-bold text-white">
          Executive Reports, Data Exports & Governance Audit Trail
        </h2>
        <p className="text-sm text-slate-400">
          Download formatted PDF executive dossiers, calibrated prediction CSV datasets, and inspect the immutable human decision log
        </p>
      </div>

      {/* Downloadable Deliverables Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="w-10 h-10 rounded-lg bg-rose-950/80 border border-rose-800 flex items-center justify-center text-rose-300 mb-3">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-white">
              Executive Procurement Risk & Model Quality Report (PDF)
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Formatted multi-section PDF containing operational KPIs, Champion ML model test metrics, and top prioritized open orders requiring human review.
            </p>
          </div>
          <button
            type="button"
            onClick={() => downloadFile('/api/reports/executive.pdf', 'executive_supplier_risk_report.pdf')}
            data-testid="download-pdf-btn"
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center justify-center gap-2"
          >
            <Download className="w-4 h-4" />
            Download Executive PDF Report
          </button>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="w-10 h-10 rounded-lg bg-emerald-950/80 border border-emerald-800 flex items-center justify-center text-emerald-300 mb-3">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-white">
              Calibrated Open Order Risk Predictions (CSV)
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Full spreadsheet export of all open purchase orders with calibrated delay probabilities, business priority scores, expected delay days, and reliability flags.
            </p>
          </div>
          <button
            type="button"
            onClick={() => downloadFile('/api/reports/predictions.csv', 'supplier_risk_predictions.csv')}
            data-testid="download-csv-btn"
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center justify-center gap-2"
          >
            <Download className="w-4 h-4" />
            Export Predictions CSV
          </button>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="w-10 h-10 rounded-lg bg-cyan-950/80 border border-cyan-800 flex items-center justify-center text-cyan-300 mb-3">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-white">
              Purchase Order Ledger & Supplier Scorecards (CSV)
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Full delivery history and supplier master data with OTD rate, average delay, lead-time volatility and cold-start flags for offline analysis.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => downloadFile('/api/reports/orders.csv', 'purchase_order_ledger.csv')}
              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center justify-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              Orders
            </button>
            <button
              type="button"
              onClick={() => downloadFile('/api/reports/suppliers.csv', 'supplier_scorecards.csv')}
              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center justify-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              Suppliers
            </button>
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="w-10 h-10 rounded-lg bg-blue-950/80 border border-blue-800 flex items-center justify-center text-blue-300 mb-3">
              <Upload className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-white">
              Standard Purchase Order Import Template (CSV)
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Pre-formatted CSV template with sample purchase orders and schema headers for bulk data import validation.
            </p>
          </div>
          <button
            type="button"
            onClick={() => downloadFile('/api/import/template', 'purchase_orders_import_template.csv')}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center justify-center gap-2"
          >
            <Download className="w-4 h-4" />
            Download Import Template CSV
          </button>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">
              Immutable Governance & Human Decision Audit Log ({auditLogs.length} entries)
            </h3>
            <p className="text-xs text-slate-400">
              Every review decision, alert acknowledgement, threshold adjustment, and model promotion is recorded with actor and timestamp
            </p>
          </div>
        </div>
        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="pb-2">Timestamp (UTC)</th>
                <th className="pb-2">Actor</th>
                <th className="pb-2">Role</th>
                <th className="pb-2">Action</th>
                <th className="pb-2">Entity</th>
                <th className="pb-2">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {auditLogs.map((l) => (
                <tr key={l.id} className="hover:bg-slate-800/40">
                  <td className="py-2 font-mono text-slate-400">
                    {l.timestamp.slice(0, 19).replace('T', ' ')}
                  </td>
                  <td className="py-2 font-medium text-white">{l.actor}</td>
                  <td className="py-2 text-slate-300">{l.role}</td>
                  <td className="py-2 font-mono text-blue-400 font-semibold">
                    {l.action}
                  </td>
                  <td className="py-2 text-slate-300">
                    {l.entity_type} #{l.entity_id}
                  </td>
                  <td className="py-2 font-mono text-[11px] text-slate-400 max-w-md truncate">
                    {JSON.stringify(l.details)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// 11. DATA IMPORT (CSV / EXCEL WITH PREVIEW & VALIDATION) TAB
// ============================================================================
export const DataImportTab: React.FC<{ role: string }> = ({ role }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [duplicateStrategy, setDuplicateStrategy] = useState('skip');
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({
    po_number: 'po_number',
    supplier_code: 'supplier_code',
    order_date: 'order_date',
    promised_delivery_date: 'promised_delivery_date',
    quantity: 'quantity',
    unit_price: 'unit_price',
    status: 'status',
    shipping_mode: 'shipping_mode',
    urgency_level: 'urgency_level',
  });
  const [importResult, setImportResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runImport = async (dryRun: boolean, fileToUse?: File) => {
    const f = fileToUse || selectedFile;
    if (!f) {
      setError('Please select a CSV or Excel (.xlsx) file or click "Load Sample Batch" first.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', f);
      formData.append('dry_run', dryRun ? 'true' : 'false');
      formData.append('duplicate_strategy', duplicateStrategy);
      formData.append('column_mapping_json', JSON.stringify(columnMapping));

      const res = await apiFetch(
        '/api/import/orders',
        {
          method: 'POST',
          body: formData,
        },
        role
      );
      setImportResult(res);
    } catch (err: any) {
      setError(err.message || 'Import validation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSampleBatch = () => {
    const csvSample = [
      'po_number,supplier_code,order_date,promised_delivery_date,quantity,unit_price,status,shipping_mode,urgency_level',
      'PO-2026-BATCH-701,SUP-1001,2026-10-15,2026-11-02,950,145.00,open,Ocean Freight,high',
      'PO-2026-BATCH-702,SUP-1003,2026-10-16,2026-10-29,1400,210.00,open,Air Freight,critical',
      'PO-2026-BATCH-BAD1,SUP-1002,2026-10-20,2026-10-05,-200,110.00,open,Ocean Freight,standard',
    ].join('\n');
    const file = new File([csvSample], 'sample_batch_with_validation_test.csv', {
      type: 'text/csv',
    });
    setSelectedFile(file);
    runImport(true, file);
  };

  return (
    <div className="space-y-6" data-testid="data-import-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">
            CSV & Excel (.xlsx) Bulk Data Import & Schema Validator
          </h2>
          <p className="text-sm text-slate-400">
            Interactive column mapping, dry-run validation preview, duplicate handling, and anomaly detection
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleLoadSampleBatch}
            data-testid="load-sample-batch-btn"
            className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-blue-300 border border-slate-700"
          >
            Load Sample Batch (Valid + Anomaly Demo)
          </button>
          <a
            href="/api/import/template"
            download="purchase_orders_import_template.csv"
            className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 flex items-center gap-1.5"
          >
            <Download className="w-3.5 h-3.5" />
            Template CSV
          </a>
        </div>
      </div>

      {/* Upload & Configuration Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4 text-xs">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-slate-400 mb-1">
              Select CSV or Excel (.xlsx) File
            </label>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => {
                const f = e.target.files?.[0] || null;
                setSelectedFile(f);
              }}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-slate-200"
            />
            {selectedFile && (
              <div className="text-emerald-400 mt-1">
                Selected: {selectedFile.name} ({selectedFile.size} bytes)
              </div>
            )}
          </div>

          <div>
            <label className="block text-slate-400 mb-1">
              Duplicate PO Number Strategy
            </label>
            <select
              value={duplicateStrategy}
              onChange={(e) => setDuplicateStrategy(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
            >
              <option value="skip">Skip Existing Duplicates Safely</option>
              <option value="update">Update / Overwrite Existing POs</option>
              <option value="error">Flag Duplicates as Validation Errors</option>
            </select>
          </div>

          <div className="flex items-end gap-2">
            <button
              onClick={() => runImport(true)}
              disabled={loading}
              className="flex-1 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-semibold border border-slate-700"
            >
              1. Dry-Run Preview & Validate
            </button>
            <button
              onClick={() => runImport(false)}
              disabled={loading || !importResult || importResult.valid_rows_count === 0}
              data-testid="commit-import-btn"
              className="flex-1 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-semibold"
            >
              2. Commit Valid Rows
            </button>
          </div>
        </div>

        {/* Column Mapping Row */}
        <div className="pt-2 border-t border-slate-800">
          <div className="font-semibold text-slate-300 mb-2">
            Column Mapping (Target Schema Field → Source File Column Header):
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {Object.entries(columnMapping).map(([targetCol, srcCol]) => (
              <div key={targetCol}>
                <label className="block text-[10px] text-slate-400 font-mono">
                  {targetCol}
                </label>
                <input
                  type="text"
                  value={srcCol}
                  onChange={(e) =>
                    setColumnMapping({
                      ...columnMapping,
                      [targetCol]: e.target.value,
                    })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono text-[11px]"
                />
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="p-3 rounded bg-rose-950/70 border border-rose-700 text-rose-200">
            {error}
          </div>
        )}
      </div>

      {/* Preview & Validation Results */}
      {importResult && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <div className="text-slate-400">Mode</div>
              <div className="text-base font-bold text-blue-400 mt-0.5">
                {importResult.dry_run ? 'DRY-RUN PREVIEW' : 'COMMITTED TO DB'}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <div className="text-slate-400">Total Rows Parsed</div>
              <div className="text-base font-bold text-white mt-0.5">
                {importResult.total_rows}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <div className="text-slate-400">Valid Rows</div>
              <div className="text-base font-bold text-emerald-400 mt-0.5">
                {importResult.valid_rows_count}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <div className="text-slate-400">Validation Errors</div>
              <div className="text-base font-bold text-rose-400 mt-0.5">
                {importResult.error_rows_count}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <div className="text-slate-400">Created / Updated</div>
              <div className="text-base font-bold text-white mt-0.5">
                {importResult.created_count} / {importResult.updated_count}
              </div>
            </div>
          </div>

          {/* Validation Errors Table */}
          {importResult.errors && importResult.errors.length > 0 && (
            <div className="bg-slate-900/90 border border-rose-800/70 rounded-xl p-5 space-y-3">
              <h4 className="text-sm font-bold text-rose-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                Row-Level Schema & Data Quality Validation Errors ({importResult.errors.length})
              </h4>
              <div className="space-y-2 text-xs">
                {importResult.errors.map((errRow: any, idx: number) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded bg-rose-950/40 border border-rose-800/60 text-rose-200"
                  >
                    <span className="font-mono font-bold">
                      Row #{errRow.row_number} (PO: {errRow.po_number || 'Missing'}):
                    </span>{' '}
                    {errRow.errors.join(' | ')}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Valid Rows Preview Table */}
          {importResult.preview_rows && importResult.preview_rows.length > 0 && (
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-3">
              <h4 className="text-sm font-bold text-white">
                Validated Rows Ready for Import ({importResult.preview_rows.length})
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400">
                      <th className="pb-2">Row</th>
                      <th className="pb-2">PO Number</th>
                      <th className="pb-2">Supplier</th>
                      <th className="pb-2">Order Date</th>
                      <th className="pb-2">Promised Date</th>
                      <th className="pb-2">Quantity</th>
                      <th className="pb-2">Total Value</th>
                      <th className="pb-2">Lead Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {importResult.preview_rows.map((r: any) => (
                      <tr key={r.row_number}>
                        <td className="py-2 text-slate-400">#{r.row_number}</td>
                        <td className="py-2 font-mono font-bold text-white">
                          {r.po_number}
                        </td>
                        <td className="py-2 text-slate-200">
                          {r.supplier_code} — {r.supplier_name}
                        </td>
                        <td className="py-2 text-slate-300">{r.order_date}</td>
                        <td className="py-2 text-slate-300">
                          {r.promised_delivery_date}
                        </td>
                        <td className="py-2 text-slate-300">{r.quantity}</td>
                        <td className="py-2 text-emerald-400 font-medium">
                          ${r.total_value.toLocaleString()}
                        </td>
                        <td className="py-2 text-slate-300">
                          {r.promised_lead_time_days}d
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// 12. SETTINGS & AI PROVIDER CONFIGURATION TAB
// ============================================================================
export const SettingsTab: React.FC<{
  role: string;
  username: string;
  onSignOut: () => void;
}> = ({ role, username, onSignOut }) => {
  const [aiConfig, setAiConfig] = useState<any>(null);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [connStatus, setConnStatus] = useState<any>(null);
  const [saveMessage, setSaveMessage] = useState('');
  const [health, setHealth] = useState<any>(null);
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([]);
  const [discoverMsg, setDiscoverMsg] = useState('');

  const handleDiscoverModels = async () => {
    setDiscoverMsg('Discovering models…');
    try {
      const res = await apiFetch('/api/ai/models', {}, role);
      setDiscoveredModels(res.models || []);
      setDiscoverMsg(
        res.message || `Discovered ${(res.models || []).length} model(s) via ${res.source}.`
      );
    } catch (err: any) {
      setDiscoverMsg(err.message || 'Model discovery failed.');
    }
  };

  const loadConfig = async () => {
    const [cfg, hlth] = await Promise.all([
      apiFetch('/api/ai/config', {}, role),
      apiFetch('/api/health', {}, role),
    ]);
    setAiConfig(cfg);
    setHealth(hlth);
  };

  useEffect(() => {
    loadConfig();
  }, [role]);

  const handleSaveAiConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveMessage('');
    try {
      const payload = {
        provider_type: aiConfig.provider_type,
        base_url: aiConfig.base_url,
        api_key: apiKeyInput ? apiKeyInput : undefined,
        model_name: aiConfig.model_name,
        timeout_seconds: Number(aiConfig.timeout_seconds),
        max_retries: Number(aiConfig.max_retries),
        max_tokens: Number(aiConfig.max_tokens),
        budget_limit_usd: Number(aiConfig.budget_limit_usd),
        is_enabled: Boolean(aiConfig.is_enabled),
      };
      const updated = await apiFetch(
        '/api/ai/config',
        {
          method: 'PUT',
          body: JSON.stringify(payload),
        },
        role
      );
      setAiConfig(updated);
      setApiKeyInput('');
      setSaveMessage(
        'AI Provider settings saved securely. Secrets are masked server-side.'
      );
    } catch (err: any) {
      setSaveMessage(`Error: ${err.message}`);
    }
  };

  const handleTestConnection = async () => {
    const res = await apiFetch('/api/ai/test-connection', { method: 'POST' }, role);
    setConnStatus(res);
  };

  if (!aiConfig) {
    return (
      <div className="p-8 text-slate-400 text-xs">
        Loading AI Provider & System Settings...
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h2 className="text-xl font-bold text-white">
          AI Provider Configuration, Role-Based Access & System Diagnostics
        </h2>
        <p className="text-sm text-slate-400">
          Configure optional LLM intelligence providers (Offline Mode default) with server-side secret masking, budget guards, and connection testing
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* AI Provider Settings Form */}
        <form
          onSubmit={handleSaveAiConfig}
          className="lg:col-span-7 bg-slate-900/90 border border-slate-800 rounded-xl p-6 space-y-4 text-xs"
          data-testid="ai-provider-form"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-blue-400" />
              <h3 className="text-sm font-bold text-white">
                Optional AI / LLM Intelligence Provider Settings
              </h3>
            </div>
            <span className="px-2.5 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700 text-[11px] font-semibold">
              {aiConfig.provider_type === 'none' || !aiConfig.is_enabled
                ? 'Offline Mode Active (Free Default)'
                : `External: ${aiConfig.provider_type.toUpperCase()}`}
            </span>
          </div>

          <p className="text-slate-400">
            The core ML system operates 100% offline without paid APIs. Optionally configure an external LLM provider for natural-language risk synthesis. API keys are stored strictly server-side and never exposed to the browser bundle.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-slate-300 font-medium mb-1">
                AI Provider Mode
              </label>
              <select
                value={aiConfig.provider_type}
                onChange={(e) => {
                  const pt = e.target.value;
                  const defaultUrls: Record<string, string> = {
                    none: '',
                    openai: 'https://api.openai.com/v1',
                    anthropic: 'https://api.anthropic.com/v1',
                    openrouter: 'https://openrouter.ai/api/v1',
                    ollama: 'http://localhost:11434/v1',
                    custom: '',
                  };
                  const defaultModels: Record<string, string> = {
                    none: 'offline-deterministic-v1',
                    openai: 'gpt-4o-mini',
                    anthropic: 'claude-3-5-haiku-latest',
                    openrouter: 'openai/gpt-4o-mini',
                    ollama: 'gemma3:latest',
                    custom: 'gpt-4o-mini',
                  };
                  setAiConfig({
                    ...aiConfig,
                    provider_type: pt,
                    base_url: defaultUrls[pt] ?? aiConfig.base_url,
                    model_name: defaultModels[pt] ?? aiConfig.model_name,
                    is_enabled: pt !== 'none',
                  });
                }}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
              >
                <option value="none">No AI / Offline Mode — free, deterministic (default)</option>
                <option value="openai">OpenAI API — easy connect (ChatGPT API key required)</option>
                <option value="anthropic">Anthropic Claude API — easy connect</option>
                <option value="openrouter">OpenRouter — multi-model gateway</option>
                <option value="ollama">Local Ollama / self-hosted (e.g. gemma3)</option>
                <option value="custom">Custom OpenAI-compatible endpoint</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                Model Identifier
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  list="ai-model-suggestions"
                  value={aiConfig.model_name}
                  onChange={(e) =>
                    setAiConfig({ ...aiConfig, model_name: e.target.value })
                  }
                  placeholder="e.g. gpt-4o-mini, claude-3-5-haiku-latest, gemma3:latest"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                />
                <datalist id="ai-model-suggestions">
                  {(aiConfig.suggested_models || []).map((m: string) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
                <button
                  type="button"
                  onClick={handleDiscoverModels}
                  className="shrink-0 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-slate-200 hover:bg-slate-700"
                >
                  Discover
                </button>
              </div>
              {discoverMsg && (
                <p className="mt-1 text-[11px] text-slate-400">{discoverMsg}</p>
              )}
              {discoveredModels.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {discoveredModels.slice(0, 8).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setAiConfig({ ...aiConfig, model_name: m })}
                      className="rounded border border-slate-700 bg-slate-950 px-1.5 py-0.5 font-mono text-[10px] text-blue-300 hover:border-blue-600"
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-slate-300 font-medium mb-1">
                API Base URL
              </label>
              <input
                type="text"
                value={aiConfig.base_url}
                onChange={(e) =>
                  setAiConfig({ ...aiConfig, base_url: e.target.value })
                }
                placeholder="https://api.openai.com/v1"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-300 font-medium mb-1">
                API Key (Stored Server-Side • Masked:{' '}
                <span className="font-mono text-amber-300">
                  {aiConfig.api_key_masked || 'None'}
                </span>
                )
              </label>
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder={
                  aiConfig.has_api_key
                    ? '•••••••••••••••• (Leave blank to keep stored key)'
                    : 'Enter API Key (never exposed in client logs)'
                }
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="block text-slate-400 mb-1">Timeout (sec)</label>
              <input
                type="number"
                min={3}
                max={120}
                value={aiConfig.timeout_seconds}
                onChange={(e) =>
                  setAiConfig({
                    ...aiConfig,
                    timeout_seconds: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Max Retries</label>
              <input
                type="number"
                min={0}
                max={5}
                value={aiConfig.max_retries}
                onChange={(e) =>
                  setAiConfig({
                    ...aiConfig,
                    max_retries: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Max Tokens</label>
              <input
                type="number"
                min={64}
                max={4096}
                value={aiConfig.max_tokens}
                onChange={(e) =>
                  setAiConfig({
                    ...aiConfig,
                    max_tokens: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">
                Budget Limit (USD)
              </label>
              <input
                type="number"
                step="0.50"
                min={0}
                value={aiConfig.budget_limit_usd}
                onChange={(e) =>
                  setAiConfig({
                    ...aiConfig,
                    budget_limit_usd: Number(e.target.value),
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-white"
              />
            </div>
          </div>

          {saveMessage && (
            <div className="p-3 rounded bg-blue-950/60 border border-blue-700 text-blue-200">
              {saveMessage}
            </div>
          )}

          {connStatus && (
            <div
              className={`p-3 rounded border ${
                connStatus.status === 'ok'
                  ? 'bg-emerald-950/50 border-emerald-700 text-emerald-200'
                  : 'bg-amber-950/50 border-amber-700 text-amber-200'
              }`}
            >
              <strong>Connection Check ({connStatus.mode}):</strong>{' '}
              {connStatus.message}
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold"
            >
              Save AI Configuration
            </button>
            <button
              type="button"
              onClick={handleTestConnection}
              data-testid="test-ai-connection-btn"
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium"
            >
              Test Provider Connection
            </button>
          </div>
        </form>

        {/* Right: RBAC identity & System Diagnostics */}
        <div className="lg:col-span-5 space-y-5">
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-3 text-xs">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">
                Signed-in Identity & Access Scope
              </h3>
            </div>
            <p className="text-slate-400">
              Your permissions are derived from the signed JWT issued at login.
              Sign out and use a different seeded account to verify
              least-privilege enforcement across review decisions, threshold
              editing, and model promotion.
            </p>
            <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-[11px] text-slate-300">
              <div>user: {username}</div>
              <div>role: {role}</div>
            </div>
            <button
              type="button"
              onClick={onSignOut}
              className="w-full rounded-lg border border-slate-700 px-3 py-2 font-semibold text-slate-200 transition hover:bg-slate-800"
            >
              Sign out / switch account
            </button>
          </div>

          {health && (
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-3 text-xs">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-bold text-white">
                  Operational Health & Database Diagnostics
                </h3>
              </div>
              <div className="space-y-1.5 text-slate-300 font-mono text-[11px]">
                <div>Status: {health.status.toUpperCase()}</div>
                <div>Reference Date: {health.reference_date}</div>
                <div>Active Champion Model: {health.champion_model}</div>
                <div>Suppliers Persisted: {health.suppliers_count}</div>
                <div>Purchase Orders Persisted: {health.purchase_orders_count}</div>
                <div>
                  AI Spend Tracker: ${aiConfig.spent_usd.toFixed(4)} / $
                  {aiConfig.budget_limit_usd.toFixed(2)} USD ({aiConfig.request_count}{' '}
                  requests)
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
