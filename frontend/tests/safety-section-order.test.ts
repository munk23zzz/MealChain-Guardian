// Urutan bagian halaman Keamanan Pangan HARUS sama dengan urutan nav
// "Lompat ke bagian".
//
// Alasan (27 Okt 2026, permintaan pemilik: "atur urutan dari tiap bagian"):
// halaman ini mengalir keadaan → bukti → tindakan tulis → rujukan panjang →
// konteks → jejak audit. Kartu "Pasokan masuk" dulu duduk di antara dua kartu
// bertindak (Penerimaan dan Menunggu persetujuan) sehingga memutus urutan
// tindakan; sekarang ia berada setelah tabel Status per batch.
//
// Uji ini tidak memeriksa tampilan: ia membaca berkas komponen dan
// membandingkan urutan jangkar di sana dengan urutan yang dihasilkan
// `safetySections`. Kalau salah satu sisi diubah sendiri-sendiri, tes ini yang
// lebih dulu merah.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { SAFETY_SECTION_IDS, safetySections } from "../lib/section-jump";

const AKAR = join(__dirname, "..");

/**
 * Urutan jangkar Keamanan Pangan sebagaimana dirender.
 *
 * `safety-bukti-suhu` dipasang di dalam `BatchPerhatianCard`, jadi yang dicatat
 * di sini adalah POSISI pemakaian komponennya (`<BatchPerhatianCard`), bukan id
 * yang tertulis di berkas itu sendiri.
 */
function urutanDiHalaman(): string[] {
  const isi = readFileSync(join(AKAR, "components/FoodSafetyBoard.tsx"), "utf8");
  const pola = /id="(safety-[a-z-]+)"|anchor="(safety-[a-z-]+)"|<BatchPerhatianCard/g;
  const hasil: string[] = [];
  for (const cocok of Array.from(isi.matchAll(pola))) {
    const id =
      cocok[1] ??
      cocok[2] ??
      (cocok[0] === "<BatchPerhatianCard" ? SAFETY_SECTION_IDS.bukti : undefined);
    if (!id || hasil.includes(id)) continue;
    hasil.push(id);
  }
  return hasil;
}

describe("urutan bagian Keamanan Pangan", () => {
  it("nav mengikuti urutan render halaman", () => {
    const diHalaman = urutanDiHalaman();
    const diNav = safetySections({ ownLocation: true, hasDecisions: true }).map((item) => item.id);
    // Halaman memuat lebih banyak bagian daripada nav (jatah lima tujuan);
    // yang wajib sama adalah urutan bagian yang muncul di keduanya.
    const bersama = diHalaman.filter((id) => diNav.includes(id));
    expect(bersama).toEqual(diNav.filter((id) => diHalaman.includes(id)));
  });

  it("nav tidak melebihi lima tujuan", () => {
    expect(safetySections({ ownLocation: true, hasDecisions: true }).length).toBeLessThanOrEqual(5);
  });

  it("tindakan lebih dulu, konteks kiriman sesudah rujukan", () => {
    const diHalaman = urutanDiHalaman();
    const posisi = (id: string) => diHalaman.indexOf(id);
    // Keadaan dan bukti di atas.
    expect(posisi(SAFETY_SECTION_IDS.ringkasan)).toBe(0);
    expect(posisi(SAFETY_SECTION_IDS.bukti)).toBe(1);
    // Tindakan tulis: penerimaan lalu persetujuan, berdampingan.
    expect(posisi(SAFETY_SECTION_IDS.terima)).toBeLessThan(posisi(SAFETY_SECTION_IDS.persetujuan));
    expect(posisi(SAFETY_SECTION_IDS.persetujuan)).toBeLessThan(posisi(SAFETY_SECTION_IDS.batch));
    // Rujukan (tabel) sebelum konteks (kiriman) sebelum jejak audit.
    expect(posisi(SAFETY_SECTION_IDS.batch)).toBeLessThan(posisi(SAFETY_SECTION_IDS.kiriman));
    expect(posisi(SAFETY_SECTION_IDS.kiriman)).toBeLessThan(posisi(SAFETY_SECTION_IDS.keputusan));
  });
});
