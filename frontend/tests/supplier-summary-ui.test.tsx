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
  it("menampilkan lima angka dengan labelnya", () => {
    expect(html).toContain('class="summary-kpi-value">60<');
    expect(html).toContain('class="summary-kpi-value">82%<');
    expect(html).toContain('class="summary-kpi-value">4<');
    expect(html).toContain('class="summary-kpi-label">Pemasok<');
    expect(html).toContain("Keandalan di bawah 60%");
    expect(html).toContain("Tanpa stok layak hari ini");
    expect(html).toContain("Di luar jangkauan 150 km");
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
    expect(nol.match(/summary-kpi-item/g)).toHaveLength(5);
  });

  it("tanpa ambang jangkauan: empat angka saja", () => {
    const tanpa = renderToStaticMarkup(<SupplierSummary metrics={metrics()} reachKm={null} />);
    expect(tanpa.match(/summary-kpi-item/g)).toHaveLength(4);
    expect(tanpa).not.toContain("Di luar jangkauan");
  });

  it("loading menandai kartu sibuk, tanpa mengubah isi", () => {
    const sibuk = renderToStaticMarkup(
      <SupplierSummary metrics={metrics()} reachKm={150} loading />
    );
    expect(sibuk).toContain('aria-busy="true"');
    expect(sibuk).toContain("summary-kpi-value");
  });
});
