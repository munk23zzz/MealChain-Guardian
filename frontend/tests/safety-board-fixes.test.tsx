// Dokumen `07-safety-evidence.md` §4.2 — empat perbaikan yang menyentuh
// halaman "Keamanan Pangan" (`components/FoodSafetyBoard.tsx`):
//
//   butir 1  postur → gerbang: baris batch bisa menyaring daftar keputusan
//            keamanan menurut komoditasnya (data klien, tanpa endpoint baru);
//   butir 3  kesegaran: tiga skor terendah terbuka + sisanya di lipatan,
//            dengan catatan "skor kosong ≠ 0" dan batas data;
//   butir 5  keterangan cakupan: satu baris yang menegaskan bahwa saringan di
//            bilah alat hanya menyaring BATCH, sedangkan daftar keputusan punya
//            saringan sendiri;
//   butir 6  ekspor baca-saja CSV/JSON dari nilai yang tampil.
//
// Butir 4 (penanda mendekati kedaluwarsa) TIDAK diuji ulang di sini: perilakunya
// sudah ada (`expiryState` + kolom "Sisa masa") dan tesnya ada di
// `food-safety.test.ts` / `food-safety-board.test.tsx`.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

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
    location: "Cianjur",
    commodity: "ayam",
    quantity_kg: 120,
    safety_status: "fail",
    freshness_score: 0.31,
    usable_until: "2026-10-12T18:00:00Z",
  },
  {
    id: "b3",
    location: "Cianjur",
    commodity: "beras",
    quantity_kg: 300,
    safety_status: "pass",
    freshness_score: null,
    usable_until: null,
  },
  {
    id: "b4",
    location: "Cianjur",
    commodity: "wortel",
    quantity_kg: 90,
    safety_status: "pass",
    freshness_score: 0.55,
    usable_until: "2026-10-13T18:00:00Z",
  },
];

const DECISIONS = [
  {
    decision_id: "d1",
    decision_type: "safety_disruption",
    status: "pending_approval",
    quantity_kg: 492,
    valid: true,
    seconds_remaining: 600,
    created_at: "2026-10-11T05:00:00Z",
    commodity_name: "ayam",
  },
  {
    decision_id: "d2",
    decision_type: "safety_disruption",
    status: "rejected",
    quantity_kg: 80,
    valid: false,
    seconds_remaining: 0,
    created_at: "2026-10-11T04:00:00Z",
    commodity_name: "telur",
  },
];

function render(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
  return renderToStaticMarkup(<FoodSafetyBoard batches={BATCHES} now={NOW} {...props} />);
}

function kartu(html: string, id: string): string {
  const mulai = html.indexOf(`id="${id}"`);
  expect(mulai, `kartu #${id} tidak dirender`).toBeGreaterThan(-1);
  return html.slice(mulai, html.indexOf("</article>", mulai));
}

describe("butir 1 — baris batch menyaring daftar keputusan keamanan", () => {
  it("pilihan saringan memuat komoditas yang ada di keputusan", () => {
    const html = kartu(render({ decisions: DECISIONS }), "safety-keputusan");
    expect(html).toContain("Semua komoditas");
    expect(html).toContain("ayam");
    expect(html).toContain("telur");
    // Tidak ada komoditas yang tidak punya keputusan keamanan.
    expect(html).not.toContain("wortel");
  });

  it("baris batch ber-komoditas ber-keputusan mendapat tombol lompat", () => {
    const html = render({ decisions: DECISIONS });
    expect(html).toContain('aria-label="Lihat keputusan keamanan telur"');
    expect(html).toContain('aria-label="Lihat keputusan keamanan ayam"');
    // beras tidak punya keputusan keamanan → tombolnya tidak dipasang.
    expect(html).not.toContain('aria-label="Lihat keputusan keamanan beras"');
  });

  it("tanpa data keputusan, tidak ada tombol lompat yang menjanjikan tujuan kosong", () => {
    const html = render();
    expect(html).not.toContain("Lihat keputusan keamanan");
    expect(html).not.toContain("Semua komoditas");
  });
});

describe("butir 3 — kesegaran tiga terendah terbuka", () => {
  it("blok kesegaran menampilkan tiga terendah dan tidak menyembunyikan sisanya", () => {
    const html = kartu(render(), "safety-segar");
    expect(html).toContain("Kesegaran terendah");
    // b2 (31%) → b4 (55%) → b1 (69%) terbuka; b3 (tanpa skor) di lipatan.
    const urut = ["31%", "55%", "69%"].map((teks) => html.indexOf(teks));
    expect(urut.every((posisi) => posisi > -1)).toBe(true);
    expect(urut[0]).toBeLessThan(urut[1]);
    expect(urut[1]).toBeLessThan(urut[2]);
    expect(html).toContain("<details");
    expect(html).toContain("1 batch lain");
  });

  it("kartu kesegaran berdiri sendiri, bukan kartu bersarang di dalam kartu lain", () => {
    // Kartu `.card` di dalam `.card` menumpuk bingkai dan latar; ringkasan
    // kesegaran harus jadi kartu saudara, bukan isi kartu "segera dipakai".
    const html = render();
    const segera = kartu(html, "safety-segera");
    expect(segera).not.toContain("Kesegaran terendah");
    const segar = kartu(html, "safety-segar");
    expect(segar).toContain("Kesegaran terendah");
  });

  it("catatan skor kosong ≠ 0 dan batas data tetap terbaca di luar lipatan", () => {
    const html = kartu(render(), "safety-segar");
    expect(html).toContain("Skor kosong ditulis");
    expect(html).toContain("tidak pernah dibaca sebagai 0");
    expect(html).toContain("maksimum 500 baris terbaru");
  });
});

describe("butir 5 — keterangan cakupan dua penyaring berbeda", () => {
  it("menulis satu baris cakupan di bawah bilah saring batch", () => {
    const html = kartu(render({ decisions: DECISIONS }), "safety-batch");
    expect(html).toContain("hanya menyaring daftar batch");
    expect(html).toContain("saringan komoditas sendiri");
  });
});

describe("butir 6 — ekspor baca-saja", () => {
  it("menyediakan CSV dan JSON dari nilai yang tampil", () => {
    const html = kartu(render(), "safety-batch");
    expect(html).toContain("Ekspor CSV");
    expect(html).toContain("Ekspor JSON");
  });
});
