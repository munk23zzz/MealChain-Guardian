// Kartu "Informasi pengiriman" (Arah A) — logika murni.
//
// Aturan yang diuji di sini datang dari riset docs/research/informasi-pengiriman-industri.md
// DAN dari aturan repo: TIDAK ADA ANGKA KARANGAN. Kalau geometri jalan belum ada,
// kartu menulis sebabnya — tidak menulis 0 km, tidak menulis "terlambat".
import { describe, expect, it } from "vitest";

import {
  pickShipments,
  shipmentDetails,
  shipmentHeadline,
  shipmentKeyFacts,
  shipmentProgressLabel,
  shipmentSafetyChip,
  shipmentSteps,
  shipmentVerdict,
  shipmentUrgency,
} from "../lib/shipment-card";
import type { SupplierRoute } from "../lib/supplier-routes";

/** Sekarang = 16 Okt 2026 14.00 WIB (07:00 UTC). */
const NOW = new Date("2026-10-16T07:00:00+00:00");

function route(over: Partial<SupplierRoute> = {}): SupplierRoute {
  return {
    id: "S1->L1",
    batchId: "B-1",
    routeKey: "k1",
    supplierId: "S1",
    supplierName: "Supplier A",
    originLatitude: -6.8,
    originLongitude: 107.1,
    destinationId: "L1",
    destinationName: "SPPG Cianjur",
    destinationLatitude: -6.2,
    destinationLongitude: 106.8,
    commodity: "telur",
    quantityKg: 800,
    harvestedAt: "2026-10-16T01:00:00+00:00",
    usableUntil: "2026-10-16T11:00:00+00:00",
    safetyStatus: "pass",
    straightKm: 13.1,
    road: {
      distanceKm: 14.2,
      durationMin: 60,
      ratioVsStraight: 1.08,
      coordinates: [
        [107.1, -6.8],
        [106.8, -6.2],
      ],
      source: "osrm",
      fetchedAt: "2026-10-16T00:10:00+00:00",
    },
    missingReason: null,
    // Berangkat 13.20 WIB, jalan 1 jam, estimasi tiba 14.20 WIB, sekarang 14.00 WIB.
    journey: {
      dispatchedAt: "2026-10-16T06:20:00+00:00",
      etaAt: "2026-10-16T07:20:00+00:00",
      state: "di_jalan",
      stateLabel: "Di jalan",
      travelMin: 60,
      elapsedMin: 40,
      remainingMin: 20,
      progress: 0.667,
      usableUntil: "2026-10-16T11:00:00+00:00",
      arrivesBeforeUsableUntil: true,
    },
    ...over,
  };
}

const TANPA_JALUR = route({
  road: null,
  missingReason: "belum_disinkron",
  journey: {
    dispatchedAt: "2026-10-16T06:20:00+00:00",
    etaAt: null,
    state: "tidak_diketahui",
    stateLabel: "Perjalanan belum bisa dipastikan",
    travelMin: null,
    elapsedMin: 40,
    remainingMin: null,
    progress: null,
    usableUntil: "2026-10-16T11:00:00+00:00",
    arrivesBeforeUsableUntil: null,
  },
});

const BELUM_BERANGKAT = route({
  journey: {
    dispatchedAt: null,
    etaAt: null,
    state: "belum_berangkat",
    stateLabel: "Belum berangkat",
    travelMin: 60,
    elapsedMin: null,
    remainingMin: null,
    progress: null,
    usableUntil: "2026-10-16T11:00:00+00:00",
    arrivesBeforeUsableUntil: null,
  },
});

const SUDAH_TIBA = route({
  journey: {
    ...route().journey!,
    state: "sudah_tiba",
    stateLabel: "Sudah tiba",
    remainingMin: -15,
    progress: 1,
  },
});

describe("shipmentHeadline — pil status ramping", () => {
  it("di jalan: nada bergerak + sisa waktu dalam bahasa manusia", () => {
    expect(shipmentHeadline(route())).toEqual({ tone: "moving", label: "Di jalan · 20 menit lagi" });
  });

  it("belum berangkat: TIDAK menyebut jam tiba (jam itu tidak ada di DB)", () => {
    const head = shipmentHeadline(BELUM_BERANGKAT);
    expect(head.tone).toBe("pending");
    expect(head.label).toBe("Belum berangkat");
    expect(head.label).not.toContain("tiba");
  });

  it("sudah tiba: menyebut jam tibanya", () => {
    expect(shipmentHeadline(SUDAH_TIBA)).toEqual({ tone: "done", label: "Sudah tiba 14.20" });
  });

  it("jalur belum tersinkron: nada tidak diketahui, bukan merah/terlambat", () => {
    expect(shipmentHeadline(TANPA_JALUR)).toEqual({
      tone: "unknown",
      label: "Perjalanan belum bisa dipastikan",
    });
  });

  it("tanpa blok journey: mengaku belum dilaporkan, tidak mengarang keadaan", () => {
    expect(shipmentHeadline(route({ journey: null }))).toEqual({
      tone: "unknown",
      label: "Perjalanan belum dilaporkan server",
    });
  });
});

describe("shipmentSteps — stepper empat tahap", () => {
  it("di jalan: panen & berangkat selesai, tahap jalan aktif, tiba belum", () => {
    const steps = shipmentSteps(route());
    expect(steps.map((s) => s.key)).toEqual(["harvest", "dispatch", "transit", "arrive"]);
    expect(steps.map((s) => s.state)).toEqual(["done", "done", "active", "todo"]);
    expect(steps[2].note).toBe("67% jalur");
  });

  it("belum berangkat: hanya panen yang selesai — tahap lain belum diklaim", () => {
    expect(shipmentSteps(BELUM_BERANGKAT).map((s) => s.state)).toEqual([
      "done",
      "todo",
      "todo",
      "todo",
    ]);
  });

  it("sudah tiba: keempat tahap selesai", () => {
    expect(shipmentSteps(SUDAH_TIBA).map((s) => s.state)).toEqual([
      "done",
      "done",
      "done",
      "done",
    ]);
  });

  it("jalur belum ada: tahap jalan 'unknown' — tidak diklaim sedang berjalan", () => {
    const states = shipmentSteps(TANPA_JALUR).map((s) => s.state);
    expect(states[2]).toBe("unknown");
    expect(states[3]).toBe("todo");
    expect(shipmentSteps(TANPA_JALUR)[2].note).toBe("estimasi tiba belum ada");
  });

  it("label berbahasa Indonesia, tanpa istilah backend", () => {
    expect(shipmentSteps(route()).map((s) => s.label)).toEqual([
      "Dipanen",
      "Berangkat",
      "Di jalan",
      "Tiba",
    ]);
  });
});

describe("shipmentKeyFacts — satu baris angka kunci", () => {
  it("jarak JALAN + waktu tempuh + muatan", () => {
    expect(shipmentKeyFacts(route())).toEqual(["14,2 km jalan", "± 1 jam", "800 kg telur"]);
  });

  it("tanpa geometri: menulis jarak lurus apa adanya, TIDAK menyebut 'jalan'", () => {
    const facts = shipmentKeyFacts(TANPA_JALUR);
    expect(facts.some((f) => f.includes("km jalan"))).toBe(false);
    expect(facts.some((f) => f.includes("lurus"))).toBe(true);
  });

  it("tidak pernah menulis 0 km saat data jalur hilang", () => {
    expect(shipmentKeyFacts(TANPA_JALUR).join(" ")).not.toContain("0,0 km");
  });

  it("tanpa muatan: barisnya hilang, bukan '— kg'", () => {
    const facts = shipmentKeyFacts(route({ quantityKg: null, commodity: null }));
    expect(facts).toEqual(["14,2 km jalan", "± 1 jam"]);
  });
});

describe("shipmentVerdict — kalimat keputusan", () => {
  it("di jalan + masih sebelum batas layak: menyebut jam tiba dan batasnya", () => {
    const teks = shipmentVerdict(route());
    expect(teks).toContain("Tiba ± 14.20 WIB");
    expect(teks).toContain("batas layak");
  });

  it("estimasi tiba melewati batas layak: dinyatakan apa adanya", () => {
    const teks = shipmentVerdict(
      route({
        journey: { ...route().journey!, arrivesBeforeUsableUntil: false },
      })
    );
    expect(teks).toContain("melewati batas layak");
  });

  it("jalur belum disinkron: sebabnya dari server, bukan tebakan", () => {
    const teks = shipmentVerdict(TANPA_JALUR);
    expect(teks).toContain("belum disinkronkan");
    expect(teks).toContain("belum bisa dipastikan");
  });

  it("belum berangkat: waktu tempuh jalur tetap boleh disebut, estimasi tiba tidak", () => {
    const teks = shipmentVerdict(BELUM_BERANGKAT);
    expect(teks).toContain("masih di pemasok");
    expect(teks).toContain("± 1 jam");
    expect(teks).not.toContain("Tiba ±");
  });

  it("tanpa journey: mengaku belum dilaporkan", () => {
    expect(shipmentVerdict(route({ journey: null }))).toContain("belum dilaporkan");
  });
});

describe("shipmentDetails — rincian di balik panel", () => {
  it("menyandingkan jalur jalan dan jarak lurus beserta rasionya", () => {
    const rows = shipmentDetails(route());
    const jalur = rows.find((r) => r.label === "Jalur jalan");
    const lurus = rows.find((r) => r.label === "Jarak lurus");
    expect(jalur?.value).toContain("14,2 km");
    expect(jalur?.value).toContain("OSRM");
    expect(lurus?.value).toContain("13,1 km");
    expect(lurus?.value).toContain("1,08");
  });

  it("geometri hilang: nilainya menjelaskan sebab, bukan angka kosong", () => {
    const jalur = shipmentDetails(TANPA_JALUR).find((r) => r.label === "Jalur jalan");
    expect(jalur?.value).toContain("belum disinkronkan");
    expect(jalur?.value).not.toContain("0 km");
  });

  it("memuat batch, panen, masa layak, berangkat, estimasi tiba", () => {
    const labels = shipmentDetails(route()).map((r) => r.label);
    expect(labels).toEqual(
      expect.arrayContaining([
        "Jalur jalan",
        "Jarak lurus",
        "Muatan",
        "Batch",
        "Panen",
        "Berangkat",
        "Estimasi tiba",
        "Masa layak",
      ])
    );
  });

  it("mutu gagal uji ditulis apa adanya", () => {
    const rows = shipmentDetails(route({ safetyStatus: "fail" }));
    expect(rows.some((r) => r.value.includes("GAGAL UJI"))).toBe(true);
  });
});

describe("shipmentProgressLabel — persentase hanya bila server mengirimnya", () => {
  it("di jalan: persentase dibulatkan", () => {
    expect(shipmentProgressLabel(route())).toBe("67% jalur");
  });

  it("tanpa progress: null, bukan 0%", () => {
    expect(shipmentProgressLabel(TANPA_JALUR)).toBeNull();
    expect(shipmentProgressLabel(BELUM_BERANGKAT)).toBeNull();
  });
});

describe("shipmentSafetyChip — mutu hanya muncul kalau bermasalah", () => {
  it("lolos uji: tidak ada chip (tidak menambah keramaian)", () => {
    expect(shipmentSafetyChip(route())).toBeNull();
  });

  it("gagal uji: chip bahaya", () => {
    expect(shipmentSafetyChip(route({ safetyStatus: "fail" }))).toEqual({
      tone: "fail",
      label: "Gagal uji keamanan",
    });
  });
});

describe("pickShipments + shipmentUrgency", () => {
  const sudah = route({ id: "tiba", journey: SUDAH_TIBA.journey });
  const belum = route({ id: "belum", journey: BELUM_BERANGKAT.journey });
  const jalanA = route({ id: "jalan-a" });
  const jalanB = route({
    id: "jalan-b",
    journey: { ...route().journey!, etaAt: "2026-10-16T07:05:00+00:00", remainingMin: 5 },
  });

  it("yang sedang di jalan didahulukan, estimasi tiba terdekat lebih dulu", () => {
    expect(pickShipments([sudah, belum, jalanA, jalanB], 4).rows.map((r) => r.id)).toEqual([
      "jalan-b",
      "jalan-a",
      "belum",
      "tiba",
    ]);
  });

  it("kiriman gagal uji naik lebih dulu di antara keadaan yang sama", () => {
    const gagal = route({ id: "jalan-gagal", safetyStatus: "fail" });
    expect(pickShipments([jalanA, gagal], 2).rows.map((r) => r.id)).toEqual([
      "jalan-gagal",
      "jalan-a",
    ]);
  });

  it("dibatasi maks, sisanya dihitung — bukan dihapus diam-diam", () => {
    const hasil = pickShipments([sudah, belum, jalanA, jalanB], 2);
    expect(hasil.rows).toHaveLength(2);
    expect(hasil.hidden).toBe(2);
  });

  it("urutan tetap sama untuk keadaan yang setara (stabil)", () => {
    const a = route({ id: "a" });
    const b = route({ id: "b" });
    expect(pickShipments([a, b], 2).rows.map((r) => r.id)).toEqual(["a", "b"]);
  });

  it("urutan mendesak: di jalan < belum berangkat < jalur belum ada < tiba", () => {
    expect(shipmentUrgency(jalanA)).toBeLessThan(shipmentUrgency(belum));
    expect(shipmentUrgency(belum)).toBeLessThan(shipmentUrgency(TANPA_JALUR));
    expect(shipmentUrgency(TANPA_JALUR)).toBeLessThan(shipmentUrgency(sudah));
  });
});

// ── Penyaringan per tujuan (dipakai tab Keamanan Pangan) ──────────────────────
// Tab Keamanan Pangan hanya boleh menampilkan kiriman yang menuju lokasi SPPG
// yang sedang dibuka. Penyaringnya harus di dalam logika murni (bukan di JSX)
// supaya hitungan "+N lain" ikut tersaring — menghitung baris yang tidak
// ditampilkan sebagai "disembunyikan" akan menyesatkan.
describe("pickShipments — penyaring tujuan", () => {
  const ke = (tujuan: string, id: string, over: Partial<SupplierRoute> = {}) =>
    route({ id, destinationName: tujuan, ...over });
  const kiriman = [
    ke("Jakarta", "a"),
    ke("Bandung", "b"),
    ke("jakarta", "c", {
      journey: {
        dispatchedAt: "2026-10-16T06:20:00+00:00",
        etaAt: "2026-10-16T07:20:00+00:00",
        state: "sudah_tiba",
        stateLabel: "Sudah tiba",
        travelMin: 60,
        elapsedMin: 60,
        remainingMin: 0,
        progress: 1,
        usableUntil: "2026-10-16T11:00:00+00:00",
        arrivesBeforeUsableUntil: true,
      },
    }),
  ];
  const keJakarta = (row: SupplierRoute) => row.destinationName.trim().toLowerCase() === "jakarta";

  it("tanpa penyaring perilaku lama tidak berubah (semua baris ikut)", () => {
    expect(pickShipments(kiriman, 10).rows).toHaveLength(3);
  });

  it("hanya baris tujuan yang cocok; huruf besar-kecil diabaikan", () => {
    const { rows, hidden } = pickShipments(kiriman, 10, keJakarta);
    expect(rows.map((r) => r.id).sort()).toEqual(["a", "c"]);
    expect(hidden).toBe(0);
  });

  it("baris di luar tujuan TIDAK dihitung sebagai 'hidden' (tidak menyesatkan)", () => {
    const { rows, hidden } = pickShipments(kiriman, 1, keJakarta);
    expect(rows).toHaveLength(1);
    expect(hidden).toBe(1); // dua cocok, satu ditampilkan — bukan tiga
  });

  it("urutan urgensi tetap berlaku setelah penyaringan", () => {
    const { rows } = pickShipments(kiriman, 10, keJakarta);
    expect(rows.map((r) => r.id)).toEqual(["a", "c"]); // di jalan dulu, tiba terakhir
  });

  it("penyaring yang tidak cocok sama sekali → kosong (kartu tidak dirender)", () => {
    const { rows, hidden } = pickShipments(kiriman, 3, (r) => r.destinationName === "Makassar");
    expect(rows).toEqual([]);
    expect(hidden).toBe(0);
  });
});
