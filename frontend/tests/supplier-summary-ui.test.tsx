// Kontrak render kartu Ringkasan — KPI strip (29 Okt 2026).
//
// Bentuk yang dijaga:
//   1. satu baris angka besar + label kecil, TANPA tombol apa pun;
//   2. tidak ada sisa bentuk lama (tile sorotan, chip sebaran, kalimat "Perlu
//      dilihat", baris status, tombol reset);
//   3. angka 0 tetap dirender.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplierSummary from "../components/SupplierSummary";
import type { DirectoryMetrics } from "../lib/suppliers-board";

function metrics(over: Partial<DirectoryMetrics> = {}): DirectoryMetrics {
  return {
    suppliers: 60,
    avgReliability: 0.82,
    avgReliabilityLabel: "82%",
    lowReliability: 4,
    excluded: 1,
    withCoordinates: 60,
    outOfReach: 30,
    unknownDistance: 0,
    shipping: 51,
    ...over,
  };
}

const html = renderToStaticMarkup(
  <SupplierSummary metrics={metrics()} reachKm={150} />
);

describe("kartu Ringkasan (KPI strip)", () => {
  it("menampilkan empat angka dengan labelnya", () => {
    // S2 (29 Okt 2026): angka yang dipromosikan = pemasok DALAM jangkauan
    // (60 pemasok − 30 di luar = 30), bukan total yang sudah jadi pil kepala.
    expect(html).toContain('class="summary-kpi-value">30<');
    expect(html).toContain("Pemasok dalam jangkauan 150 km");
    expect(html).toContain('class="summary-kpi-value">82%<');
    expect(html).toContain('class="summary-kpi-value">4<');
    expect(html).toContain("Keandalan di bawah 60%");
    expect(html).toContain("Tanpa stok layak hari ini");
  });

  it("hanya angka pertama yang dipromosikan", () => {
    expect(html.match(/data-lead="true"/g)).toHaveLength(1);
    expect(html).toMatch(/<li class="summary-kpi-item" data-tone="plain" data-lead="true">/);
  });

  it("tidak lagi menampilkan kolom 'Di luar jangkauan'", () => {
    expect(html).not.toContain("Di luar jangkauan");
  });

  it("tidak punya satu pun tombol", () => {
    expect(html).not.toContain("<button");
    expect(html).not.toContain("aria-pressed");
  });

  it("tidak menyisakan bentuk lama", () => {
    expect(html).not.toContain("summary-lihat");
    expect(html).not.toContain("summary-item");
    expect(html).not.toContain("summary-sebaran");
    expect(html).not.toContain("Perlu dilihat");
    expect(html).not.toContain('role="status"');
    expect(html).not.toContain("summary-reset");
  });

  it("angka nol tetap dirender", () => {
    const nol = renderToStaticMarkup(
      <SupplierSummary metrics={metrics({ lowReliability: 0, outOfReach: 0 })} reachKm={150} />
    );
    expect(nol).toContain('data-tone="plain"');
    expect(nol.match(/summary-kpi-item/g)).toHaveLength(4);
  });

  it("tanpa ambang jangkauan: tetap empat angka, yang dipromosikan = pemasok terdaftar", () => {
    const tanpa = renderToStaticMarkup(<SupplierSummary metrics={metrics()} reachKm={null} />);
    expect(tanpa.match(/summary-kpi-item/g)).toHaveLength(4);
    expect(tanpa).toContain("Pemasok terdaftar");
    expect(tanpa).toContain('class="summary-kpi-value">60<');
  });

  it("loading menandai kartu sibuk, tanpa mengubah isi", () => {
    const sibuk = renderToStaticMarkup(
      <SupplierSummary metrics={metrics()} reachKm={150} loading />
    );
    expect(sibuk).toContain('aria-busy="true"');
    expect(sibuk).toContain("summary-kpi-value");
  });
});
