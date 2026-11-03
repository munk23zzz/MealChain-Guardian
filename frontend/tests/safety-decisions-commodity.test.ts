// Dokumen `07-safety-evidence.md` §4.2 butir 1 — postur dan gerbang terhubung.
//
// Di repo ini "postur" = tabel Status keamanan per batch (satu baris per batch,
// kolom Komoditas), dan "gerbang" = daftar "Keputusan keamanan lokasi ini" di
// kartu bawah. Keduanya sudah memuat data di klien (`batches` + `decisions`),
// jadi tautannya TIDAK butuh endpoint baru: cukup menyaring daftar keputusan
// menurut `commodity_name` yang memang dikirim `GET /decisions`
// (`backend/app/api/decisions.py`).
//
// Aturan yang dikunci di sini:
//  - hanya `decision_type = safety_disruption` yang dihitung (keputusan jenis
//    lain bukan urusan halaman keamanan);
//  - komoditas kosong (`null`) TIDAK ditebak menjadi komoditas mana pun;
//  - pilihan penyaring tetap memuat SEMUA komoditas yang ada di data, supaya
//    pengguna bisa berpindah walau pilihan sekarang kosong;
//  - kalimat ringkasan menyebut bahwa daftar sedang disaring — angka "N
//    keputusan keamanan" tidak boleh terbaca sebagai seluruh riwayat.
import { describe, expect, it } from "vitest";

import { safetyDecisionSummaryLine, safetyDecisions } from "../lib/food-safety";

const DECISIONS = [
  {
    decision_id: "d1",
    decision_type: "safety_disruption",
    status: "pending_approval",
    quantity_kg: 100,
    valid: true,
    seconds_remaining: 600,
    created_at: "2026-10-16T10:00:00Z",
    commodity_name: "telur",
  },
  {
    decision_id: "d2",
    decision_type: "safety_disruption",
    status: "rejected",
    quantity_kg: 50,
    valid: false,
    seconds_remaining: 0,
    created_at: "2026-10-15T10:00:00Z",
    commodity_name: "ayam",
  },
  {
    decision_id: "d3",
    decision_type: "safety_disruption",
    status: "proposed",
    quantity_kg: 70,
    valid: false,
    seconds_remaining: 0,
    created_at: "2026-10-15T09:00:00Z",
    commodity_name: null,
  },
  // Bukan keputusan keamanan: tidak boleh ikut daftar maupun pilihan saringan.
  {
    decision_id: "d4",
    decision_type: "regional_balance",
    status: "proposed",
    quantity_kg: 600,
    valid: false,
    seconds_remaining: 0,
    created_at: "2026-10-16T09:27:02Z",
    commodity_name: "telur",
  },
];

describe("safetyDecisions — saringan komoditas (postur ↔ gerbang)", () => {
  it("tanpa saringan: semua keputusan keamanan, seperti sebelumnya", () => {
    const ringkas = safetyDecisions(DECISIONS);
    expect(ringkas.total).toBe(3);
    expect(ringkas.allTotal).toBe(4);
    expect(ringkas.filteredCommodity).toBe(null);
  });

  it("pilihan saringan = komoditas yang benar-benar ada di data (bukan dikarang)", () => {
    // `d4` ber-komoditas telur tetapi bukan keputusan keamanan; `d3` tanpa
    // komoditas. Yang tersisa: ayam + telur, urut abjad.
    expect(safetyDecisions(DECISIONS).commodities).toEqual(["ayam", "telur"]);
  });

  it("menyaring ke satu komoditas: angka & kg ikut himpunan tersaring", () => {
    const ringkas = safetyDecisions(DECISIONS, "telur");
    expect(ringkas.total).toBe(1);
    expect(ringkas.totalKg).toBe(100);
    expect(ringkas.rows.map((row) => row.id)).toEqual(["d1"]);
    expect(ringkas.filteredCommodity).toBe("telur");
    // Total feed tetap disebut apa adanya, supaya tidak terbaca sebagai riwayat
    // yang lebih pendek.
    expect(ringkas.allTotal).toBe(4);
  });

  it("saringan tidak peka huruf besar/spasi, dan mengembalikan nama kanonik data", () => {
    const ringkas = safetyDecisions(DECISIONS, "  TELUR ");
    expect(ringkas.total).toBe(1);
    expect(ringkas.filteredCommodity).toBe("telur");
  });

  it("komoditas tanpa keputusan → daftar kosong, pilihan tetap utuh", () => {
    const ringkas = safetyDecisions(DECISIONS, "wortel");
    expect(ringkas.total).toBe(0);
    expect(ringkas.commodities).toEqual(["ayam", "telur"]);
    expect(ringkas.filteredCommodity).toBe("wortel");
  });

  it("keputusan tanpa komoditas tidak pernah ikut saringan komoditas mana pun", () => {
    expect(safetyDecisions(DECISIONS, "ayam").rows.map((row) => row.id)).toEqual(["d2"]);
    expect(safetyDecisions(DECISIONS, "ayam").total).toBe(1);
  });

  it("kalimat ringkasan menyebut saringan, tanpa mengubah kalimat tanpa saringan", () => {
    const tanpa = safetyDecisionSummaryLine(safetyDecisions(DECISIONS));
    expect(tanpa).not.toContain("Disaring");
    const disaring = safetyDecisionSummaryLine(safetyDecisions(DECISIONS, "telur"));
    expect(disaring).toContain("Disaring ke komoditas telur");
    expect(disaring).toContain("Dari 4 keputusan");
  });
});
