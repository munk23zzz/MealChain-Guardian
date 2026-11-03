import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak CSS latar popup (revisi pemilik, 19 Okt 2026).
 *
 * Permintaan pemilik: "background dibuat blur 20% saja", lalu "untuk blur nya
 * mungkin bisa 15% saja", lalu "blur nya itu masih samar samar untuk tampilan
 * di belakangnya, berarti di turunin lagi". Yang dikunci sekarang:
 *  - scrim memakai blur RINGAN (6-10 px), TANPA saturate(): tambahan efek
 *    dibuang. Rentang, bukan satu angka, karena pemilik menala kadarnya
 *    beberapa kali; batasnya: < 6 px huruf di belakang mulai terbaca,
 *    > 10 px latar meleleh (bukan lagi "samar-samar");
 *  - tint putih tipis (0,15-0,30) — cukup jadi kabut, teks di belakang tetap
 *    tidak terbaca karena blur-nya, bukan karena ditutup cat;
 *  - ada fallback untuk browser tanpa backdrop-filter (di sana tint tipis
 *    tidak menolong, jadi scrim gelap pekat dipakai);
 *  - prefers-reduced-transparency mematikan blur dan memekatkan latar.
 *
 * Tes ini membaca globals.css karena nilainya tidak bisa diuji dari unit
 * komponen (tidak ada CSSOM di jsdom).
 */
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

function blok(selector: string): string {
  const cocok = new RegExp(`^${selector}\\s*\\{([^}]*)\\}`, "ms").exec(css);
  if (!cocok) throw new Error(`blok CSS tidak ditemukan: ${selector}`);
  // Komentar dibuang: penjelasan di dalam blok menyebut nilai lama ("saturate",
  // "0,66") dan itu bukan deklarasi yang berlaku.
  return cocok[1].replace(/\/\*[\s\S]*?\*\//g, "");
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

describe("latar popup: blur ringan saja", () => {
  it("scrim memakai backdrop blur 6-10 px tanpa efek tambahan", () => {
    const scrim = blok("\\.popup-backdrop");
    // Awalan \n supaya yang terbaca deklarasi biasa, bukan `-webkit-` di baris
    // sebelumnya (keduanya bernilai sama, tapi tes harus menguji yang kanonik).
    const blur = /\n\s*backdrop-filter:\s*blur\((\d+(?:\.\d+)?)px\)\s*;/.exec(scrim)?.[1];
    expect(blur).toBeDefined();
    expect(Number(blur)).toBeGreaterThanOrEqual(6);
    expect(Number(blur)).toBeLessThanOrEqual(10);
    // Prefix webkit wajib untuk Safari — nilainya harus sama dengan yang kanonik.
    expect(scrim).toMatch(new RegExp(`-webkit-backdrop-filter:\\s*blur\\(${blur}px\\)\\s*;`));
    // "saja": saturasi & efek lain tidak ikut menumpang di latar.
    expect(scrim).not.toMatch(/saturate\(/);
  });

  it("tint tipis: kabut, bukan cat penutup", () => {
    const scrim = blok("\\.popup-backdrop");
    const alpha = /background:\s*rgba\(248,\s*250,\s*252,\s*([\d.]+)\)/.exec(scrim)?.[1];
    expect(alpha).toBeDefined();
    expect(Number(alpha)).toBeGreaterThanOrEqual(0.15);
    expect(Number(alpha)).toBeLessThanOrEqual(0.3);
    // Bukan scrim gelap datar lama (0,5) dan bukan kabut pekat 0,66.
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
