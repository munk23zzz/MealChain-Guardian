import { describe, expect, it } from "vitest";

import {
  adequacySummary,
  bucketBatches,
  buildAdequacyRows,
  buildCommodityAdequacy,
  formatCoverage,
  formatSignedKg,
  sortAdequacyRows,
} from "../lib/supply-adequacy";

const NOW = new Date("2026-10-20T12:00:00Z");

const BATCHES = [
  // 200 kg masih >48 jam → segar
  {
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 200,
    safety_status: "pass",
    quarantine_status: "none",
    receipt_status: "accepted",
    usable_until: "2026-10-25T12:00:00Z",
  },
  // 100 kg tinggal 12 jam → mendekati batas
  {
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 100,
    safety_status: "pass",
    quarantine_status: "none",
    receipt_status: "accepted",
    usable_until: "2026-10-21T00:00:00Z",
  },
  // gagal uji
  {
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 50,
    safety_status: "fail",
    usable_until: "2026-10-25T12:00:00Z",
  },
  // belum diuji
  {
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 30,
    safety_status: "pending",
    usable_until: "2026-10-25T12:00:00Z",
  },
  // sudah lewat masa layak
  {
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 20,
    safety_status: "pass",
    usable_until: "2026-10-19T12:00:00Z",
  },
  // ditahan karantina
  {
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 40,
    safety_status: "pass",
    quarantine_status: "quarantined",
    usable_until: "2026-10-25T12:00:00Z",
  },
  // lokasi/komoditas lain tidak boleh ikut
  {
    location: "Bandung",
    commodity: "telur",
    quantity_kg: 999,
    safety_status: "pass",
    usable_until: "2026-10-25T12:00:00Z",
  },
];

const MAP = {
  telur: [
    {
      location: "Jakarta",
      demand_kg: 1080,
      supply_kg: 300,
      shortage_kg: 780,
      surplus_kg: 0,
      status: "shortage",
      demand_state: "terukur",
    },
  ],
  beras: [
    {
      location: "Jakarta",
      demand_kg: 3010,
      supply_kg: 1179,
      shortage_kg: 1831,
      surplus_kg: 0,
      status: "shortage",
      demand_state: "terukur",
    },
  ],
  ayam: [
    {
      location: "Jakarta",
      demand_kg: 0,
      supply_kg: 0,
      shortage_kg: 0,
      surplus_kg: 0,
      status: "balanced",
      demand_state: "tidak_ada_baris",
    },
  ],
  wortel: [],
};

describe("bucketBatches", () => {
  it("memisahkan segar, mendekati batas, tidak layak, dan belum terverifikasi", () => {
    const hasil = bucketBatches(BATCHES, "Jakarta", "telur", NOW);
    expect(hasil.freshKg).toBe(200);
    expect(hasil.nearKg).toBe(100);
    expect(hasil.unsafeKg).toBe(110); // 50 gagal + 20 kedaluwarsa + 40 ditahan
    expect(hasil.unverifiedKg).toBe(30);
    expect(hasil.usableKg).toBe(300); // hanya segar + mendekati batas
    expect(hasil.totalKg).toBe(440); // stok fisik, termasuk yang tidak layak
    expect(hasil.batchCount).toBe(6);
    expect(hasil.nearCount).toBe(1);
  });

  it("batch tanpa usable_until tidak dianggap segar", () => {
    const hasil = bucketBatches(
      [
        {
          location: "Jakarta",
          commodity: "telur",
          quantity_kg: 25,
          safety_status: "pass",
          usable_until: null,
        },
      ],
      "Jakarta",
      "telur",
      NOW
    );
    expect(hasil.freshKg).toBe(0);
    expect(hasil.nearKg).toBe(0);
    expect(hasil.unverifiedKg).toBe(25);
    expect(hasil.usableKg).toBe(0);
  });

  it("lokasi kosong tidak mencampur batch dari lokasi lain", () => {
    expect(bucketBatches(BATCHES, "", "telur", NOW).totalKg).toBe(0);
  });
});

describe("buildCommodityAdequacy", () => {
  it("menghitung cakupan dan kekurangan dari stok layak pakai", () => {
    const row = buildCommodityAdequacy("telur", MAP.telur, BATCHES, "Jakarta", NOW);
    expect(row.demandKg).toBe(1080);
    expect(row.buckets.usableKg).toBe(300);
    expect(row.coverage).toBeCloseTo(300 / 1080, 5);
    expect(row.freshCoverage).toBeCloseTo(200 / 1080, 5);
    expect(row.gapKg).toBe(-780);
    expect(row.freshGapKg).toBe(-880);
    expect(row.status).toBe("shortage");
    expect(row.tone).toBe("danger");
    expect(row.dataState).toBe("terukur");
  });

  it("stok layak tidak melebihi pasokan tercatat (batch belum masuk pembukuan tidak diklaim)", () => {
    const row = buildCommodityAdequacy(
      "telur",
      [
        {
          location: "Jakarta",
          demand_kg: 1080,
          supply_kg: 300,
          shortage_kg: 780,
          surplus_kg: 0,
          status: "shortage",
          demand_state: "terukur",
        },
      ],
      [
        {
          location: "Jakarta",
          commodity: "telur",
          quantity_kg: 900,
          safety_status: "pass",
          quarantine_status: "none",
          receipt_status: "accepted",
          usable_until: "2026-10-25T12:00:00Z",
        },
      ],
      "Jakarta",
      NOW
    );
    expect(row.supplyRecordKg).toBe(300);
    expect(row.buckets.usableKg).toBe(300);
    expect(row.buckets.freshKg).toBe(300);
    expect(row.coverage).toBeCloseTo(300 / 1080, 5);
    expect(row.gapKg).toBe(-780);
  });

  it("kebutuhan 0 atau tidak ada baris bukan 0% (tidak boleh tampak aman)", () => {
    const tanpaBaris = buildCommodityAdequacy(
      "ayam",
      MAP.ayam,
      [],
      "Jakarta",
      NOW
    );
    expect(tanpaBaris.demandKg).toBeNull();
    expect(tanpaBaris.coverage).toBeNull();
    expect(tanpaBaris.dataState).toBe("tanpa_data");
    expect(tanpaBaris.tone).toBe("muted");

    const kosong = buildCommodityAdequacy("wortel", MAP.wortel, [], "Jakarta", NOW);
    expect(kosong.coverage).toBeNull();
    expect(kosong.dataState).toBe("tanpa_data");
  });

  it("kebutuhan terukur tetapi tidak ada batch = kekurangan 100%, bukan tanpa data", () => {
    const row = buildCommodityAdequacy("beras", MAP.beras, [], "Jakarta", NOW);
    expect(row.demandKg).toBe(3010);
    expect(row.coverage).toBe(0);
    expect(row.gapKg).toBe(-3010);
    expect(row.dataState).toBe("terukur");
    expect(row.tone).toBe("danger");
  });
});

describe("sortAdequacyRows + adequacySummary", () => {
  const rows = buildAdequacyRows({
    commodities: ["telur", "ayam", "beras", "wortel"],
    byCommodity: MAP,
    batches: BATCHES,
    location: "Jakarta",
    now: NOW,
  });

  it("kepala SPPG: cakupan total terendah lebih dulu, data tak terukur di belakang", () => {
    const urut = sortAdequacyRows(rows, "quantity");
    expect(urut[0].commodity).toBe("beras"); // 0%
    expect(urut[1].commodity).toBe("telur"); // 27,8%
    expect(urut.slice(2).every((row) => row.coverage === null)).toBe(true);
  });

  it("ahli gizi: cakupan stok SEGAR terendah lebih dulu", () => {
    const urut = sortAdequacyRows(rows, "freshness");
    expect(urut[0].commodity).toBe("beras"); // segar 0
    expect(urut[1].commodity).toBe("telur"); // segar 18,5%
  });

  it("ringkasan menghitung hanya komoditas dengan kebutuhan terukur", () => {
    const ringkas = adequacySummary(rows, "quantity");
    expect(ringkas.measured).toBe(2);
    expect(ringkas.short).toBe(2);
    expect(ringkas.worst?.commodity).toBe("beras");
  });
});

describe("format", () => {
  it("menulis tanda minus yang terbaca dan satuan kg", () => {
    expect(formatSignedKg(-780)).toBe("−780 kg");
    expect(formatSignedKg(685)).toBe("+685 kg");
    expect(formatSignedKg(0)).toBe("0 kg");
    expect(formatSignedKg(null)).toBe("—");
  });

  it("cakupan dibulatkan ke persen", () => {
    expect(formatCoverage(0.2777)).toBe("28%");
    expect(formatCoverage(null)).toBe("—");
  });
});
