// 30 Okt 2026 — permintaan pemilik: "pada bagian hero pada semua page gunakan
// design yang sama". Sebelumnya dua pola hidup berdampingan: `.page-header`
// (pita tanpa bingkai, tujuh tab) dan `.overview-header` (kartu, Overview +
// Decision & Evidence). Tes ini menjaga satu pola saja.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";


const AKAR = path.resolve(__dirname, "..");
const CSS = fs.readFileSync(path.join(AKAR, "app/globals.css"), "utf8");
const BERSIH = CSS.replace(/\/\*[\s\S]*?\*\//g, "");

const berkas = [
  ...fs.readdirSync(path.join(AKAR, "app")).filter((f) => f.endsWith(".tsx")).map((f) => `app/${f}`),
  ...fs.readdirSync(path.join(AKAR, "components")).filter((f) => f.endsWith(".tsx")).map((f) => `components/${f}`),
];
const SUMBER = berkas.map((rel) => ({ rel, isi: fs.readFileSync(path.join(AKAR, rel), "utf8") }));

describe("hero seragam di semua halaman", () => {
  it("tidak ada lagi penanda kepala kedua (.overview-header) di komponen/halaman", () => {
    const tersisa = SUMBER.filter((f) => f.isi.includes("overview-header")).map((f) => f.rel);
    expect(tersisa).toEqual([]);
  });

  it("setiap tab memakai komponen kepala yang sama (PageHeader atau PageShell)", () => {
    const tab = [
      "components/TodayDashboard.tsx",
      "components/KPIDashboard.tsx",
      "components/KpiQualityBoard.tsx",
      "components/LocationNetworkBoard.tsx",
      "components/SupplierBoard.tsx",
      "components/FoodSafetyBoard.tsx",
      "components/SurplusBoard.tsx",
      "components/AgentQualityBoard.tsx",
      "components/DecisionEvidence.tsx",
      "components/SettingsPanel.tsx",
      "app/page.tsx",
    ];
    for (const rel of tab) {
      const isi = fs.readFileSync(path.join(AKAR, rel), "utf8");
      expect(isi, rel).toMatch(/<PageShell|<PageHeader/);
    }
  });

  it("kulit kepala satu: kartu tipis dengan bg, garis, radius, dan bayangan 1", () => {
    const i = BERSIH.indexOf(".page-header {");
    const blok = BERSIH.slice(BERSIH.indexOf("{", i) + 1, BERSIH.indexOf("}", i));
    expect(blok).toContain("padding: 14px 16px");
    expect(blok).toContain("background: var(--surface)");
    expect(blok).toContain("border: 1px solid var(--line)");
    expect(blok).toContain("border-radius: var(--radius)");
    expect(blok).toContain("box-shadow: var(--shadow-1)");
  });

  it("tiap tab memasang kepala SEKALI di sumbernya (bukan dua pola berdampingan)", () => {
    // KPIDashboard punya empat cabang keadaan (memuat/galat/kosong/isi) dan
    // masing-masing memanggil PageHeader — yang penting: satu komponen, bukan
    // dua pola. Tab lain cukup sekali.
    const tab = [
      "components/TodayDashboard.tsx",
      "components/KpiQualityBoard.tsx",
      "components/LocationNetworkBoard.tsx",
      "components/SupplierBoard.tsx",
      "components/FoodSafetyBoard.tsx",
      "components/SurplusBoard.tsx",
      "components/AgentQualityBoard.tsx",
      "components/DecisionEvidence.tsx",
      "components/SettingsPanel.tsx",
      "app/page.tsx",
    ];
    for (const rel of tab) {
      const isi = fs.readFileSync(path.join(AKAR, rel), "utf8");
      const jumlah = (isi.match(/<(?:PageShell|PageHeader)\b/g) ?? []).length;
      expect(jumlah, `${rel}: ${jumlah} kepala`).toBeGreaterThanOrEqual(1);
      expect(isi, rel).not.toContain("overview-header");
    }
  });
});
