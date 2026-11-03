// Tahap 1 redesein Recommendation Feed (30 Okt 2026): empat baris kendali
// (pencarian+urutan, periode, chip status, hitungan) disatukan jadi satu pita.
//
// Kenapa diperiksa di tingkat sumber, bukan render: halaman daftar rekomendasi
// adalah komponen klien raksasa (`app/page.tsx`, 2.500+ baris) yang butuh sesi
// login dan seluruh query hidup; tes ini menjaga hal yang memang bisa rusak
// tanpa terlihat — blok kendali kembali berserak dan membawa margin sendiri.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const AKAR = path.resolve(__dirname, "..");
const HALAMAN = fs.readFileSync(path.join(AKAR, "app/page.tsx"), "utf8");
const CSS = fs.readFileSync(path.join(AKAR, "app/globals.css"), "utf8");

/** Potong JSX tepat dari <div className="feed-kendali"> sampai penutupnya. */
function pitaKendali(sumber: string): string {
  const tanda = sumber.indexOf('className="feed-kendali"');
  expect(tanda, "pita .feed-kendali tidak ditemukan di app/page.tsx").toBeGreaterThan(-1);
  const buka = sumber.lastIndexOf("<div", tanda);
  const pola = /<div\b|<\/div>/g;
  pola.lastIndex = buka;
  let kedalaman = 0;
  let m: RegExpExecArray | null;
  while ((m = pola.exec(sumber))) {
    kedalaman += m[0] === "</div>" ? -1 : 1;
    if (kedalaman === 0) return sumber.slice(buka, m.index + m[0].length);
  }
  throw new Error("tag <div> pita kendali tidak pernah tertutup");
}

describe("pita kendali Recommendation Feed", () => {
  const pita = pitaKendali(HALAMAN);

  it("hanya ada satu pita, dan keempat blok kendali ada di dalamnya", () => {
    expect(HALAMAN.match(/className="feed-kendali"/g) ?? []).toHaveLength(1);
    for (const blok of ["feed-toolbar", 'kpi-period feed-period', "feed-filters", "feed-status-row"]) {
      expect(pita, `${blok} tidak berada di dalam pita`).toContain(blok);
    }
  });

  it("urutan blok di dalam pita tetap seperti sebelumnya (urutan Tab tidak berubah)", () => {
    const posisi = ["feed-toolbar", 'kpi-period feed-period', "feed-filters", "feed-status-row"].map(
      (blok) => pita.indexOf(blok)
    );
    const urut = [...posisi].sort((a, b) => a - b);
    expect(posisi).toEqual(urut);
    // Bidang pencarian tetap sebelum chip status — Tab dari pencarian mendarat
    // di urutan yang sama seperti sebelum penggabungan.
    expect(pita.indexOf('id="feed-search"')).toBeLessThan(pita.indexOf("feed-filters"));
  });

  it("tidak ada blok kendali yang tertinggal di luar pita", () => {
    const diLuar = HALAMAN.slice(0, HALAMAN.indexOf('className="feed-kendali"')) +
      HALAMAN.slice(HALAMAN.indexOf('className="feed-kendali"') + pita.length);
    for (const blok of ["feed-toolbar", "feed-filters", "feed-status-row"]) {
      expect(diLuar, `${blok} masih dipakai di luar pita`).not.toContain(`className="${blok}"`);
    }
  });

  it("CSS: pita membungkus baris dan margin anak-anaknya dinolkan", () => {
    const aturan = CSS.slice(CSS.indexOf(".feed-kendali {"));
    expect(aturan).toContain("flex-wrap: wrap");
    expect(aturan).toContain("align-items: flex-end");
    // Inti tahap ini: margin bawaan tiap blok tidak boleh bertumpuk lagi.
    const anak = ["feed-toolbar", "feed-period", "feed-filters", "feed-status-row", "feed-status"];
    for (const k of anak) {
      const blok = CSS.match(new RegExp(`\\.feed-kendali > \\.${k}\\s*\\{([^}]*)\\}`));
      expect(blok, `aturan .feed-kendali > .${k} tidak ada`).not.toBeNull();
      expect(blok![1]).toContain("margin: 0");
    }
  });

  it("CSS: di layar sempit pita menumpuk, bukan menggulir mendatar", () => {
    const media = CSS.slice(CSS.indexOf("@media (max-width: 720px)", CSS.indexOf(".feed-kendali {")));
    expect(media.slice(0, 400)).toContain("flex-direction: column");
    expect(media.slice(0, 400)).not.toContain("overflow-x");
  });
});
