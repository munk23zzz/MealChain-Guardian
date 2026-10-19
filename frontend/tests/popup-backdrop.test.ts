import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak CSS latar popup (Langkah 1, 19 Okt 2026).
 *
 * Permintaan pemilik: "jangan transparan tapi blur smooth". Yang dikunci:
 *  - scrim memakai blur (bukan sekadar warna datar) — ini yang membuat tepi
 *    konten di belakang halus, bukan tembus;
 *  - tint cukup pekat (>=0,6) supaya teks di belakang TIDAK terbaca — kalau
 *    tint terlalu bening, hasilnya "transparan" lagi walau ada blur;
 *  - ada fallback untuk browser tanpa backdrop-filter, karena tanpa blur tint
 *    bening akan menampilkan teks yang mengganggu;
 *  - prefers-reduced-transparency mematikan blur dan memekatkan latar.
 *
 * Tes ini membaca globals.css karena nilainya tidak bisa diuji dari unit
 * komponen (tidak ada CSSOM di jsdom).
 */
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

function blok(selector: string): string {
  const cocok = new RegExp(`^${selector}\\s*\\{([^}]*)\\}`, "ms").exec(css);
  if (!cocok) throw new Error(`blok CSS tidak ditemukan: ${selector}`);
  return cocok[1];
}

/** Isi blok @media/@supports yang judulnya memuat penanda. */
function blokAturan(penanda: string): string {
  const mulai = css.indexOf(penanda);
  if (mulai < 0) throw new Error(`aturan tidak ditemukan: ${penanda}`);
  const buka = css.indexOf("{", mulai);
  let i = buka + 1;
  let dalam = 1;
  while (i < css.length && dalam > 0) {
    if (css[i] === "{") dalam++;
    else if (css[i] === "}") dalam--;
    i++;
  }
  return css.slice(buka + 1, i - 1);
}

describe("latar popup: kabut blur, bukan transparan", () => {
  it("scrim memakai backdrop blur + saturasi", () => {
    const scrim = blok("\\.popup-backdrop");
    expect(scrim).toMatch(/backdrop-filter:\s*blur\(20px\)\s*saturate\(140%\)/);
    // Prefix webkit wajib untuk Safari.
    expect(scrim).toMatch(/-webkit-backdrop-filter:\s*blur\(20px\)/);
  });

  it("tint cukup pekat supaya teks di belakang tidak terbaca", () => {
    const scrim = blok("\\.popup-backdrop");
    const alpha = /background:\s*rgba\(248,\s*250,\s*252,\s*([\d.]+)\)/.exec(scrim)?.[1];
    expect(alpha).toBeDefined();
    expect(Number(alpha)).toBeGreaterThanOrEqual(0.6);
    // Bukan lagi scrim gelap datar 50% yang lama.
    expect(scrim).not.toMatch(/rgba\(15,\s*23,\s*42,\s*0\.5\)/);
  });

  it("ada fallback pekat untuk browser tanpa backdrop-filter", () => {
    const fallback = blokAturan("@supports not ((backdrop-filter: blur(1px))");
    expect(fallback).toMatch(/\.popup-backdrop\s*\{[^}]*background:\s*rgba\(15,\s*23,\s*42,\s*0\.55\)/);
  });

  it("prefers-reduced-transparency mematikan blur dan memekatkan latar", () => {
    const redup = blokAturan("@media (prefers-reduced-transparency: reduce)");
    const aturan = /\.popup-backdrop\s*\{([^}]*)\}/.exec(redup)?.[1] ?? "";
    expect(aturan).toMatch(/background:\s*rgba\(248,\s*250,\s*252,\s*0\.97\)/);
    expect(aturan).toMatch(/backdrop-filter:\s*none/);
  });
});

describe("kaki popup: kontrol tetap terjangkau saat ringkasan panjang", () => {
  it("kaki menu menempel di dasar popup, bukan ikut tergulir", () => {
    const kaki = blok("\\.approval-menu-foot");
    expect(kaki).toMatch(/position:\s*sticky/);
    expect(kaki).toMatch(/bottom:\s*calc\(-1 \* var\(--space-4\)\)/);
    // Latar solid: tanpa itu isi yang lewat di belakang kaki terbaca.
    expect(kaki).toMatch(/background:\s*var\(--surface\)/);
  });
});
