// Rencana alokasi surplus dari server (20 Okt 2026).
//
// Regresi yang dipaku: panel "Rencana alokasi surplus" dulu merakit pasangannya
// dari /balance/map, yang untuk peran SPPG hanya berisi lokasinya sendiri —
// jadi SELALU kosong di satu-satunya peran yang boleh membuka halaman Surplus &
// Limbah (terukur: Kepala Bandung melihat "0 lokasi surplus"). Sekarang baris
// rencana datang dari GET /surplus/allocations (lintas lokasi), dan pesan kosong
// menyebut SEBABNYA.
import { describe, expect, it } from "vitest";

import { alasanTanpaRencana, planFromServer } from "../lib/surplus";

const PAYLOAD = {
  commodity: "wortel",
  available: true,
  reason: null,
  pairs: [
    { from: "Cianjur", to: "Bogor", kg: 204.83, distance_km: 90, region: "Jawa Barat", cost_share_pct: 3.2 },
    { from: "Jakarta", to: "Bandung", kg: 189.17, distance_km: 118, region: "Jawa Barat", cost_share_pct: 4.1 },
  ],
};

describe("planFromServer", () => {
  it("membaca pasangan dari server apa adanya", () => {
    const plan = planFromServer(PAYLOAD);
    expect(plan.available).toBe(true);
    expect(plan.reason).toBeNull();
    expect(plan.rows).toEqual([
      { from: "Cianjur", to: "Bogor", kg: 204.83, distanceKm: 90, region: "Jawa Barat", costSharePct: 3.2 },
      { from: "Jakarta", to: "Bandung", kg: 189.17, distanceKm: 118, region: "Jawa Barat", costSharePct: 4.1 },
    ]);
  });

  it("baris tanpa tujuan, tanpa sumber, atau tanpa kg dibuang", () => {
    const plan = planFromServer({
      available: true,
      pairs: [
        { from: "", to: "Bogor", kg: 10 },
        { from: "Cianjur", to: "", kg: 10 },
        { from: "Cianjur", to: "Bogor", kg: 0 },
        { from: "Cianjur", to: "Bogor", kg: 12 },
      ],
    });
    expect(plan.rows).toHaveLength(1);
    expect(plan.rows[0].kg).toBe(12);
  });

  it("menghormati limit dan jarak yang tidak ada tetap null", () => {
    const plan = planFromServer(
      {
        available: true,
        pairs: [
          { from: "A", to: "B", kg: 5, distance_km: null, region: null },
          { from: "A", to: "C", kg: 5, distance_km: 40, region: "X" },
        ],
      },
      1
    );
    expect(plan.rows).toHaveLength(1);
    expect(plan.rows[0].distanceKm).toBeNull();
    expect(plan.rows[0].region).toBeNull();
  });

  it("server bilang tidak tersedia → available false, sebab dibawa", () => {
    const plan = planFromServer({
      available: false,
      reason: "tidak_ada_kekurangan_terukur",
      pairs: [],
    });
    expect(plan.available).toBe(false);
    expect(plan.reason).toBe("tidak_ada_kekurangan_terukur");
    expect(plan.rows).toEqual([]);
  });

  it("membawa ambang 150 kg dari server", () => {
    const plan = planFromServer({ available: false, reason: "surplus_di_bawah_ambang", min_surplus_kg: 150, pairs: [] });
    expect(plan.minSurplusKg).toBe(150);
    expect(planFromServer({ pairs: [] }).minSurplusKg).toBeNull();
  });

  it("payload rusak/kosong tidak menghasilkan pasangan karangan", () => {
    expect(planFromServer(null).rows).toEqual([]);
    expect(planFromServer({ pairs: "bukan-array" }).rows).toEqual([]);
  });
});

describe("alasanTanpaRencana", () => {
  it("membedakan sebab: sisi tidak tercatat, tanpa surplus, tanpa kekurangan", () => {
    expect(alasanTanpaRencana("tidak_ada_sisi_terukur")).toContain("Belum ada catatan");
    expect(alasanTanpaRencana("tidak_ada_surplus_terukur")).toContain("Tidak ada lokasi bersurplus");
    expect(alasanTanpaRencana("tidak_ada_kekurangan_terukur")).toContain("Tidak ada lokasi");
  });

  it("surplus di bawah 150 kg dijelaskan, bukan 'tidak ada pasangan'", () => {
    expect(alasanTanpaRencana("surplus_di_bawah_ambang")).toContain("150 kg");
  });

  it("sebab yang tidak dikenal tetap memberi kalimat, bukan kosong", () => {
    expect(alasanTanpaRencana(null)).toContain("Tidak ada pasangan");
    expect(alasanTanpaRencana("sebab-aneh")).toContain("Tidak ada pasangan");
  });
});
