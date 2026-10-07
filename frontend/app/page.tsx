"use client";

import { useCallback, useEffect, useState } from "react";
import {
  login,
  fetchDecisions,
  fetchDecisionTraces,
} from "../lib/api";
import { decodeRole } from "../lib/auth";
import StatusBadge from "../components/StatusBadge";
import RecommendationCard from "../components/RecommendationCard";
import AgentTraceViewer from "../components/AgentTraceViewer";
import DecisionActions from "../components/DecisionActions";
import ProviderPanel from "../components/ProviderPanel";

// Panel provider dihitung dari trace aktual (VERIFY/PREDICT/SUPERVISE);
// tanpa karangan — agen tanpa langkah model tampil UNAVAILABLE.
function providersFromTraces(steps: any[]): Record<string, any> {
  const out: Record<string, any> = {};
  for (const s of steps ?? []) {
    const outSum = s.output_summary ?? {};
    if (s.step_name === "VERIFY") {
      out.verifier = {
        status: outSum.verdict === "UNAVAILABLE" ? "unavailable" : "ok",
        provider: outSum.provider ?? null,
        fallback_used: outSum.fallback_used ?? false,
        attempts: (outSum.attempts ?? []).length,
      };
    }
    if (s.step_name === "PREDICT") {
      const stat = outSum.method === "statistical_fallback";
      out.forecast = {
        status: stat ? "fallback" : outSum.provider ? "ok" : "unavailable",
        provider: outSum.provider ?? null,
        fallback_used: outSum.fallback_used ?? stat,
        attempts: (outSum.attempts ?? []).length,
      };
    }
    if (s.step_name === "SUPERVISE") {
      out.supervisor = {
        status: outSum.status === "narrated" ? "ok" : outSum.status,
        provider: outSum.provider ?? null,
        fallback_used: outSum.fallback_used ?? false,
        attempts: (outSum.attempts ?? []).length,
      };
    }
  }
  return out;
}

type Decision = {
  decision_id: string;
  decision_type: string;
  status: string;
  quantity_kg: number | null;
  safe_delivered_cost: number | null;
  expires_at: string;
  valid: boolean;
};

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [traces, setTraces] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadDecisions = useCallback(async (t: string) => {
    try {
      const data = await fetchDecisions(t);
      setDecisions(data.items ?? []);
      setError(null);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  }, []);

  // Polling 5 detik (design.md §5 — tanpa WebSocket untuk MVP).
  useEffect(() => {
    if (!token) return;
    loadDecisions(token);
    const iv = setInterval(() => loadDecisions(token), 5000);
    return () => clearInterval(iv);
  }, [token, loadDecisions]);

  useEffect(() => {
    if (!token || !selectedId) return;
    let stopped = false;
    const load = async () => {
      try {
        const data = await fetchDecisionTraces(selectedId, token);
        if (!stopped) setTraces(data.steps ?? []);
      } catch {
        /* feed tetap jalan; error trace tidak fatal */
      }
    };
    load();
    const iv = setInterval(load, 5000);
    return () => {
      stopped = true;
      clearInterval(iv);
    };
  }, [token, selectedId]);

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const data = await login(email, password);
      setToken(data.access_token);
      // Role dari JWT hanya untuk display; otorisasi tetap di backend.
      setRole(decodeRole(data.access_token));
      setLoginError(null);
    } catch (e: any) {
      setLoginError(
        e?.message
          ? String(e.message)
          : "Login gagal — periksa koneksi ke server API."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    const demoAccounts = [
      { label: "SPPG Head", email: "sppg.head@demo.local", password: "Demo#SPPG2026" },
      { label: "Nutritionist", email: "sppg.nutritionist@demo.local", password: "Demo#Nut2026" },
      { label: "BGN Monitor", email: "bgn.monitor@demo.local", password: "Demo#BGN2026" },
    ];
    return (
      <main className="login-shell">
        {/* Panel brand: dunia subject — rantai dingin SPPG, angka dari data demo asli */}
        <section className="login-brand" aria-label="Tentang MealChain Guardian">
          <p className="brand-eyebrow">Badan Gizi Nasional · Program SPPG</p>
          <h1 className="brand-title">MealChain Guardian</h1>
          <p className="brand-tagline">
            Agentic AI untuk cross-regional food supply balancing — memantau
            kesegaran, stok, dan keputusan distribusi antar SPPG.
          </p>
          <div className="brand-route" aria-hidden="true">
            <div className="route-line">
              <span className="route-node" />
              <span className="route-cold" />
              <span className="route-truck">❄</span>
              <span className="route-cold" />
              <span className="route-node route-node-end" />
            </div>
            <div className="route-labels">
              <span>Bogor</span>
              <span> Jakarta</span>
            </div>
          </div>
          <ul className="brand-stats">
            <li>
              <strong>50 km</strong>
              <span>rute demo Bogor → Jakarta</span>
            </li>
            <li>
              <strong>Rp16,2 jt</strong>
              <span>safe delivered cost</span>
            </li>
            <li>
              <strong>0,90</strong>
              <span>skor kesegaran minimum</span>
            </li>
          </ul>
        </section>

        <section className="login-panel">
          <form onSubmit={onLogin} className="login-form">
            <h2>Masuk ke konsol</h2>
            <p className="login-sub">Gunakan akun SPPG atau BGN yang terdaftar.</p>
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            {loginError && (
              <p className="status-danger login-error" role="alert">
                {loginError}
              </p>
            )}
            <button className="button login-submit" type="submit" disabled={submitting}>
              {submitting ? "Memeriksa…" : "Masuk"}
            </button>
            <div className="demo-block">
              <p className="demo-hint">Akun demo — klik untuk mengisi form:</p>
              <div className="demo-chips">
                {demoAccounts.map((acc) => (
                  <button
                    key={acc.email}
                    type="button"
                    className="demo-chip"
                    onClick={() => {
                      setEmail(acc.email);
                      setPassword(acc.password);
                      setLoginError(null);
                    }}
                  >
                    <span>{acc.label}</span>
                    <small>{acc.email}</small>
                  </button>
                ))}
              </div>
            </div>
          </form>
        </section>
      </main>
    );
  }

  const selected = decisions.find((d) => d.decision_id === selectedId) ?? null;

  return (
    <main>
      <div className="header-bar">
        <strong>MealChain Guardian</strong>
        <span>
          {role ?? "user"} ·{" "}
          <button
            type="button"
            className="button-secondary button"
            onClick={() => {
              setToken(null);
              setRole(null);
              setSelectedId(null);
            }}
          >
            Keluar
          </button>
        </span>
      </div>

      <section className="feed-section">
        <h2>Recommendation Feed</h2>
        {error && (
          <p className="status-danger">
            Gagal memuat data: {error}{" "}
            <button type="button" onClick={() => token && loadDecisions(token)}>
              Coba lagi
            </button>
          </p>
        )}
        {decisions.length === 0 && !error && (
          <p className="empty-state">Belum ada rekomendasi aktif.</p>
        )}
        <div className="feed">
          {decisions.map((d) => (
            <div key={d.decision_id}>
              <button
                type="button"
                className="link-button"
                onClick={() => setSelectedId(d.decision_id)}
              >
                <RecommendationCard
                  decision={d}
                  mockSourced={d.status === "executed"}
                />
              </button>
            </div>
          ))}
        </div>
      </section>

      {selected && (
        <section className="detail-section">
          <h2>Decision Detail</h2>
          <RecommendationCard decision={selected} mockSourced={false} />
          <DecisionActions
            decisionId={selected.decision_id}
            role={role ?? ""}
            status={selected.status}
            token={token}
          />
          <h3>Agent Activity Log</h3>
          <ProviderPanel providers={providersFromTraces(traces)} />
          <AgentTraceViewer steps={traces} />
        </section>
      )}
    </main>
  );
}
