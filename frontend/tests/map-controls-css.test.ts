import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak CSS kontrol peta (langkah 7b-1).
 *
 * Kenapa ada: dua kelas kesalahan di sini TIDAK bisa ditangkap tes unit biasa.
 *
 * 1) Tombol "Tampilkan semua" sempat TIDAK BISA DIKLIK walau terlihat: sudut
 *    kontrol MapLibre (`.maplibregl-ctrl-top-right`) memakai `pointer-events: none`
 *    dan mewariskannya ke anak. Kontrol bawaan diselamatkan oleh kelas
 *    `.maplibregl-ctrl { pointer-events: auto }` yang ditambahkan MapLibre, tapi
 *    kontrol buatan sendiri tidak dapat kelas itu. Ketahuan hanya saat Playwright
 *    menolak mengklik ("subtree intercepts pointer events").
 * 2) Chip peta (`min-height` kelas) MENANG atas `button { min-height: 44px }`
 *    sehingga tetap 24-26 px di ponsel walaupun ada komentar yang mengklaim
 *    44 px sudah berlaku — karena itu target sentuh ditulis EKSPLISIT.
 */
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

/** Isi blok deklarasi baris `selector { ... }` (tanpa sarang di dalamnya).
 *  Diikat ke AWAL BARIS supaya `.map-layer-toggle` tidak tertukar dengan
 *  varian berganda seperti `.map-overlay-toggles .map-layer-toggle`. */
function blok(selector: string): string {
  const cocok = new RegExp(`^${selector}\\s*\\{([^}]*)\\}`, "ms").exec(css);
  if (!cocok) throw new Error(`blok CSS tidak ditemukan: ${selector}`);
  return cocok[1];
}

/** Isi setiap blok `@media` yang judulnya memuat penanda tertentu. */
function blokMedia(penanda: string): string[] {
  const hasil: string[] = [];
  const pembuka = /@media[^{]*\{/g;
  let m: RegExpExecArray | null;
  while ((m = pembuka.exec(css)) !== null) {
    if (!m[0].includes(penanda)) continue;
    let i = m.index + m[0].length;
    let dalam = 1;
    const mulai = i;
    while (i < css.length && dalam > 0) {
      if (css[i] === "{") dalam++;
      else if (css[i] === "}") dalam--;
      i++;
    }
    hasil.push(css.slice(mulai, i));
  }
  return hasil;
}

describe("kontrak CSS kontrol peta (7b-1)", () => {
  it("tombol Tampilkan semua bisa DIKLIK (pointer-events auto, bukan mewarisi none)", () => {
    // Titik paling penting dari berkas ini: tanpa baris ini tombol hanya hiasan.
    expect(blok("\\.map-reset-view")).toMatch(/pointer-events:\s*auto/);
  });

  it("kontrol peta ringkas di desktop: chip tetap 26 px, bukan 44 px", () => {
    expect(blok("\\.map-layer-toggle")).toMatch(/min-height:\s*26px/);
  });

  it("chip peta naik ke 44 px di perangkat sentuh / jendela sempit", () => {
    const blokKontrol = blokMedia("(pointer: coarse), (max-width: 720px)");
    expect(blokKontrol.length).toBeGreaterThan(0);
    const gabungan = blokKontrol.join("\n");
    for (const selector of [
      "\\.map-layer-toggle",
      "\\.map-overlay-toggles \\.map-legend-toggle",
      "\\.map-layer-info-toggle",
      "\\.map-reset-view",
    ]) {
      expect(gabungan, `aturan 44px hilang untuk ${selector}`).toMatch(
        new RegExp(`${selector}[^{}]*\\{[^}]*min-height:\\s*44px|${selector}[^{}]*\\{[^}]*height:\\s*44px`)
      );
    }
  });

  it("grup kontrol MapLibre (zoom/kompas) juga 44 px di layar sentuh", () => {
    const gabungan = blokMedia("(pointer: coarse), (max-width: 720px)").join("\n");
    expect(gabungan).toMatch(/\.maplibregl-ctrl-group button[^{}]*\{[^}]*min-height:\s*44px/);
    expect(gabungan).toMatch(/\.maplibregl-ctrl-group button[^{}]*\{[^}]*min-width:\s*44px/);
  });

  it("bilah skala peta punya gaya sendiri (dibaca di atas peta terang)", () => {
    expect(blok("\\.map-shell \\.maplibregl-ctrl-scale")).toMatch(/background:/);
  });

  it("layar pesan gestur dipergelap: bawaan MapLibre terlalu tipis di atas peta terang", () => {
    const cssGestur = blok("\\.map-shell \\.maplibregl-cooperative-gesture-screen");
    expect(cssGestur).toMatch(/font-size:\s*var\(--fs-/);
    // Bawaan `rgba(0,0,0,.4)` hanya sekitar 2,8:1 dengan teks putih.
    expect(cssGestur).not.toMatch(/background:\s*rgba\(0,\s*0,\s*0,\s*\.?4\)/);
    expect(cssGestur).toMatch(/background:\s*rgba\(15,\s*23,\s*42/);
  });

  it("rincian Info map tidak lagi mengapung: ikut alur di bawah kanvas", () => {
    // Langkah 7b-2 (celah C5): satu-satunya elemen mengapung di kanvas adalah
    // pil kendali. Kalau panggung absolut ini kembali, artinya rincian legenda
    // bisa menutupi pin lagi — persis yang dilarang pemilik 2026-10-16.
    const cssLegenda = blok("\\.map-legend-detail");
    expect(cssLegenda).not.toMatch(/position:\s*absolute/);
    expect(cssLegenda).toMatch(/margin-top/);
    expect(blok("\\.map-overlay-toggles \\.map-legend-toggle")).toMatch(/border:\s*0/);
  });
});
