"use client";

// OpsConsole — interaksi SEBELUM hasil (arah Roy 2026-10-07):
//   1. user pilih lokasi + komoditas → "Muat kondisi" (snapshot supply/
//      demand nyata dari /balance/{loc}/{com}, bukan karangan);
//   2. "Jalankan Analisis Agent" → /balance/analyze (14 kandidat,
//      flag harga janggal) — agent bekerja di depan juri;
//   3. role approver (sppg_head/nutritionist) mengajukan usulan →
//      POST /decisions → muncul di feed → approve/reject/execute.
// bgn_monitor read-only: bisa melihat semuanya, tanpa tombol Ajukan.

import { useEffect, useState } from "react";
import StatusBadge from "./StatusBadge";
import Event2Panel from "./Event2Panel";
import { formatIDR } from "../lib/auth";
import { fetchBalance, runAnalysis, createDecision, proposeAction } from "../lib/api";

const APPROVER = new Set(["sppg_head", "sppg_nutritionist"]);
const LOCATIONS = ["Jakarta", "Bogor", "Cianjur", "Bandung", "Surabaya"];
const COMMODITIES = ["telur", "beras", "ayam"];

export default function OpsConsole({
  role,
  token,
  ownLocationName = null,
  onSubmitted,
  snapshot: initialSnapshot = null,
  analysis: initialAnalysis = null,
  priceQuotes: initialPriceQuotes = null,
  event2: initialEvent2 = null,
}: {
  role: string;
  ownLocationName?: string | null;
  token: string | null;
  onSubmitted?: () => void;
  snapshot?: any;
  analysis?: any;
  priceQuotes?: any;
  event2?: any;
}) {
  const [location, setLocation] = useState("Jakarta");
  // Ruling 2026-10-14: kondisi lokasi lain hanya boleh dibaca bgn_monitor;
  // peran SPPG terkunci ke lokasinya (server membalas 403 untuk yang lain).
  const canChooseLocation = role === "bgn_monitor";

  useEffect(() => {
    if (!canChooseLocation && ownLocationName) setLocation(ownLocationName);
  }, [canChooseLocation, ownLocationName]);
  const [commodity, setCommodity] = useState("telur");
  const [snapshot, setSnapshot] = useState<any>(initialSnapshot);
  const [analysis, setAnalysis] = useState<any>(initialAnalysis);
  const [busy, setBusy] = useState<"" | "snapshot" | "analysis" | "submit">(
    ""
  );
  const [msg, setMsg] = useState<string | null>(null);
  const canSubmit = APPROVER.has(role) && !!token;

  async function loadSnapshot() {
    if (!token) return setMsg("Login diperlukan");
    setBusy("snapshot");
    setMsg(null);
    try {
      const data = await fetchBalance(location, commodity, token);
      setSnapshot(data);
      setAnalysis(null);
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy("");
    }
  }

  async function runAgent() {
    if (!token) return setMsg("Login diperlukan");
    setBusy("analysis");
    setMsg(null);
    try {
      // Ruling S4-05 p10: pipeline difilter ke komoditas panel —
      // proposal mengikuti komoditas yang dianalisis (bukan rank-1 global).
      const data = await runAnalysis(token, commodity);
      setAnalysis(data);
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy("");
    }
  }

  async function submit(rec: any) {
    if (!canSubmit) return;
    setBusy("submit");
    setMsg(null);
    try {
      // Dua langkah dalam satu klik: simpan snapshot (proposed) lalu
      // ajukan untuk persetujuan (pending_approval) — supaya kartu
      // langsung punya tombol Approve/Reject di feed (tanpa jalan buntu).
      const created = await createDecision(rec, 120, token);
      await proposeAction(
        created.decision_id,
        String(rec.candidate_id ?? "MAT-DEMO"),
        token
      );
      setMsg(
        `Usulan ${rec.candidate?.source_location} → ${rec.candidate?.destination_location} masuk feed (menunggu persetujuan).`
      );
      onSubmitted?.();
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy("");
    }
  }

  const recs: any[] = analysis?.recommendations ?? [];
  const sum = analysis?.summary;

  return (
    <section className="ops-console" aria-label="Konsol operasi">
      <h3>Konsol Operasi — minta agent bekerja</h3>
      <div className="ops-controls">
        <label className="field">
          <span>Lokasi</span>
          <select
            className="ops-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            disabled={!canChooseLocation}
            aria-describedby="ops-location-note"
          >
            {canChooseLocation
              ? LOCATIONS.map((l) => <option key={l}>{l}</option>)
              : ownLocationName
                ? [ownLocationName].map((l) => <option key={l}>{l}</option>)
                : null}
          </select>
          <small id="ops-location-note" className="field-note">
            {canChooseLocation
              ? "Cakupan nasional (bgn_monitor) — semua lokasi."
              : "Terkunci ke SPPG Anda (cakupan lokasi 2026-10-14)."}
          </small>
        </label>
        <label className="field">
          <span>Komoditas</span>
          <select
            className="ops-commodity"
            value={commodity}
            onChange={(e) => setCommodity(e.target.value)}
          >
            {COMMODITIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="button"
          disabled={busy !== ""}
          onClick={loadSnapshot}
        >
          {busy === "snapshot" ? "Memuat…" : "Muat kondisi"}
        </button>
        <button
          type="button"
          className="button button-primary"
          disabled={busy !== ""}
          onClick={runAgent}
        >
          {busy === "analysis" ? "Agent bekerja…" : "Jalankan Analisis Agent"}
        </button>
      </div>

      {snapshot && (
        <div className="ops-snapshot card">
          <div className="card-header">
            <h4>
              Kondisi {snapshot.location} · {snapshot.commodity}
            </h4>
            <StatusBadge status={snapshot.status} />
          </div>
          <dl className="ops-facts">
            <dt>Pasokan</dt>
            <dd>{snapshot.supply_kg} kg</dd>
            <dt>Permintaan</dt>
            <dd>{snapshot.demand_kg} kg</dd>
            <dt>Surplus</dt>
            <dd>{snapshot.surplus_kg} kg</dd>
            <dt>Shortage</dt>
            <dd>{snapshot.shortage_kg} kg</dd>
          </dl>
        </div>
      )}

      {sum && (
        <>
          <p className="ops-summary">
            Agent menemukan <strong>{sum.candidates_total} kandidat</strong> —{" "}
            {sum.eligible} layak, {sum.flagged_price} kandidat harga janggal
            (butuh penelaahan manusia).
          </p>
          <div className="ops-candidates">
            {recs.map((r: any) => {
              const cand = r.candidate ?? {};
              const flagged = Boolean(r.price_anomaly?.flagged);
              return (
                <div
                  key={r.candidate_id}
                  className={`card ops-candidate${flagged ? " ops-flagged" : ""}`}
                >
                  <div className="card-header">
                    <h4>
                      {cand.source_location} → {cand.destination_location}
                    </h4>
                    <StatusBadge
                      status={flagged ? "verifier_flagged" : "proposed"}
                    />
                  </div>
                  <dl className="ops-facts">
                    <dt>Jumlah</dt>
                    <dd>{cand.quantity_kg} kg</dd>
                    <dt>SDC</dt>
                    <dd>{formatIDR(r.safe_delivered_cost)}</dd>
                    <dt>Freshness</dt>
                    <dd>{cand.freshness_score ?? "-"}</dd>
                  </dl>
                  {canSubmit && (
                    <button
                      type="button"
                      className="button"
                      disabled={busy !== ""}
                      onClick={() => submit(r)}
                    >
                      {busy === "submit" ? "Mengajukan…" : "Ajukan"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {msg && <p className="action-message">{msg}</p>}
      <Event2Panel
        role={role}
        token={token}
        ownLocationName={ownLocationName}
        onDecisionCreated={onSubmitted}
        initialQuotes={initialPriceQuotes}
        initialResult={initialEvent2}
      />
    </section>
  );
}
