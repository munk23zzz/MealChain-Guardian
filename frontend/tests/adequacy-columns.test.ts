// Model kolom bar vertikal "Kecukupan pasokan" (28 Okt 2026).
//
// Yang dipaku: urutan kolom, skala bersama, tinggi 0 hanya untuk kg 0, dan
// baris tanpa kebutuhan terukur TIDAK pernah muncul sebagai kolom 0%.
import { describe, expect, it } from "vitest";

import {
  columnFillPct,
  columnMissingPct,
  columnOverflow,
  commodityColumns,
  locationColumns,
} from "../lib/adequacy-columns";
import { buildAdequacyRows, type CommodityAdequacy } from "../lib/supply-adequacy";

const NOW = new Date("2026-10-20T12:00:00Z");

function batch(commodity: string, kg: number, hari: number) {
  return {
    location: "Jakarta",
    commodity,
    quantity_kg: kg,
    safety_status: "pass",
    quarantine_status: "none",
    usable_until: new Date(NOW.getTime() + hari * 86_400_000).toISOString(),
  };
}

function mapFor(commodity: string, demand: number, supply: number) {
  return [
    {
      location: "Jakarta",
      demand_kg: demand,
      supply_kg: supply,
      demand_state: "terukur",
      status: demand > supply ? "shortage" : "surplus",
    },
  ];
}

function rows(): CommodityAdequacy[] {
  return buildAdequacyRows({
    commodities: ["telur", "ayam", "beras", "wortel"],
    byCommodity: {
      // telur: kebutuhan 1.080, batch layak 800 → kurang
      telur: mapFor("telur", 1080, 800),
      // ayam: kebutuhan 0 → tidak ada kebutuhan
      ayam: mapFor("ayam", 0, 0),
      // beras: kebutuhan 1.000, batch 1.200 → lebih
      beras: mapFor("beras", 1000, 1200),
      // wortel: tidak punya baris di peta → belum tercatat
      wortel: [],
    } as never,
    batches: [
      batch("telur", 800, 5),
      batch("beras", 1200, 5),
    ],
    location: "Jakarta",
    now: NOW,
  });
}

describe("commodityColumns", () => {
  it("satu kolom per komoditas, urut sesuai lensa (terburuk dulu)", () => {
    const v = commodityColumns(rows(), "quantity");
    expect(v.columns.map((c) => c.key)).toHaveLength(4);
    // telur kurang (-280), beras lebih (+200): yang kurang di kiri.
    expect(v.columns[0].key).toBe("telur");
    expect(v.columns[0].gap).toBe("−280 kg");
    expect(v.columns[0].coverage).toBe("74%");
  });

  it("kolom membawa segmen batch layak, bukan supply_kg tercatat", () => {
    const v = commodityColumns(rows(), "quantity");
    const telur = v.columns.find((c) => c.key === "telur")!;
    expect(telur.segments).toEqual([{ tone: "fresh", kg: 800 }]);
    expect(telur.note).toBe("800 kg layak");
    expect(telur.demandKg).toBe(1080);
    expect(telur.demandLabel).toBe("kebutuhan 1.080 kg");
  });

  it("baris tanpa kebutuhan terukur: cakupan '—', tanpa segmen, di belakang", () => {
    const v = commodityColumns(rows(), "quantity");
    const wortel = v.columns.find((c) => c.key === "wortel")!;
    expect(wortel.coverage).toBe("—");
    expect(wortel.segments).toEqual([]);
    expect(wortel.demandKg).toBeNull();
    expect(v.columns[v.columns.length - 1].key).toBe("wortel");
  });

  it("tinggi batang = stok dibagi kebutuhan kolom itu sendiri (sama dengan angkanya)", () => {
    const v = commodityColumns(rows(), "quantity");
    const telur = v.columns.find((c) => c.key === "telur")!;
    // 800 kg layak / 1.080 kg kebutuhan = 74% — persis angka cakupannya.
    expect(columnFillPct(telur)).toBeCloseTo(74.07, 1);
    expect(telur.coverage).toBe("74%");
  });

  it("komoditas berkebutuhan kecil TIDAK jadi tonggak pendek hanya karena kg-nya kecil", () => {
    const v = commodityColumns(rows(), "quantity");
    const beras = v.columns.find((c) => c.key === "beras")!; // 1.200 / 1.000 = 120%
    // Batang mentok 100% dan ditandai "lebih", bukan digambar 94% dari skala kg.
    expect(columnFillPct(beras)).toBe(100);
    expect(columnOverflow(beras)).toBe(true);
    expect(beras.coverage).toBe("120%");
  });

  it("tanpa kebutuhan terukur tidak ada batang (bukan 100% mengarang)", () => {
    const v = commodityColumns(rows(), "quantity");
    const wortel = v.columns.find((c) => c.key === "wortel")!;
    expect(columnFillPct(wortel)).toBe(0);
    expect(columnOverflow(wortel)).toBe(false);
  });

  it("lensa kesegaran mengubah label dan angka, bukan jumlah segmen", () => {
    const kuantitas = commodityColumns(rows(), "quantity");
    const segar = commodityColumns(rows(), "freshness");
    expect(segar.columns[0].coverageLabel).toBe("segar");
    expect(kuantitas.columns[0].coverageLabel).toBe("cakupan");
    expect(segar.columns.map((c) => c.segments.length)).toEqual(
      kuantitas.columns.map((c) => c.segments.length)
    );
  });

  it("aria-label selalu lengkap dan tanpa NaN", () => {
    const v = commodityColumns(rows(), "quantity");
    for (const c of v.columns) {
      expect(c.aria).not.toMatch(/NaN|undefined/);
      expect(c.aria).toContain(c.label);
    }
  });

  it("tanpa baris sama sekali: kolom kosong, bukan lemparan", () => {
    expect(commodityColumns([], "quantity").columns).toEqual([]);
  });
});

describe("locationColumns", () => {
  const LOKASI = [
    {
      location: "Jakarta",
      region: "DKI Jakarta",
      demand_kg: 1000,
      supply_kg: 400,
      demand_state: "terukur",
      supply_state: "terukur",
      status: "shortage",
    },
    {
      location: "Cianjur",
      region: "Jawa Barat",
      demand_kg: 500,
      supply_kg: 900,
      demand_state: "terukur",
      supply_state: "terukur",
      status: "surplus",
    },
    {
      location: "Semarang",
      region: "Jawa Tengah",
      demand_kg: 0,
      supply_kg: 0,
      demand_state: "tidak_ada_baris",
      supply_state: "tidak_ada_baris",
      status: "unknown",
    },
  ];

  it("satu kolom per lokasi, kekurangan terbesar dulu", () => {
    const v = locationColumns(LOKASI);
    expect(v.columns.map((c) => c.key)).toEqual(["Jakarta", "Cianjur", "Semarang"]);
    expect(v.columns[0].gap).toBe("−600 kg");
    expect(v.columns[0].coverage).toBe("40%");
  });

  it("batang mode lokasi memakai satu segmen pasokan + nada barisnya", () => {
    const v = locationColumns(LOKASI);
    const jakarta = v.columns[0];
    expect(jakarta.segments).toEqual([{ tone: "pasokan", kg: 400 }]);
    expect(jakarta.barTone).toBe("danger");
    expect(v.columns[1].barTone).toBe("safe");
  });

  it("lokasi tanpa catatan tidak digambar sebagai batang 0% yang menakutkan", () => {
    const v = locationColumns(LOKASI);
    const semarang = v.columns.find((c) => c.key === "Semarang")!;
    expect(semarang.segments).toEqual([]);
    expect(semarang.coverage).toBe("—");
    expect(semarang.note).toBe("kebutuhan belum tercatat");
  });

  it("masukan kosong/null tidak melempar", () => {
    expect(locationColumns(null).columns).toEqual([]);
    expect(locationColumns([]).columns).toEqual([]);
  });
});

describe("stok tidak layak TIDAK lagi mengubah tinggi batang", () => {
  function rowsDenganRusak() {
    return buildAdequacyRows({
      commodities: ["telur", "ayam", "beras", "wortel"],
      byCommodity: {
        telur: [
          {
            location: "Jakarta",
            demand_kg: 1000,
            supply_kg: 1000,
            demand_state: "terukur",
            status: "surplus",
          },
        ],
      } as never,
      batches: [
        batch("telur", 600, 6),
        // Batch gagal uji keamanan: tercatat, tapi TIDAK boleh dihitung layak.
        { ...batch("telur", 400, 6), safety_status: "fail" },
      ],
      location: "Jakarta",
      now: NOW,
    });
  }

  it("batang = stok LAYAK ÷ kebutuhan, sama dengan angka cakupan (60%)", () => {
    const v = commodityColumns(rowsDenganRusak(), "quantity");
    const telur = v.columns.find((c) => c.key === "telur")!;
    // 600 kg layak dari 1.000 kg kebutuhan → batang 60%, angkanya "60%".
    // 400 kg yang gagal uji keamanan TIDAK menambah tinggi batang; ia hanya
    // terbaca di aria/tooltip. Inilah yang dulu bikin diagram sulit dipahami.
    expect(columnFillPct(telur)).toBeCloseTo(60, 5);
    expect(telur.coverage).toBe("60%");
    expect(telur.aria).toContain("400 kg tidak layak");
  });

  it("ruang kosong di atas batang = kekurangan", () => {
    const v = commodityColumns(rowsDenganRusak(), "quantity");
    const telur = v.columns.find((c) => c.key === "telur")!;
    expect(columnMissingPct(telur)).toBeCloseTo(40, 5);
  });
});

describe("columnMissingPct", () => {
  it("kekurangan = 100 − tinggi batang", () => {
    const v = commodityColumns(rows(), "quantity");
    const telur = v.columns.find((c) => c.key === "telur")!;
    expect(columnMissingPct(telur)).toBeCloseTo(100 - columnFillPct(telur), 6);
  });

  it("pasokan berlebih tidak menghasilkan kekurangan negatif", () => {
    const v = commodityColumns(rows(), "quantity");
    const beras = v.columns.find((c) => c.key === "beras")!;
    expect(columnMissingPct(beras)).toBe(0);
  });

  it("tanpa kebutuhan terukur → 0, bukan 100% kekurangan palsu", () => {
    const v = commodityColumns(rows(), "quantity");
    const wortel = v.columns.find((c) => c.key === "wortel")!;
    expect(columnMissingPct(wortel)).toBe(0);
  });
});
