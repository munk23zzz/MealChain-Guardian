// Kartu KPI sebagai grid datar + pil kesegaran angka (29 Okt 2026).
//
// Riwayat: sempat ada judul kelompok per domain di atas kartu. Pemilik meminta
// bagian itu dihapus — yang tampil hanya kartu KPI. Tes ini menjaga dua hal:
//   1. Tidak ada lagi judul/keterangan kelompok di atas kartu.
//   2. Semua metrik tetap tampil (tidak ada yang hilang saat judul dihapus),
//      dan `computed_at` server dipakai sebagai cap waktu — bukan jam klien.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import KPIDashboard from "../components/KPIDashboard";

const METRIK = [
  { name: "Meal Continuity Rate", unit: "percent", state: "no_data", value: null, reason: "belum ada rencana menu", sample_count: 0, trend: null },
  { name: "Regional Imbalance Resolution Rate", unit: "percent", state: "available", value: "0.00", sample_count: 2, coverage: "1.00", trend: null },
  { name: "Avoidable Food Loss", unit: "percent", state: "no_data", value: null, reason: "belum ada pembuangan", sample_count: 0, trend: null },
  { name: "Safe Delivered Cost", unit: "IDR", state: "no_data", value: null, reason: "belum ada PO", sample_count: 0, trend: null },
  { name: "Procurement Price Deviation", unit: "percent", state: "available", value: "3.21", sample_count: 4, trend: null },
  { name: "Decision Time", unit: "minutes", state: "no_data", value: null, reason: "belum ada usulan", sample_count: 0, trend: null },
  { name: "Evidence Completeness", unit: "percent", state: "no_data", value: null, reason: "belum ada bukti", sample_count: 0, trend: null },
];

const ENVELOPE = {
  period: { start: "2026-10-28T17:00:00+00:00", end: "2026-10-29T06:26:39+00:00" },
  scope: { location_id: "loc-1", role: "sppg_head" },
  // 06.26 UTC = 13.26 WIB
  computed_at: "2026-10-29T06:26:39.714707+00:00",
  data_source: "live_aggregate",
  data_mode: "operational",
  method_version: "kpi-2026.10.28",
  metrics: METRIK,
};

describe("grid KPI datar", () => {
  it("tidak lagi punya judul/keterangan kelompok di atas kartu", () => {
    const html = renderToStaticMarkup(<KPIDashboard kpi={ENVELOPE} />);
    expect(html).not.toContain("kpi-domains");
    expect(html).not.toContain("kpi-domain-title");
    expect(html).not.toContain("kpi-domain-count");
    expect(html).not.toContain("kpi-domain-hint");
    expect(html).not.toContain("Kontinuitas &amp; pemerataan pasokan");
    expect(html).not.toContain("Porsi rencana vs yang terkirim");
  });

  it("delapan metrik tetap tampil setelah judul kelompok dihapus", () => {
    const html = renderToStaticMarkup(<KPIDashboard kpi={ENVELOPE} />);
    for (const m of METRIK) {
      expect(html).toContain(m.name);
    }
    expect(html.match(/<article[^>]*class="kpi-card/g)?.length).toBe(METRIK.length);
  });

  it("urutan kartu mengikuti payload backend", () => {
    const html = renderToStaticMarkup(<KPIDashboard kpi={ENVELOPE} />);
    const sdc = html.indexOf("Safe Delivered Cost");
    const dev = html.indexOf("Procurement Price Deviation");
    expect(sdc).toBeGreaterThan(-1);
    expect(dev).toBeGreaterThan(sdc);
  });

  it("menampilkan waktu hitung server dalam WIB", () => {
    const html = renderToStaticMarkup(<KPIDashboard kpi={ENVELOPE} />);
    expect(html).toContain('data-testid="kpi-computed-at"');
    expect(html).toContain("Dihitung 13.26 WIB");
  });

  it("tanpa computed_at yang sah, pil kesegaran tidak dirender", () => {
    const html = renderToStaticMarkup(
      <KPIDashboard kpi={{ ...ENVELOPE, computed_at: null }} />
    );
    expect(html).not.toContain('data-testid="kpi-computed-at"');
  });
});
