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

const UNIT_FMT: Record<string, (v: string) => string> = {
  IDR: (v) =>
    "Rp" + Number(v).toLocaleString("id-ID", { maximumFractionDigits: 0 }),
};

function fmtValue(unit: string, value: string | null): string | null {
  if (value === null) return null;
  const fmt = UNIT_FMT[unit];
  return fmt ? fmt(value) : Number(value).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const STATE_LABEL: Record<string, string> = {
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
      <section className="kpi-dashboard card" aria-busy="true">
        <div className="kpi-console-header">
          <div>
            <div className="kpi-breadcrumb" aria-hidden="true">
              <span>Guardian Core</span>
              <span className="kpi-breadcrumb-sep">/</span>
              <span>KPI &amp; Analytics</span>
            </div>
            <h3>KPI</h3>
          </div>
        </div>
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
      <section className="kpi-dashboard card">
        <div className="kpi-console-header">
          <div>
            <div className="kpi-breadcrumb" aria-hidden="true">
              <span>Guardian Core</span>
              <span className="kpi-breadcrumb-sep">/</span>
              <span>KPI &amp; Analytics</span>
            </div>
            <h3>KPI</h3>
          </div>
        </div>
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
    <section className="kpi-dashboard card">
      {/* Header konsol ala mockup Stitch: breadcrumb + judul + pill scope */}
      <div className="kpi-console-header">
        <div>
          <div className="kpi-breadcrumb" aria-hidden="true">
            <span>Guardian Core</span>
            <span className="kpi-breadcrumb-sep">/</span>
            <span>KPI &amp; Analytics Dashboard</span>
          </div>
          <h3>KPI</h3>
          {/* Pill filter periode + scope — data murni dari envelope live */}
          <div className="kpi-scope" data-testid="kpi-scope">
            <span className="kpi-scope-pill kpi-scope-period">
              <svg
                viewBox="0 0 24 24"
                width="12"
                height="12"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <path d="M4 6h16v14H4zM8 3v5M16 3v5M4 11h16" />
              </svg>
              Periode {kpi.period?.start ?? "-"} s.d. {kpi.period?.end ?? "-"}
            </span>
            <span className="kpi-scope-pill kpi-scope-loc">
              scope {kpi.scope?.location_id ?? "global"} ({kpi.scope?.role ?? "-"})
            </span>
          </div>
        </div>
      </div>
      {/* Bento grid ala Stitch: 4 kartu pertama sel lebar, 3 sisanya rapat */}
      <div className="kpi-grid">
        {kpi.metrics.map((m: any) => {
          const shown = fmtValue(m.unit, m.value);
          const trend = trendClass(m.trend);
          return (
            <div key={m.name} className={`kpi-card kpi-${m.state}`}>
              <div className="card-header">
                <h4>{m.name}</h4>
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
              <span className={`kpi-state kpi-state-${m.state}`}>
                {STATE_LABEL[m.state] ?? m.state}
              </span>
              {m.reason && <p className="kpi-reason">{m.reason}</p>}
              <p className="kpi-meta">
                sampel {m.sample_count ?? 0}
                {m.coverage !== null && m.coverage !== undefined
                  ? ` · coverage ${Number(m.coverage).toLocaleString("id-ID")}`
                  : ""}
              </p>
              {trend && (
                <p className={`kpi-trend ${trend}`}>
                  {m.trend === "up" ? (
                    <>
                      <svg
                        viewBox="0 0 24 24"
                        width="11"
                        height="11"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M12 19V5m0 0-6 6m6-6 6 6" />
                      </svg>{" "}
                      naik
                    </>
                  ) : m.trend === "down" ? (
                    <>
                      <svg
                        viewBox="0 0 24 24"
                        width="11"
                        height="11"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M12 5v14m0 0-6-6m6 6 6-6" />
                      </svg>{" "}
                      turun
                    </>
                  ) : (
                    <>
                      <svg
                        viewBox="0 0 24 24"
                        width="11"
                        height="11"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        aria-hidden="true"
                      >
                        <path d="M4 12h16" />
                      </svg>{" "}
                      datar
                    </>
                  )}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
