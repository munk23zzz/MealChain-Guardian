"use client";

// OpsConsole — interaksi SEBELUM hasil (arah Roy 2026-10-07):
//   1. user pilih lokasi + komoditas → "Muat kondisi" (snapshot supply/
//      demand nyata dari /balance/{loc}/{com}, bukan karangan);
//   2. "Jalankan Analisis Agent" → /balance/analyze (14 kandidat,
//      flag harga janggal) — agent bekerja di depan juri;
//   3. "Jalankan Event 1 penuh" → /demo/event1 (2026-10-16): menjalankan
//      SELURUH alur orkestrator (DETECT→…→DECIDE→SUPERVISE) sehingga keputusan
//      lahir bersama narasi supervisor; analisis di atas hanya menampilkan
//      rekomendasi dan belum menulis keputusan apa pun;
//   4. role approver (sppg_head/nutritionist) mengajukan usulan →
//      POST /decisions → muncul di feed → approve/reject/execute.
// bgn_monitor read-only: bisa melihat semuanya, tanpa tombol Ajukan.

import { useEffect, useState } from "react";
import StatusBadge from "./StatusBadge";
import { kodeWilayah } from "../lib/wilayah";
import Event2Panel from "./Event2Panel";
import { formatIDR } from "../lib/auth";
import {
  fetchBalance,
  runAnalysis,
  createDecision,
  proposeAction,
  runEvent1,
} from "../lib/api";

const APPROVER = new Set(["sppg_head", "sppg_nutritionist"]);
const LOCATIONS = ["Jakarta", "Bogor", "Cianjur", "Bandung", "Surabaya"];
const COMMODITIES = ["telur", "beras", "ayam"];

function labelReview7Agen(status?: string): string {
  switch (status) {
    case "completed":
      return "selesai";
    case "partial":
      return "selesai sebagian";
    case "vetoed":
      return "diblokir guardian";
    case "timeout":
      return "masih berjalan (melewati batas)";
    case "unavailable":
      return "runtime belum tersedia";
    case "failed":
      return "gagal";
    case "disabled":
      return "belum aktif";
    default:
      return "belum ada hasil";
  }
}

export default function OpsConsole({
  role,
  token,
  ownLocationName = null,
  asOf = null,
  demoSessionId = null,
  onSubmitted,
  onDecisionCreated,
  snapshot: initialSnapshot = null,
  analysis: initialAnalysis = null,
  priceQuotes: initialPriceQuotes = null,
  event2: initialEvent2 = null,
  event1Result: initialEvent1 = null,
}: {
  role: string;
  ownLocationName?: string | null;
  /** Batas waktu snapshot peta; detail memakai instant yang sama. */
  asOf?: string | null;
  /** Sesi demo yang sedang dipilih (Fase 10 MG). `null` = data operasional. */
  demoSessionId?: string | null;
  token: string | null;
  onSubmitted?: () => void;
  /** Dipanggil setelah keputusan Event 1 dibuat — TANPA memindah tab, supaya
   *  hasil + narasi supervisor tetap terlihat di panel ini. */
  onDecisionCreated?: () => void;
  snapshot?: any;
  analysis?: any;
  priceQuotes?: any;
  event2?: any;
  /** Hasil Event 1 penuh yang sudah ada (dipakai tes/SSR, mis. dari sesi lain). */
  event1Result?: any;
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
  const [busy, setBusy] = useState<
    "" | "snapshot" | "analysis" | "submit" | "event1"
  >("");
  const [msg, setMsg] = useState<string | null>(null);
  // Hasil Event 1 penuh (jalur orkestrator) — disimpan terpisah dari `analysis`
  // supaya isi dua jalur itu tidak saling menimpa di layar.
  const [event1, setEvent1] = useState<any>(initialEvent1);
  // PLAN.md §13.3: pengajuan rekomendasi & Event 1 penuh = usul keputusan
  // operasional → hanya Kepala SPPG. Ahli gizi tetap bisa approve di feed.
  const canSubmit = role === "sppg_head" && !!token;

  async function loadSnapshot() {
    if (!token) return setMsg("Login diperlukan");
    setBusy("snapshot");
    setMsg(null);
    try {
      const data = await fetchBalance(location, commodity, token, asOf);
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
      // Fase 10 MG: sesi demo yang dipilih ikut dikirim, supaya balasan dan
      // keputusan berikutnya tidak dicap "sesi aktif" yang berbeda.
      const data = await runAnalysis(token, commodity, demoSessionId);
      setAnalysis(data);
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy("");
    }
  }

  // Jalur ORKESTRATOR penuh (DETECT→…→DECIDE→SUPERVISE). Berbeda dari
  // `runAgent` di atas yang hanya meminta rekomendasi: backend di sini menulis
  // keputusan + seluruh jejak langkah, termasuk narasi supervisor.
  async function jalankanEvent1Penuh() {
    if (!canSubmit) return;
    setBusy("event1");
    setMsg(null);
    try {
      const data = await runEvent1(commodity, location, token, 30, demoSessionId);
      setEvent1(data);
      setMsg(
        `Event 1 penuh selesai — keputusan ${data.decision_id} masuk feed (menunggu persetujuan).`
      );
      // Sengaja `onDecisionCreated` (bukan `onSubmitted` yang memindah tab):
      // hasil + narasi supervisor harus terbaca di panel ini dulu.
      onDecisionCreated?.();
    } catch (e: any) {
      // 409 = tidak ada kandidat eligible (keadaan data), bukan kerusakan.
      setMsg(
        e?.status === 409
          ? `Tidak ada kandidat eligible untuk ${commodity} → ${location}.`
          : String(e.message ?? e)
      );
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
    <section className="ops-console card" aria-label="Konsol operasi">
      <div className="card-header">
        <h3>Konsol Operasi — minta agent bekerja</h3>
        <span className="demo-step">Langkah 3 · picu agen</span>
      </div>
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
        {canSubmit && (
          <button
            type="button"
            className="button ops-event1"
            disabled={busy !== ""}
            onClick={jalankanEvent1Penuh}
            title="Jalankan alur Event 1 penuh (DETECT→…→SUPERVISE) lewat /demo/event1"
          >
            {busy === "event1"
              ? "Event 1 berjalan…"
              : "Jalankan Event 1 penuh"}
          </button>
        )}
        {!canSubmit && APPROVER.has(role) && (
          <p className="ops-readonly">
            Mode baca — pengajuan & Event 1 hanya untuk Kepala SPPG; Anda tetap
            bisa memberi approval di feed.
          </p>
        )}
      </div>

      {event1 && (
        <div className="card ops-event1-result" aria-label="Hasil Event 1 penuh">
          <div className="card-header">
            <h4>
              Event 1 penuh — {event1.detect?.commodity} → {location}
            </h4>
            <StatusBadge status={event1.decision_snapshot?.status ?? "proposed"} />
          </div>
          <dl className="ops-facts">
            <dt>Keputusan</dt>
            <dd>{event1.decision_id}</dd>
            <dt>Verifier</dt>
            <dd>{event1.verifier?.verdict ?? "-"}</dd>
            <dt>Forecast</dt>
            <dd>
              {event1.forecast?.forecast_qty_kg != null
                ? `${event1.forecast.forecast_qty_kg} kg`
                : "-"}
            </dd>
            <dt>Supervisor</dt>
            <dd>
              {event1.supervisor?.status ?? "-"}
              {event1.supervisor?.provider
                ? ` (${event1.supervisor.provider})`
                : ""}
            </dd>
            <dt>Langkah</dt>
            <dd>{(event1.trace_steps ?? []).join(" → ")}</dd>
            {event1.agent_review && (
              <>
                <dt>Review 8 agen</dt>
                <dd>{labelReview7Agen(event1.agent_review.status)}</dd>
              </>
            )}
          </dl>
          {event1.supervisor?.summary && (
            <p className="ops-summary">{event1.supervisor.summary}</p>
          )}
        </div>
      )}

      {snapshot && (
        <div className="ops-snapshot card">
          <div className="card-header">
            <h4>
              Kondisi {kodeWilayah(snapshot.location)} · {snapshot.commodity}
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
