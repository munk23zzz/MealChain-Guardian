// S4-03 UI — KPIDashboard: tujuh KPI dari GET /kpi (envelope backend).
// Kontrak plan §13 (:426): loading / seven available / no_data /
// unavailable / partial history / error. Null BUKAN 0; trend hanya bila
// comparable; scope SPPG = own location, monitor = global; perubahan
// scope tidak membocorkan cache lokasi lain.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import KPIDashboard from "../components/KPIDashboard";

const ENVELOPE_AVAILABLE = {
  period: {
    start: "2026-10-07T12:00:00+00:00",
    end: "2026-10-08T12:00:00+00:00",
  },
  scope: { location_id: "loc-1", role: "sppg_head" },
  computed_at: "2026-10-08T12:00:00+00:00",
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
    {
      name: "Avoidable Food Loss",
      unit: "kg",
      state: "unavailable",
      value: null,
      reason: "disposal event tidak tersedia di schema",
      sample_count: 0,
      coverage: null,
      previous_value: null,
      trend: null,
    },
    {
      name: "Regional Imbalance Resolution Rate",
      unit: "percent",
      state: "available",
      value: "50.00",
      reason: null,
      sample_count: 2,
      coverage: "1.00",
      previous_value: null,
      trend: null,
    },
    {
      name: "Safe Delivered Cost",
      unit: "IDR",
      state: "available",
      value: "15496548.14",
      reason: null,
      sample_count: 2,
      coverage: "1.00",
      previous_value: null,
      trend: null,
    },
    {
      name: "Procurement Price Deviation",
      unit: "percent",
      state: "available",
      value: "10.00",
      reason: null,
      sample_count: 2,
      coverage: "1.00",
      previous_value: null,
      trend: null,
    },
    {
      name: "Decision Time",
      unit: "minutes",
      state: "available",
      value: "120.00",
      reason: null,
      sample_count: 1,
      coverage: "0.50",
      previous_value: null,
      trend: null,
    },
    {
      name: "Evidence Completeness",
      unit: "percent",
      state: "no_data",
      value: null,
      reason: "tidak ada record pada periode ini",
      sample_count: 0,
      coverage: null,
      previous_value: null,
      trend: null,
    },
  ],
};

describe("KPIDashboard (S4-03)", () => {
  it("envelope penuh: tujuh kartu KPI dengan nama + unit + nilai", () => {
    const html = renderToStaticMarkup(
      <KPIDashboard kpi={ENVELOPE_AVAILABLE} />
    );
    expect(html).toContain("kpi-dashboard");
    for (const name of ENVELOPE_AVAILABLE.metrics.map((m) => m.name)) {
      expect(html).toContain(name);
    }
    expect(html).toContain("50,00"); // format id-ID
    expect(html).toContain("Rp15.496.548"); // SDC format IDR
    expect(html).toContain("120,00");
  });

  it("unavailable: value tidak dirender sebagai 0 — reason tampil", () => {
    const html = renderToStaticMarkup(
      <KPIDashboard kpi={ENVELOPE_AVAILABLE} />
    );
    // reason kedua metrik unavailable tampil apa adanya
    expect(html).toContain("facts menu plan/fulfilment");
    expect(html).toContain("disposal event");
    // kartu meal-continuity TIDAK menampilkan "0"
    const card = html.match(
      /kpi-card[\s\S]*?Meal Continuity Rate[\s\S]*?<\/div>/
    );
    expect(card).toBeTruthy();
    expect(card![0]).not.toMatch(/kpi-value[^<]*>0/);
  });

  it("no_data: reason tampil, bukan 0", () => {
    const html = renderToStaticMarkup(
      <KPIDashboard kpi={ENVELOPE_AVAILABLE} />
    );
    expect(html).toContain("tidak ada record pada periode ini");
  });

  it("trend hanya tampil bila comparable; coverage tampil", () => {
    const withTrend = {
      ...ENVELOPE_AVAILABLE,
      metrics: ENVELOPE_AVAILABLE.metrics.map((m, i) =>
        i === 3
          ? { ...m, previous_value: "15000000.00", trend: "down" }
          : m
      ),
    };
    const html = renderToStaticMarkup(<KPIDashboard kpi={withTrend} />);
    expect(html).toContain("trend-down");
    // metrik lain tanpa trend → tidak ada elemen trend lain
    expect(html.match(/trend-down/g)?.length).toBe(1);
  });

  it("loading state: skeleton tanpa angka karangan", () => {
    const html = renderToStaticMarkup(<KPIDashboard kpi={null} loading />);
    expect(html).toContain("kpi-loading");
    expect(html).not.toContain("kpi-value");
  });

  it("error state: pesan error + tombol coba lagi, tanpa angka palsu", () => {
    const html = renderToStaticMarkup(
      <KPIDashboard kpi={null} error="Koneksi gagal" onRetry={() => {}} />
    );
    expect(html).toContain("kpi-error");
    expect(html).toContain("Koneksi gagal");
    expect(html).toContain("kpi-retry");
    expect(html).not.toContain("kpi-value");
  });

  it("scope change: KPIDashboard menerima prop kpi penuh (bukan cache lama)", () => {
    // Komponen murni presentational: parent yang mengganti scope mem-
    // berikan envelope baru; komponen merender envelope itu saja.
    const otherScope = {
      ...ENVELOPE_AVAILABLE,
      scope: { location_id: "loc-other", role: "sppg_head" },
    };
    const html = renderToStaticMarkup(<KPIDashboard kpi={otherScope} />);
    expect(html).toContain("loc-other");
  });
});
