// Fase 2 redesign (Overview bento) — logika murni tile hero.
//
// Aturan yang dipegang: SEMUA angka dihitung dari data peta nyata dan nilai
// yang tidak tersedia ditulis `null` (ditampilkan "—"), BUKAN 0. Ini aturan
// proyek: tidak ada angka karangan di layar.
import { describe, expect, it } from "vitest";

import {
  demandCoveragePct,
  formatSignedKg,
  gapShareOfDemand,
  heroGap,
  networkTotals,
} from "../lib/overview-bento";
import type { BalanceMapLocation } from "../lib/overview-format";

const JAKARTA: BalanceMapLocation = {
  location: "Jakarta",
  status: "shortage",
  supply_kg: 300,
  demand_kg: 1080,
  shortage_kg: 780,
};
const CIANJUR: BalanceMapLocation = {
  location: "Cianjur",
  status: "surplus",
  supply_kg: 1400,
  demand_kg: 0,
  surplus_kg: 1400,
};
const BANDUNG: BalanceMapLocation = {
  location: "Bandung",
  status: "balanced",
  supply_kg: 400,
  demand_kg: 400,
};
const BOGOR: BalanceMapLocation = {
  location: "Bogor",
  status: "surplus",
  supply_kg: 800,
  demand_kg: 308,
  surplus_kg: 492,
};

describe("heroGap — tile hero Overview", () => {
  it("lokasi aktif shortage → selisih NEGATIF dan nama lokasi ikut", () => {
    const hero = heroGap([JAKARTA, CIANJUR], "Jakarta");
    expect(hero.scope).toBe("location");
    expect(hero.name).toBe("Jakarta");
    expect(hero.gapKg).toBe(-780);
    expect(hero.supplyKg).toBe(300);
    expect(hero.demandKg).toBe(1080);
    expect(hero.tone).toBe("shortage");
  });

  it("lokasi aktif surplus → selisih POSITIF", () => {
    const hero = heroGap([JAKARTA, CIANJUR], "Cianjur");
    expect(hero.scope).toBe("location");
    expect(hero.gapKg).toBe(1400);
    expect(hero.tone).toBe("surplus");
  });

  it("lokasi aktif seimbang → selisih 0 (bukan null)", () => {
    const hero = heroGap([BANDUNG], "Bandung");
    expect(hero.gapKg).toBe(0);
    expect(hero.tone).toBe("balanced");
  });

  it("tanpa lokasi aktif → lingkup JARINGAN: surplus dikurangi shortage", () => {
    const hero = heroGap([JAKARTA, CIANJUR, BOGOR, BANDUNG], null);
    expect(hero.scope).toBe("network");
    expect(hero.name).toBeNull();
    // 1400 + 492 - 780 = 1112
    expect(hero.gapKg).toBe(1112);
    expect(hero.tone).toBe("surplus");
  });

  it("lokasi aktif TIDAK ada di data → jatuh ke jaringan, bukan mengarang lokasi", () => {
    const hero = heroGap([JAKARTA, CIANJUR], "Surabaya");
    expect(hero.scope).toBe("network");
    expect(hero.name).toBeNull();
  });

  it("shortage_kg hilang → gapKg null (ditulis —), tone tetap jujur 'shortage'", () => {
    const hero = heroGap(
      [{ location: "Medan", status: "shortage", supply_kg: 200, demand_kg: 206 }],
      "Medan",
    );
    expect(hero.gapKg).toBeNull();
    expect(hero.tone).toBe("shortage");
    expect(hero.supplyKg).toBe(200);
  });

  it("status tak dikenal di jaringan → gapKg null (tidak dianggap 0)", () => {
    const hero = heroGap(
      [{ location: "X", status: "belum-tersedia" }, JAKARTA],
      null,
    );
    expect(hero.gapKg).toBeNull();
    expect(hero.tone).toBe("unknown");
  });

  it("daftar lokasi kosong → null semua, bukan 0", () => {
    const hero = heroGap([], null);
    expect(hero.scope).toBe("network");
    expect(hero.gapKg).toBeNull();
    expect(hero.supplyKg).toBeNull();
    expect(hero.demandKg).toBeNull();
    expect(hero.tone).toBe("unknown");
  });
});

describe("gapShareOfDemand — persentase selisih terhadap kebutuhan", () => {
  it("Jakarta 780 dari 1.080 kg → 72%", () => {
    expect(gapShareOfDemand(-780, 1080)).toBe(72);
  });

  it("selisih null atau kebutuhan 0/tidak diketahui → null, bukan 0%", () => {
    expect(gapShareOfDemand(null, 1080)).toBeNull();
    expect(gapShareOfDemand(-780, null)).toBeNull();
    expect(gapShareOfDemand(-780, 0)).toBeNull();
    expect(gapShareOfDemand(-780, -5)).toBeNull();
  });

  it("selisih kecil tidak dibulatkan jadi 0% palsu... tapi tetap angka apa adanya", () => {
    // 4/1000 = 0,4% → dibulatkan 0. Yang penting: nilainya bukan null.
    expect(gapShareOfDemand(-4, 1000)).toBe(0);
    expect(gapShareOfDemand(-5, 1000)).toBe(1);
  });
});

describe("formatSignedKg — angka hero bertanda", () => {
  it("negatif memakai tanda minus tipografis (U+2212), bukan hyphen", () => {
    expect(formatSignedKg(-780)).toBe("−780 kg");
    expect(formatSignedKg(-1400)).toBe("−1.400 kg");
  });

  it("positif diberi tanda + eksplisit", () => {
    expect(formatSignedKg(1400)).toBe("+1.400 kg");
  });

  it("nol ditulis polos tanpa tanda", () => {
    expect(formatSignedKg(0)).toBe("0 kg");
  });

  it("null → — (bukan 0 kg)", () => {
    expect(formatSignedKg(null)).toBe("—");
  });
});

describe("demandCoveragePct — pangsa pasokan terhadap kebutuhan", () => {
  it("pasokan 300 dari kebutuhan 1.080 kg → 28%", () => {
    expect(demandCoveragePct(300, 1080)).toBe(28);
  });

  it("pasokan melebihi kebutuhan tetap dilaporkan apa adanya (162%)", () => {
    expect(demandCoveragePct(2900, 1788)).toBe(162);
  });

  it("kebutuhan 0 / tidak diketahui → null (bukan 0% atau 100%)", () => {
    expect(demandCoveragePct(300, 0)).toBeNull();
    expect(demandCoveragePct(300, null)).toBeNull();
    expect(demandCoveragePct(null, 1080)).toBeNull();
  });
});

describe("networkTotals — pasokan & kebutuhan jaringan", () => {
  it("menjumlahkan pasokan dan kebutuhan semua lokasi", () => {
    const totals = networkTotals([JAKARTA, CIANJUR, BANDUNG, BOGOR]);
    expect(totals.supplyKg).toBe(2900);
    expect(totals.demandKg).toBe(1788);
  });

  it("satu nilai hilang → total null (fail-closed, bukan jumlah semu)", () => {
    const totals = networkTotals([JAKARTA, { location: "Medan", status: "shortage", supply_kg: 200 }]);
    expect(totals.supplyKg).toBe(500);
    expect(totals.demandKg).toBeNull();
  });

  it("daftar kosong → null (bukan 0 kg)", () => {
    const totals = networkTotals([]);
    expect(totals.supplyKg).toBeNull();
    expect(totals.demandKg).toBeNull();
  });
});
