// Recommendation Feed memakai pagination 10 kartu per halaman, bukan tombol
// "tampilkan lagi". Kontrak ini mengikat halaman ke komponen Pager yang sama
// dengan Daftar Pemasok/Papan Kiriman supaya perilaku dan bahasanya seragam.

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { paginate } from "../lib/pagination";

const pageSrc = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");

describe("Recommendation Feed — pagination", () => {
  it("membagi 24 rekomendasi menjadi 10 + 10 + 4", () => {
    const rows = Array.from({ length: 24 }, (_, i) => ({ id: i + 1 }));
    expect(paginate(rows, 1, 10).items).toHaveLength(10);
    expect(paginate(rows, 2, 10).items).toHaveLength(10);
    expect(paginate(rows, 3, 10).items).toHaveLength(4);
    expect(paginate(rows, 3, 10).pageCount).toBe(3);
  });

  it("memotong feed menjadi 10 kartu per halaman lewat paginate()", () => {
    expect(pageSrc).toMatch(/const FEED_PAGE_SIZE = 10;/);
    expect(pageSrc).toMatch(/paginate\(feedRows, feedPage, FEED_PAGE_SIZE\)/);
    expect(pageSrc).toMatch(/<Pager\s+page=\{feedPageData\}/);
    expect(pageSrc).toMatch(/label="rekomendasi"/);
  });

  it("tidak lagi memakai tombol 'Tampilkan … lagi'", () => {
    expect(pageSrc).not.toMatch(/feedLimit|setFeedLimit/);
    expect(pageSrc).not.toMatch(/Tampilkan \{Math\.min\(/);
  });

  it("mengembalikan pembaca ke halaman 1 saat pencarian, urutan, atau filter berubah", () => {
    expect(pageSrc).toMatch(/setFeedQuery\(e\.target\.value\);\s*setFeedPage\(1\);/);
    expect(pageSrc).toMatch(/setFeedSort\(e\.target\.value as FeedSort\);\s*setFeedPage\(1\);/);
    // Tahap 2 (30 Okt 2026): bentuknya berubah karena chip kini punya keadaan
    // sendiri (`aktif` dipakai juga untuk `aria-pressed`, `disabled`, dan label).
    // Yang diuji tetap PERILAKUNYA: menekan chip yang sedang aktif melepas
    // saringan ke FEED_SCOPE_ALL, menekan chip lain memilih chip itu — lalu
    // daftar kembali ke halaman 1.
    expect(pageSrc).toMatch(/const aktif = feedScope === chip\.id;/);
    expect(pageSrc).toMatch(/setFeedScope\(aktif \? FEED_SCOPE_ALL : chip\.id\);\s*setFeedPage\(1\);/);
    expect(pageSrc).toMatch(/setFeedQuery\(""\);\s*setFeedPage\(1\);/);
  });
});
