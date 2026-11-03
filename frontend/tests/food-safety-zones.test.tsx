// Tiga zona halaman Keamanan Pangan (redesign 29 Okt 2026, tahap 1).
//
// Alasan: halaman ini menjawab satu pertanyaan lebih dulu ("ada yang harus saya
// tindak?"), baru tindakan, lalu daftar & bukti. Sebelumnya lima kartu bertumpuk
// tanpa penanda, sehingga pembaca harus menggulir buta untuk tahu di mana ia
// berada. Uji ini mengunci dua hal yang mudah rusak tanpa terlihat:
//
//   1. urutan zona A -> B -> C, dan setiap zona yang TAMPIL punya nama aksesibel;
//   2. label zona BUKAN heading — hierarki halaman tetap h1 -> h2 (judul kartu).
//
// 30 Okt 2026 — kontrak berubah: zona B ("Tindakan") hanya dirender bila ada
// isinya. Dulu kartu kosong "Tidak ada barang baru yang menunggu diuji …" selalu
// mengisi zona itu; kartu tersebut dihapus atas permintaan pemilik, jadi tanpa
// barang baru halaman tampil dua zona (A -> C), bukan tiga zona dengan label
// yang menggantung tanpa isi.
//
// Urutan kartu di dalam zona tetap dijaga `safety-section-order.test.ts`.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-11T06:00:00Z");
const BATCHES = [
  { id: "b1", location: "Cianjur", commodity: "telur", quantity_kg: 400, safety_status: "pass", freshness_score: 0.69, usable_until: "2026-10-11T18:00:00Z" },
  { id: "b2", location: "Surabaya", commodity: "ayam", quantity_kg: 120, safety_status: "fail", freshness_score: null, usable_until: null },
];
// 30 Okt 2026: kartu kosong "Tidak ada barang baru yang menunggu diuji …"
// dihapus atas permintaan pemilik, jadi zona B hanya ada bila ADA barang baru.
const BARU_TIBA = [
  {
    id: "jx1",
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 300,
    safety_status: "pending",
    freshness_score: 0.8,
    usable_until: "2026-11-07T12:00:00Z",
  },
];

function render(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
  return renderToStaticMarkup(<FoodSafetyBoard batches={BATCHES} now={NOW} {...props} />);
}

/** Id label zona yang muncul, berurutan sesuai dokumen. */
function urutanZona(html: string): string[] {
  return Array.from(html.matchAll(/id="(zona-[abc])-label"/g)).map((m) => m[1]);
}

describe("zona halaman Keamanan Pangan", () => {
  it("tanpa tindakan: dua zona tampil berurutan A -> C", () => {
    // Tidak ada barang baru menunggu diuji → tidak ada zona "Tindakan" kosong
    // yang hanya berisi label.
    expect(urutanZona(render())).toEqual(["zona-a", "zona-c"]);
  });

  it("ada barang baru menunggu diuji: zona B kembali muncul, A -> B -> C", () => {
    const html = render({ ownLocation: "Jakarta", ownLocationId: "loc-jkt", batches: BARU_TIBA });
    expect(urutanZona(html)).toEqual(["zona-a", "zona-b", "zona-c"]);
  });

  it("setiap zona yang tampil adalah region bernama (aria-labelledby ke label yang ada)", () => {
    const html = render({ ownLocation: "Jakarta", ownLocationId: "loc-jkt", batches: BARU_TIBA });
    for (const kunci of urutanZona(html)) {
      expect(html).toContain(`aria-labelledby="${kunci}-label"`);
      expect(html).toContain(`id="${kunci}-label"`);
    }
  });

  it("label zona bukan heading — hierarki h1 -> h2 tidak berubah", () => {
    const html = render({ ownLocation: "Jakarta", ownLocationId: "loc-jkt", batches: BARU_TIBA });
    // Label dirender sebagai paragraf, bukan h2/h3.
    expect(html).not.toMatch(/<h[1-6][^>]*id="zona-[abc]-label"/);
    // Tidak ada heading baru yang menyelip di antara judul kartu.
    const judulKartu = (html.match(/<h2/g) ?? []).length;
    expect(judulKartu).toBeGreaterThanOrEqual(3);
  });

  it("zona A memuat ringkasan+bukti, B memuat tindakan, C memuat daftar", () => {
    const html = render({ ownLocation: "Jakarta", ownLocationId: "loc-jkt", batches: BARU_TIBA });
    const posisi = (tanda: string) => html.indexOf(tanda);
    // A sebelum B sebelum C.
    expect(posisi('id="zona-a-label"')).toBeLessThan(posisi('id="zona-b-label"'));
    expect(posisi('id="zona-b-label"')).toBeLessThan(posisi('id="zona-c-label"'));
    // Isi tiap zona berada di dalam rentang zonanya.
    expect(posisi('id="safety-ringkasan"')).toBeGreaterThan(posisi('id="zona-a-label"'));
    expect(posisi('id="safety-ringkasan"')).toBeLessThan(posisi('id="zona-b-label"'));
    expect(posisi('id="safety-batch"')).toBeGreaterThan(posisi('id="zona-c-label"'));
  });
});
