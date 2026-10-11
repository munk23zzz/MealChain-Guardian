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

/** Tanggal periode dalam bahasa manusia (acuan: "24 Sep 2026 22:08 WIB").
 *  Envelope membawa ISO lengkap — menampilkannya mentah itu tidak terbaca. */
function fmtPeriodDate(iso?: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** UUID panjang dipotong supaya pill tetap ringkas tapi masih bisa dilacak. */
function shortId(id?: string | null): string {
  if (!id) return "global";
  return id.length > 10 ? `${id.slice(0, 8)}…` : id;
}

/** Keadaan metrik dari backend (kata apa adanya, tidak dikarang). Diekspor
 *  untuk halaman "Hari Ini" supaya istilahnya sama dengan tab KPI. */
export const STATE_LABEL: Record<string, string> = {
  available: "tersedia",
  no_data: "belum ada data",
  unavailable: "tidak tersedia",
};

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
}: {
  kpi: any | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}) {
  if (loading) {
    return (
      <section className="kpi-dashboard" aria-busy="true">
        <PageHeader
          title="KPI"
          description="Tujuh indikator kontinuitas pangan institusional dari /kpi."
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
          description="Tujuh indikator kontinuitas pangan institusional dari /kpi."
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
        description="Tujuh indikator kontinuitas pangan institusional dari /kpi. Nilai null tidak pernah diganti 0 — keadaan dan alasannya selalu terlihat."
        meta={
          <span className="page-header-pills" data-testid="kpi-scope">
            <span className="commodity-pill">
              Periode {fmtPeriodDate(kpi.period?.start)} – {fmtPeriodDate(kpi.period?.end)}
            </span>
            <span className="commodity-pill">
              scope {shortId(kpi.scope?.location_id)} ({kpi.scope?.role ?? "-"})
            </span>
          </span>
        }
      />
      {/* Grid kartu metrik tiga kolom (pola halaman KPI acuan). */}
      <div className="kpi-grid">
        {kpi.metrics.map((m: any) => {
          const shown = fmtValue(m.unit, m.value);
          const trend = trendClass(m.trend);
          return (
            <article key={m.name} className={`kpi-card card kpi-${m.state}`}>
              <div className="kpi-card-top">
                <p className="kpi-card-name">{m.name}</p>
                <MetricIcon name={m.name} />
              </div>
              {shown !== null ? (
                <p className="kpi-value">
                  {shown}
                  <small> {m.unit === "IDR" ? "" : m.unit}</small>
                </p>
              ) : (
                <p className="kpi-value kpi-value-none">—</p>
              )}
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
                  ? ` · coverage ${Number(m.coverage).toLocaleString("id-ID")}`
                  : ""}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
