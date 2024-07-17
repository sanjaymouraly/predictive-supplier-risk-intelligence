import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, Lock, ShieldCheck, User } from 'lucide-react';
import { storeSession, type AuthUser } from '../api';

interface DemoAccount {
  username: string;
  password: string;
  full_name: string;
  title: string;
  role: string;
}

interface LoginPageProps {
  onAuthenticated: (token: string, user: AuthUser) => void;
}

const ROLE_BADGES: Record<string, string> = {
  admin: 'bg-purple-950/80 text-purple-300 border-purple-800',
  procurement_lead: 'bg-blue-950/80 text-blue-300 border-blue-800',
  reviewer: 'bg-emerald-950/80 text-emerald-300 border-emerald-800',
  viewer: 'bg-slate-800 text-slate-300 border-slate-700',
};

export const LoginPage: React.FC<LoginPageProps> = ({ onAuthenticated }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [demoAccounts, setDemoAccounts] = useState<DemoAccount[]>([]);

  useEffect(() => {
    fetch('/api/auth/demo-accounts')
      .then((r) => (r.ok ? r.json() : []))
      .then(setDemoAccounts)
      .catch(() => setDemoAccounts([]));
  }, []);

  const submit = async (user: string, pass: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: user, password: pass }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Login failed (HTTP ${res.status})`);
      }
      const data = await res.json();
      storeSession(data.access_token, data.user);
      onAuthenticated(data.access_token, data.user);
    } catch (err: any) {
      setError(err.message || 'Unable to sign in');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void submit(username, password);
  };

  return (
    <div
      data-testid="login-page"
      className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6"
    >
      <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center text-white font-black text-lg shadow-lg shadow-blue-900/50">
              SR
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Supplier Risk IQ</h1>
              <p className="text-sm text-slate-400">
                Predictive Procurement Risk & Decision Support
              </p>
            </div>
          </div>

          <h2 className="text-3xl font-bold leading-tight text-white">
            Anticipate late deliveries.
            <br />
            <span className="text-blue-400">Keep humans in command.</span>
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Point-in-time calibrated ML forecasts every open purchase order,
            explains the contributing factors, and routes high-impact risks to a
            review queue. The system never cancels orders or rejects suppliers on
            its own.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="flex items-start gap-2 rounded-lg border border-slate-800 bg-slate-900/70 p-3">
              <ShieldCheck className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              <span className="text-slate-300">
                Role-based access with immutable audit trail
              </span>
            </div>
            <div className="flex items-start gap-2 rounded-lg border border-slate-800 bg-slate-900/70 p-3">
              <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
              <span className="text-slate-300">
                Leakage-tested, calibrated and explainable predictions
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 shadow-2xl shadow-black/40 space-y-5">
          <div>
            <h3 className="text-lg font-bold text-white">Sign in</h3>
            <p className="text-xs text-slate-400 mt-1">
              Use a seeded account or a JWT issued by your deployment.
            </p>
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-lg border border-rose-800 bg-rose-950/60 px-3 py-2 text-xs text-rose-200"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-300">
                Username
              </span>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
                <input
                  required
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="marcus.chen"
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-300">
                Password
              </span>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
                <input
                  required
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </label>
            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-60"
            >
              {loading ? 'Signing in…' : 'Sign in'}
              {!loading && <ArrowRight className="h-4 w-4" />}
            </button>
          </form>

          {demoAccounts.length > 0 && (
            <div className="border-t border-slate-800 pt-4">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Seeded demo accounts (local evaluation)
              </p>
              <div className="space-y-1.5">
                {demoAccounts.map((account) => (
                  <button
                    key={account.username}
                    type="button"
                    onClick={() => {
                      setUsername(account.username);
                      setPassword(account.password);
                      void submit(account.username, account.password);
                    }}
                    className="flex w-full items-center justify-between rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-left transition hover:border-slate-600 hover:bg-slate-800/60"
                  >
                    <span>
                      <span className="block text-xs font-medium text-slate-200">
                        {account.full_name} · {account.title}
                      </span>
                      <span className="block font-mono text-[10px] text-slate-500">
                        {account.username}
                      </span>
                    </span>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                        ROLE_BADGES[account.role] || ROLE_BADGES.viewer
                      }`}
                    >
                      {account.role}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <p className="text-[11px] leading-relaxed text-slate-500">
            Demo credentials are only returned while <code>ALLOW_DEMO_MODE=true</code>.
            Set it to <code>false</code> and provide real JWTs for any shared deployment.
          </p>
        </div>
      </div>
    </div>
  );
};
