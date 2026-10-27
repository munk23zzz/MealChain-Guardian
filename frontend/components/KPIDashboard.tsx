"use client";

// KPIDashboard (S4-03) — tujuh KPI dari GET /kpi via fetchKpis().
// Presentational murni: envelope dari server dirender apa adanya.
// Null TIDAK diganti 0 (ruling O-KPI); state available/no_data/
// unavailable selalu terlihat + reason bila bukan available.
// Angka format id-ID; SDC format IDR.
//
// Restyle 2026-10-10: layout mengikuti mockup Stitch
// (mockupui/kpi_analytics_dashboard/code.html) — header konsol dengan
// breadcrumb, bento grid 7 kartu (4 atas + 3 bawah), ikon inline SVG.
// Kontrak markup untuk test TIDAK berubah (class kpi-* dipin).

import PageHeader from "./PageHeader";
import {
  bulletOf,
  directionLabel,
  fmtCoverage,
  KPI_WINDOWS,
  metricLabel,
  periodePil,
  type KpiWindowKey,
} from "../lib/kpi";
import {
  baselineText,
  baselineOf,
  estimateLine,
  estimateOf,
  factLine,
  KPI_SCOPES,
  provenanceLines,
  SCOPE_EXPLANATION,
  scopeLabel,
  type KpiScope,
} from "../lib/kpi-provenance";
import { roleLabel } from "../lib/settings";

const UNIT_FMT: Record<string, (v: string) => string> = {
  IDR: (v) =>
    "Rp" + Number(v).toLocaleString("id-ID", { maximumFractionDigits: 0 }),
};

/** Format nilai metrik KPI (id-ID; SDC memakai IDR). Diekspor supaya halaman
 *  "Hari Ini" memakai format yang SAMA — dua format persen di satu aplikasi
 *  akan terbaca seperti dua sumber data. */
export function fmtValue(unit: string, value: string | null): string | null {
  if (value === null) return null;
  const fmt = UNIT_FMT[unit];
  return fmt ? fmt(value) : Number(value).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Nama satuan untuk LAYAR. Nilai `unit` dari server tidak diubah — hanya
 *  namanya yang diterjemahkan, supaya kontrak API tetap dan fixture tetap sah
 *  (WS-C, QA 16 Okt: layar menampilkan "percent" berbahasa Inggris).
 *  Satuan tak dikenal ditampilkan apa adanya — jangan mengarang nama. */
const UNIT_LABELS: Record<string, string> = {
  IDR: "", // nilainya sudah berawalan Rp — jangan ditulis dua kali
  percent: "persen",
  percentage: "persen",
  pct: "persen",
  minutes: "menit",
};

export function unitLabel(unit: unknown): string {
  const key = String(unit ?? "").trim();
  if (!key) return "";
  return key in UNIT_LABELS ? UNIT_LABELS[key] : key;
}

/** Keadaan metrik dari backend (kata apa adanya, tidak dikarang). Diekspor
 *  untuk halaman "Hari Ini" supaya istilahnya sama dengan tab KPI. */
export const STATE_LABEL: Record<string, string> = {
  available: "tersedia",
  no_data: "belum ada data",
  unavailable: "tidak tersedia",
};

/**
 * Pil cakupan data: operasional vs simulasi (Fase 8).
 *
 * Kenapa ada: sejak kartu KPI memisahkan fakta demo dari fakta kerja, pembaca
 * harus tahu angka mana yang sedang ia lihat. Komponen ini hanya MEMILIH
 * cakupan; ia tidak menghitung apa pun dan tidak menebak mode dari angka.
 *
 * `aria-describedby` + teks penjelas dipakai supaya perbedaannya tidak hanya
 * tersirat dari warna pil (pembaca layar tidak melihat warna).
 */
export function KpiScopeToggle({
  scope,
  onScopeChange,
  disabled = false,
  disabledReason = null,
}: {
  scope: KpiScope;
  onScopeChange?: (scope: KpiScope) => void;
  /** Simulasi butuh sesi demo aktif; tanpa sesi, pilihannya dimatikan. */
  disabled?: boolean;
  disabledReason?: string | null;
}) {
  const aktif = KPI_SCOPES.find((s) => s.key === scope) ?? KPI_SCOPES[0];
  return (
    <div
      className="kpi-scope-toggle"
      role="group"
      aria-label="Cakupan data KPI"
      data-testid="kpi-scope-toggle"
      data-scope={scope}
      aria-describedby="kpi-scope-explanation"
    >
      <span className="kpi-period-label">Cakupan data:</span>
      {KPI_SCOPES.map((s) => {
        const dipilih = s.key === scope;
        return (
          <button
            key={s.key}
            type="button"
            className={`commodity-pill kpi-scope-pill${dipilih ? " is-active" : ""}`}
            data-scope-option={s.key}
            aria-pressed={dipilih}
            disabled={disabled && s.key === "demo"}
            onClick={() => onScopeChange?.(s.key)}
          >
            {s.label}
          </button>
        );
      })}
      <span id="kpi-scope-explanation" className="kpi-scope-hint">
        {disabled && disabledReason ? `${disabledReason} ` : ""}
        {aktif.hint} {SCOPE_EXPLANATION}
      </span>
    </div>
  );
}

function trendClass(trend: string | null): string | null {
  if (trend === "up") return "trend-up";
  if (trend === "down") return "trend-down";
  if (trend === "flat") return "trend-flat";
  return null;
}

// Ikon inline SVG kecil per metrik — tanpa emoji, mengikuti mockup Stitch
// (restaurant/eco/sync_alt/wallet/gavel/timer/verified_user disederhanakan).
function MetricIcon({ name }: { name: string }) {
  const n = name.toLowerCase();
  let d = "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 3v7"; // fallback: titik lingkaran
  if (n.includes("continuity")) {
    // piring + garis menu (restaurant)
    d = "M3 13h18a9 9 0 0 1-18 0ZM7 4v6M10 4v6M10 7H7M17 4c-1.5 1-2 3-2 6";
  } else if (n.includes("avoidable") || n.includes("loss")) {
    // daun (eco)
    d = "M6 20c0-8 4-12 12-12 0 8-4 12-12 12Zm0 0c2-4 5-6 9-7";
  } else if (n.includes("imbalance") || n.includes("rebalance")) {
    // panah bolak-balik (sync_alt)
    d = "M7 8h11m0 0-3-3m3 3-3 3M17 16H6m0 0 3-3m-3 3 3 3";
  } else if (n.includes("cost") || n.includes("delivered")) {
    // dompet (account_balance_wallet)
    d = "M3 7a2 2 0 0 1 2-2h12v3h3a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Zm13 6h4";
  } else if (n.includes("procurement") || n.includes("deviation")) {
    // palu hakim (gavel)
    d = "M14 3l7 7-2 2-7-7 2-2Zm-3 5 5 5-8 8H3v-5l8-8Z";
  } else if (n.includes("decision") || n.includes("time")) {
    // stopwatch (timer)
    d = "M12 8a7 7 0 1 1 0 14 7 7 0 0 1 0-14Zm0 3v4l3 2M9 2h6";
  } else if (n.includes("evidence") || n.includes("completeness")) {
    // perisai centang (verified_user)
    d = "M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5l8-3Zm-3 10 2.5 2.5L16 10";
  }
  return (
    <span className="kpi-icon" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d={d} />
      </svg>
    </span>
  );
}

export default function KPIDashboard({
  kpi,
  loading = false,
  error = null,
  onRetry,
  windowKey = "today",
  onWindowChange,
  scope = "operational",
  onScopeChange,
  scopeDisabledReason = null,
}: {
  kpi: any | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** Jendela yang sedang diminta PARENT (halaman) — komponen tidak menyimpan
   *  state sendiri, supaya angka di layar dan label periode tidak bisa berbeda. */
  windowKey?: KpiWindowKey;
  onWindowChange?: (key: KpiWindowKey) => void;
  /** Cakupan data yang diminta halaman: fakta kerja atau satu sesi demo. */
  scope?: KpiScope;
  onScopeChange?: (scope: KpiScope) => void;
  /** Diisi halaman bila tidak ada sesi demo aktif (simulasi tidak bisa dipilih). */
  scopeDisabledReason?: string | null;
}) {
  if (loading) {
    return (
      <section className="kpi-dashboard" aria-busy="true">
        <PageHeader
          title="KPI"
          description="Tujuh indikator kontinuitas pangan institusional."
        />
        {/* Kelas kpi-loading tetap ada (dipin tes) tetapi hanya untuk pembaca
            layar: tampilannya kini skeleton, bukan teks "Memuat…" berkedip. */}
        <p className="kpi-loading sr-only" aria-live="polite">
          Memuat KPI…
        </p>
        <div className="skeleton-grid" aria-hidden="true">
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="kpi-dashboard">
        <PageHeader
          title="KPI"
          description="Tujuh indikator kontinuitas pangan institusional."
        />
        <p className="kpi-error status-danger" role="alert">
          {error}
        </p>
        {onRetry && (
          <button type="button" className="button kpi-retry" onClick={onRetry}>
            Coba lagi
          </button>
        )}
      </section>
    );
  }

  if (!kpi || !Array.isArray(kpi.metrics)) {
    return null;
  }

  return (
    <section className="kpi-dashboard">
      <PageHeader
        title="KPI"
        description="Tujuh indikator kontinuitas pangan institusional. Indikator yang belum bisa dihitung ditulis alasannya, bukan diganti nol."
        meta={
          <span className="page-header-pills" data-testid="kpi-scope">
            <span className="commodity-pill">
              {periodePil(windowKey, kpi.period?.start, kpi.period?.end)}
            </span>
            <span className="commodity-pill" title={kpi.scope?.location_id ?? undefined}>
              Cakupan: {kpi.scope?.role ? roleLabel(kpi.scope.role) : "—"}
            </span>
            <span className="commodity-pill" data-testid="kpi-data-mode">
              {scopeLabel(kpi.data_mode)}
            </span>
          </span>
        }
      />
      {/* Pemilih periode (permintaan pemilik 2026-10-16). Jendela 24 jam tetap
          sah, tetapi dataset demo beracuan 8 Okt: tanpa pilihan ini, kartu
          "Avoidable Food Loss" dan "Procurement Price Deviation" selalu
          menjawab "belum ada data" padahal datanya ADA di database — hanya di
          luar 24 jam. Kontrol ini tidak menghitung apa pun; ia memberi tahu
          HALAMAN jendela mana yang harus dimuat (angkanya tetap dari backend). */}
      <div className="kpi-period" role="group" aria-label="Jendela periode KPI">
        <span className="kpi-period-label">Periode:</span>
        {KPI_WINDOWS.map((w) => {
          const aktif = w.key === windowKey;
          return (
            <button
              key={w.key}
              type="button"
              className={`commodity-pill kpi-period-pill${aktif ? " is-active" : ""}`}
              data-window={w.key}
              aria-pressed={aktif}
              onClick={() => onWindowChange?.(w.key)}
            >
              {w.label}
            </button>
          );
        })}
      </div>
      {/* Cakupan data (Fase 8): operasional vs simulasi. Angka kedua cakupan
          TIDAK boleh tercampur — backend menyaring baris sesi demo di SQL. */}
      <KpiScopeToggle
        scope={scope}
        onScopeChange={onScopeChange}
        disabled={Boolean(scopeDisabledReason)}
        disabledReason={scopeDisabledReason}
      />
      {/* Grup terpisah: angka simulasi tidak boleh terbaca sebagai hasil
          operasional, jadi judulnya menyebut mode data yang dikirim backend. */}
      <section
        className="kpi-group"
        data-mode={String(kpi.data_mode ?? "")}
        aria-label={scopeLabel(kpi.data_mode)}
      >
        <h2 className="kpi-group-title">{scopeLabel(kpi.data_mode)}</h2>
        {String(kpi.data_mode) === "demo" ? (
          <p className="kpi-group-note" data-testid="kpi-demo-note">
            Angka di grup ini berasal dari sesi demo — simulasi, bukan hasil
            lapangan. Kartu bertanda <strong>estimasi</strong> adalah proyeksi
            model, bukan catatan kejadian.
          </p>
        ) : null}
      {/* Grid kartu metrik tiga kolom (pola halaman KPI acuan).
          Fase 4: tiap kartu = angka besar + bullet bar (hanya untuk metrik
          yang memang punya skala, lihat lib/kpi.ts) + arah perbaikan. */}
      <div className="kpi-grid">
        {kpi.metrics.map((m: any) => {
          const shown = fmtValue(m.unit, m.value);
          const trend = trendClass(m.trend);
          const bullet = bulletOf(m);
          const arah = bullet ? directionLabel(bullet.direction) : null;
          const prov = provenanceLines(m);
          const est = estimateOf(m);
          const estText = estimateLine(m);
          const factText = factLine(m);
          return (
            <article key={m.name} className={`kpi-card card kpi-${m.state}`}>
              <div className="kpi-card-top">
                <p className="kpi-card-name" title={m.name}>
                  {metricLabel(m.name)}
                </p>
                <MetricIcon name={m.name} />
              </div>
              {shown !== null ? (
                <p className="kpi-value">
                  {shown}
                  <small> {unitLabel(m.unit)}</small>
                </p>
              ) : (
                <p className="kpi-value kpi-value-none">—</p>
              )}
              {bullet && bullet.pct !== null ? (
                <div
                  className="kpi-bullet"
                  data-over={bullet.overMax ? "true" : undefined}
                  role="img"
                  aria-label={`${shown} ${unitLabel(m.unit)} dari skala 0–${bullet.max}${
                    bullet.overMax ? " (melewati skala)" : ""
                  }`}
                >
                  <span className="kpi-bullet-track" aria-hidden="true">
                    <span
                      className="kpi-bullet-fill"
                      style={{ width: `${bullet.pct}%` }}
                    />
                  </span>
                  <span className="kpi-bullet-scale" aria-hidden="true">
                    <span>0</span>
                    <span>
                      {bullet.max}
                      {unitLabel(m.unit) ? ` ${unitLabel(m.unit)}` : ""}
                    </span>
                  </span>
                </div>
              ) : null}
              {arah ? <p className="kpi-direction">{arah}</p> : null}
              <p className="kpi-card-flags">
                <span className={`kpi-state kpi-state-${m.state}`}>
                  {STATE_LABEL[m.state] ?? m.state}
                </span>
                {trend && (
                  <span className={`kpi-trend ${trend}`}>
                    {m.trend === "up" ? "▲ naik" : m.trend === "down" ? "▼ turun" : "■ datar"}
                  </span>
                )}
              </p>
              {m.reason && <p className="kpi-reason">{m.reason}</p>}
              <p className="kpi-meta">
                sampel {m.sample_count ?? 0}
                {m.coverage !== null && m.coverage !== undefined
                  ? ` · cakupan ${fmtCoverage(m.coverage)}`
                  : ""}
              </p>
              {/* Provenance (Fase 8): tingkat bukti selalu terlihat; sumber,
                  periode, metode, dan baseline ada satu klik di bawahnya. */}
              {prov.length ? (
                <div className="kpi-prov" data-testid="kpi-provenance">
                  <p className="kpi-prov-evidence">
                    Bukti:{" "}
                    <strong>
                      {prov.find((l) => l.key === "evidence")?.value ?? "—"}
                    </strong>
                  </p>
                  <details className="kpi-prov-detail">
                    <summary>Asal data, periode, dan metode</summary>
                    <dl>
                      {prov.map((l) => (
                        <div key={l.key} className="kpi-prov-row">
                          <dt>{l.label}</dt>
                          <dd>{l.value}</dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                </div>
              ) : null}
              {estText ? (
                <p className="kpi-estimate" data-testid="kpi-estimate">
                  {estText}
                  {est?.definition ? (
                    <span className="kpi-estimate-note"> — {est.definition}</span>
                  ) : null}
                </p>
              ) : null}
              {factText ? <p className="kpi-fact">{factText}</p> : null}
            </article>
          );
        })}
      </div>
      </section>
    </section>
  );
}
