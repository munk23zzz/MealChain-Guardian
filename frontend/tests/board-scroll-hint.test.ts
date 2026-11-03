import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Petunjuk "Geser tabel ke samping" — kontrak CSS-nya.
 *
 * Riwayat singkat: semula tampil hanya di `max-width: 640px`, lalu dinaikkan ke 900 px
 * (langkah 3). Hasil ukur lalu membuktikan ambang lebar hanyalah PROKSI dari "tabel
 * benar-benar meluap": tabel "Daftar pemasok" butuh wadah >= 879 px, sehingga pada
 * 901–1150 px tabelnya bisa digeser TANPA petunjuk. Karena itu (langkah 4) tampilnya
 * ditentukan pengukuran luapan nyata di `components/ScrollHint.tsx` (`data-tampil`),
 * dan CSS tidak lagi boleh mengikat kelas ini ke ambang lebar layar.
 */
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

/** Isi setiap blok `@media` (dengan hitung kurung, supaya sarang di dalamnya ikut). */
function isiBlokMedia(teks: string): string[] {
  const hasil: string[] = [];
  const pembuka = /@media[^{]*\{/g;
  let m: RegExpExecArray | null;
  while ((m = pembuka.exec(teks)) !== null) {
    let i = m.index + m[0].length;
    let dalam = 1;
    const mulai = i;
    while (i < teks.length && dalam > 0) {
      if (teks[i] === "{") dalam++;
      else if (teks[i] === "}") dalam--;
      i++;
    }
    hasil.push(teks.slice(mulai, i));
  }
  return hasil;
}

describe("petunjuk geser tabel (`.board-scroll-hint`)", () => {
  it("sembunyi secara bawaan — tanpa pengukuran, jangan menebak", () => {
    expect(css).toMatch(/\.board-scroll-hint\s*\{[^}]*display:\s*none/);
  });

  it("tampil hanya saat pengukuran menyatakan tabel meluap", () => {
    expect(css).toMatch(/\.board-scroll-hint\[data-tampil="true"\]\s*\{[^}]*display:\s*block/);
  });

  it("tidak lagi diikat ambang lebar layar (proksi yang menyisakan zona senyap)", () => {
    const diDalamMedia = isiBlokMedia(css).filter((isi) => isi.includes(".board-scroll-hint"));
    expect(diDalamMedia, "petunjuk geser tidak boleh diatur ambang lebar layar").toEqual([]);
  });
});
