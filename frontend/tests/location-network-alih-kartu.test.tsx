// L5 redesign Location Network (30 Okt 2026): "Rencana alih" ikut keluarga
// bentuk yang sama dengan tabel lokasi — kartu berlabel di ≤760 px, dan baris
// tujuan yang sedang dibuka ditandai TEKS, bukan hanya latar.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import fs from "node:fs";
import path from "node:path";

import AllocationTable from "../components/AllocationTable";

const CSS = fs.readFileSync(path.resolve(__dirname, "../app/globals.css"), "utf8")
  .replace(/\/\*[\s\S]*?\*\//g, "");

// Bentuk respons GET /surplus/allocations apa adanya (snake_case, `pairs`).
const PLAN = {
  available: true,
  min_surplus_kg: 150,
  pairs: [
    { from: "Dapur Pusat", to: "SPPG Cakung", kg: 180, distance_km: 7.2, cost_share_pct: 3.4 },
    { from: "Dapur Pusat", to: "SPPG Bekasi", kg: 240, distance_km: 12.8, cost_share_pct: 4.1 },
  ],
};

const render = (highlight: string | null = null) =>
  renderToStaticMarkup(<AllocationTable plan={PLAN} highlight={highlight} />);

describe("L5 — Rencana alih sebagai kartu berlabel", () => {
  it("setiap sel membawa label kolomnya (dipakai `td::before` di ≤760 px)", () => {
    const html = render();
    for (const label of ["Dari", "Tujuan", "Jumlah", "Jarak", "Biaya"]) {
      expect(html).toContain(`data-label="${label}"`);
    }
    // Lima sel per baris, dua baris → sepuluh label.
    expect((html.match(/data-label="/g) ?? []).length).toBe(10);
  });

  it("tabelnya punya kelas sendiri, bukan menumpang `.location-table` saja", () => {
    expect(render()).toContain('class="location-table allocation-table"');
    expect(render()).toContain('class="board-table-wrap allocation-table-wrap"');
  });

  it("baris yang sedang dibuka ditandai teks, bukan hanya latar", () => {
    const terbuka = render("SPPG Bekasi");
    expect(terbuka).toContain("sedang dibuka");
    expect((terbuka.match(/sedang dibuka/g) ?? []).length).toBe(1);
    const baris = terbuka.slice(terbuka.indexOf("SPPG Bekasi") - 200, terbuka.indexOf("SPPG Bekasi") + 200);
    expect(baris).toContain("sedang dibuka");
    // Tanpa rincian terbuka, tidak ada penanda yang menyesatkan.
    expect(render()).not.toContain("sedang dibuka");
  });

  it("CSS: mode kartu mematikan geseran mendatar di ≤760 px", () => {
    // Blok 760 px yang memuat aturan tabel alih (bukan blok 760 pertama di berkas).
    const i = CSS.indexOf(".allocation-table thead");
    const mulai = CSS.lastIndexOf("@media (max-width: 760px)", i);
    const blok = CSS.slice(mulai, CSS.indexOf("@media", i));
    expect(blok).toContain(".board-table-wrap.allocation-table-wrap {");
    expect(blok).toMatch(/\.allocation-table thead \{\s*display: none;/);
    expect(blok).toMatch(/\.allocation-table td::before \{\s*content: attr\(data-label\)/);
    // Wadahnya harus menang atas `.board-table-wrap { overflow-x: auto }`.
    const j = blok.indexOf(".board-table-wrap.allocation-table-wrap");
    expect(blok.slice(j, blok.indexOf("}", j))).toContain("overflow: visible");
  });
});
