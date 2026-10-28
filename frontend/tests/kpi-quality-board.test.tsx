// Kontrak markup tab gabungan "KPI & Kualitas Agen" (keputusan pemilik 2026-10-15).
//
// Yang diuji di sini BUKAN angka KPI atau skor mutu (itu milik
// kpi-dashboard.test.tsx dan agent-quality-board.test.tsx), melainkan sifat
// penggabungannya:
// - kedua bagian ada di SATU halaman, urutannya KPI dulu lalu mutu agen;
// - kegagalan satu bagian TIDAK menyembunyikan bagian lain (dua siklus muat yang
//   terpisah: GET /kpi vs sampel jejak agen);
// - tidak ada angka target PRD yang ikut kembali (kontrol negatif untuk
//   penghapusan strip Target KPI di hari yang sama).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import KpiQualityBoard from "../components/KpiQualityBoard";
import { runOf } from "../lib/agent-quality";

const TRACE = {
  steps: [
    {
      step_name: "PREDICT",
      tool_called: "forecast.daily",
      output_summary: { method: "provider_forecast" },
      step_at: "2026-10-11T05:16:46Z",
    },
  ],
};

const RUNS = [
  runOf(
    {
      decision_id: "e430a0e8-9d9a",
      decision_type: "regional_balance",
      status: "pending_approval",
      iteration: 3,
    },
    TRACE,
    { verifier: { verdict: "consistent" } }
  ),
];

const KPI = {
  period: { start: "2026-10-07T12:00:00+00:00", end: "2026-10-08T12:00:00+00:00" },
  scope: { location_id: "loc-1", role: "sppg_head" },
  data_source: "live_aggregate",
  metrics: [
    {
      name: "Meal Continuity Rate",
      unit: "percent",
      state: "unavailable",
      value: null,
      reason: "facts menu plan/fulfilment tidak tersedia di schema",
      sample_count: 0,
      coverage: null,
      previous_value: null,
      trend: null,
    },
  ],
};

function render(props: Partial<Parameters<typeof KpiQualityBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <KpiQualityBoard
      kpi={KPI}
      runs={RUNS}
      evaluatedCount={8}
      totalDecisions={95}
      {...props}
    />
  );
}

describe("KpiQualityBoard (tab gabungan KPI & Kualitas Agen)", () => {
  it("KPI dulu, lalu mutu agen, dalam satu halaman", () => {
    const html = render();
    expect(html).toContain('class="kpi-quality-page"');
    expect(html).toContain("kpi-dashboard");
    expect(html).toContain("Skor agregat");
    expect(html).toContain("Rincian per run");
    // Urutan: blok KPI muncul sebelum blok mutu agen.
    expect(html.indexOf("kpi-dashboard")).toBeLessThan(html.indexOf("board-page"));
  });

  it("ada pembatas antar-bagian", () => {
    expect(render()).toContain("kpi-quality-divider");
  });

  it("galat KPI tidak menyembunyikan mutu agen", () => {
    const html = render({ kpi: null, kpiError: "KPI tidak bisa dihitung saat ini" });
    expect(html).toContain("KPI tidak bisa dihitung saat ini");
    expect(html).toContain("Skor agregat");
    expect(html).toContain("Rincian per run");
  });

  it("galat sampel tidak menyembunyikan KPI", () => {
    const html = render({ runs: [], qualityError: "jejak agen tidak bisa dimuat" });
    expect(html).toContain("jejak agen tidak bisa dimuat");
    expect(html).toContain("kpi-dashboard");
    expect(html).toContain("Tujuh indikator kontinuitas pangan. Angka yang belum bisa dihitung ditulis alasannya.");
  });

  it("loading tiap bagian berdiri sendiri", () => {
    const html = render({ kpiLoading: true, qualityLoading: true });
    expect(html).toContain("kpi-dashboard");
    expect(html).toContain("board-page");
  });

  it("tanpa payload KPI mutu agen tetap tampil (dan sebaliknya)", () => {
    const tanpaKpi = render({ kpi: null });
    expect(tanpaKpi).toContain("Skor agregat");
    const tanpaRun = render({ runs: [] });
    expect(tanpaRun).toContain("Tujuh indikator kontinuitas pangan. Angka yang belum bisa dihitung ditulis alasannya.");
  });

  it("tidak ada angka target PRD yang ikut kembali (kontrol negatif)", () => {
    const html = render();
    expect(html).not.toContain("Target KPI");
    expect(html).not.toContain("TARGET DEMO");
  });
});
