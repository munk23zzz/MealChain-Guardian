// Kontrak halaman "Keamanan Pangan" (halaman sidebar acuan /compliance).
import { describe, expect, it } from "vitest";

import {
  balanceForLocation,
  checkedForReceipt,
  coverageSentence,
  expiryState,
  filterSafetyRows,
  safetyFilterCounts,
  hoursLabel,
  hoursLeft,
  incomingBatchId,
  incomingShipments,
  ownLocationRows,
  receiptRows,
  RECEIVING_CHECKS,
  RECEIVING_OTHER,
  receivingBatchOptions,
  receivingCommodityGroups,
  receivingChecks,
  receiptSavedSentence,
  receiptNeedLabel,
  receiptStatusLabel,
  receivingSentence,
  receivingState,
  safetyDecisions,
  safetyLabel,
  safetyRows,
  safetySummary,
  safetyTone,
  sortByDeadline,
  usableLabel,
  WATCH_HOURS,
  URGENT_HOURS,
} from "../lib/food-safety";

const NOW = new Date("2026-10-11T06:00:00Z");

const BATCHES = [
  {
    id: "b1",
    location: "Cianjur",
    commodity: "telur",
    quantity_kg: 400,
    safety_status: "pass",
    freshness_score: 0.69,
    usable_until: "2026-10-11T18:00:00Z",
  },
  {
    id: "b2",
    location: "Surabaya",
    commodity: "ayam",
    quantity_kg: 120,
    safety_status: "fail",
    freshness_score: null,
    usable_until: null,
  },
  { id: "b3", location: "Bogor", commodity: "telur", quantity_kg: 50, safety_status: "needs_verification" },
];

describe("safetyLabel / safetyTone", () => {
  it("kosakata backend dibaca manusia", () => {
    expect(safetyLabel("pass")).toBe("Aman");
    expect(safetyLabel("fail")).toBe("Gagal uji");
    expect(safetyLabel("needs_verification")).toBe("Perlu verifikasi");
    expect(safetyLabel("pending")).toBe("Belum diuji");
  });

  it("status asing tetap ditulis apa adanya, kosong jadi '—'", () => {
    expect(safetyLabel("quarantine")).toBe("quarantine");
    expect(safetyLabel(null)).toBe("—");
  });

  it("warna mengikuti makna: fail merah, needs_verification kuning, pass hijau", () => {
    expect(safetyTone("fail")).toBe("danger");
    expect(safetyTone("needs_verification")).toBe("warn");
    expect(safetyTone("pass")).toBe("ok");
    expect(safetyTone("")).toBe("muted");
  });
});

describe("hoursLeft / hoursLabel", () => {
  it("12 jam ke depan ditulis 'lagi', yang sudah lewat 'lewat'", () => {
    expect(hoursLeft("2026-10-11T18:00:00Z", NOW)).toBe(12);
    expect(hoursLabel(12)).toBe("12 jam lagi");
    expect(hoursLabel(-3)).toBe("lewat 3 jam");
    expect(hoursLabel(null)).toBe("—");
  });

  it("tanggal tak terbaca → null (bukan 0)", () => {
    expect(hoursLeft(null, NOW)).toBe(null);
    expect(hoursLeft("bukan tanggal", NOW)).toBe(null);
  });

  it("lebih dari sehari ditulis hari + jam", () => {
    expect(hoursLabel(30)).toBe("1 hari 6 jam lagi");
  });
});

describe("safetyRows", () => {
  it("kolom terisi dari data, yang kosong '—' (tanpa angka karangan)", () => {
    const rows = safetyRows(BATCHES, NOW);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toMatchObject({
      location: "Cianjur",
      commodity: "telur",
      kg: 400,
      statusLabel: "Aman",
      freshness: "69%",
      hoursLabel: "12 jam lagi",
    });
    expect(rows[1].kg).toBe(120);
    expect(rows[1].statusLabel).toBe("Gagal uji");
    expect(rows[1].freshness).toBe("—");
    expect(rows[1].usableUntil).toBe("—");
    expect(rows[2].statusLabel).toBe("Perlu verifikasi");
  });

  it("daftar bukan array → halaman kosong, bukan error", () => {
    expect(safetyRows(null, NOW)).toEqual([]);
    expect(safetyRows({ batches: [] }, NOW)).toEqual([]);
  });
});

describe("safetySummary", () => {
  it("menghitung aman/gagal/perlu verifikasi + kilogram batch gagal", () => {
    const summary = safetySummary(BATCHES);
    expect(summary).toMatchObject({
      total: 3,
      safe: 1,
      failed: 1,
      needsVerification: 1,
      unchecked: 0,
      failedKg: 120,
      failedLocations: ["Surabaya"],
      hasFail: true,
    });
  });

  it("tanpa batch gagal: failedKg null (bukan 0 kg palsu)", () => {
    const summary = safetySummary([{ safety_status: "pass", quantity_kg: 10 }]);
    expect(summary.failed).toBe(0);
    expect(summary.failedKg).toBe(null);
    expect(summary.hasFail).toBe(false);
  });

});

// ── Fase 11 — halaman Keamanan Pangan untuk kepala SPPG (permintaan pemilik) ──

describe("ownLocationRows — hanya batch milik lokasi sendiri", () => {
  const rows = safetyRows(BATCHES, NOW);
  it("menyaring tanpa peduli besar-kecil huruf dan spasi", () => {
    expect(ownLocationRows(rows, "  cianjur ").map((row) => row.location)).toEqual(["Cianjur"]);
  });
  it("peran nasional (lokasi null/kosong) tetap melihat semua baris", () => {
    expect(ownLocationRows(rows, null).length).toBe(rows.length);
    expect(ownLocationRows(rows, "").length).toBe(rows.length);
  });
});

describe("sortByDeadline — paling mendesak di atas", () => {
  it("kedaluwarsa lebih dulu, tanggal kosong paling akhir", () => {
    const rows = safetyRows(
      [
        { id: "a", location: "X", commodity: "telur", quantity_kg: 1, usable_until: "2026-10-20T06:00:00Z" },
        { id: "b", location: "X", commodity: "telur", quantity_kg: 1, usable_until: "2026-09-01T06:00:00Z" },
        { id: "c", location: "X", commodity: "telur", quantity_kg: 1, usable_until: null },
        { id: "d", location: "X", commodity: "telur", quantity_kg: 1, usable_until: "2026-10-12T06:00:00Z" },
      ],
      NOW
    );
    expect(sortByDeadline(rows).map((row) => row.id)).toEqual(["b", "d", "a", "c"]);
  });
});

describe("expiryState — keadaan yang bisa ditindak, bukan angka mentah", () => {
  it("lewat masa layak = Kedaluwarsa (bukan 'kesegaran 0%')", () => {
    const state = expiryState(-867);
    expect(state.key).toBe("expired");
    expect(state.label).toBe("Kedaluwarsa");
    expect(state.detail).toContain("lewat");
  });
  it("ambang eksplisit: ≤48 jam mendesak, ≤7 hari dipantau, lebih dari itu aman", () => {
    expect(expiryState(URGENT_HOURS).key).toBe("urgent");
    expect(expiryState(URGENT_HOURS + 1).key).toBe("watch");
    expect(expiryState(WATCH_HOURS).key).toBe("watch");
    expect(expiryState(WATCH_HOURS + 1).key).toBe("ok");
  });
  it("tanpa tanggal: '—' dan tidak diklaim aman", () => {
    expect(expiryState(null).key).toBe("unknown");
    expect(expiryState(null).label).toBe("—");
  });
});

const ROUTE_PAYLOAD = {
  routes: [
    {
      id: "r1",
      batch_id: "None",
      supplier_id: "s1",
      supplier_name: "Supplier A Cianjur",
      origin: { latitude: -6.854, longitude: 107.1306, name: "Supplier A Cianjur" },
      destination_id: "loc-jkt",
      destination_name: "Jakarta",
      destination: { latitude: -6.2088, longitude: 106.8456, name: "Jakarta" },
      commodity: "telur",
      quantity_kg: 800,
      usable_until: "2026-11-07T12:00:00+00:00",
      safety_status: "pass",
      straight_km: 78.35,
      road: {
        distance_km: 110.4,
        duration_min: 84.3,
        ratio_vs_straight: 1.41,
        geometry: { type: "LineString", coordinates: [[107.13, -6.85], [106.84, -6.2]] },
        source: "osrm",
        fetched_at: null,
      },
    },
  ],
};

describe("incomingShipments — kiriman yang sedang menuju lokasi sendiri", () => {
  it("membaca amplop {routes} dari /supplier-routes apa adanya", () => {
    const list = incomingShipments(ROUTE_PAYLOAD, NOW);
    expect(list).toHaveLength(1);
    const ship = list[0];
    expect(ship.supplierName).toBe("Supplier A Cianjur");
    expect(ship.commodity).toBe("telur");
    expect(ship.kg).toBe(800);
    expect(ship.roadKm).toBe(110.4);
    expect(ship.durationMin).toBe(84.3);
    expect(ship.ratio).toBe(1.41);
    expect(ship.roadKmLabel).toContain("110,4");
    expect(ship.durationLabel).toContain("84");
    expect(ship.hoursLeft).toBeGreaterThan(24 * 20);
  });
  it("kiriman tanpa tanggal tetap tampil dengan sisa masa '—'", () => {
    const list = incomingShipments({ routes: [{ ...ROUTE_PAYLOAD.routes[0], usable_until: null }] }, NOW);
    expect(list[0].hoursLeft).toBe(null);
    expect(list[0].usableLabel).toBe("—");
  });
  it("payload rusak/kosong → daftar kosong (bukan error)", () => {
    expect(incomingShipments(null, NOW)).toEqual([]);
    expect(incomingShipments({ routes: [] }, NOW)).toEqual([]);
  });
});

describe("coverageSentence — kebutuhan vs kiriman masuk", () => {
  const dasar = { demandKg: 1080, supplyKg: 300, shortageKg: 780 };
  it("kiriman menutup kekurangan: menyebut sisa berapa", () => {
    const teks = coverageSentence({ ...dasar, incomingKg: 800 });
    expect(teks).toContain("1.080");
    expect(teks).toContain("780");
    expect(teks).toContain("menutup");
    expect(teks).toContain("+20");
  });
  it("kiriman belum menutup: menyebut sisanya masih kurang", () => {
    const teks = coverageSentence({ ...dasar, incomingKg: 500 });
    expect(teks).toContain("belum menutup");
    expect(teks).toContain("280");
  });
  it("tidak ada kekurangan → tidak ada kalimat alarm", () => {
    expect(coverageSentence({ demandKg: 300, supplyKg: 300, shortageKg: 0, incomingKg: null })).toContain(
      "Tidak ada kekurangan"
    );
  });
  it("tanpa kiriman masuk: dikatakan apa adanya", () => {
    expect(coverageSentence({ ...dasar, incomingKg: null })).toContain("belum ada kiriman");
  });
  it("data tidak lengkap → null (tidak mengarang)", () => {
    expect(coverageSentence({ demandKg: null, supplyKg: 300, shortageKg: 0, incomingKg: null })).toBe(null);
  });
});

describe("incomingBatchId — batch mana yang diperiksa saat kiriman tiba", () => {
  const rows = safetyRows(BATCHES, NOW);
  it("cocokkan komoditas + jumlah kg", () => {
    expect(incomingBatchId(rows, { commodity: "telur", kg: 400 })).toBe("b1");
  });
  it("kalau jumlah tidak diketahui, komoditas yang menentukan (kiriman terbesar)", () => {
    expect(incomingBatchId(rows, { commodity: "telur", kg: null })).toBe("b1");
  });
  it("tidak ada yang cocok → null (tombol uji disembunyikan)", () => {
    expect(incomingBatchId(rows, { commodity: "wortel", kg: 10 })).toBe(null);
  });
});

const DECISIONS = [
  { decision_id: "d1", decision_type: "safety_disruption", status: "proposed", quantity_kg: 492, valid: false, seconds_remaining: 0, created_at: "2026-10-16T09:27:02Z" },
  { decision_id: "d2", decision_type: "safety_disruption", status: "pending_approval", quantity_kg: 100, valid: true, seconds_remaining: 600, created_at: "2026-10-16T10:00:00Z" },
  { decision_id: "d3", decision_type: "safety_disruption", status: "rejected", quantity_kg: 50, valid: false, seconds_remaining: 0, created_at: "2026-10-15T10:00:00Z" },
  { decision_id: "d4", decision_type: "regional_balance", status: "proposed", quantity_kg: 600, valid: false, seconds_remaining: 0, created_at: "2026-10-16T09:27:02Z" },
];

describe("safetyDecisions — riwayat keputusan KEAMANAN untuk lokasi ini", () => {
  it("hanya menghitung decision_type keamanan, bukan semua keputusan", () => {
    const ringkas = safetyDecisions(DECISIONS);
    expect(ringkas.total).toBe(3);
    expect(ringkas.allTotal).toBe(4);
    expect(ringkas.totalKg).toBe(642);
  });
  it("membedakan yang masih berlaku dari yang sudah kedaluwarsa", () => {
    const ringkas = safetyDecisions(DECISIONS);
    expect(ringkas.active).toBe(1);
    expect(ringkas.expired).toBe(2);
    expect(ringkas.rejected).toBe(1);
  });
  it("bisa diajukan ulang HANYA kalau ditolak — kontrak /actions/repropose", () => {
    // Backend (backend/app/api/actions.py:541) menolak 409 kalau status bukan
    // "rejected" dan alasannya kosong. Jadi tombolnya jangan dipasang pada
    // keputusan yang cuma kedaluwarsa — terukur di UI: 409 → "Tidak bisa
    // mengajukan ulang".
    const ringkas = safetyDecisions(DECISIONS);
    expect(ringkas.rows.find((row) => row.id === "d1")?.canRepropose).toBe(false);
    expect(ringkas.rows.find((row) => row.id === "d2")?.canRepropose).toBe(false);
    expect(ringkas.rows.find((row) => row.id === "d3")?.canRepropose).toBe(true);
    expect(ringkas.reproposable).toBe(1);
  });
  it("daftar kosong tidak melempar", () => {
    expect(safetyDecisions(null).total).toBe(0);
  });
});

const BALANCE = {
  commodity: "telur",
  locations: [
    { location: "Jakarta", region: "DKI Jakarta", supply_kg: 300, demand_kg: 1080, surplus_kg: 0, shortage_kg: 780, status: "shortage" },
    { location: "Cianjur", region: "Jawa Barat", supply_kg: 1900, demand_kg: 500, surplus_kg: 1400, shortage_kg: 0, status: "surplus" },
  ],
};

describe("balanceForLocation — kebutuhan & kekurangan dari /balance/map", () => {
  it("lokasi sendiri diambil apa adanya dari server", () => {
    const slice = balanceForLocation(BALANCE, "Jakarta");
    expect(slice?.demandKg).toBe(1080);
    expect(slice?.supplyKg).toBe(300);
    expect(slice?.shortageKg).toBe(780);
    expect(slice?.isAggregate).toBe(false);
    expect(slice?.commodity).toBe("telur");
  });
  it("peran nasional: dijumlahkan dan disebut agregat (bukan angka satu kota)", () => {
    const slice = balanceForLocation(BALANCE, null);
    expect(slice?.demandKg).toBe(1580);
    expect(slice?.shortageKg).toBe(780);
    expect(slice?.surplusKg).toBe(1400);
    expect(slice?.isAggregate).toBe(true);
  });
  it("lokasi tidak ada di payload → null (tidak menampilkan angka kota lain)", () => {
    expect(balanceForLocation(BALANCE, "Medan")).toBe(null);
  });
  it("payload kosong/rusak → null", () => {
    expect(balanceForLocation(null, "Jakarta")).toBe(null);
    expect(balanceForLocation({ locations: [] }, "Jakarta")).toBe(null);
  });
});

describe("daftar periksa penerimaan barang (workflow petugas, bukan data server)", () => {
  it("punya lima titik periksa dengan id tetap", () => {
    expect(RECEIVING_CHECKS.map((c) => c.id)).toEqual([
      "kemasan",
      "suhu",
      "bau_warna",
      "timbang",
      "lot",
    ]);
  });
  it("label suhu menyebut batas yang benar-benar dipakai mesin", () => {
    // Sumber angka: `_SAFE_TEMP_BY_COMMODITY` di backend/app/api/freshness.py
    // (telur/ayam/wortel 0–8 °C, beras 15–30 °C). Label tanpa angka membuat
    // petugas menebak arti "sesuai" — itu yang diperbaiki 20 Okt 2026.
    const suhu = RECEIVING_CHECKS.find((c) => c.id === "suhu");
    expect(suhu?.label).toContain("0–8 °C");
    expect(suhu?.label).toContain("15–30 °C");
  });
  it("menghitung yang sudah ditandai, dan tahu kalau lengkap", () => {
    const dua = receivingState({ kemasan: true, suhu: true });
    expect(dua.done).toBe(2);
    expect(dua.total).toBe(5);
    expect(dua.allDone).toBe(false);
    expect(receivingSentence(dua)).toContain("2 dari 5");

    const semua = receivingState({ kemasan: true, suhu: true, bau_warna: true, timbang: true, lot: true });
    expect(semua.allDone).toBe(true);
    expect(receivingSentence(semua)).toContain("5 dari 5");
  });
  it("tanpa centang tetap terbaca dan tidak melempar", () => {
    expect(receivingState(null).done).toBe(0);
    expect(receivingState(undefined).allDone).toBe(false);
    expect(receivingSentence(receivingState(null))).toContain("0 dari 5");
  });
  it("centang bernilai non-boolean tidak dihitung", () => {
    expect(receivingState({ kemasan: "ya", suhu: 1 }).done).toBe(0);
  });
});

// Audit 20 Okt 2026: kalimat lama menjanjikan gerbang yang tidak ada ("tandai
// sisanya sebelum barang dipakai") padahal tombolnya aktif di 0/5 dan server
// menerima snapshot kosong; pesan sesudah simpan pun menyuruh menandai ulang.
describe("kalimat penerimaan — tanpa gerbang palsu, bentuk lampau sesudah simpan", () => {
  it("sebelum simpan: menyebut sisa titik dan izin mencatat sebagian", () => {
    const s = receivingSentence(receivingState({ kemasan: true }));
    expect(s).toContain("1 dari 5");
    expect(s).toContain("4 belum");
    expect(s).toContain("Boleh disimpan sebagian");
    expect(s).not.toContain("tandai sisanya");
  });

  it("sesudah simpan: bentuk lampau, tanpa perintah", () => {
    const s = receiptSavedSentence(receivingState({ kemasan: true, suhu: true }));
    expect(s).toContain("Catatan tersimpan");
    expect(s).toContain("2 dari 5 titik tercatat");
    expect(s).toContain("3 belum diperiksa");
    expect(s).not.toContain("tandai");
  });

  it("lengkap: tidak ada lagi kata 'belum'", () => {
    const penuh = receivingState({
      kemasan: true,
      suhu: true,
      bau_warna: true,
      timbang: true,
      lot: true,
    });
    expect(receivingSentence(penuh)).toContain("semuanya sesuai");
    expect(receiptSavedSentence(penuh)).toContain("semuanya sesuai");
    expect(receiptSavedSentence(penuh)).not.toContain("belum");
  });
});

describe("catatan penerimaan barang — opsi Lainnya (tersimpan di /receipts)", () => {
  it("opsi Lainnya berdiri sendiri, tidak ikut dihitung sebagai titik periksa", () => {
    expect(RECEIVING_OTHER.id).toBe("lainnya");
    expect(RECEIVING_CHECKS.map((c) => c.id)).not.toContain(RECEIVING_OTHER.id);
    expect(RECEIVING_OTHER.label.toLowerCase()).toContain("lainnya");
  });

  it("receiptRows menormalkan balasan server apa adanya", () => {
    const rows = receiptRows({
      items: [
        {
          id: "r1",
          batch_id: "b1",
          checked: { kemasan: true },
          checked_count: 1,
          other_note: "Karung lapis kedua basah, isi masih kering.",
          recorded_by: "u1",
          recorded_by_name: "SPPG Ops",
          recorded_at: "2026-10-16T07:56:22+00:00",
        },
        {
          id: "r2",
          batch_id: "b1",
          checked: {},
          checked_count: 0,
          other_note: "   ",
          recorded_by_name: null,
          recorded_at: null,
        },
      ],
    });
    expect(rows).toHaveLength(2);
    expect(rows[0].note).toContain("Karung lapis kedua basah");
    expect(rows[0].checkedCount).toBe(1);
    expect(rows[0].byName).toBe("SPPG Ops");
    expect(rows[0].waktuLabel).not.toBe("—");
    // spasi bukan catatan; UI harus bisa bilang "tidak ada catatan"
    expect(rows[1].note).toBe(null);
    expect(rows[1].checkedCount).toBe(0);
    expect(rows[1].byName).toBe(null);
  });

  it("status penerimaan dipetakan ke label + nada; baris lama dianggap menunggu", () => {
    expect(receiptStatusLabel("disetujui")).toEqual({ label: "Disetujui", nada: "ok" });
    expect(receiptStatusLabel("ditolak")).toEqual({ label: "Ditolak", nada: "danger" });
    expect(receiptStatusLabel(undefined)).toEqual({
      label: "Menunggu persetujuan",
      nada: "warn",
    });
    // Baris sebelum migrasi 026 tidak punya `status` — jangan jadi "undefined".
    const lama = receiptRows({
      items: [{ id: "r0", checked_count: 2, recorded_at: "2026-10-16T07:56:22+00:00" }],
    });
    expect(lama[0].status).toBe("menunggu");
    expect(lama[0].statusLabel).toBe("Menunggu persetujuan");
  });

  it("receiptRows membawa pemutus, waktu keputusan, kg stok, dan alasan tolak", () => {
    const rows = receiptRows({
      items: [
        {
          id: "r1",
          checked_count: 5,
          recorded_at: "2026-10-20T10:00:00+00:00",
          status: "disetujui",
          reviewed_by_name: "SPPG Head Demo",
          reviewed_at: "2026-10-20T10:05:00+00:00",
          stock_kg: 128,
          review_note: null,
        },
        {
          id: "r2",
          checked_count: 1,
          recorded_at: "2026-10-20T10:10:00+00:00",
          status: "ditolak",
          reviewed_by_name: "SPPG Head Demo",
          reviewed_at: "2026-10-20T10:12:00+00:00",
          stock_kg: null,
          review_note: "kemasan penyok",
        },
      ],
    });
    expect(rows[0].statusNada).toBe("ok");
    expect(rows[0].reviewedByName).toBe("SPPG Head Demo");
    expect(rows[0].stockKg).toBe(128);
    expect(rows[1].statusNada).toBe("danger");
    expect(rows[1].stockKg).toBe(null);
    expect(rows[1].reviewNote).toBe("kemasan penyok");
  });

  it("balasan kosong/rusak → daftar kosong, tidak melempar", () => {
    expect(receiptRows(null)).toEqual([]);
    expect(receiptRows({})).toEqual([]);
    expect(receiptRows({ items: "bukan array" })).toEqual([]);
  });

  it("checkedForReceipt mengirim snapshot LENGKAP 5 titik, tanpa kunci asing", () => {
    const kirim = checkedForReceipt({ kemasan: true, suhu: false, lainnya: true });
    // Snapshot penuh: server menerima keadaaan semua titik, bukan hanya yang dicentang.
    expect(kirim).toEqual({
      kemasan: true,
      suhu: false,
      bau_warna: false,
      timbang: false,
      lot: false,
    });
    // Kunci lama "warna" tidak dikirim lagi; baris lama di database tetap
    // menyimpan kuncinya sendiri (snapshot disimpan apa adanya).
    expect(Object.keys(kirim)).not.toContain("warna");
    // Opsi "Lainnya" BUKAN titik periksa — catatannya dikirim lewat other_note.
    expect(Object.keys(kirim)).not.toContain("lainnya");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Opsi "Batch yang diterima" (audit 20 Okt 2026). Server menolak 403 kalau batch
// bukan milik dapur pemakai ("lokasi batch di cakupan lokasi di luar SPPG Anda"):
// barang diterima di dapur sendiri, ruling 2026-10-14. Karena itu daftar opsi
// TIDAK BOLEH ikut cakupan tabel — saat cakupan "Semua lokasi (pengawasan)"
// dropdown sempat menawarkan 50+ batch kota lain, pilihan yang dijamin gagal.
describe("opsi 'Batch yang diterima' selalu milik dapur sendiri", () => {
  const now = new Date("2026-10-20T10:00:00+07:00");
  const batch = (id: string, location: string, commodity: string, kg: number) => ({
    id,
    location,
    commodity,
    quantity_kg: kg,
    usable_until: "2026-10-22T10:00:00+07:00",
    safety_status: "pending",
    freshness_score: 0.9,
    quarantine_status: null,
  });
  const rows = safetyRows(
    [
      batch("b-jkt", "Jakarta", "ayam", 80),
      batch("b-smg", "Semarang", "ayam", 120),
      batch("b-yog", "Yogyakarta", "wortel", 100),
    ],
    now
  );

  it("membuang batch lokasi lain meski sumbernya seluruh jaringan", () => {
    const opsi = receivingBatchOptions(rows, "Jakarta");
    expect(opsi.map((row) => row.id)).toEqual(["b-jkt"]);
  });

  it("nama lokasi dibandingkan tanpa peduli huruf besar/kecil dan spasi", () => {
    const opsi = receivingBatchOptions(rows, "  jakarta ");
    expect(opsi.map((row) => row.id)).toEqual(["b-jkt"]);
  });

  it("tanpa lokasi sendiri (peran pengawasan) semua baris tetap sah — kartunya tidak dirender", () => {
    expect(receivingBatchOptions(rows, null)).toHaveLength(3);
  });

  it("baris tanpa id tidak pernah jadi opsi", () => {
    const tanpaId = safetyRows([{ ...batch("x", "Jakarta", "beras", 10), id: null }], now);
    expect(receivingBatchOptions(tanpaId, "Jakarta")).toHaveLength(0);
  });

  it("label tanggal layak pakai selalu menyebut tahun (lintas tahun tidak ambigu)", () => {
    // Batch beras demo layak sampai Maret TAHUN BERIKUTNYA; tanpa tahun labelnya
    // terbaca "19 Mar" — seolah bulan depan. Di kartu penerimaan label ini
    // dipakai memilih batch, jadi ambiguitasnya bukan kosmetik.
    expect(usableLabel("2027-03-19T01:00:00+07:00")).toContain("2027");
    expect(usableLabel("2026-10-22T10:00:00+07:00")).toContain("2026");
    expect(usableLabel("2027-03-19T01:00:00+07:00")).toContain("19");
    expect(usableLabel(null)).toBe("—");
  });

  it("batch yang masih layak didahulukan; yang kedaluwarsa tetap ada di bawah", () => {
    const campur = safetyRows(
      [
        { ...batch("b-lewat", "Jakarta", "ayam", 80), usable_until: "2026-10-11T10:00:00+07:00" },
        { ...batch("b-layak", "Jakarta", "wortel", 90), usable_until: "2026-10-24T10:00:00+07:00" },
        { ...batch("b-gesit", "Jakarta", "telur", 40), usable_until: "2026-10-20T20:00:00+07:00" },
      ],
      now
    );
    const opsi = receivingBatchOptions(campur, "Jakarta");
    // Default = yang paling cepat kedaluwarsa TAPI masih layak, bukan yang sudah lewat.
    expect(opsi.map((row) => row.id)).toEqual(["b-gesit", "b-layak", "b-lewat"]);
  });
});

describe("saringan daftar batch (redesign 20 Okt 2026)", () => {
  const rows = safetyRows(BATCHES, new Date("2026-10-10T00:00:00Z"));

  it("menghitung isi tiap saringan dari keadaan baris", () => {
    const n = safetyFilterCounts(rows);
    expect(n.semua).toBe(3);
    expect(n.aman).toBe(1);
    expect(n.gagal).toBe(1);
    expect(n.verifikasi).toBe(1);
    // "perlu tindakan" = gagal + perlu verifikasi + ditahan; aman tidak ikut.
    expect(n.tindakan).toBe(2);
  });

  it("saringan tindakan mengeluarkan baris aman, saringan gagal hanya yang merah", () => {
    const tindakan = filterSafetyRows(rows, "tindakan", "");
    expect(tindakan.map((r) => r.id)).toEqual(["b2", "b3"]);
    expect(filterSafetyRows(rows, "gagal", "").map((r) => r.id)).toEqual(["b2"]);
    expect(filterSafetyRows(rows, "aman", "").map((r) => r.id)).toEqual(["b1"]);
  });

  it("pencarian mencocokkan lokasi & komoditas tanpa peduli huruf besar/kecil", () => {
    expect(filterSafetyRows(rows, "semua", "SURABAYA").map((r) => r.id)).toEqual(["b2"]);
    expect(filterSafetyRows(rows, "semua", "telur").map((r) => r.id)).toEqual(["b1", "b3"]);
    expect(filterSafetyRows(rows, "semua", "  ")).toHaveLength(3);
    expect(filterSafetyRows(rows, "semua", "tidak-ada")).toHaveLength(0);
  });

  it("saringan dan pencarian digabung, bukan saling menimpa", () => {
    expect(filterSafetyRows(rows, "tindakan", "bogor").map((r) => r.id)).toEqual(["b3"]);
  });
});

describe("pilihan penerimaan dua langkah: komoditas lalu batch", () => {
  // Penerimaan hanya untuk barang BELUM diuji; batch fixture kanonik sudah
  // punya hasil, jadi statusnya dijadikan `pending` untuk menguji pengelompokan.
  const rows = safetyRows(
    BATCHES.map((batch) => ({ ...batch, safety_status: "pending" })),
    new Date("2026-10-10T00:00:00Z")
  );

  it("mengelompokkan batch per komoditas, mempertahankan urutan tenggat", () => {
    const grup = receivingCommodityGroups(rows, null);
    expect(grup.map((g) => g.commodity)).toEqual(["telur", "ayam"]);
    expect(grup[0].rows.map((r) => r.id)).toEqual(["b1", "b3"]);
    expect(grup[1].rows.map((r) => r.id)).toEqual(["b2"]);
  });

  it("menjumlahkan berat per komoditas, dan null bila tak ada kg", () => {
    const grup = receivingCommodityGroups(rows, null);
    expect(grup[0].totalKg).toBe(450); // 400 + 50
    expect(grup[1].totalKg).toBe(120);
    const tanpaKg = safetyRows(
      [{ id: "x", location: "Bogor", commodity: "sayur", safety_status: "pending" }],
      new Date()
    );
    expect(receivingCommodityGroups(tanpaKg, null)[0].totalKg).toBeNull();
  });

  it("cakupan lokasi tetap dihormati seperti daftar batch", () => {
    const grup = receivingCommodityGroups(rows, "Bogor");
    expect(grup).toHaveLength(1);
    expect(grup[0].rows.map((r) => r.id)).toEqual(["b3"]);
  });

  it("komoditas kosong tetap punya kelompok, tidak hilang dari pilihan", () => {
    const tanpaNama = safetyRows(
      [{ id: "y", location: "Bogor", quantity_kg: 10, safety_status: "pending" }],
      new Date()
    );
    expect(receivingCommodityGroups(tanpaNama, null)[0].commodity).toBe("—");
  });
});

describe("titik periksa menyesuaikan komoditas", () => {
  const ids = ["kemasan", "suhu", "bau_warna", "timbang", "lot"];

  it("id titik tetap lima yang sama, hanya kalimatnya yang berubah", () => {
    for (const komoditas of ["ayam", "telur", "beras", "wortel", "tidak-dikenal"]) {
      expect(receivingChecks(komoditas).map((c) => c.id)).toEqual(ids);
      expect(receivingChecks(komoditas)).toHaveLength(5);
    }
  });

  it("beras memakai karung + rentang 15–30 °C dan ciri apek", () => {
    const cek = receivingChecks("beras");
    expect(cek[0].label).toContain("Karung");
    expect(cek[1].label).toContain("15–30 °C");
    expect(cek[2].label).toContain("apek");
  });

  it("ayam, telur, wortel membawa ciri masing-masing", () => {
    expect(receivingChecks("ayam")[2].label).toContain("amis");
    expect(receivingChecks("ayam")[1].label).toContain("0–8 °C");
    expect(receivingChecks("telur")[2].label).toContain("retak");
    expect(receivingChecks("wortel")[2].label).toContain("layu");
  });

  it("komoditas tak dikenal / kosong memakai kalimat umum, bukan kosong", () => {
    const umum = receivingChecks("jagung");
    expect(umum[0].label).toBe("Kemasan utuh, tidak sobek atau bocor");
    expect(umum[1].label).toContain("0–8 °C");
    expect(umum[2].label).toBe("Bau & warna normal");
    expect(receivingChecks(null)[1].label).toContain("0–8 °C");
  });

  it("huruf besar/kecil tidak mengubah profil", () => {
    expect(receivingChecks("BERAS")[1].label).toContain("15–30 °C");
  });
});

describe("batch yang ditawarkan = yang masih perlu diperiksa/dicatat", () => {
  const now = new Date("2026-10-10T00:00:00Z");
  const rows = safetyRows(
    [
      { id: "n1", location: "Bogor", commodity: "beras", quantity_kg: 10, safety_status: "pending" },
      { id: "n2", location: "Bogor", commodity: "beras", quantity_kg: 20, safety_status: "pending", receipt_status: "ditolak" },
      { id: "n3", location: "Bogor", commodity: "beras", quantity_kg: 30, safety_status: "pending", receipt_status: "menunggu" },
      { id: "n4", location: "Bogor", commodity: "beras", quantity_kg: 40, safety_status: "pending", receipt_status: "disetujui" },
    ],
    now
  );

  it("hanya batch yang BELUM dinilai yang ditawarkan", () => {
    const id = receivingBatchOptions(rows, "Bogor").map((r) => r.id);
    // menunggu, ditolak, dan disetujui sama-sama sudah dinilai → keluar.
    expect(id).toEqual(["n1"]);
  });

  it("batch menunggu tidak kembali ke form; ia pindah ke antrean persetujuan", () => {
    expect(receivingBatchOptions(rows, "Bogor").map((r) => r.id)).not.toContain("n3");
  });

  it("kelompok komoditas ikut aturan yang sama", () => {
    const grup = receivingCommodityGroups(rows, "Bogor");
    expect(grup).toHaveLength(1);
    expect(grup[0].rows.map((r) => r.id)).toEqual(["n1"]);
    expect(grup[0].totalKg).toBe(10);
  });

  it("label kebutuhan mencatat jujur per status", () => {
    expect(receiptNeedLabel(null)).toBe("belum dinilai");
    expect(receiptNeedLabel("ditolak")).toContain("dinilai ulang");
    expect(receiptNeedLabel("menunggu")).toContain("menunggu persetujuan");
    expect(receiptNeedLabel("disetujui")).toContain("sudah disetujui");
  });
});
