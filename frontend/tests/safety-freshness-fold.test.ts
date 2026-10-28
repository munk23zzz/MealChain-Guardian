// Dokumen `07-safety-evidence.md` §4.2 butir 3 — rincian kesegaran tidak boleh
// hanya hidup di dalam lipatan.
//
// Di repo ini skor kesegaran sudah tampil di kolom "Kesegaran" tabel status
// (tidak pernah tersembunyi), jadi yang ditambahkan di sini BUKAN lipatan baru
// yang menggantikan tabel — melainkan ringkasan tiga skor TERENDAH yang duduk
// terbuka, dengan sisanya di dalam satu lipatan untuk dipindai.
//
// Aturan yang dikunci:
//  - urutan dari skor terendah (yang paling perlu diperiksa lebih dulu);
//  - batch TANPA skor diletakkan paling akhir dan TIDAK pernah dihitung 0 —
//    kalau slot terbuka masih tersisa, batch tanpa skor tetap tidak mengisi
//    slot itu (0 akan terbaca "paling tidak segar", padahal tidak diukur);
//  - tidak ada angka karangan: skor yang tidak terbaca tetap `null`.
import { describe, expect, it } from "vitest";

import { lowestFreshness, safetyRows } from "../lib/food-safety";

const NOW = new Date("2026-10-11T06:00:00Z");

const BATCHES = [
  { id: "b1", location: "Cianjur", commodity: "beras", quantity_kg: 100, safety_status: "pass", freshness_score: 0.91, usable_until: "2026-11-11T06:00:00Z" },
  { id: "b2", location: "Cianjur", commodity: "telur", quantity_kg: 50, safety_status: "pass", freshness_score: 0.42, usable_until: "2026-10-20T06:00:00Z" },
  { id: "b3", location: "Cianjur", commodity: "ayam", quantity_kg: 30, safety_status: "fail", freshness_score: null, usable_until: null },
  { id: "b4", location: "Cianjur", commodity: "wortel", quantity_kg: 20, safety_status: "pass", freshness_score: 0.67, usable_until: "2026-10-25T06:00:00Z" },
  { id: "b5", location: "Cianjur", commodity: "beras", quantity_kg: 10, safety_status: "pass", freshness_score: 0.8, usable_until: "2026-11-01T06:00:00Z" },
];

describe("lowestFreshness — tiga terendah terbuka, sisanya di lipatan", () => {
  const rows = safetyRows(BATCHES, NOW);

  it("tiga skor terendah di depan, urut menaik", () => {
    const { open } = lowestFreshness(rows, 3);
    expect(open.map((row) => row.id)).toEqual(["b2", "b4", "b5"]);
    expect(open.map((row) => row.freshnessScore)).toEqual([0.42, 0.67, 0.8]);
  });

  it("sisa baris tetap dikembalikan (tidak ada yang dibuang)", () => {
    const { open, rest } = lowestFreshness(rows, 3);
    expect(rest.map((row) => row.id)).toEqual(["b1", "b3"]);
    expect(open.length + rest.length).toBe(rows.length);
  });

  it("batch tanpa skor diletakkan paling akhir dan tidak mengisi slot terbuka", () => {
    // 2 batch ber-skror + 1 tanpa skor, n = 3: slot ketiga dibiarkan kosong.
    const sebagian = safetyRows(BATCHES.slice(0, 3), NOW); // b2 (0,42), b1 (0,91), b3 (null)
    const { open, rest } = lowestFreshness(sebagian, 3);
    expect(open.map((row) => row.id)).toEqual(["b2", "b1"]);
    expect(rest.map((row) => row.id)).toEqual(["b3"]);
    expect(open.some((row) => row.freshnessScore === 0)).toBe(false);
  });

  it("skor tidak terbaca tetap null pada baris (tidak diganti 0)", () => {
    const { rest } = lowestFreshness(rows, 3);
    expect(rest.find((row) => row.id === "b3")?.freshnessScore).toBe(null);
    expect(rest.find((row) => row.id === "b3")?.freshness).toBe("—");
  });

  it("daftar kosong tidak melempar", () => {
    expect(lowestFreshness([], 3)).toEqual({ open: [], rest: [] });
  });
});
