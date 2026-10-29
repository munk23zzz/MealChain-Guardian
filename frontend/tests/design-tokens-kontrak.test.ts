import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrak design system lintas berkas CSS (audit 22 Okt 2026).
 *
 * Tiga kelas cacat di sini tidak mungkin ditangkap tes komponen: ia hanya
 * terlihat saat computed style dibaca dari DOM hidup, dan semuanya "diam":
 *
 * 1) Token hantu — `var(--warning-ink, #92400e)` padahal `--warning-ink` tidak
 *    pernah dideklarasikan: fallback itulah warna yang tampil, tanpa error.
 *    Terukur: pil komoditas "aktif" di Surplus tampil cokelat #92400e, bukan
 *    amber token (#8A5A00) yang dipakai halaman lain.
 * 2) Kontrol form tidak mewarisi tipografi proyek: `button`/`select` tampil
 *    dengan Arial 13.3333px (bawaan peramban) dan `select.dc-select` berteks
 *    hitam, satu-satunya elemen hitam di aplikasi.
 * 3) Bahasa gerak tidak merata: 4 dari 11 layar punya gerak masuk, sisanya
 *    muncul mendadak. Satu reveal per layar, dengan pagar reduced-motion.
 */
const app = join(__dirname, "..", "app");
const baca = (nama: string) => readFileSync(join(app, nama), "utf8");
const tanpaKomentar = (isi: string) => isi.replace(/\/\*[\s\S]*?\*\//g, "");

// S6 (29 Okt 2026): lembar gaya khas halaman Pemasok ikut diaudit di sini, bukan
// hanya globals.css — dua berkas itu tumbuh di luar globals dan luput dari
// kontrak tipografi/palet.
const berkas = [
  "globals.css",
  "theme-ext.css",
  "map-console.css",
  "supply-adequacy.css",
  "evidence-dossier.css",
  "supplier-summary.css",
  "supplier-receipts.css",
];
const isiBersih = Object.fromEntries(berkas.map((f) => [f, tanpaKomentar(baca(f))]));
const semuaCss = Object.values(isiBersih).join("\n");

function tokenDideklarasikan(css: string): Set<string> {
  const set = new Set<string>();
  for (const m of Array.from(css.matchAll(/(--[a-z0-9-]+)\s*:/g))) set.add(m[1]);
  return set;
}
const dideklarasikan = tokenDideklarasikan(isiBersih["globals.css"] + isiBersih["theme-ext.css"]);

describe("kontrak token CSS", () => {
  it("tidak ada token hantu yang fallback-nya menang", () => {
    const hantu: string[] = [];
    for (const m of Array.from(semuaCss.matchAll(/var\(\s*(--[a-z0-9-]+)\s*,/g))) {
      const tok = m[1];
      // Token yang diisi lewat style inline (--i, --chart-h, --truk-arah) bukan hantu.
      if (["--i", "--chart-h", "--truk-arah"].includes(tok)) continue;
      if (!dideklarasikan.has(tok)) hantu.push(tok);
    }
    expect(hantu, `token tanpa deklarasi: ${Array.from(new Set(hantu)).join(", ")}`).toEqual([]);
  });

  it("alias token lama dideklarasikan dan menunjuk token kanonik", () => {
    const ext = isiBersih["theme-ext.css"];
    for (const [alias, kanonik] of [
      ["--warning-ink", "--warn-ink"],
      ["--warning-bg", "--warn-bg"],
      ["--warning-line", "--warn-border"],
      ["--status-warn", "--status-warning"],
      ["--safe", "--status-safe"],
      ["--warn", "--warn-ink"],
      ["--surface-2", "--surface-sunken"],
    ]) {
      expect(ext, `alias ${alias} belum ada`).toMatch(new RegExp(`${alias}:\\s*var\\(${kanonik}\\)`));
      expect(dideklarasikan.has(kanonik), `${kanonik} harus token kanonik`).toBe(true);
    }
  });

  it("kontrol form mewarisi tipografi proyek, bukan Arial bawaan", () => {
    expect(isiBersih["theme-ext.css"]).toMatch(/button,\s*\n?\s*input,\s*\n?\s*select,\s*\n?\s*textarea\s*\{[^}]*font:\s*inherit/);
  });

  it("satu gerak masuk per layar, dengan pagar reduced-motion", () => {
    const ext = isiBersih["theme-ext.css"];
    expect(ext).toMatch(/@keyframes\s+page-reveal\s*\{/);
    expect(ext).toMatch(/\.app-content\s*>\s*\*\s*\{[^}]*animation:\s*page-reveal/);
    // Reveal hanya untuk pengguna yang TIDAK meminta gerak dikurangi.
    expect(ext).toMatch(/@media\s*\(prefers-reduced-motion:\s*no-preference\)\s*\{[^}]*\.app-content\s*>\s*\*/);
  });

  it("lantai tipografi 12 px: tidak ada font-size literal di bawah 12", () => {
    // docs/design.md §Tipografi: skala 8 langkah, lantai 12 px. Sebelum audit
    // 22 Okt 2026 ada 11 px di Overview & Keamanan Pangan, dan 8,5–10,5 px di
    // popup peta — semuanya dinaikkan ke --fs-1.
    const kecil: string[] = [];
    for (const [nama, isi] of Object.entries(isiBersih)) {
      for (const m of Array.from(isi.matchAll(/font-size:\s*(\d+(?:\.\d+)?)px/g))) {
        if (parseFloat(m[1]) < 12) kecil.push(`${nama}: ${m[1]}px`);
      }
    }
    expect(kecil, "nilai font-size di bawah lantai 12 px").toEqual([]);
  });

  it("popup peta dibatasi supaya tidak menjulur keluar kanvas", () => {
    // Popup 12 px setinggi 402 px pada kanvas 400 px: jagaPopup menyerah
    // (tinggi > tinggi peta − 24) dan kartu menggantung di luar peta.
    expect(isiBersih["map-console.css"]).toMatch(
      /\.map-card \.maplibregl-popup-content \{[^}]*max-height:\s*\d+px[^}]*overflow-y:\s*auto/
    );
  });

  it("font-family literal hanya boleh di @font-face", () => {
    // Di luar deklarasi font, nama huruf harus lewat --font-ui / --font-data:
    // literal "Fira Sans" membuat penggantian tumpukan huruf tidak merambat.
    const liar: string[] = [];
    for (const [nama, isi] of Object.entries(isiBersih)) {
      const tanpaFontFace = isi.replace(/@font-face\s*\{[^}]*\}/g, "");
      for (const m of Array.from(tanpaFontFace.matchAll(/font-family:\s*([^;]+);/g))) {
        const nilai = m[1].trim();
        // `var(--font-mono, ui-monospace, "SFMono-Regular", …)` sah: tokennya
        // dipakai, kutip hanya ada di daftar cadangan.
        if (nilai.startsWith("var(")) continue;
        if (nilai.includes('"') || nilai.includes("'")) liar.push(`${nama}: ${nilai}`);
      }
    }
    expect(liar, "font-family literal di luar @font-face").toEqual([]);
  });

  it("blok .summary-*, .directory-*, .register-*, .receipt-* memakai token ukuran", () => {
    // Lantai 12 px sudah dijaga tes sebelumnya; ini menjaga hal lain: ukuran di
    // dalam komponen Pemasok harus lewat skala (--fs-1..--fs-8) supaya tidak ada
    // nilai 13/15/17 px yang menyelinap dan memutus tangga tipografi.
    const mentah: string[] = [];
    const sumber = [isiBersih["globals.css"], isiBersih["supplier-summary.css"], isiBersih["supplier-receipts.css"]];
    for (const isi of sumber) {
      for (const m of Array.from(isi.matchAll(/([^{}]+)\{([^{}]*)\}/g))) {
        const selektor = m[1].trim().replace(/\s+/g, " ");
        if (!/\.(summary|directory|register|receipt)-/.test(selektor)) continue;
        for (const ukuran of Array.from(m[2].matchAll(/font-size:\s*([^;]+);/g))) {
          const nilai = ukuran[1].trim();
          if (!nilai.startsWith("var(--fs-")) mentah.push(`${selektor} → ${nilai}`);
        }
      }
    }
    expect(mentah, "font-size di luar skala token").toEqual([]);
  });

  it("pager menyempit di ≤720 px: nomor halaman disembunyikan", () => {
    // Pada 44 px per tombol (batas sentuh) enam nomor halaman meluap 15 px dari
    // kartu di 375 px, atau membungkus jadi pager setinggi 214 px. Rentang
    // "1–10 dari 105" + Sebelumnya/Berikutnya memberi posisi yang sama.
    const css = isiBersih["globals.css"];
    expect(css).toMatch(/@media \(max-width: 720px\) \{[\s\S]{0,600}?\.pager-list \{\s*display: none;/);
    expect(css).toMatch(/\.pager-controls \{[\s\S]{0,200}?min-width: 0;/);
  });

  it("tidak ada hex di luar palet token (komentar tidak dihitung)", () => {
    // Palet sah = nilai dari deklarasi token, bukan semua hex di berkas (kalau
    // palet diambil dari semua hex, tes ini selalu hijau dan tidak menjaga apa pun).
    const palet = new Set<string>();
    for (const m of Array.from(semuaCss.matchAll(/--[a-z0-9-]+\s*:\s*(#[0-9a-fA-F]{3,8})/g))) {
      palet.add(m[1].toLowerCase());
    }
    const liar: string[] = [];
    const ke6 = (h: string) => (h.length === 4 ? `#${h[1]}${h[1]}${h[2]}${h[2]}${h[3]}${h[3]}` : h);
    for (const [nama, isi] of Object.entries(isiBersih)) {
      const tanpaDeklarasi = isi.replace(/--[a-z0-9-]+\s*:\s*#[0-9a-fA-F]{3,8}/g, "");
      for (const m of Array.from(tanpaDeklarasi.matchAll(/(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b/g))) {
        const nilai = ke6(m[1].toLowerCase());
        if (!palet.has(nilai)) liar.push(`${nama}: ${nilai}`);
      }
    }
    expect(Array.from(new Set(liar)), "hex di luar palet").toEqual([]);
  });
});
