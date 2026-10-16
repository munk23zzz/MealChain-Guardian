"use client";

/**
 * ChaosPanel (P4, paket 1-6, keputusan Roy 2026-10-09).
 *
 * "Slider chaos" yang JUJUR: tidak ada injeksi di luar kontrak backend.
 * Penetapan safety TETAP dihitung server-side dari temperature_log persisted
 * via POST /events/safety-disruption (Event 3, ambang 30 menit terkunci).
 *
 * Catatan audit 2026-10-11: slider tingkat gangguan TIDAK dikirim ke server.
 * Backend memakai extra="forbid" sehingga mengirim field tambahan membalas 422
 * (dulu setiap "Picu Event 3" gagal karena itu). Besar gangguan yang dinilai
 * adalah temperature_log batch terpilih — pilih batch, bukan angka slider.
 * Semua panggilan lewat lib/api.ts (Rules.md §3: tanpa fetch manual di komponen).
 *
 * Ruling 2026-10-14 (cakupan lokasi): yang dikunci adalah lokasi TUJUAN
 * keputusan. Panel karenanya mengirim target = lokasi SPPG pemakai (dari
 * /auth/me), bukan lokasi batch seperti sebelumnya — batch dari lokasi sumber
 * mana pun tetap sah dan justru itu skenarionya. Lihat lib/chaos-scope.ts.
 */

import { useCallback, useEffect, useState } from "react";

import { fetchBatches, triggerSafetyDisruption } from "../lib/api";
import {
  batchLabel,
  blockedReason,
  eventTargetNote,
  resolveEventTarget,
} from "../lib/chaos-scope";

import StatusBadge from "./StatusBadge";

const MUTATING = new Set(["sppg_head", "sppg_nutritionist"]);

export default function ChaosPanel({
  role,
  token,
  ownLocationId,
  ownLocationName = null,
  onDecisionCreated,
}: {
  role: string;
  token: string | null;
  ownLocationId?: string | null;
  ownLocationName?: string | null;
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
      const rows = await fetchBatches(token);
      setBatches(rows);
      // Bentuk fungsional: tidak menutup nilai batchId lama (dulu pilihan
      // pengguna bisa diam-diam direset ke batch pertama).
      if (rows.length) setBatchId((prev) => prev || String(rows[0].id ?? ""));
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    void loadBatches();
  }, [loadBatches]);

  const eventTarget = resolveEventTarget(ownLocationId);
  const blocked = blockedReason(ownLocationId);

  async function run() {
    if (!token || !batchId) return;
    if (!eventTarget) {
      setMsg(blockedReason(ownLocationId));
      return;
    }
    setBusy(true);
    setMsg(null);
    setResult(null);
    try {
      const d = await triggerSafetyDisruption(
        batchId,
        eventTarget,
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-0000-4000-8000-${Date.now()
              .toString()
              .padStart(12, "0")}`,
        token
      );
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
        <h3>Chaos Skenario — Event 3 (thermal excursion)</h3>
        <span className="card-header-tags">
          <span className="demo-step">Langkah 4 · skenario</span>
          <StatusBadge status={result ? result.status : "proposed"} />
        </span>
      </div>
      <p className="chaos-note">
        Keputusan safety dihitung server dari temperature_log batch terpilih —
        tidak pernah dari browser. Pilih batch untuk memilih skenario; angka
        slider hanya penanda skenario dan TIDAK dikirim ke server.
      </p>
      <label className="field chaos-slider">
        <span>Penanda tingkat gangguan (tidak memengaruhi hasil): {severity}%</span>
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
              {batchLabel(b)}
            </option>
          ))}
        </select>
        <small className="field-note">{eventTargetNote(ownLocationId, ownLocationName)}</small>
      </label>
      {canRun && (
        <button
          type="button"
          className="button button-primary"
          disabled={busy || !batchId || blocked !== null}
          onClick={run}
        >
          {busy ? "Agent menganalisis…" : "Picu Event 3"}
        </button>
      )}
      {blocked && <p className="chaos-readonly">{blocked}</p>}
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
