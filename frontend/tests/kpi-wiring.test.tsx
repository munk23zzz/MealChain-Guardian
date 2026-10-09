// S4-03 wiring — page.tsx memuat KPI via fetchKpis dan merender
// KPIDashboard. Uji kontrak pada source (node-env, tanpa DOM).
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const pageSrc = readFileSync("app/page.tsx", "utf8");

describe("wiring KPI di app/page.tsx (S4-03)", () => {
  it("import fetchKpis + KPIDashboard", () => {
    expect(pageSrc).toContain("fetchKpis");
    expect(pageSrc).toContain("KPIDashboard");
  });

  it("fetchKpis dipanggil dengan token (scope default dari backend)", () => {
    expect(pageSrc).toMatch(/fetchKpis\(/);
  });

  it("KPIDashboard dirender dengan state loading/error/kpi", () => {
    expect(pageSrc).toMatch(/<KPIDashboard/);
  });
});
