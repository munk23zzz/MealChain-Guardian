// Test logika murni halaman Recommendation Feed (14 Okt 2026).
//
// Kenapa ada: feed berisi 126 kartu dan pengguna (juri demo) harus bisa
// menjawab tiga hal dalam beberapa detik — "apa yang perlu saya tindak?",
// "mana yang saya cari?", "kenapa urutannya begini?". Sebelum ini:
//   - angka di sidebar = jumlah SELURUH keputusan (126), bukan yang perlu
//     tindakan;
//   - chip filter memakai istilah backend mentah (PENDING_APPROVAL,
//     VERIFIER_FLAGGED) dan diurutkan alfabetis;
//   - tidak ada pencarian maupun kontrol urutan, padahal kepala halaman
//     mengklaim "urutan berdasarkan urgensi".
// Semua fungsi di sini murni (tanpa DOM) supaya bisa diuji dan tidak
// menimbulkan selisih render server/klien.

import { describe, expect, it } from "vitest";

import {
  FEED_SORT_LABELS,
  feedChips,
  feedSummary,
  feedVisible,
  hasActiveFilter,
  sortFeed,
} from "../lib/decision-feed";

/** Baris keputusan seperti yang benar-benar dikirim GET /decisions. */
function row(over: Record<string, unknown> = {}) {
  return {
    decision_id: "aaaaaaaa-1111-2222-3333-444444444444",
    decision_type: "regional_balance",
    status: "proposed",
    quantity_kg: 600,
    safe_delivered_cost: 16206000,
    expires_at: "2026-10-11T17:10:15+00:00",
    created_at: "2026-10-11T16:40:15+00:00",
    valid: false,
    rejection_reason: null,
    verifier_note: null,
    demo_case: null,
    ...over,
  };
}

const NOW = new Date("2026-10-14T12:00:00+00:00");

const DATA = [
  row({ decision_id: "id-proposed-1", status: "proposed", decision_type: "regional_balance" }),
  row({ decision_id: "id-harga-1", status: "proposed", decision_type: "price_anomaly", created_at: "2026-10-12T00:00:00+00:00" }),
  row({ decision_id: "id-aman-1", status: "proposed", decision_type: "safety_disruption", created_at: "2026-10-01T00:00:00+00:00" }),
  row({ decision_id: "id-approve-1", status: "pending_approval", decision_type: "price_anomaly", expires_at: "2026-10-10T00:00:00+00:00" }),
  row({ decision_id: "id-approve-2", status: "pending_approval", decision_type: "regional_balance", expires_at: "2026-10-13T00:00:00+00:00" }),
  row({ decision_id: "id-flag-1", status: "verifier_flagged", decision_type: "safety_disruption", expires_at: "2026-10-15T00:00:00+00:00" }),
  row({ decision_id: "id-tolak-1", status: "rejected", decision_type: "regional_balance", rejection_reason: "Kuota SPPG Jakarta penuh" }),
];

describe("feedChips (label + urutan chip filter)", () => {
  it("chip pertama = 'Perlu tindakan' dengan jumlah keputusan yang menunggu tindakan", () => {
    const chips = feedChips(DATA);
    expect(chips[0].id).toBe("action");
    expect(chips[0].label).toBe("Perlu tindakan");
    // 2 pending_approval + 1 verifier_flagged = 3 (proposed/rejected bukan).
    expect(chips[0].count).toBe(3);
  });

  it("label status memakai bahasa manusia, bukan enum backend", () => {
    const chips = feedChips(DATA);
    const labels = chips.map((c) => c.label);
    expect(labels).toContain("menunggu persetujuan");
    expect(labels).toContain("ditandai verifier");
    expect(labels.join(" ")).not.toContain("PENDING_APPROVAL");
    expect(labels.join(" ")).not.toContain("VERIFIER_FLAGGED");
  });

  it("urutan bermakna: yang menuntut tindakan lebih dulu, bukan alfabetis", () => {
    const ids = feedChips(DATA).slice(1).map((c) => c.id);
    expect(ids).toEqual(["pending_approval", "verifier_flagged", "proposed", "rejected"]);
  });

  it("status di luar kosakata yang dikenal tetap muncul apa adanya", () => {
    const chips = feedChips([...DATA, row({ decision_id: "x", status: "menunggu_kepala" })]);
    const chip = chips.find((c) => c.id === "menunggu_kepala");
    expect(chip?.label).toBe("menunggu kepala");
    expect(chip?.count).toBe(1);
  });

  it("daftar kosong → tanpa chip (halaman tidak menampilkan filter kosong)", () => {
    expect(feedChips([])).toEqual([]);
    expect(feedChips(null)).toEqual([]);
  });

  it("baris tanpa status tidak dihitung ke chip mana pun", () => {
    expect(feedChips([row({ status: "" }), row({ status: null })])).toEqual([]);
  });
});

describe("feedVisible (cakupan + pencarian)", () => {
  it("cakupan 'action' hanya keputusan yang menunggu tindakan", () => {
    const list = feedVisible(DATA, { scope: "action", query: "" });
    expect(list.map((d: any) => d.decision_id)).toEqual(["id-approve-1", "id-approve-2", "id-flag-1"]);
  });

  it("cakupan status menyaring satu status saja", () => {
    const list = feedVisible(DATA, { scope: "rejected", query: "" });
    expect(list.map((d: any) => d.decision_id)).toEqual(["id-tolak-1"]);
  });

  it("cakupan 'all' tidak menyaring", () => {
    expect(feedVisible(DATA, { scope: "all", query: "" })).toHaveLength(DATA.length);
  });

  it("pencarian cocok dengan istilah MANUSIA pada kartu (bukan hanya enum)", () => {
    const list = feedVisible(DATA, { scope: "all", query: "harga" });
    expect(list.map((d: any) => d.decision_id)).toEqual(["id-harga-1", "id-approve-1"]);
  });

  it("pencarian cocok dengan awalan id keputusan", () => {
    const list = feedVisible(DATA, { scope: "all", query: "id-tolak" });
    expect(list).toHaveLength(1);
    expect(list[0].decision_id).toBe("id-tolak-1");
  });

  it("pencarian cocok dengan kata status manusia", () => {
    const list = feedVisible(DATA, { scope: "all", query: "ditolak" });
    expect(list).toHaveLength(1);
  });

  it("pencarian cocok dengan alasan penolakan yang benar-benar ada", () => {
    const list = feedVisible(DATA, { scope: "all", query: "kuota" });
    expect(list).toHaveLength(1);
    expect(list[0].decision_id).toBe("id-tolak-1");
  });

  it("kata kunci yang tidak ada → daftar kosong (bukan diam-diam semua)", () => {
    expect(feedVisible(DATA, { scope: "all", query: "wortel-di-bulan" })).toEqual([]);
  });

  it("cakupan dan kata kunci digabung (AND), bukan salah satu", () => {
    const list = feedVisible(DATA, { scope: "action", query: "keamanan" });
    expect(list.map((d: any) => d.decision_id)).toEqual(["id-flag-1"]);
  });
});

describe("sortFeed (urutan yang bisa dipertanggungjawabkan)", () => {
  it("'urgency': keputusan perlu-tindakan di paling atas, yang paling lama lewat dulu", () => {
    const out = sortFeed(DATA, "urgency", NOW).map((d: any) => d.decision_id);
    expect(out.slice(0, 3)).toEqual(["id-approve-1", "id-approve-2", "id-flag-1"]);
  });

  it("'urgency': sisanya berurut keamanan → ketidakseimbangan → harga, terbaru dulu", () => {
    const out = sortFeed(DATA, "urgency", NOW).map((d: any) => d.decision_id);
    expect(out.slice(3)).toEqual(["id-aman-1", "id-proposed-1", "id-tolak-1", "id-harga-1"]);
  });

  it("'due': tenggat terdekat dulu, yang sudah lewat diletakkan di akhir", () => {
    const out = sortFeed(DATA, "due", NOW).map((d: any) => d.decision_id);
    expect(out[0]).toBe("id-approve-1"); // 10 Okt — tenggat paling awal
    expect(out.slice(-1)[0]).toBe("id-flag-1"); // 15 Okt — tenggat paling akhir
  });

  it("'newest': dibuat terbaru dulu, tanggal tak terbaca di akhir tanpa diacak", () => {
    const data = [
      row({ decision_id: "a", created_at: "2026-10-01T00:00:00+00:00" }),
      row({ decision_id: "b", created_at: "bukan-tanggal" }),
      row({ decision_id: "c", created_at: "2026-10-13T00:00:00+00:00" }),
    ];
    expect(sortFeed(data, "newest", NOW).map((d: any) => d.decision_id)).toEqual(["c", "a", "b"]);
  });

  it("urutan tidak mengubah data (hanya memindah)", () => {
    const out = sortFeed(DATA, "urgency", NOW);
    expect(out).toHaveLength(DATA.length);
    expect(new Set(out.map((d: any) => d.decision_id))).toEqual(new Set(DATA.map((d: any) => d.decision_id)));
  });

  it("label urutan tersedia untuk kontrol di UI", () => {
    expect(Object.keys(FEED_SORT_LABELS)).toEqual(["urgency", "due", "newest"]);
    expect(FEED_SORT_LABELS.urgency).toContain("Urgensi");
  });
});

describe("feedSummary + hasActiveFilter", () => {
  it("ringkasan menyebut jumlah tampil/total dan filter yang aktif", () => {
    expect(
      feedSummary({ shown: 24, total: 42, scope: "pending_approval", query: "" })
    ).toBe("Menampilkan 24 dari 42 rekomendasi · filter: menunggu persetujuan");
  });

  it("ringkasan menyebut kata kunci bila ada", () => {
    expect(feedSummary({ shown: 2, total: 2, scope: "all", query: "harga" })).toBe(
      'Menampilkan 2 dari 2 rekomendasi · pencarian: "harga"'
    );
  });

  it("tanpa filter, ringkasannya polos", () => {
    expect(feedSummary({ shown: 24, total: 126, scope: "all", query: "" })).toBe(
      "Menampilkan 24 dari 126 rekomendasi"
    );
  });

  it("hasActiveFilter true hanya kalau ada cakupan/status atau kata kunci", () => {
    expect(hasActiveFilter({ scope: "all", query: "" })).toBe(false);
    expect(hasActiveFilter({ scope: "action", query: "" })).toBe(true);
    expect(hasActiveFilter({ scope: "all", query: "harga" })).toBe(true);
  });
});
