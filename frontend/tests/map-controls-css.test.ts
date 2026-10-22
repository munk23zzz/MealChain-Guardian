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

  it("kontrol peta naik ke 44 px di perangkat sentuh / jendela sempit", () => {
    const blokKontrol = blokMedia("(pointer: coarse), (max-width: 720px)");
    expect(blokKontrol.length).toBeGreaterThan(0);
    const gabungan = blokKontrol.join("\n");
    // Tombol lapisan sudah dihapus (20 Okt 2026); yang tersisa tetap wajib 44 px.
    for (const selector of ["\\.map-layer-info-toggle", "\\.map-reset-view"]) {
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

  it("pin pemasok yang sedang mengirim: isian violet + halo, bukan cincin hijau", () => {
    // Audit 22 Okt 2026: dulu ada DUA blok dengan selektor yang SAMA. Blok
    // pertama (cincin hijau --status-safe) menang cascade, sehingga aturan
    // violet di bawahnya tidak pernah berlaku — dan tes lama justru mengunci
    // cincin itu, jadi terasa aman. Sekarang: tepat satu blok, dan isinya violet.
    const semua = Array.from(
      css.matchAll(/\.map-pin-supplier-shipping \.map-pin-supplier-dot \{([^}]*)\}/g)
    );
    expect(semua.length, "selektor dasar pin pengirim harus tunggal").toBe(1);
    const aturan = semua[0][1];
    expect(aturan).toMatch(/background:\s*var\(--status-live\)/);
    expect(aturan).toMatch(/border-color:\s*var\(--status-live\)/);
    expect(aturan).not.toMatch(/--status-safe/);
    // Halo membawa arti "masih di jalan" (bukan hiasan) → dimatikan saat
    // reduced-motion, bukan dihapus.
    expect(css).toMatch(/@keyframes pin-kirim-halo\s*\{/);
    const kurangiGerak =
      /@media \(prefers-reduced-motion: reduce\) \{\s*\.map-pin-supplier-shipping \.map-pin-supplier-dot::after \{([^}]*)\}/
        .exec(css)?.[1] ?? "";
    expect(kurangiGerak).toMatch(/animation:\s*none/);
  });

  it("contoh garis legenda memakai warna kanvas yang sama (tanpa drift)", () => {
    // Legend yang menjanjikan warna berbeda dari kanvas = dua cerita warna.
    // Nilai token di sini WAJIB sama dengan ROUTE_DONE_COLORS / ROUTE_TODO_COLORS
    // dan warna layer "sudah tiba" di SupplyMap.
    expect(css).toMatch(/\.map-legend-line-ok\s*\{[^}]*border-top-color:\s*var\(--route-live-strong\)/);
    expect(css).toMatch(/\.map-legend-line-sisa\s*\{[^}]*border-top-color:\s*var\(--route-live-soft\)/);
    expect(css).toMatch(/\.map-legend-line-tiba\s*\{[^}]*border-top-color:\s*var\(--route-arrived\)/);
    expect(css).not.toMatch(/\.map-legend-line-sisa\s*\{[^}]*--accent-strong/);
    expect(css).toMatch(/--route-live-strong:\s*#7C3AED/);
    expect(css).toMatch(/--route-live-soft:\s*#8B5CF6/);
    expect(css).toMatch(/--route-arrived:\s*#475569/);
  });

  it("layar pesan gestur dipergelap: bawaan MapLibre terlalu tipis di atas peta terang", () => {
    const cssGestur = blok("\\.map-shell \\.maplibregl-cooperative-gesture-screen");
    expect(cssGestur).toMatch(/font-size:\s*var\(--fs-/);
    // Bawaan `rgba(0,0,0,.4)` hanya sekitar 2,8:1 dengan teks putih.
    expect(cssGestur).not.toMatch(/background:\s*rgba\(0,\s*0,\s*0,\s*\.?4\)/);
    expect(cssGestur).toMatch(/background:\s*rgba\(15,\s*23,\s*42/);
  });

  it("pil 'Pilih kiriman' minimal 28 px di desktop (WCAG 2.5.8: 24 px, terukur 22)", () => {
    const pil = blok("\\.map-card \\.route-focus-pill");
    expect(pil).toMatch(/min-height:\s*28px/);
  });

  it("pil 'Pilih kiriman' kembali 44 px di layar sentuh", () => {
    // Kelas (0,3,0) MENANG atas `button { min-height: 44px }` (0,0,1); tanpa
    // aturan eksplisit di media block, pil jatuh ke 28 px di ponsel (terukur).
    const sentuh = blokMedia("pointer: coarse").join("\n");
    expect(sentuh).toMatch(/\.map-card \.route-focus-pill \{[^}]*min-height:\s*44px/);
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
