// Tahap 3 redesign Recommendation Feed (30 Okt 2026): satu bobot aksi.
//
// Dua hal yang dijaga di sini:
// 1. Tombol "Tinjau" tidak lagi biru penuh secara bawaan. Dulu sepuluh kartu =
//    sepuluh tombol primer bersaing; kini garis biru, dan biru penuh hanya saat
//    disentuh/difokus.
// 2. Judul kartu adalah heading sungguhan, dengan <h2> di atasnya supaya
//    tingkatannya tidak melompat (h1 → h3 = kegagalan urutan heading).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import fs from "node:fs";
import path from "node:path";

import RecommendationCard from "../components/RecommendationCard";

const AKAR = path.resolve(__dirname, "..");
const HALAMAN = fs.readFileSync(path.join(AKAR, "app/page.tsx"), "utf8");
const CSS = fs.readFileSync(path.join(AKAR, "app/globals.css"), "utf8");

const KARTU = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  created_at: "2026-10-10T18:16:47.844642+00:00",
  valid: false,
  iteration: 1,
  commodity_name: "telur",
};

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

function token(nama: string): string {
  const m = new RegExp(`--${nama}:\\s*([^;]+);`).exec(CSS);
  if (!m) throw new Error(`token --${nama} tidak ditemukan`);
  return m[1].trim();
}

describe("satu bobot aksi di kartu rekomendasi", () => {
  const html = renderToStaticMarkup(
    <RecommendationCard decision={KARTU as any} onBuka={() => {}} hint={null} />
  );

  it("judul kartu adalah <h3>, bukan paragraf", () => {
    expect(html).toContain('<h3 class="rec-title">');
    expect(html).not.toContain('<p class="rec-title">');
    expect(html).toContain("</h3>");
  });

  it("daerah daftar punya h2 (sr-only) sehingga tingkat heading tidak melompat", () => {
    expect(HALAMAN).toContain('<section className="feed" aria-labelledby="feed-judul">');
    expect(HALAMAN).toContain('<h2 className="sr-only" id="feed-judul">');
    expect(HALAMAN).toContain("Daftar rekomendasi");
    // .sr-only = position absolute, jadi judul ini tidak memakan baris grid.
    expect(CSS).toMatch(/\.sr-only\s*\{[^}]*position: absolute/);
  });

  it("tombol Tinjau memakai garis biru sebagai bawaan, bukan biru penuh", () => {
    const dasar = CSS.match(/\.rec-act-btn--utama \{([^}]*)\}/);
    expect(dasar, "aturan dasar .rec-act-btn--utama tidak ditemukan").not.toBeNull();
    expect(dasar![1]).toContain("background: var(--surface)");
    expect(dasar![1]).toContain("color: var(--accent-strong)");
    expect(dasar![1]).not.toContain("background: var(--accent-strong)");
    // Biru penuh hanya pada keadaan disentuh/difokus.
    const sorot = CSS.match(/\.rec-act-btn--utama:hover,\s*\.rec-act-btn--utama:focus-visible \{([^}]*)\}/);
    expect(sorot, "keadaan hover/focus tombol Tinjau tidak ditemukan").not.toBeNull();
    expect(sorot![1]).toContain("background: var(--accent-strong)");
  });

  it("kontras teks dan tepi tombol tetap lolos AA", () => {
    // Teks --accent-strong di atas putih.
    expect(kontras(token("accent-strong"), token("surface"))).toBeGreaterThanOrEqual(4.5);
    // Tepi kontrol (batas tombol) minimal 3:1 terhadap latar.
    expect(kontras(token("accent-strong"), token("surface"))).toBeGreaterThanOrEqual(3);
  });

  it("judul tidak menambah jarak bawaan heading", () => {
    const judul = CSS.match(/\.rec-title \{([^}]*)\}/);
    expect(judul).not.toBeNull();
    expect(judul![1]).toContain("margin: 0");
    // Ukuran & bobot eksplisit: heading punya ukuran bawaan peramban.
    expect(judul![1]).toContain("font-size");
    expect(judul![1]).toContain("font-weight");
  });

  it("baris meta: kg dan komoditas tinta penuh, sisanya tinta sekunder", () => {
    expect(CSS).toMatch(/\.rec-qty \{[^}]*color: var\(--ink\)/);
    expect(CSS).toMatch(/\.rec-komoditas \{[^}]*color: var\(--ink\)/);
    expect(CSS).toMatch(/\.rec-meta-line \{[^}]*color: var\(--ink-muted\)/);
  });
});
