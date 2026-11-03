// Kontrak CSS papan kiriman di layar sempit (S3, 29 Okt 2026).
//
// Sebabnya: papan ini punya sepuluh kolom. Di ponsel, tabel selebar itu hanya
// bisa dibaca dengan menggeser ke samping — dan kolom "Keadaan" (yang justru
// paling sering dicari) ada di ujung kanan. Aturan di globals.css kini
// mengubah tiap baris menjadi kartu berlabel di bawah 760 px, sama seperti
// `.safety-table`.
//
// Yang dikunci di sini: ambangnya ada, kepala tabel disembunyikan, label sel
// datang dari `data-label`, dan tidak ada nilai mentah di luar skala token.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");

function blokMedia(ambang: string, penanda: string): string {
  const kepala = `@media (max-width: ${ambang})`;
  let dari = 0;
  while (dari < css.length) {
    const mulai = css.indexOf(kepala, dari);
    if (mulai === -1) break;
    let dalam = 0;
    const awal = css.indexOf("{", mulai);
    let tutup = -1;
    for (let i = awal; i < css.length; i += 1) {
      if (css[i] === "{") dalam += 1;
      if (css[i] === "}") {
        dalam -= 1;
        if (dalam === 0) {
          tutup = i;
          break;
        }
      }
    }
    const isi = css.slice(awal, tutup + 1);
    // Blok pertama dengan ambang yang sama bukan milik papan kiriman: ambil
    // yang benar-benar memuat selektornya. Lanjut SESUDAH blok ini — versi lama
    // melompati kepala blok berikutnya sehingga dua blok sekali lewat, dan
    // pemeriksaan gagal begitu ada blok 760 px baru di atas blok papan kiriman.
    if (isi.includes(penanda)) return isi;
    dari = tutup + 1;
  }
  throw new Error(`blok @media (max-width: ${ambang}) untuk ${penanda} tidak ditemukan`);
}

const blok = blokMedia("760px", ".shipment-table");

describe("papan kiriman di layar sempit", () => {
  it("kepala tabel disembunyikan dan baris menjadi blok", () => {
    expect(blok).toMatch(/\.shipment-table thead\s*\{[^}]*display:\s*none/);
    expect(blok).toMatch(/\.shipment-table tr\s*,\s*\.shipment-table td/);
    expect(blok).toMatch(/\.shipment-table td\s*\{[^}]*display:\s*block|\.shipment-table td\s*\{[^}]*display:\s*flex/);
  });

  it("label sel datang dari data-label, bukan teks yang ditulis dua kali", () => {
    expect(blok).toMatch(/\.shipment-table td::before\s*\{[^}]*content:\s*attr\(data-label\)/);
  });

  it("judul kartu = nama pemasok (th scope=row)", () => {
    expect(blok).toMatch(/\.shipment-table th\[scope="row"\]/);
  });

  it("ukuran huruf & radius memakai token, bukan piksel mentah", () => {
    const ukuranMentah = [...blok.matchAll(/font-size:\s*([^;]+);/g)]
      .map((m) => m[1].trim())
      .filter((v) => !v.startsWith("var(--fs-"));
    expect(ukuranMentah).toEqual([]);
    const radiusMentah = [...blok.matchAll(/border-radius:\s*([^;]+);/g)]
      .map((m) => m[1].trim())
      .filter((v) => !v.startsWith("var(--radius"));
    expect(radiusMentah).toEqual([]);
  });
});
