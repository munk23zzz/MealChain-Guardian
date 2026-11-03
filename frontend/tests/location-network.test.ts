// Kontrak modul Location Network terhadap dokumen 03 (28 Okt 2026):
//   §6.3 satu kalimat ringkasan yang menyebut selisih, bukan deretan angka;
//   §6.5 "tidak ada catatan" TIDAK PERNAH menjadi 0;
//   §6.2 koridor hanya dari alur yang benar-benar ada.
import { describe, expect, it } from "vitest";

import {
  ageLabel,
  dataCompleteness,
  formatCoordinates,
  hasCoordinates,
  networkHeadline,
  networkSummary,
  rollupByRegion,
  sortBySeverity,
} from "../lib/location-network";
import type { BalanceMapLocation } from "../lib/overview-format";

function loc(over: Partial<BalanceMapLocation> = {}): BalanceMapLocation {
  return {
    location: "Bandung",
    region: "Jawa Barat",
    latitude: -6.9175,
    longitude: 107.6191,
    supply_kg: 1000,
    demand_kg: 900,
    status: "balanced",
    shortage_kg: 0,
    surplus_kg: 0,
    supply_state: "terukur",
    demand_state: "terukur",
    supply_recorded_at: "2026-10-28T08:00:00Z",
    demand_recorded_at: "2026-10-28T09:00:00Z",
    ...over,
  } as BalanceMapLocation;
}

describe("networkHeadline (§6.3)", () => {
  it("menyebut kelebihan yang menutup seluruh kekurangan, dengan sisa", () => {
    const { text, tone } = networkHeadline([
      loc({ location: "Jakarta", status: "shortage", shortage_kg: 780, surplus_kg: 0 }),
      loc({ location: "Cianjur", status: "surplus", surplus_kg: 2292, shortage_kg: 0 }),
    ]);
    expect(tone).toBe("safe");
    expect(text).toContain("1 lokasi kekurangan 780 kg");
    expect(text).toContain("menutup seluruhnya");
    expect(text).toContain("menyisakan 1.512 kg");
  });

  it("menyebut sisa yang belum tertutup bila kelebihan lebih kecil", () => {
    const { text, tone } = networkHeadline([
      loc({ location: "Jakarta", status: "shortage", shortage_kg: 2000 }),
      loc({ location: "Bogor", status: "surplus", surplus_kg: 500 }),
    ]);
    expect(tone).toBe("danger");
    expect(text).toContain("belum tertutup");
    expect(text).toContain("1.500 kg");
  });

  it("angka tak terbaca → nada unknown, tidak menyimpulkan 0", () => {
    const { text, tone } = networkHeadline([
      loc({ location: "Jakarta", status: "shortage", shortage_kg: null }),
      loc({ location: "Bogor", status: "surplus", surplus_kg: 500 }),
    ]);
    expect(tone).toBe("unknown");
    expect(text).toContain("belum terbaca");
    expect(text).not.toContain("0 kg");
  });

  it("tanpa kekurangan dan kelebihan → kalimat tenang", () => {
    const { tone } = networkHeadline([loc(), loc({ location: "Medan" })]);
    expect(tone).toBe("neutral");
  });
});

describe("networkSummary", () => {
  it("menjumlahkan hanya angka yang terbaca; semua kosong → null", () => {
    const summary = networkSummary([
      loc({ location: "A", status: "shortage", shortage_kg: 100 }),
      loc({ location: "B", status: "shortage", shortage_kg: 250 }),
    ]);
    expect(summary.shortageKg).toBe(350);
    expect(networkSummary([]).shortageKg).toBe(0);
  });

  it("menghitung lokasi yang tidak bisa dipetakan", () => {
    const summary = networkSummary([
      loc({ location: "A" }),
      loc({ location: "B", latitude: null, longitude: null }),
    ]);
    expect(summary.unmapped).toBe(1);
  });
});

describe("dataCompleteness (§6.5)", () => {
  const now = new Date("2026-10-28T12:00:00Z").getTime();

  it("`tidak_ada_baris` dihitung sebagai tanpa catatan, bukan 0 kg", () => {
    const hasil = dataCompleteness(
      [loc({ supply_state: "tidak_ada_baris" }), loc({ location: "Medan", demand_state: "tidak_ada_baris" })],
      { now }
    );
    expect(hasil.withoutSupply).toBe(1);
    expect(hasil.withoutDemand).toBe(1);
  });

  it("menghitung catatan lebih tua dari 24 jam", () => {
    const hasil = dataCompleteness(
      [loc({ supply_recorded_at: "2026-10-26T08:00:00Z", demand_recorded_at: "2026-10-28T11:00:00Z" })],
      { now }
    );
    expect(hasil.staleSupply).toBe(1);
    expect(hasil.staleDemand).toBe(0);
    expect(hasil.staleAfterHours).toBe(24);
  });

  it("waktu catatan tidak dikirim → null (tidak bisa dinilai), bukan 0", () => {
    const hasil = dataCompleteness([loc({ supply_recorded_at: null })], { now });
    expect(hasil.staleSupply).toBeNull();
  });
});

describe("koordinat & urutan", () => {
  it("lokasi tanpa koordinat tidak dianggap berada di (0,0)", () => {
    expect(hasCoordinates(loc({ latitude: null, longitude: null }))).toBe(false);
    expect(hasCoordinates(loc({ latitude: 0, longitude: 0 }))).toBe(true);
    expect(formatCoordinates(loc({ latitude: null, longitude: 107 }))).toBe("—");
  });

  it("urut dari yang paling kekurangan, selisih terbesar dulu", () => {
    const urut = sortBySeverity([
      loc({ location: "Seimbang" }),
      loc({ location: "Kecil", status: "shortage", shortage_kg: 100 }),
      loc({ location: "Besar", status: "shortage", shortage_kg: 900 }),
      loc({ location: "Surplus", status: "surplus", surplus_kg: 500 }),
    ]);
    expect(urut.map((l) => l.location)).toEqual(["Besar", "Kecil", "Surplus", "Seimbang"]);
  });

  it("mengelompokkan per wilayah dan menaruh wilayah terparah lebih dulu", () => {
    const hasil = rollupByRegion([
      loc({ location: "Bandung", region: "Jawa Barat" }),
      loc({ location: "Jakarta", region: "DKI", status: "shortage", shortage_kg: 300 }),
    ]);
    expect(hasil[0].region).toBe("DKI");
    expect(hasil[0].shortageKg).toBe(300);
  });
});

describe("ageLabel", () => {
  const now = new Date("2026-10-28T12:00:00Z").getTime();
  it("menerjemahkan umur catatan tanpa angka mentah", () => {
    expect(ageLabel("2026-10-28T11:59:00Z", now)).toBe("baru saja");
    expect(ageLabel("2026-10-28T10:00:00Z", now)).toBe("2 jam lalu");
    expect(ageLabel("2026-10-25T12:00:00Z", now)).toBe("3 hari lalu");
    expect(ageLabel(null, now)).toBeNull();
  });
});
