import { describe, expect, it } from "vitest";

import {
  buildLocationBalanceRows,
  formatCoverage,
  formatSignedKg,
  locationBalanceSummary,
  locationStatusLabel,
  sortLocationBalanceRows,
} from "../lib/location-balance";

const LOKASI = [
  {
    location: "Surabaya",
    status: "shortage",
    demand_kg: 1000,
    supply_kg: 988,
    shortage_kg: 12,
    surplus_kg: 0,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Jakarta",
    status: "shortage",
    demand_kg: 1000,
    supply_kg: 220,
    shortage_kg: 780,
    surplus_kg: 0,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Cianjur",
    status: "surplus",
    demand_kg: 400,
    supply_kg: 1085,
    shortage_kg: 0,
    surplus_kg: 685,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Bandung",
    status: "balanced",
    demand_kg: 500,
    supply_kg: 500,
    shortage_kg: 0,
    surplus_kg: 0,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Semarang",
    status: "balanced",
    demand_kg: "",
    supply_kg: 200,
    demand_state: "tidak_ada_baris",
    supply_state: "terukur",
  },
  {
    location: "Bogor",
    status: "balanced",
    demand_kg: 0,
    supply_kg: 300,
    demand_state: "terukur",
    supply_state: "terukur",
  },
  {
    location: "Medan",
    status: "balanced",
    demand_kg: 100,
    supply_kg: null,
    demand_state: "terukur",
    supply_state: "tidak_ada_baris",
  },
];

describe("keseimbangan pasokan per lokasi", () => {
  it("menghitung cakupan dan selisih dari pasokan vs kebutuhan", () => {
    const rows = buildLocationBalanceRows(LOKASI);
    const jakarta = rows.find((row) => row.location === "Jakarta")!;
    expect(jakarta.coverage).toBeCloseTo(0.22);
    expect(jakarta.gapKg).toBe(-780);
    expect(jakarta.status).toBe("shortage");
    expect(jakarta.tone).toBe("danger");

    const surabaya = rows.find((row) => row.location === "Surabaya")!;
    expect(surabaya.gapKg).toBe(-12);
    expect(surabaya.tone).toBe("warning");

    const cianjur = rows.find((row) => row.location === "Cianjur")!;
    expect(cianjur.gapKg).toBe(685);
    expect(cianjur.status).toBe("surplus");
    expect(cianjur.tone).toBe("safe");

    const bandung = rows.find((row) => row.location === "Bandung")!;
    expect(bandung.gapKg).toBe(0);
    expect(bandung.status).toBe("balanced");
  });

  it("tidak mengubah data yang tidak tercatat menjadi nol", () => {
    const rows = buildLocationBalanceRows(LOKASI);
    const semarang = rows.find((row) => row.location === "Semarang")!;
    expect(semarang.demandKg).toBeNull();
    expect(semarang.coverage).toBeNull();
    expect(semarang.gapKg).toBeNull();
    expect(semarang.dataState).toBe("tanpa_data");
    expect(locationStatusLabel(semarang)).toBe("kebutuhan belum tercatat");

    const bogor = rows.find((row) => row.location === "Bogor")!;
    expect(bogor.dataState).toBe("tanpa_kebutuhan");
    expect(bogor.coverage).toBeNull();

    const medan = rows.find((row) => row.location === "Medan")!;
    expect(medan.supplyKg).toBeNull();
    expect(medan.gapKg).toBeNull();
    expect(locationStatusLabel(medan)).toBe("pasokan belum tercatat");
  });

  it("mengurutkan kekurangan terbesar lebih dulu, data tak terukur di akhir", () => {
    const rows = sortLocationBalanceRows(buildLocationBalanceRows(LOKASI));
    expect(rows.slice(0, 4).map((row) => row.location)).toEqual([
      "Jakarta",
      "Surabaya",
      "Bandung",
      "Cianjur",
    ]);
    expect(rows.slice(4).every((row) => row.gapKg === null)).toBe(true);
  });

  it("ringkasan hanya menghitung lokasi yang benar-benar terukur", () => {
    const rows = sortLocationBalanceRows(buildLocationBalanceRows(LOKASI));
    const ringkas = locationBalanceSummary(rows);
    expect(ringkas.measured).toBe(4);
    expect(ringkas.shortage).toBe(2);
    expect(ringkas.worst?.location).toBe("Jakarta");
  });

  it("format angka sama dengan grafik SPPG", () => {
    expect(formatSignedKg(-780)).toBe("−780 kg");
    expect(formatSignedKg(685)).toBe("+685 kg");
    expect(formatCoverage(0.22)).toBe("22%");
  });
});
