"use client";

// Event 2 Panel (S4-01) — price anomaly review, TANPA auto-PO.
// Semua angka dari backend (GET /price/quotes + POST /events/price-anomaly).
// Wording review-required (plan §11/§16), bukan tuduhan fraud.
import { useEffect, useState } from "react";
import StatusBadge from "./StatusBadge";
import { formatIDR } from "../lib/auth";
import { fetchPriceQuotes, triggerPriceAnomaly } from "../lib/api";

const LOCATIONS = ["Jakarta", "Bogor", "Cianjur", "Bandung", "Surabaya"];
const COMMODITIES = ["telur", "ayam", "wortel"];

export default function Event2Panel({
  role,
  token,
  ownLocationName = null,
  onDecisionCreated,
  initialQuotes = null,
  initialResult = null,
}: {
  role: string;
  token: string | null;
  ownLocationName?: string | null;
  onDecisionCreated?: () => void;
  initialQuotes?: any;
  initialResult?: any;
}) {
  const [location, setLocation] = useState("Jakarta");
  const [commodity, setCommodity] = useState("telur");
  const [data, setData] = useState<any>(initialQuotes);
  const [selected, setSelected] = useState<string>(
    initialQuotes?.quotes?.[0]?.id ?? ""
  );
  const [opKey, setOpKey] = useState<string>(
    initialQuotes
      ? "00000000-0000-4000-8000-000000000000"
      : ""
  );
  const [result, setResult] = useState<any>(initialResult);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // Pemicu Event 2 membuat keputusan operasional → usul, jadi hanya Kepala
  // SPPG (PLAN.md §13.3). Ahli gizi tetap bisa approve di feed.
  const canRun = token !== null && role === "sppg_head";
  // Ruling 2026-10-14: penawaran hanya boleh dibaca untuk SPPG sendiri, jadi
  // pilihan lokasi dikunci untuk peran SPPG (hanya bgn_monitor lintas lokasi).
  const canChooseLocation = role === "bgn_monitor";

  useEffect(() => {
    if (!canChooseLocation && ownLocationName) setLocation(ownLocationName);
  }, [canChooseLocation, ownLocationName]);

  async function loadQuotes() {
    if (!token) return setMsg("Login diperlukan");
    setBusy(true);
    setMsg(null);
    setResult(null);
    try {
      const d = await fetchPriceQuotes(location, commodity, token);
      setData(d);
      setSelected(d.quotes?.[0]?.id ?? "");
      // operation_key baru per sesi pemilihan (idempotensi per aksi —
      // retry aksi yang sama memakai key yang sama → replay aman).
      setOpKey(
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}-0000-4000-8000-${Date.now().toString().padStart(12, "0")}`
      );
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    if (!token || !selected) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await triggerPriceAnomaly(
        selected,
        data.location_id,
        opKey,
        token
      );
      setResult(r);
      if (r.decision_id) onDecisionCreated?.();
    } catch (e: any) {
      setMsg(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="event2-panel card" aria-label="Event 2 — anomali harga">
      <div className="card-header">
        <h3>Event 2 — Deteksi Anomali Harga</h3>
        <StatusBadge status={result ? result.status : "proposed"} />
      </div>
      <p className="event2-note">
        Bandingkan penawaran supplier dengan referensi PIHPS. Deviasi dihitung
        otomatis oleh sistem; hasilnya adalah deteksi untuk ditelaah manusia.
      </p>
      <div className="ops-controls">
        <label className="field">
          <span>Lokasi</span>
          <select
            className="event2-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            disabled={!canRun || busy || !canChooseLocation}
            aria-describedby="event2-location-note"
          >
            {canChooseLocation
              ? LOCATIONS.map((l) => <option key={l}>{l}</option>)
              : ownLocationName
                ? [ownLocationName].map((l) => <option key={l}>{l}</option>)
                : null}
          </select>
          <small id="event2-location-note" className="field-note">
            {canChooseLocation
              ? "Cakupan nasional (bgn_monitor) — semua lokasi."
              : "Terkunci ke SPPG Anda (cakupan lokasi 2026-10-14)."}
          </small>
        </label>
        <label className="field">
          <span>Komoditas</span>
          <select
            className="event2-commodity"
            value={commodity}
            onChange={(e) => setCommodity(e.target.value)}
            disabled={!canRun || busy}
          >
            {COMMODITIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        {canRun && (
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={loadQuotes}
          >
            {busy ? "Memuat…" : "Muat penawaran"}
          </button>
        )}
      </div>

      {canRun && data && (
        <>
          <div className="event2-reference">
            Referensi PIHPS{" "}
            {data.reference ? (
              <>
                {formatIDR(data.reference.price_per_kg)}/kg
                <span className="event2-ref-at">
                  {" "}
                  (
                  {new Date(data.reference.recorded_at).toLocaleString(
                    "id-ID"
                  )}
                  )
                </span>
              </>
            ) : (
              " tidak tersedia"
            )}
          </div>
          <ul className="event2-quotes">
            {data.quotes.map((q: any) => (
              <li key={q.id}>
                <label>
                  <input
                    type="radio"
                    name="event2-quote"
                    value={q.id}
                    checked={selected === q.id}
                    onChange={() => setSelected(q.id)}
                  />
                  <span className="event2-supplier">{q.supplier_name}</span>
                  <span className="event2-price">
                    {formatIDR(q.price_per_kg)}/kg
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="button button-primary event2-run"
            disabled={busy || !selected}
            onClick={run}
          >
            {busy ? "Agent menganalisis…" : "Jalankan Event 2"}
          </button>
        </>
      )}

      {result && (
        <div className={`event2-result event2-${result.status}`}>
          <p className="event2-message">{result.message}</p>
          <dl className="ops-facts">
            <dt>Deviasi</dt>
            <dd>{String(result.deviation_pct).replace(".", ",")}%</dd>
            <dt>Klasifikasi</dt>
            <dd>{result.classification}</dd>
            {result.decision_id ? (
              <>
                <dt>Status</dt>
                <dd>Masuk review queue</dd>
              </>
            ) : null}
          </dl>
        </div>
      )}

      {msg && <p className="action-message">{msg}</p>}
      {!canRun && (
        <p className="event2-readonly">
          Mode baca — Event 2 dijalankan oleh approver.
        </p>
      )}
    </section>
  );
}
