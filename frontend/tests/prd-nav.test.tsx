// PRD 2.4 alignment (arah Roy 2026-10-09): navigasi konsol = 5 tab sesuai
// 7 screen PRD (login sudah ada; decision detail gabung di recommendations).
// Kontrak: tab overview/kpi/recommendations/agent-log; demo-control
// approver-only. Strip "Target KPI — Demo Day" (PRD 2.4 §5) DIHAPUS
// 2026-10-15 atas arahan pemilik — halaman KPI hanya menampilkan angka
// live dari backend. Persona label sesuai PRD §2.
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";

const pageSrc = readFileSync("app/page.tsx", "utf8");

describe("navigasi PRD 2.4 (7 screen → konsol tab)", () => {
  it("memiliki tab overview, kpi, recommendations, agent-log", () => {
    expect(pageSrc).toContain('"overview"');
    expect(pageSrc).toContain('"kpi-kualitas"');
    expect(pageSrc).toContain('"recommendations"');
    expect(pageSrc).toContain('"agent-log"');
  });

  it("demo-control = tab terpisah, approver-only", () => {
    expect(pageSrc).toContain('"demo-control"');
    expect(pageSrc).toMatch(/demo-control[\s\S]{0,200}isApprover|isApprover[\s\S]{0,200}demo-control/);
  });

  it("strip \"Target KPI — Demo Day\" sudah dihapus dari halaman KPI (arahan pemilik)", () => {
    // Dulu tab KPI memuat <KpiTargets/> berlabel "TARGET DEMO · bukan angka live"
    // (PRD 2.4 §5). Pemilik meminta bagian itu dibuang; kontrak barunya: tab KPI
    // tetap ada, tetapi tidak ada lagi angka target yang tidak berasal dari backend.
    expect(pageSrc).toMatch(/tab === "kpi-kualitas"/);
    expect(pageSrc).not.toContain("KpiTargets");
    expect(existsSync("components/KpiTargets.tsx")).toBe(false);
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

  it("demo-control memakai DemoControlPanel (jalankan agent lewat API resmi, bukan mock)", () => {
    // 2026-10-19: skenario Event 1/2/3 dilepas dari tab; tombol pintas rail
    // "Muat kasus demo" ikut dihapus supaya hanya ada SATU jalan menyiapkan data
    // (blok 1 di panel).
    expect(pageSrc).toContain("<DemoControlPanel");
    expect(pageSrc).not.toContain("<OpsConsole");
    expect(pageSrc).not.toContain("onSeedDemo");
  });
});
