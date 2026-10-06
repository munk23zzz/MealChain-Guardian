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
    try {
      const data = await login(email, password);
      setToken(data.access_token);
      // Role dari JWT hanya untuk display; otorisasi tetap di backend.
      setRole(decodeRole(data.access_token));
      setLoginError(null);
    } catch (e: any) {
      setLoginError(String(e.message ?? e));
    }
  }

  if (!token) {
    return (
      <main className="login-wrap">
        <h1>MealChain Guardian</h1>
        <p>Agentic AI untuk cross-regional food supply balancing</p>
        <form onSubmit={onLogin} className="card login-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {loginError && <p className="status-danger">{loginError}</p>}
          <button className="button" type="submit">
            Masuk
          </button>
        </form>
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
          <AgentTraceViewer steps={traces} />
        </section>
      )}
    </main>
  );
}
