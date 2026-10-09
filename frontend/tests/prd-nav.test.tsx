// PRD 2.4 alignment (arah Roy 2026-10-09): navigasi konsol = 5 tab sesuai
// 7 screen PRD (login sudah ada; decision detail gabung di recommendations).
// Kontrak: tab overview/kpi/recommendations/agent-log; demo-control
// approver-only. KPI target PRD tampil BERLABEL "TARGET DEMO" (bukan
// angka live). Persona label sesuai PRD §2.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const pageSrc = readFileSync("app/page.tsx", "utf8");

describe("navigasi PRD 2.4 (7 screen → konsol tab)", () => {
  it("memiliki tab overview, kpi, recommendations, agent-log", () => {
    expect(pageSrc).toContain('"overview"');
    expect(pageSrc).toContain('"kpi"');
    expect(pageSrc).toContain('"recommendations"');
    expect(pageSrc).toContain('"agent-log"');
  });

  it("demo-control = tab terpisah, approver-only", () => {
    expect(pageSrc).toContain('"demo-control"');
    expect(pageSrc).toMatch(/demo-control[\s\S]{0,200}isApprover|isApprover[\s\S]{0,200}demo-control/);
  });

  it("KPI target PRD tampil berlabel TARGET DEMO (bukan angka live)", () => {
    expect(pageSrc).toMatch(/<KpiTargets/);
    const targets = readFileSync("components/KpiTargets.tsx", "utf8");
    expect(targets).toContain("TARGET DEMO");
    // Angka target PRD §5 ada, dengan label eksplisit:
    expect(targets).toContain("99,42");
  });

  it("persona label sesuai PRD §2 (Operations Lead / Food Safety Officer / National Inspector)", () => {
    expect(pageSrc).toContain("Operations Lead");
    expect(pageSrc).toContain("Food Safety Officer");
    expect(pageSrc).toContain("National Inspector");
  });

  it("agent-log: trace console terpisah dari detail (AgentTraceViewer tetap ter-wire)", () => {
    expect(pageSrc).toMatch(/<AgentTraceViewer/);
    expect(pageSrc).toMatch(/<ProviderPanel/);
  });

  it("demo-control menjalankan skenario via API resmi (seed + OpsConsole), bukan mock", () => {
    expect(pageSrc).toMatch(/demo-control[\s\S]{0,400}OpsConsole|<OpsConsole/);
    expect(pageSrc).toMatch(/onSeedDemo/);
  });
});
