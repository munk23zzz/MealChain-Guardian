"use client";

// KpiTargets (PRD 2.4 alignment, arah Roy 2026-10-09) — strip target KPI
// dari PRD §5 untuk demo day. BERLABEL EKSPLISIT "TARGET DEMO": angka ini
// BUKAN angka live dari backend (KPI live tetap jujur di panel terpisah,
// ruling O-KPI tetap berlaku — null tidak pernah diganti dummy).
// Roy: "Gunakan data dummy yang dibutuhkan untuk KPI… angka harus
// realistis" → target di bawah = angka PRD + progress bar ilustratif.
//
// Restyle 2026-10-10: layout mengikuti mockup Stitch (kpi_analytics_dashboard)
// — baris tabel padat dengan ikon inline SVG, nilai mono tabular, progress
// bar primary-container. Data TARGETS tidak diubah.

const TARGETS = [
  { name: "Meal Continuity Rate", target: "99,42%", baseline: "94,10% (manual)", progress: 99.4 },
  { name: "Avoidable Food Loss Saved", target: "94,2%", baseline: "8,40% loss (manual)", progress: 94.2 },
  { name: "Emergency Rebalance Velocity", target: "48 menit", baseline: "4,2 jam (manual)", progress: 85 },
  { name: "Delivered Cost vs Ceiling", target: "−7,2% di bawah plafon", baseline: "+4,8% di atas plafon", progress: 92 },
  { name: "Operator Triage Latency", target: "4,18 menit", baseline: "35,0 menit (manual)", progress: 88 },
  { name: "Evidence Auditability", target: "100% (Merkle-bound)", baseline: "0% (kertas)", progress: 100 },
];

// Ikon inline SVG kecil per baris target — tanpa emoji.
function TargetIcon({ name }: { name: string }) {
  const n = name.toLowerCase();
  let d = "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4v5l3 3";
  if (n.includes("continuity")) {
    d = "M3 13h18a9 9 0 0 1-18 0Z";
  } else if (n.includes("food loss")) {
    d = "M6 20c0-8 4-12 12-12 0 8-4 12-12 12Zm0 0c2-4 5-6 9-7";
  } else if (n.includes("rebalance")) {
    d = "M7 8h11m0 0-3-3m3 3-3 3M17 16H6m0 0 3-3m-3 3 3 3";
  } else if (n.includes("cost")) {
    d = "M3 7a2 2 0 0 1 2-2h12v3h3a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Zm13 6h4";
  } else if (n.includes("triage") || n.includes("latency")) {
    d = "M12 8a7 7 0 1 1 0 14 7 7 0 0 1 0-14Zm0 3v4l3 2M9 2h6";
  } else if (n.includes("evidence") || n.includes("audit")) {
    d = "M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5l8-3Zm-3 10 2.5 2.5L16 10";
  }
  return (
    <span className="kpi-target-icon" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        width="16"
        height="16"
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

export default function KpiTargets() {
  return (
    <section className="kpi-targets card" aria-label="Target KPI demo">
      <div className="card-header">
        <h3>Target KPI — Demo Day</h3>
        <span className="kpi-target-badge">TARGET DEMO · bukan angka live</span>
      </div>
      <p className="kpi-target-note">
        Angka target dari PRD v2.4 (baseline manual → target MealChain
        Guardian). Panel KPI live yang jujur ada di bagian atas halaman —
        strip ini hanya referensi target untuk skenario demo.
      </p>
      <ul className="kpi-target-list">
        {TARGETS.map((t) => (
          <li key={t.name} className="kpi-target-row">
            <span className="kpi-target-name">
              <TargetIcon name={t.name} />
              {t.name}
            </span>
            <span className="kpi-target-value">{t.target}</span>
            <span className="kpi-target-baseline">dari {t.baseline}</span>
            <span
              className="kpi-target-bar"
              role="img"
              aria-label={`progres menuju target ${t.name}: ${t.progress}%`}
            >
              <i style={{ width: `${t.progress}%` }} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
