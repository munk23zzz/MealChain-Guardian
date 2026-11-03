// Tahap 6 redesign Recommendation Feed (30 Okt 2026): kepadatan, responsif,
// dan gerak. Diperiksa di tingkat CSS karena yang berubah hanya tata letak —
// markup kartu tidak disentuh (itu milik tahap 3–5 dan sudah dipin tes lain).
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const CSS = fs.readFileSync(path.resolve(__dirname, "../app/globals.css"), "utf8");
const BERSIH = CSS.replace(/\/\*[\s\S]*?\*\//g, "");

/** Aturan EFEKTIF: kemunculan terakhir — CSS memakai urutan berkas sebagai
 *  penentu, dan sampai tahap 7 selektor `.feed` masih muncul dua kali. */
function aturan(sel: string): string {
  const i = BERSIH.lastIndexOf(`${sel} {`);
  expect(i, `aturan ${sel} tidak ditemukan`).toBeGreaterThan(-1);
  return BERSIH.slice(BERSIH.indexOf("{", i) + 1, BERSIH.indexOf("}", i));
}

/** Blok `@media` pertama yang memuat `penanda`. */
function media(pembuka: string, penanda: string): string {
  let i = BERSIH.indexOf(pembuka);
  while (i > -1) {
    const buka = BERSIH.indexOf("{", i);
    let kedalaman = 0;
    let akhir = -1;
    for (let j = buka; j < BERSIH.length; j += 1) {
      if (BERSIH[j] === "{") kedalaman += 1;
      else if (BERSIH[j] === "}") {
        kedalaman -= 1;
        if (kedalaman === 0) {
          akhir = j;
          break;
        }
      }
    }
    const isi = BERSIH.slice(buka, akhir);
    if (isi.includes(penanda)) return isi;
    i = BERSIH.indexOf(pembuka, akhir);
  }
  throw new Error(`tidak ada ${pembuka} yang memuat ${penanda}`);
}

describe("Tahap 6 — kepadatan, responsif, dan gerak feed", () => {
  it("jarak antar kartu 10 px: satu daftar, bukan sepuluh kotak", () => {
    expect(aturan(".feed")).toContain("gap: 10px");
  });

  it("≤720 px: kendali menumpuk dan tombol Tinjau selebar kartu ≥ 44 px", () => {
    const blok = media("@media (max-width: 720px)", ".rec-act-btn");
    // Pencarian selebar penuh — dulu 260 px + pemilih urutan di sebelahnya.
    expect(blok).toContain(".feed-field-search");
    expect(blok).toContain("flex: 1 1 100%");
    // Tombol aksi kartu melebar mengisi baris kartu, tetap 44 px.
    expect(blok).toContain(".rec-act { width: 100% }");
    expect(blok).toContain("min-height: 44px");
  });

  it("kartu pertama punya jarak aman terhadap bilah lengket", () => {
    expect(BERSIH).toContain(".feed > div:first-child { scroll-margin-top: 128px; }");
  });

  it("gerak masuk hanya untuk enam baris pertama dan dipagari reduced-motion", () => {
    const reduce = media("@media (prefers-reduced-motion: reduce)", ".feed > div");
    expect(reduce).toContain("animation: none");

    // Tidak ada animasi baru pada kelas feed/rec di luar `.feed > div`.
    const animasi = [...BERSIH.matchAll(/([^\n{}]*\{[^}]*animation:[^}]*\})/g)]
      .map((m) => m[1])
      .filter((blok) => /\.(feed|rec-)/.test(blok.split("{")[0]));
    expect(animasi.map((b) => b.split("{")[0].trim())).toEqual([".feed > div"]);

    // Yang dianimasikan hanya enam baris pertama: delay eksplisit berhenti di 6.
    expect(BERSIH).toContain(".feed > div:nth-child(6) { animation-delay: 175ms; }");
    expect(BERSIH).not.toContain(".feed > div:nth-child(7)");
  });
});
