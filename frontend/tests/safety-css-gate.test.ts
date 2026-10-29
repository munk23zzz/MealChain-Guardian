// Gerbang mutu Tahap 7 (30 Okt 2026) — mengunci hasil konsolidasi gaya
// Keamanan Pangan supaya tidak mundur lagi.
//
// Kenapa gerbang, bukan sekadar pemeriksaan sekali jalan: 11 kelas `.safety-*`
// yang sudah mati sempat hidup berbulan-bulan tanpa ada yang sadar, dan warna
// `.safety-state-*` sempat ditulis dua kali di dua berkas (yang kedua menang
// diam-diam). Dua jenis kesalahan itu tidak pernah memerahkan tes apa pun.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const AKAR = path.resolve(__dirname, "..");
const CSS = {
  globals: "app/globals.css",
  tema: "app/theme-ext.css",
  papan: "components/FoodSafetyBoard.module.css",
  drawer: "components/ReceiptDrawer.module.css",
};

/** Semua berkas .css di app/ dan components/ — definisi .safety-* bisa tinggal
 *  di mana saja (mis. app/evidence-dossier.css untuk halaman Decision & Evidence). */
function semuaBerkasCss(): string[] {
  const keluar: string[] = [];
  for (const dir of ["app", "components"]) {
    for (const isi of fs.readdirSync(path.join(AKAR, dir), { withFileTypes: true })) {
      if (isi.isFile() && isi.name.endsWith(".css")) keluar.push(`${dir}/${isi.name}`);
    }
  }
  return keluar;
}

function baca(rel: string): string {
  return fs.readFileSync(path.join(AKAR, rel), "utf8");
}

/** Buang komentar supaya pencarian selektor tidak tertipu contoh di komentar. */
function tanpaKomentar(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, (m) => " ".repeat(m.length));
}

function kelasTerdefinisi(css: string): string[] {
  return Array.from(new Set(Array.from(tanpaKomentar(css).matchAll(/\.(safety-[a-z0-9-]+)/g)).map((m) => m[1])));
}

/** Kode produk = semua .ts/.tsx di luar tests/ dan di luar node_modules. */
function kodeProduk(): string {
  const keluar: string[] = [];
  const telusuri = (dir: string) => {
    for (const isi of fs.readdirSync(dir, { withFileTypes: true })) {
      if (["node_modules", ".next", ".next-build", "out", "coverage", "tests"].includes(isi.name)) continue;
      const p = path.join(dir, isi.name);
      if (isi.isDirectory()) telusuri(p);
      else if (/\.tsx?$/.test(isi.name)) keluar.push(tanpaKomentar(fs.readFileSync(p, "utf8")));
    }
  };
  telusuri(AKAR);
  return keluar.join("\n");
}

function dipakaiDiKode(kelas: string, kode: string): boolean {
  return new RegExp(`(?<![\\w-])${kelas}(?![\\w-])`).test(kode);
}

/** Rasio kontras WCAG untuk dua warna heksadesimal. */
function luminans(hex: string): number {
  const h = hex.replace("#", "");
  const penuh = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const kanal = [0, 2, 4].map((i) => parseInt(penuh.slice(i, i + 2), 16) / 255);
  const linier = kanal.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * linier[0] + 0.7152 * linier[1] + 0.0722 * linier[2];
}

function kontras(a: string, b: string): number {
  const [x, y] = [luminans(a), luminans(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

function token(css: string, nama: string): string {
  const m = new RegExp(`--${nama}:\\s*([^;]+);`).exec(css);
  if (!m) throw new Error(`token --${nama} tidak ditemukan`);
  return m[1].trim();
}

describe("gerbang gaya Keamanan Pangan (tahap 7)", () => {
  const kode = kodeProduk();
  const semuaCss = Object.fromEntries(Object.entries(CSS).map(([k, v]) => [k, baca(v)]));

  it("tidak ada kelas .safety-* yatim (didefinisikan, tidak dipakai kode)", () => {
    const terdefinisi = new Set(semuaBerkasCss().flatMap((rel) => kelasTerdefinisi(baca(rel))));
    // `safety-state-${state.key}` dirakit di JSX: keempat nilai itu sah walau
    // namanya tidak pernah ditulis utuh.
    const dinamis = ["safety-state-watch", "safety-state-urgent", "safety-state-expired", "safety-state-unknown"];
    const yatim = [...terdefinisi].filter((k) => !dinamis.includes(k) && !dipakaiDiKode(k, kode));
    expect(yatim).toEqual([]);
  });

  it("setiap kelas .safety-* yang dipakai JSX punya definisi CSS", () => {
    const terdefinisi = new Set(semuaBerkasCss().flatMap((rel) => kelasTerdefinisi(baca(rel))));
    // Hanya nama yang benar-benar dipakai sebagai kelas (className="…"),
    // bukan id/atribut data yang kebetulan berawalan "safety-".
    const dipakai = Array.from(
      new Set(
        Array.from(kode.matchAll(/className=(?:"|\{`)([^"`}]*)/g))
          .flatMap((m) => m[1].split(/\s+/))
          .filter((k) => /^safety-[a-z0-9-]+$/.test(k))
      )
    ).filter((k) => !k.startsWith("safety-state-")); // dirakit dinamis, diperiksa di atas
    const hilang = dipakai.filter((k) => !terdefinisi.has(k));
    expect(hilang).toEqual([]);
  });

  it("warna .safety-state-* hanya didefinisikan sekali (theme-ext menang, globals tidak menyalin)", () => {
    for (const nama of ["watch", "urgent", "expired"]) {
      const diGlobals = new RegExp(`\\.safety-state-${nama}\\b`).test(tanpaKomentar(semuaCss.globals));
      expect(diGlobals, `.safety-state-${nama} masih ditulis di globals.css`).toBe(false);
      const diTema = new RegExp(`\\.safety-state-${nama}\\b`).test(tanpaKomentar(semuaCss.tema));
      expect(diTema, `.safety-state-${nama} hilang dari theme-ext.css`).toBe(true);
    }
    // "unknown" tidak punya padanan di theme-ext, jadi tetap di globals.
    expect(/\.safety-state-unknown\b/.test(tanpaKomentar(semuaCss.globals))).toBe(true);
  });

  it("setiap kontrol yang bisa dijangkau Tab punya cincin fokus terlihat", () => {
    const cincin = /outline:\s*2px solid var\(--(?:accent-strong|focus-ring)/;
    // Global: tombol dan tautan.
    expect(/button:focus-visible/.test(semuaCss.globals)).toBe(true);
    expect(/a:focus-visible/.test(semuaCss.globals)).toBe(true);
    // Papan: tile saringan, select komoditas, dan lipatan "Rincian angka".
    const papan = semuaCss.papan;
    expect(/\.tile:focus-visible\s*\{[^}]*outline:\s*2px/.test(papan)).toBe(true);
    expect(/\.decisionFilter select:focus-visible\s*\{[^}]*outline:\s*2px/.test(papan)).toBe(true);
    expect(/\.safety-more > summary:focus-visible\s*\{[^}]*outline:\s*2px/.test(semuaCss.tema)).toBe(true);
    // Drawer: kotak berat, tombol opsi (label yang membungkus radio), tombol aksi.
    const drawer = semuaCss.drawer;
    for (const pola of [/\.weighInput:focus-visible/, /\.option:has\(input:focus-visible\)/, /\.button:focus-visible/]) {
      expect(pola.test(drawer), `aturan ${pola} tidak ada di ReceiptDrawer.module.css`).toBe(true);
    }
    expect(cincin.test(drawer)).toBe(true);
  });

  it("berkas yang punya gerak punya pagar prefers-reduced-motion", () => {
    for (const [nama, css] of Object.entries(semuaCss)) {
      const bersih = tanpaKomentar(css);
      const bergerak = /(transition|animation):/.test(bersih);
      const berpagar = bersih.includes("prefers-reduced-motion");
      if (bergerak) {
        expect(berpagar, `${nama} punya transition/animation tanpa pagar reduced-motion`).toBe(true);
      }
    }
  });

  it("kontras teks pada bidangnya ≥ 4,5:1", () => {
    const gl = semuaCss.globals;
    const pasangan: Array<[string, string, string]> = [
      ["ink-subtle", "surface", "fakta sekunder"],
      ["ink-muted", "surface", "keterangan"],
      ["ink", "surface", "teks utama"],
      ["accent-strong", "surface", "tautan/aksen"],
      ["sev-medium-ink", "sev-medium-bg", "lencana sedang"],
      ["sev-hard-ink", "sev-hard-bg", "lencana berat"],
      ["sev-critical-ink", "sev-critical-bg", "lencana kritis"],
    ];
    const gagal = pasangan
      .map(([depan, belakang, label]) => ({
        label,
        rasio: kontras(token(gl, depan), token(gl, belakang)),
      }))
      .filter(({ rasio }) => rasio < 4.5)
      .map(({ label, rasio }) => `${label}=${rasio.toFixed(2)}:1`);
    expect(gagal).toEqual([]);
  });

  it("tidak ada teks di bawah 12 px di papan maupun drawer", () => {
    for (const [nama, css] of Object.entries({ papan: semuaCss.papan, drawer: semuaCss.drawer })) {
      const kecil = Array.from(tanpaKomentar(css).matchAll(/font-size:\s*(\d+(?:\.\d+)?)px/g))
        .map((m) => Number(m[1]))
        .filter((px) => px < 12);
      expect(kecil, `${nama} memakai font-size < 12px`).toEqual([]);
    }
    expect(token(semuaCss.globals, "fs-1")).toBe("12px");
  });
});
