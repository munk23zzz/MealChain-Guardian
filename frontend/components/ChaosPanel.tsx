"use client";

/**
 * ChaosPanel (P4, paket 1-6, keputusan Roy 2026-10-09).
 *
 * "Slider chaos" yang JUJUR: tidak ada injeksi di luar kontrak backend.
 * Slider memilih TINGKAT GANGGUAN (persen kenaikan suhu simulasi pada
 * batch terpilih) — namun penetapan safety TETAP dihitung server-side
 * dari temperature_log persisted via POST /events/safety-disruption
 * (Event 3, ambang 30 menit terkunci). Slider hanyalah pemilih skenario.
 */

import { useCallback, useEffect, useState } from "react";

import StatusBadge from "./StatusBadge";

const MUTATING = new Set(["sppg_head", "sppg_nutritionist"]);

export default function ChaosPanel({
  role,
  token,
  onDecisionCreated,
}: {
  role: string;
  token: string | null;
  onDecisionCreated?: () => void;
}) {
  const [batches, setBatches] = useState<any[]>([]);
  const [batchId, setBatchId] = useState("");
  const [severity, setSeverity] = useState(50);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const canRun = token !== null && MUTATING.has(role);

  const loadBatches = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    try {
      const r = await fetch("/batches", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      setBatches(d.batches ?? []);
      if (d.batches?.length && !batchId) setBatchId(d.batches[0].id);
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    void loadBatches();
  }, [loadBatches]);

  async function run() {
    if (!token || !batchId) return;
    setBusy(true);
    setMsg(null);
    setResult(null);
    try {
      const target = batches.find((b) => b.id === batchId);
      const r = await fetch("/events/safety-disruption", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          batch_id: batchId,
          target_location_id: batches.find((b) => b.id === batchId)
            ?.location_id,
          operation_key:
            typeof crypto !== "undefined" && crypto.randomUUID
              ? crypto.randomUUID()
              : `${Date.now()}-0000-4000-8000-${Date.now()
                  .toString()
                  .padStart(12, "0")}`,
          // severity = petunjuk skenario demo (ditampilkan di trace);
          // keputusan safety TETAP dihitung server dari temperature_log.
          severity_hint_pct: severity,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`);
      setResult(d);
      if (d.decision_id) onDecisionCreated?.();
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="chaos-panel card" aria-label="Chaos skenario Event 3">
      <div className="card-header">
        <h4>Chaos Skenario — Event 3 (thermal excursion)</h4>
        <StatusBadge status={result ? result.status : "proposed"} />
      </div>
      <p className="chaos-note">
        Slider memilih tingkat gangguan skenario. Safety status TETAP dihitung
        server dari temperature_log batch (tidak pernah dari browser).
      </p>
      <label className="field chaos-slider">
        <span>Tingkat gangguan: {severity}%</span>
        <input
          type="range"
          min={0}
          max={100}
          value={severity}
          data-testid="chaos-slider"
          onChange={(e) => setSeverity(Number(e.target.value))}
          disabled={!canRun || busy}
        />
      </label>
      <label className="field">
        <span>Batch</span>
        <select
          className="chaos-batch"
          value={batchId}
          onChange={(e) => setBatchId(e.target.value)}
          disabled={!canRun || busy}
        >
          <option value="">— pilih batch —</option>
          {batches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.commodity} · {b.location} · {b.quantity_kg} kg ·{" "}
              {b.safety_status}
            </option>
          ))}
        </select>
      </label>
      {canRun && (
        <button
          type="button"
          className="button button-primary"
          disabled={busy || !batchId}
          onClick={run}
        >
          {busy ? "Agent menganalisis…" : "Picu Event 3"}
        </button>
      )}
      {result && (
        <div className={`chaos-result chaos-${result.status}`}>
          <p>{result.message ?? result.status}</p>
          {result.decision_id && (
            <p>
              Keputusan: <code>{String(result.decision_id).slice(0, 8)}</code>{" "}
              — lanjut di tab Recommendations.
            </p>
          )}
        </div>
      )}
      {msg && <p className="action-message">{msg}</p>}
      {!canRun && (
        <p className="chaos-readonly">Mode baca — Event 3 dijalankan approver.</p>
      )}
    </section>
  );
}
