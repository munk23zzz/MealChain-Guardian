// Kontrak halaman "Surplus & Limbah" (halaman sidebar acuan /surplus).
import { describe, expect, it } from "vitest";

import {
  SURPLUS_SOURCE_NOTE,
  allocationPlan,
  haversineKm,
  surplusSummary,
  wasteFacts,
} from "../lib/surplus";

const NODES = [
  { location: "Cianjur", region: "Jawa Barat", latitude: -6.8168, longitude: 107.1425, surplus_kg: 1400, shortage_kg: 0, status: "surplus" },
  { location: "Bogor", region: "Jawa Barat", latitude: -6.595, longitude: 106.8166, surplus_kg: 492, shortage_kg: 0, status: "surplus" },
  { location: "Jakarta", region: "DKI Jakarta", latitude: -6.2088, longitude: 106.8456, surplus_kg: 0, shortage_kg: 780, status: "shortage" },
  { location: "Bandung", region: "Jawa Barat", latitude: -6.9175, longitude: 107.6191, surplus_kg: 0, shortage_kg: 0, status: "balanced" },
  { location: "Surabaya", region: "Jawa Timur", latitude: -7.2575, longitude: 112.7521, surplus_kg: 0, shortage_kg: 12, status: "shortage" },
];

describe("surplusSummary", () => {
  it("menjumlahkan surplus/kekurangan dan menghitung lokasi", () => {
    const summary = surplusSummary(NODES);
    expect(summary).toMatchObject({
      surplusKg: 1892,
      surplusCount: 2,
      shortageKg: 792,
      shortageCount: 2,
      balancedCount: 1,
    });
  });

  it("tanpa surplus: nilainya null, bukan 0 (0 terbaca 'tidak ada data')", () => {
    const summary = surplusSummary([{ location: "X", shortage_kg: 5 }]);
    expect(summary.surplusKg).toBe(null);
    expect(summary.surplusCount).toBe(0);
    expect(summary.shortageKg).toBe(5);
  });

  it("masukan bukan array → ringkasan kosong yang jujur", () => {
    expect(surplusSummary(null)).toMatchObject({ surplusKg: null, surplusCount: 0, shortageKg: null });
  });
});

describe("haversineKm", () => {
  it("jarak Cianjur→Jakarta wajar (± 100 km)", () => {
    const km = haversineKm({ latitude: -6.8168, longitude: 107.1425 }, { latitude: -6.2088, longitude: 106.8456 });
    expect(km).toBeGreaterThan(60);
    expect(km).toBeLessThan(110);
  });

  it("koordinat tidak lengkap → null (tidak dikarang)", () => {
    expect(haversineKm({ latitude: -6.8 }, { latitude: -6.2, longitude: 106.8 })).toBe(null);
  });
});

describe("allocationPlan", () => {
  it("kebutuhan terbesar diisi surplus terbesar lebih dulu", () => {
    const plan = allocationPlan(NODES, 3);
    expect(plan[0]).toMatchObject({ from: "Cianjur", to: "Jakarta", kg: 780 });
    expect(plan[0].distanceKm).toBeGreaterThan(0);
    expect(plan[1]).toMatchObject({ from: "Cianjur", to: "Surabaya", kg: 12 });
    // Cianjur masih punya sisa 608 kg, Bogor belum terpakai
    expect(plan[2]).toBeUndefined();
  });

  it("sisa surplus dipakai lintas tujuan (tidak ada kg yang hilang)", () => {
    const plan = allocationPlan(
      [
        { location: "A", surplus_kg: 100, latitude: -6, longitude: 106 },
        { location: "B", surplus_kg: 50, latitude: -7, longitude: 107 },
        { location: "C", shortage_kg: 120, latitude: -6.5, longitude: 106.5 },
      ],
      5
    );
    expect(plan.map((row) => row.kg)).toEqual([100, 20]);
    expect(plan.map((row) => row.from)).toEqual(["A", "B"]);
  });

  it("tidak ada surplus atau tidak ada kekurangan → rencana kosong", () => {
    expect(allocationPlan([{ location: "A", shortage_kg: 10 }])).toEqual([]);
    expect(allocationPlan([{ location: "A", surplus_kg: 10 }])).toEqual([]);
  });
});

describe("bagian limbah", () => {
  it("ditulis '—' dengan alasan, bukan angka nol", () => {
    const facts = wasteFacts();
    expect(facts).toHaveLength(3);
    for (const fact of facts) {
      expect(fact.value).toBe("—");
      expect(fact.hint).toBeTruthy();
    }
  });

  it("catatan sumber menyebut endpoint dan keterbatasan", () => {
    expect(SURPLUS_SOURCE_NOTE).toContain("/balance/map");
    expect(SURPLUS_SOURCE_NOTE).toContain("limbah");
  });
});
