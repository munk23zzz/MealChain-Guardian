// "Papan kiriman" (Arah B riset 16 Okt 2026) — logika MURNI.
//
// Aturan yang diuji di sini: TIDAK ADA ANGKA KARANGAN (tanpa geometri jalan →
// tulis jarak lurus berlabel + sebabnya, bukan 0 km; tanpa ETA → "—" dan barisnya
// paling belakang, bukan dianggap paling awal), dan urutan yang bisa diprediksi
// petugas (pemutus terakhir = nama pemasok).
import { describe, expect, it } from "vitest";

import {
  BOARD_SORTS,
  boardBerangkat,
  boardBerangkatPenuh,
  boardCounts,
  boardEtaPenuh,
  boardWaktuPenuh,
  boardWaktuRingkas,
  boardEta,
  boardJalur,
  boardKeadaan,
  boardLayakNote,
  boardMasaLayak,
  boardMuatan,
  boardMutu,
  boardSisa,
  boardSort,
  boardSumber,
  boardTibaRingkas,
} from "../lib/shipment-board";
import type { SupplierRoute } from "../lib/supplier-routes";

type Journey = NonNullable<SupplierRoute["journey"]>;

function journey(over: Partial<Journey> = {}): Journey {
  return {
    dispatchedAt: "2026-10-16T12:24:00+00:00",
    etaAt: "2026-10-16T12:24:00+00:00",
    state: "di_jalan",
    stateLabel: "Di jalan",
    travelMin: 84,
    elapsedMin: 64,
    remainingMin: 20,
    progress: 0.76,
    usableUntil: "2026-10-16T11:00:00+00:00",
    arrivesBeforeUsableUntil: true,
    ...over,
  };
}

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
    destinationName: "Jakarta",
    destinationLatitude: -6.2,
    destinationLongitude: 106.8,
    commodity: "telur",
    quantityKg: 800,
    harvestedAt: "2026-10-16T01:00:00+00:00",
    usableUntil: "2026-10-16T11:00:00+00:00",
    safetyStatus: "pass",
    straightKm: 78.35,
    road: {
      distanceKm: 110.4,
      durationMin: 84.3,
      ratioVsStraight: 1.41,
      coordinates: [
        [107.1, -6.8],
        [106.8, -6.2],
      ],
      source: "osrm",
      fetchedAt: "2026-10-16T00:10:00+00:00",
    },
    missingReason: null,
    journey: journey(),
    ...over,
  };
}

const tanpaJourney = route({ id: "x", journey: undefined });
const tanpaJalur = route({
  id: "y",
  road: undefined,
  missingReason: "belum_disinkron",
  journey: journey({ state: "tidak_diketahui", etaAt: null, remainingMin: null }),
});
const sudahTiba = route({
  id: "z",
  journey: journey({ state: "sudah_tiba", remainingMin: 0 }),
});

describe("papan kiriman — isi sel (tanpa angka karangan)", () => {
  it("muatan menyebut berat DAN komoditas", () => {
    expect(boardMuatan(route())).toBe("800 kg telur");
    expect(boardMuatan(route({ commodity: null }))).toBe("800 kg");
    expect(boardMuatan(route({ quantityKg: null }))).toBe("telur");
    expect(boardMuatan(route({ quantityKg: null, commodity: null }))).toBe("—");
  });

  it("jalur memakai jarak JALAN + waktu tempuh bila ada", () => {
    expect(boardJalur(route())).toBe("110,4 km jalan · ± 1 jam 24 menit");
  });

  it("tanpa geometri jalan: jarak lurus DIBERI LABEL + sebabnya, bukan 0 km", () => {
    const teks = boardJalur(tanpaJalur);
    expect(teks).toContain("78,4 km lurus");
    expect(teks).toContain("belum disinkronkan");
    expect(teks).not.toContain("0 km");
  });

  it("tanpa geometri DAN tanpa jarak lurus: '—' (bukan 0)", () => {
    expect(boardJalur(route({ road: undefined, straightKm: null }))).toBe("—");
  });

  it("sumber geometri tetap dilaporkan; rasio jarak lurus TIDAK lagi ditampilkan", () => {
    // Rasio jalur↔garis lurus dibuang atas permintaan pemilik (16 Okt 2026): angka itu
    // tidak mengubah keputusan apa pun di layar. Jejak sumbernya (OSRM) TETAP, supaya
    // angka jarak/waktu masih bisa ditelusuri. Penjaga "tidak boleh muncul" ada di tes
    // markup (tests/shipment-board-component.test.tsx).
    expect(boardSumber(route())).toBe("OSRM");
    expect(boardSumber(tanpaJalur)).toBeNull();
  });

  it("berangkat: waktu RINGKAS di sel (16 Okt 19.24), lengkap di tooltip", () => {
    expect(boardBerangkat(route())).toBe("16 Okt 19.24");
    expect(boardBerangkatPenuh(route())).toBe("16 Okt 2026 19.24 WIB");
    expect(boardBerangkat(tanpaJourney)).toBe("belum berangkat");
    expect(boardBerangkatPenuh(tanpaJourney)).toBe("belum berangkat");
  });

  it("waktu ringkas: tahun sengaja tidak diulang; nilai kosong/tak sah → '—'", () => {
    expect(boardWaktuRingkas("2026-10-16T12:24:00+00:00")).toBe("16 Okt 19.24");
    expect(boardWaktuRingkas(null)).toBe("—");
    expect(boardWaktuRingkas("bukan tanggal")).toBe("—");
    // Tahun lengkap tetap tersedia untuk tooltip.
    expect(boardWaktuPenuh("2026-10-16T12:24:00+00:00")).toBe("16 Okt 2026 19.24 WIB");
  });

  it("ETA & sisa: '—' bila belum ada, tanpa menebak", () => {
    expect(boardEta(route())).toBe("16 Okt 19.24");
    expect(boardEtaPenuh(route())).toBe("16 Okt 2026 19.24 WIB");
    expect(boardEta(tanpaJourney)).toBe("—");
    expect(boardSisa(route())).toBe("20 menit");
    expect(boardSisa(tanpaJourney)).toBe("—");
  });

  it("sisa waktu hanya untuk perjalanan yang sedang berjalan", () => {
    // Sudah tiba / belum berangkat: kolom "Keadaan" yang menjelaskan, bukan angka sisa.
    expect(boardSisa(sudahTiba)).toBe("—");
    expect(boardSisa(tanpaJalur)).toBe("—"); // state tidak_diketahui
    expect(boardSisa(route({ journey: journey({ state: "belum_berangkat" }) }))).toBe("—");
  });

  it("catatan masa layak hanya untuk PERINGATAN, bukan kabar baik", () => {
    expect(boardMasaLayak(route())).toBe("16 Okt 2026");
    expect(boardMasaLayak(route({ usableUntil: null }))).toBe("—");
    // "Tiba sebelum batas layak" dibuang (pemilik: info itu tidak diperlukan pembaca —
    // tanggal layaknya sendiri sudah ada di kolom ini). Yang disimpan adalah yang
    // mengubah keputusan: peringatan akan MELEWATI batas.
    expect(boardLayakNote(route())).toBeNull();
    expect(boardLayakNote(route({ journey: journey({ arrivesBeforeUsableUntil: false }) }))).toEqual({
      text: "tiba MELEWATI batas",
      tone: "danger",
    });
    // Server belum bisa memastikan → tidak ada catatan (jangan mengarang "aman").
    expect(boardLayakNote(route({ journey: journey({ arrivesBeforeUsableUntil: null }) }))).toBeNull();
  });

  it("mutu: gagal/lolos apa adanya; tanpa status → '—'", () => {
    expect(boardMutu(route())).toBe("Lolos uji");
    expect(boardMutu(route({ safetyStatus: "fail" }))).toBe("Gagal uji");
    expect(boardMutu(route({ safetyStatus: null }))).toBe("—");
    // Enum mentah tidak boleh tampil di UI: "Mutu" adalah status keamanan,
    // jadi pakai label manusia yang sama dengan halaman Keamanan Pangan.
    expect(boardMutu(route({ safetyStatus: "needs_verification" }))).toBe("Perlu verifikasi");
    expect(boardMutu(route({ safetyStatus: "pending" }))).toBe("Belum diuji");
    // Nilai yang belum dikenal tetap apa adanya — jangan dikarang.
    expect(boardMutu(route({ safetyStatus: "kustom_status" }))).toBe("kustom_status");
  });

  it("keadaan: label dari server + nada untuk warna", () => {
    expect(boardKeadaan(route())).toEqual({ label: "Di jalan", tone: "moving" });
    expect(boardKeadaan(route({ journey: journey({ state: "belum_berangkat" }) })).tone).toBe("pending");
    expect(boardKeadaan(tanpaJourney)).toEqual({ label: "Belum dilaporkan", tone: "unknown" });
  });

  it("jam tiba ringkas hanya untuk yang sudah tiba", () => {
    // `formatClockWib` menghasilkan jam WIB ringkas ("19.24") — dipakai di ringkasan.
    expect(boardTibaRingkas(sudahTiba)).toMatch(/^\d{2}\.\d{2}$/);
    expect(boardTibaRingkas(route())).toBeNull();
  });

  it("ringkasan jumlah menyebut keadaan yang benar-benar ada", () => {
    expect(boardCounts([])).toBe("Tidak ada kiriman");
    expect(boardCounts([route(), sudahTiba])).toBe("2 kiriman · 1 di jalan · 1 sudah tiba");
    expect(boardCounts([route(), tanpaJourney])).toBe("2 kiriman · 1 di jalan · 1 tanpa laporan");
  });
});

describe("papan kiriman — pengurutan", () => {
  it("pilihan urutan berlabel bahasa pengguna, 'paling mendesak' lebih dulu", () => {
    expect(BOARD_SORTS.map((s) => s.id)).toEqual(["mendesak", "eta", "layak"]);
    expect(BOARD_SORTS[0].label).toBe("Paling mendesak");
  });

  it("mendesak: yang bergerak dulu, yang sudah tiba terakhir", () => {
    const a = route({ id: "a", supplierName: "A", journey: journey({ state: "sudah_tiba" }) });
    const b = route({ id: "b", supplierName: "B", journey: journey({ state: "belum_berangkat" }) });
    const c = route({ id: "c", supplierName: "C" }); // di jalan
    expect(boardSort([a, b, c], "mendesak").map((r) => r.id)).toEqual(["c", "b", "a"]);
  });

  it("mendesak: kiriman gagal uji naik lebih dulu di keadaan yang sama", () => {
    const gagal = route({ id: "gagal", supplierName: "Gagal", safetyStatus: "fail" });
    const aman = route({ id: "aman", supplierName: "Aman" });
    expect(boardSort([aman, gagal], "mendesak").map((r) => r.id)).toEqual(["gagal", "aman"]);
  });

  it("eta: urut menurut ETA, yang BELUM punya ETA paling belakang", () => {
    const pagi = route({ id: "pagi", supplierName: "A", journey: journey({ etaAt: "2026-10-16T09:00:00+00:00" }) });
    const sore = route({ id: "sore", supplierName: "B", journey: journey({ etaAt: "2026-10-16T15:00:00+00:00" }) });
    const kosong = route({ id: "kosong", supplierName: "C", journey: undefined });
    expect(boardSort([kosong, sore, pagi], "eta").map((r) => r.id)).toEqual(["pagi", "sore", "kosong"]);
  });

  it("layak: urut menurut batas layak, yang belum ada paling belakang", () => {
    const dekat = route({ id: "dekat", supplierName: "A", usableUntil: "2026-10-16T11:00:00+00:00" });
    const jauh = route({ id: "jauh", supplierName: "B", usableUntil: "2026-11-07T11:00:00+00:00" });
    const kosong = route({ id: "kosong", supplierName: "C", usableUntil: null });
    expect(boardSort([kosong, jauh, dekat], "layak").map((r) => r.id)).toEqual(["dekat", "jauh", "kosong"]);
  });

  it("urutan bisa diprediksi: keadaan & waktu sama → nama pemasok jadi pemutus", () => {
    const b = route({ id: "b", supplierName: "Bakti" });
    const a = route({ id: "a", supplierName: "Anugerah" });
    expect(boardSort([b, a], "mendesak").map((r) => r.id)).toEqual(["a", "b"]);
    // tidak mengubah array masukan
    const masukan = [b, a];
    boardSort(masukan, "mendesak");
    expect(masukan.map((r) => r.id)).toEqual(["b", "a"]);
  });

  it("dua baris tanpa data tidak membuat urutan kacau (NaN bukan pembanding)", () => {
    const x = route({ id: "x", supplierName: "X", journey: undefined });
    const y = route({ id: "y", supplierName: "Y", journey: undefined });
    expect(boardSort([y, x], "eta").map((r) => r.id)).toEqual(["x", "y"]);
    expect(boardSort([y, x], "layak").map((r) => r.id)).toEqual(["x", "y"]);
  });
});
