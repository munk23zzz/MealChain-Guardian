// S4-03 wiring — page.tsx memuat KPI lewat hook React Query (Rules.md §3), dan
// hook itulah yang memanggil fetchKpis. Uji kontrak pada sumber (node-env,
// tanpa DOM): batas "komponen tidak fetch sendiri" ikut dipatok di sini.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const pageSrc = readFileSync("app/page.tsx", "utf8");
const hookSrc = readFileSync("lib/hooks/useKpi.ts", "utf8");
// Tab gabungan (2026-10-15): halaman menyerahkan kedua payload ke satu
// komponen, dan KOMPONEN ITU yang merender KPIDashboard.
const boardSrc = readFileSync("components/KpiQualityBoard.tsx", "utf8");

describe("wiring KPI di app/page.tsx (S4-03)", () => {
  it("halaman memakai hook useKpi lewat komponen tab gabungan", () => {
    expect(pageSrc).toContain("useKpi");
    expect(pageSrc).toMatch(/from "\.\.\/lib\/hooks\/useKpi"/);
    expect(pageSrc).toContain("KpiQualityBoard");
    expect(pageSrc).toMatch(/<KpiQualityBoard/);
  });

  it("hanya hook yang memanggil fetchKpis (bukan komponen)", () => {
    expect(hookSrc).toMatch(/fetchKpis\(/);
    // Batas Rules.md §3: setelah migrasi, halaman tidak menyentuh API langsung.
    expect(pageSrc).not.toMatch(/fetchKpis\(/);
  });

  it("KPIDashboard dirender oleh tab gabungan dengan state loading/error/kpi", () => {
    expect(boardSrc).toMatch(/<KPIDashboard/);
    expect(boardSrc).toContain("kpiLoading");
    expect(boardSrc).toContain("kpiError");
    expect(boardSrc).toContain("kpi={kpi}");
  });
});
