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

  it("sakelar lapisan ikon: 32 px persegi di desktop, bukan chip berteks", () => {
    const tombol = blok("\\.map-layer-toggle");
    expect(tombol).toMatch(/width:\s*32px/);
    expect(tombol).toMatch(/height:\s*32px/);
    // Tidak ada lagi teks di dalam tombol, jadi jangan ada padding horizontal
    // yang menyisakan ruang untuk label (ikon dipusatkan dengan flex).
    expect(tombol).toMatch(/display:\s*inline-flex/);
    expect(tombol).toMatch(/justify-content:\s*center/);
  });

  it("keadaan MATI ditandai garis miring — bukan hanya warna", () => {
    // ui-ux-pro-max prioritas 1: makna tidak boleh disampaikan warna saja.
    const aturan = css.match(
      /\.map-layer-toggle\[aria-pressed="false"\] \.map-layer-toggle-icon::after\s*\{([^}]*)\}/
    );
    expect(aturan, "garis miring untuk keadaan mati hilang").toBeTruthy();
    expect(aturan?.[1]).toMatch(/transform:\s*rotate\(-45deg\)/);
  });

  it("chip peta naik ke 44 px di perangkat sentuh / jendela sempit", () => {
    const blokKontrol = blokMedia("(pointer: coarse), (max-width: 720px)");
    expect(blokKontrol.length).toBeGreaterThan(0);
    const gabungan = blokKontrol.join("\n");
    for (const selector of [
      "\\.map-layer-toggle",
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

  it("bilah skala dihapus: kiri-bawah milik pil sakelar lapisan", () => {
    // Keputusan pemilik 19 Okt 2026 ("info km di kiri-bawah hapus saja").
    expect(css).not.toMatch(/\.maplibregl-ctrl-scale\s*\{/);
  });

  it("pil sakelar pindah ke KIRI-BAWAH dan piring putihnya dihapus", () => {
    const pil = blok("\\.map-overlay-toggles");
    expect(pil).toMatch(/bottom:\s*8px/);
    expect(pil).toMatch(/left:\s*8px/);
    expect(pil).toMatch(/background:\s*transparent/);
    // Tanpa piring: tidak ada latar permukaan, bingkai, atau bayangan.
    expect(pil).not.toMatch(/background:\s*var\(--surface\)/);
    expect(pil).not.toMatch(/box-shadow/);
    expect(pil).toMatch(/border:\s*0/);
  });

  it("tombol pil transparan saat diam; plat hover = kaca gelap tema (bukan putih)", () => {
    const tombol = blok("\\.map-layer-toggle");
    expect(tombol).toMatch(/background:\s*transparent/);
    // Kontras ikon dijaga halo putih tipis, bukan kotak latar.
    expect(tombol).toMatch(/filter:\s*drop-shadow/);
    // Plat hover/fokus TIDAK putih: tema konsol memakai kaca gelap. Nilainya
    // ditulis sama di globals.css dengan fallback supaya hasil tidak bergantung
    // urutan berkas CSS.
    const hover = /^\.map-card \.map-overlay-toggles \.map-layer-toggle:hover,\s*\n\.map-card \.map-overlay-toggles \.map-layer-toggle:focus-visible \{([^}]*)\}/m.exec(css)?.[1] ?? "";
    const latar = /background:\s*([^;]+);/.exec(hover)?.[1] ?? "";
    expect(latar).toMatch(/var\(--map-glass-deep/);
    expect(latar).not.toMatch(/#fff|rgba\(255/);
  });

  it("layar pesan gestur dipergelap: bawaan MapLibre terlalu tipis di atas peta terang", () => {
    const cssGestur = blok("\\.map-shell \\.maplibregl-cooperative-gesture-screen");
    expect(cssGestur).toMatch(/font-size:\s*var\(--fs-/);
    // Bawaan `rgba(0,0,0,.4)` hanya sekitar 2,8:1 dengan teks putih.
    expect(cssGestur).not.toMatch(/background:\s*rgba\(0,\s*0,\s*0,\s*\.?4\)/);
    expect(cssGestur).toMatch(/background:\s*rgba\(15,\s*23,\s*42/);
  });

  it("cincin fokus pil memakai tinta gelap + halo putih, BUKAN --map-focus", () => {
    // Terukur 19 Okt 2026: --map-focus #7dd3fc hanya 1,43:1 di atas ubin peta
    // terang (gagal WCAG 1.4.11 / 2.4.7), karena token itu dirancang untuk kaca
    // konsol GELAP. Pil kini transparan di atas peta terang.
    // Selector yang sama dipakai dua aturan (hover dan fokus khusus), jadi
    // ambil SEMUA blok dengan selector itu dan cari yang berisi `outline`.
    const semua = Array.from(css.matchAll(/^\.map-card \.map-overlay-toggles \.map-layer-toggle:focus-visible \{([^}]*)\}/gm), (m) => m[1]);
    const fokus = semua.find((isi) => isi.includes("outline")) ?? "";
    // Dua lapis: cincin PUTIH di dalam (piringan fokus gelap) + halo tinta
    // gelap di luar (ubin peta terang). Satu warna saja selalu hilang di salah
    // satu sisi.
    expect(fokus).toMatch(/outline:\s*2px solid rgba\(255,\s*255,\s*255/);
    expect(fokus).toMatch(/box-shadow:\s*0 0 0 5px rgba\(15,\s*23,\s*42/);
    expect(fokus).not.toMatch(/outline:\s*none/);
  });

  it("pil 'Pilih kiriman' minimal 28 px di desktop (WCAG 2.5.8: 24 px, terukur 22)", () => {
    const pil = blok("\\.map-card \\.route-focus-pill");
    expect(pil).toMatch(/min-height:\s*28px/);
  });

  it("panel 'Info map' yang terpisah sudah tidak ada (dilebur ke rincian lapisan)", () => {
    // 19 Okt 2026: isinya duplikat baris legenda, jadi panelnya dihapus. Kalau
    // kelas ini kembali, berarti legenda dibaca di dua tempat lagi.
    expect(css).not.toContain(".map-legend-toggle");
    expect(css).not.toContain(".map-legend-detail");
    // Legenda ringkas (yang terbaca tanpa klik) tetap punya gayanya sendiri.
    expect(css).toContain(".map-legend-compact");
  });
});
