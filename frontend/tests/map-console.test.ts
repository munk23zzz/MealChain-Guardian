// Logika murni peta (arah Roy 2026-10-11): nada & label pin + bar telemetri
// node. Tanpa DOM supaya bisa diuji langsung.
import { describe, expect, it } from "vitest";

import { nodeGauges, pinLabel, pinTone } from "../lib/map-console";

const CIANJUR = { location: "Cianjur", region: "Jawa Barat", status: "surplus", surplus_kg: 1400, shortage_kg: 0 };
const JAKARTA = { location: "Jakarta", region: "DKI Jakarta", status: "shortage", surplus_kg: 0, shortage_kg: 780 };
const BOGOR = { location: "Bogor", region: "Jawa Barat", status: "balanced", surplus_kg: 0, shortage_kg: 0 };

describe("peta acuan — pin", () => {
  it("memetakan status ke nada pin", () => {
    expect(pinTone("surplus")).toBe("surplus");
    expect(pinTone("shortage")).toBe("shortage");
    expect(pinTone("balanced")).toBe("balanced");
    expect(pinTone(undefined)).toBe("unknown");
    expect(pinTone("entah")).toBe("unknown");
  });

  it("label pin = nama + selisih (tanpa angka karangan)", () => {
    expect(pinLabel(CIANJUR)).toBe("Cianjur +1.400 kg");
    expect(pinLabel(JAKARTA)).toBe("Jakarta −780 kg");
    expect(pinLabel(BOGOR)).toBe("Bogor seimbang");
    // Angka tidak tersedia → jangan menulis 0 atau tebakan.
    expect(pinLabel({ location: "Medan", status: "surplus" })).toBe("Medan");
    expect(pinLabel({ location: "Malang", status: "entah" })).toBe("Malang");
  });
});

describe("peta acuan — bar telemetri node", () => {
  it("proporsi bar memakai dua angka yang ada (bukan skala karangan)", () => {
    expect(nodeGauges({ location: "Cianjur", status: "surplus", supply_kg: 1000, demand_kg: 800 })).toEqual({
      supply: { value: 1000, share: 100 },
      demand: { value: 800, share: 80 },
    });
    expect(nodeGauges({ location: "Malang", status: "shortage", supply_kg: 250, demand_kg: 1000 })).toEqual({
      supply: { value: 250, share: 25 },
      demand: { value: 1000, share: 100 },
    });
  });

  it("angka kosong tetap kosong (share 0, bukan 100%)", () => {
    expect(nodeGauges({ location: "Medan", status: "balanced" })).toEqual({
      supply: { value: null, share: 0 },
      demand: { value: null, share: 0 },
    });
    expect(nodeGauges({ location: "Medan", status: "balanced", supply_kg: 0, demand_kg: 0 })).toEqual({
      supply: { value: 0, share: 0 },
      demand: { value: 0, share: 0 },
    });
  });
});
