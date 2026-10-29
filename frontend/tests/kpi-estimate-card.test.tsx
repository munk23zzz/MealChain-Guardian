// KPI × penerimaan (demo "kasus pengiriman", 29 Okt 2026).
//
// Backend sudah lama mengirim blok `estimate` (proyeksi porsi dari bahan
// diterima, estimasi susut dari kesegaran), tetapi TIDAK ADA komponen yang
// membacanya — `estimateLine()` hanya dipakai tesnya sendiri. Akibatnya
// menyetujui penerimaan mengubah angka di server tanpa satu pun perubahan di
// layar: "penulis tanpa pembaca".
//
// Kontrak sekarang:
// - KARTU tetap BERSIH tanpa baris estimasi. Keputusan pemilik 29 Okt 2026
//   ("baris estimasi tidak lagi dirender di kartu") tetap berlaku — lihat
//   `tests/kpi-provenance.test.tsx`. Yang ditambahkan bukan mengembalikan
//   lipatan itu.
// - PANEL PENJELASAN (satu metrik, muncul saat kartu diklik) menyebut
//   estimasinya: angka proyeksi bila ada, atau alasannya bila belum. Di situlah
//   pembaca mencari "lalu angka apa yang bergerak saat barang diterima".
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import KPIDashboard from "../components/KPIDashboard";
import KpiDetailPanel from "../components/KpiDetailPanel";

function metrik(extra: Record<string, unknown> = {}) {
  return {
    name: "Meal Continuity Rate",
    unit: "percent",
    state: "no_data",
    value: null,
    reason: "tidak ada menu plan fakta operasional pada periode ini",
    sample_count: 0,
    coverage: null,
    previous_value: null,
    trend: null,
    provenance: {
      source: "menu_plans.plan_date, delivery_events.delivered_portions",
      evidence_kind: "derived",
    },
    ...extra,
  };
}

const ESTIMASI_TERSEDIA = {
  state: "available",
  value: "5120.00",
  unit: "porsi",
  reason: null,
  definition:
    "Proyeksi porsi yang bisa disajikan dari BAHAN YANG DITERIMA (kg ÷ gram per porsi).",
  method: "Σ (kg_diterima × 1000 ÷ gram_per_porsi) per komoditas",
  coverage: "1.00",
};

const ESTIMASI_KOSONG = {
  state: "no_data",
  value: null,
  unit: null,
  reason: "tidak ada penerimaan disetujui pada periode ini",
  definition: null,
  method: null,
  coverage: null,
};

describe("kartu KPI tetap bersih dari baris estimasi", () => {
  it("estimasi tersedia TIDAK menambah baris di kartu", () => {
    const html = renderToStaticMarkup(
      <KPIDashboard kpi={{ metrics: [metrik({ estimate: ESTIMASI_TERSEDIA })] }} />
    );
    expect(html).not.toContain('data-testid="kpi-estimate"');
  });

  it("metrik tanpa blok estimate sama sekali tetap aman", () => {
    const html = renderToStaticMarkup(<KPIDashboard kpi={{ metrics: [metrik()] }} />);
    expect(html).not.toContain('data-testid="kpi-estimate"');
  });
});

describe("panel penjelasan KPI menyebut estimasi penerimaan", () => {
  it("estimasi tersedia → angka + definisinya", () => {
    const html = renderToStaticMarkup(
      <KpiDetailPanel
        metric={metrik({ estimate: ESTIMASI_TERSEDIA })}
        onClose={() => {}}
      />
    );
    expect(html).toContain('data-testid="kpi-detail-estimate"');
    expect(html).toContain("estimasi 5.120 porsi");
    expect(html).toContain("BAHAN YANG DITERIMA");
  });

  it("estimasi kosong → ALASAN dari server, bukan angka 0", () => {
    const html = renderToStaticMarkup(
      <KpiDetailPanel
        metric={metrik({ estimate: ESTIMASI_KOSONG })}
        onClose={() => {}}
      />
    );
    expect(html).toContain('data-testid="kpi-detail-estimate"');
    expect(html).toContain("tidak ada penerimaan disetujui pada periode ini");
    expect(html).not.toMatch(/estimasi 0\b/);
  });

  it("metrik tanpa blok estimate tidak memunculkan blok estimasi", () => {
    const html = renderToStaticMarkup(
      <KpiDetailPanel metric={metrik()} onClose={() => {}} />
    );
    expect(html).not.toContain('data-testid="kpi-detail-estimate"');
  });
});
