// Kontrak halaman "Pemasok" (halaman sidebar acuan /suppliers).
import { describe, expect, it } from "vitest";

import {
  SUPPLIER_SOURCE_NOTE,
  exclusionRows,
  reliabilityLabel,
  rosterMetrics,
  supplierRoster,
} from "../lib/suppliers-board";

const PAIRS = [
  { decisionId: "d1", decisionType: "regional_balance", commodity: "telur", supplier: { id: "s1", name: "Supplier A Cianjur", reliability_score: 0.8 } },
  { decisionId: "d2", decisionType: "regional_balance", commodity: "ayam", supplier: { id: "s1", name: "Supplier A Cianjur", reliability_score: 0.8 } },
  { decisionId: "d3", decisionType: "regional_balance", commodity: "telur", supplier: { id: "s2", name: "Supplier B Bogor", reliability_score: 0.65 } },
  { decisionId: "d4", decisionType: "supplier_exclusion", commodity: null, supplier: null },
];

describe("reliabilityLabel", () => {
  it("skor 0..1 jadi persen, kosong jadi '—'", () => {
    expect(reliabilityLabel(0.8)).toBe("80%");
    expect(reliabilityLabel("0.65")).toBe("65%");
    expect(reliabilityLabel(null)).toBe("—");
    expect(reliabilityLabel("bukan angka")).toBe("—");
  });
});

describe("supplierRoster", () => {
  it("mengelompokkan pemasok, menghitung keputusan + komoditasnya", () => {
    const roster = supplierRoster(PAIRS);
    expect(roster).toHaveLength(2);
    expect(roster[0]).toMatchObject({
      name: "Supplier A Cianjur",
      reliabilityLabel: "80%",
      decisions: 2,
      commodities: ["ayam", "telur"],
    });
    expect(roster[1]).toMatchObject({ name: "Supplier B Bogor", decisions: 1, commodities: ["telur"] });
  });

  it("keputusan tanpa pemasok dilewati, bukan jadi baris kosong", () => {
    expect(supplierRoster([{ decisionId: "x" }])).toEqual([]);
    expect(supplierRoster(null)).toEqual([]);
  });

  it("ringkasan: jumlah pemasok, rata-rata keandalan, total keputusan", () => {
    const metrics = rosterMetrics(supplierRoster(PAIRS));
    expect(metrics).toMatchObject({ suppliers: 2, totalDecisions: 3 });
    expect(metrics.avgReliabilityLabel).toBe("73%");
    expect(rosterMetrics([]).avgReliabilityLabel).toBe("—");
  });
});

describe("exclusionRows", () => {
  it("membaca register eksklusi dari endpoint", () => {
    const rows = exclusionRows([
      { id: "e1", supplier_name: "Supplier C Jakarta", reason: "dua kiriman suhu menyimpang", excluded_at: "2026-10-11T02:00:00Z", decision_id: "d9", status: "excluded" },
    ]);
    expect(rows[0]).toMatchObject({
      supplier: "Supplier C Jakarta",
      reason: "dua kiriman suhu menyimpang",
      decisionId: "d9",
      status: "excluded",
    });
  });

  it("daftar kosong → tidak ada baris (halaman menjelaskan keadaannya)", () => {
    expect(exclusionRows({ items: [], count: 0 })).toEqual([]);
    expect(exclusionRows(null)).toEqual([]);
  });

  it("catatan sumber menyebut keterbatasan endpoint", () => {
    expect(SUPPLIER_SOURCE_NOTE).toContain("belum punya endpoint daftar pemasok");
    expect(SUPPLIER_SOURCE_NOTE).toContain("/supplier-exclusions");
  });
});
