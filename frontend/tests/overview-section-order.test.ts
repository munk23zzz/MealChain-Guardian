// Urutan nav "Lompat ke bagian" HARUS sama dengan urutan bagian di halaman.
//
// Bug yang dijaga di sini (21 Okt 2026): nav Overview menaruh "Kiriman" di atas
// "Kecukupan", padahal `app/page.tsx` merender Kecukupan lebih dulu. Akibatnya
// mengeklik "Kiriman" menggulir MELEWATI Kecukupan — terasa seperti lompatannya
// ke-skip — dan penanda posisi berpindah tidak sesuai urutan yang dibaca mata.
//
// Uji ini TIDAK memeriksa tampilan: ia membaca berkas halaman dan membandingkan
// urutan kemunculan `id="ov-…"` dengan urutan yang dihasilkan `overviewSections`.
// Jadi kalau kelak salah satu sisi diubah sendiri-sendiri, tes ini yang lebih
// dulu merah — bukan pengguna yang menemukannya.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { overviewSections } from "../lib/section-jump";

const AKAR = join(__dirname, "..");

/** Urutan jangkar Overview sebagaimana ditulis di halaman. */
function urutanDiHalaman(): string[] {
  const isi = readFileSync(join(AKAR, "app/page.tsx"), "utf8");
  return Array.from(isi.matchAll(/id="(ov-[a-z-]+)"/g)).map((cocok) => cocok[1]);
}

describe("urutan bagian Overview", () => {
  it("nav mengikuti urutan render halaman", () => {
    const diHalaman = urutanDiHalaman();
    const diNav = overviewSections({ isApprover: true, hasShipments: true }).map((item) => item.id);
    // Halaman boleh memuat jangkar tambahan; yang wajib sama adalah urutan
    // bersama keduanya.
    const bersama = diHalaman.filter((id) => diNav.includes(id));
    expect(bersama).toEqual(diNav.filter((id) => diHalaman.includes(id)));
  });

  it("Kecukupan dirender sebelum Kiriman di halaman", () => {
    const diHalaman = urutanDiHalaman();
    expect(diHalaman.indexOf("ov-kecukupan")).toBeGreaterThan(-1);
    expect(diHalaman.indexOf("ov-kecukupan")).toBeLessThan(diHalaman.indexOf("ov-kiriman"));
  });

  it("peran non-approver tetap memakai urutan yang sama", () => {
    const ids = overviewSections({ isApprover: false, hasShipments: true }).map((item) => item.id);
    expect(ids.indexOf("ov-kecukupan")).toBeLessThan(ids.indexOf("ov-kiriman"));
    // Label berubah mengikuti peran, urutannya tidak.
    expect(overviewSections({ isApprover: false, hasShipments: true })).toContainEqual({
      id: "ov-kecukupan",
      label: "Pasokan per lokasi",
    });
  });
});
