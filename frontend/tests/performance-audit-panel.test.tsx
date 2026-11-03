// Panel "Audit performa" (tab Performance & Audit).
//
// Kontrak yang dikunci di sini:
//   1. Jejak perhitungan (metode agregasi, versi rumus SDC, jendela simpan,
//      waktu hitung WIB) dibaca dari amplop `GET /kpi` — bukan angka tetap.
//   2. Tabel cakupan menyebut keadaan + jumlah sampel + alasan `no_data`
//      setiap metrik; "belum ada data" tidak pernah diganti nol.
//
// 29 Okt 2026: KPI "Effective Price per Accepted Kg" dihapus dari kontrak atas
// keputusan pemilik, jadi bagian "Pengiriman & penyelesaian" (yang seluruhnya
// bersumber dari `facts` metrik itu) ikut dilepas. Tes di bawah tidak lagi
// menguji blok tersebut karena permukaannya sudah tidak ada.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import PerformanceAuditPanel from "../components/PerformanceAuditPanel";

const ENVELOPE = {
  period: {
    start: "2026-10-29T00:00:00+00:00",
    end: "2026-10-29T12:00:00+00:00",
  },
  scope: { location_id: "loc-1", role: "sppg_head" },
  computed_at: "2026-10-29T06:26:39+00:00",
  data_source: "live_aggregate",
  data_mode: "operational",
  method_version: "kpi-2026.10.28",
  metrics: [
    {
      name: "Meal Continuity Rate",
      unit: "percent",
      state: "no_data",
      value: null,
      reason: "belum ada rencana menu pada periode ini",
      sample_count: 0,
      coverage: null,
    },
    {
      name: "Safe Delivered Cost",
      unit: "IDR",
      state: "available",
      value: "42000.00",
      reason: null,
      sample_count: 4,
      coverage: "1.00",
      facts: {
        invoice_unit_price_mean_idr: "40000.00",
        invoice_sample_count: 4,
        formula_version: "sdc-2026.10.29",
        storage_default_days: "1",
        storage_default_basis: "asumsi_siklus_harian",
      },
    },
  ],
};

describe("PerformanceAuditPanel", () => {
  it("menampilkan jejak perhitungan dari amplop, bukan angka tetap", () => {
    const html = renderToStaticMarkup(<PerformanceAuditPanel kpi={ENVELOPE} />);
    expect(html).toContain('data-testid="audit-method-version"');
    expect(html).toContain("kpi-2026.10.28");
    expect(html).toContain("sdc-2026.10.29");
    expect(html).toContain("1 hari (asumsi siklus harian SPPG)");
    expect(html).toContain("13.26 WIB");
  });

  it("cakupan dibaca sebagai kalimat, angkanya dari server", () => {
    const html = renderToStaticMarkup(<PerformanceAuditPanel kpi={ENVELOPE} />);
    expect(html).toContain("100% dari populasi yang bisa dinilai");
    expect(html).toContain("tidak dianggap nol");
  });

  it("alasan no_data ikut tampil, bukan angka nol", () => {
    const html = renderToStaticMarkup(<PerformanceAuditPanel kpi={ENVELOPE} />);
    expect(html).toContain("belum ada rencana menu pada periode ini");
    expect(html).toContain("Belum ada data");
  });

  it("tidak lagi merender rincian pengiriman milik metrik yang dihapus", () => {
    const html = renderToStaticMarkup(<PerformanceAuditPanel kpi={ENVELOPE} />);
    expect(html).not.toContain('data-testid="audit-delivery"');
    expect(html).not.toContain("harga efektif");
  });
});
