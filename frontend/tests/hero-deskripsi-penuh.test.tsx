// Deskripsi kepala halaman SELEBAR KARTU (permintaan pemilik, 30 Okt 2026):
// "untuk bagian deskripsi kepala halaman pada halaman Demo Control, Suppliers,
// Food Safety, Decision & Evidence dibuat full saja, yang sekarang setengah
// halaman".
//
// Sebab "setengah halaman": `.page-header-text > p` dibatasi `max-width: 78ch`,
// sehingga paragraf berhenti di tengah kartu walau ruangnya ada. Perbaikannya
// opt-in (prop `wideDescription`), jadi halaman lain tidak berubah.
import fs from "node:fs";
import path from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import PageHeader from "../components/PageHeader";

const AKAR = path.resolve(__dirname, "..");
const baca = (rel: string) => fs.readFileSync(path.join(AKAR, rel), "utf8");
const CSS = baca("app/globals.css").replace(/\/\*[\s\S]*?\*\//g, "");

describe("deskripsi kepala selebar kartu", () => {
  it("PageHeader menambahkan kelas page-header-wide hanya saat diminta", () => {
    const lebar = renderToStaticMarkup(
      <PageHeader title="Demo Control" description="Penjelas." wideDescription />
    );
    expect(lebar).toContain("page-header page-header-wide");
    const biasa = renderToStaticMarkup(<PageHeader title="Pengaturan" description="Penjelas." />);
    expect(biasa).not.toContain("page-header-wide");
    // Kelas lain yang sudah dipakai halaman tidak boleh hilang.
    const gabung = renderToStaticMarkup(
      <PageHeader title="X" description="Y" wideDescription className="jump-target" />
    );
    expect(gabung).toContain("page-header page-header-wide jump-target");
  });

  it("empat halaman yang diminta memakainya, halaman lain tidak", () => {
    const diminta = [
      "app/page.tsx", // blok tab Demo Control
      "components/SupplierBoard.tsx",
      "components/FoodSafetyBoard.tsx",
      "components/DecisionEvidence.tsx",
    ];
    for (const rel of diminta) {
      expect(baca(rel), rel).toContain("wideDescription");
    }
    const lain = [
      "components/TodayDashboard.tsx",
      "components/KpiQualityBoard.tsx",
      "components/LocationNetworkBoard.tsx",
      "components/SettingsPanel.tsx",
    ];
    for (const rel of lain) {
      expect(baca(rel), rel).not.toContain("wideDescription");
    }
  });

  it("CSS: paragraf jadi baris kedua selebar kartu, batas 78ch dilepas", () => {
    const mulai = CSS.indexOf(".page-header-wide {");
    expect(mulai).toBeGreaterThan(-1);
    const blok = CSS.slice(mulai, CSS.indexOf("\n}", mulai));
    expect(blok).toContain("display: grid");
    expect(blok).toContain("grid-template-columns: minmax(0, 1fr) auto");

    // Pembungkus teks jadi `display: contents` supaya judul, paragraf, dan meta
    // duduk dalam satu grid — tanpa itu paragraf tidak bisa selebar kartu.
    expect(CSS).toMatch(/\.page-header-wide \.page-header-text \{\s*display: contents/);

    const paragraf = CSS.slice(
      CSS.indexOf(".page-header-wide .page-header-text > p:not(.page-header-eyebrow)")
    );
    const isi = paragraf.slice(0, paragraf.indexOf("}"));
    expect(isi).toContain("grid-column: 1 / -1");
    expect(isi).toContain("max-width: none");
  });

  it("meta tetap kanan-atas di baris pertama, dan layar sempit kembali satu kolom", () => {
    const meta = CSS.slice(CSS.indexOf(".page-header-wide .page-header-meta"));
    const isi = meta.slice(0, meta.indexOf("}"));
    expect(isi).toContain("grid-column: 2");
    expect(isi).toContain("grid-row: 1");
    expect(CSS).toMatch(
      /@media \(max-width: 640px\) \{\s*\.page-header-wide \{\s*grid-template-columns: minmax\(0, 1fr\)/
    );
  });

  // 30 Okt 2026 — permintaan pemilik lanjutan: "yang di bagian Demo Control
  // sisakan pojok kanan space". Demo Control satu-satunya halaman berdeskripsi
  // panjang tanpa meta di kanan, jadi paragrafnya dibatasi ±3/4 kartu; tiga
  // halaman lain tetap selebar kartu (mereka punya pil meta di pojok kanan).
  it("Demo Control menyisakan ruang di pojok kanan, tiga halaman lain tidak", () => {
    expect(baca("app/page.tsx")).toContain('className="page-header-space-right"');
    for (const rel of [
      "components/SupplierBoard.tsx",
      "components/FoodSafetyBoard.tsx",
      "components/DecisionEvidence.tsx",
    ]) {
      expect(baca(rel), rel).not.toContain("page-header-space-right");
    }
    const mulai = CSS.indexOf(".page-header-wide.page-header-space-right .page-header-text > p");
    expect(mulai).toBeGreaterThan(-1);
    const isi = CSS.slice(mulai, CSS.indexOf("}", mulai));
    expect(isi).toContain("max-width: 112ch");
  });
});
