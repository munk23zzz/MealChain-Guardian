// Kontrak halaman "Kualitas Agen" (halaman sidebar acuan /quality).
import { describe, expect, it } from "vitest";

import {
  VERDICT_LABEL,
  agentQuality,
  averageLabel,
  durationLabel,
  percentLabel,
  qualityMetrics,
  runOf,
  shortId,
  verdictOf,
} from "../lib/agent-quality";

const DECISION = { decision_id: "e430a0e8-9d9a-4584-bc85-cb9ba41064ca", decision_type: "regional_balance", status: "pending_approval", iteration: 3 };
const TRACE = {
  steps: [
    { step_name: "PREDICT", tool_called: "forecast.daily", output_summary: { method: "provider_forecast" }, step_at: "2026-10-11T05:16:46.287258+00:00" },
    { step_name: "DECIDE", tool_called: "supply_balance.propose", output_summary: { sdc: 16206000 }, step_at: "2026-10-11T05:16:48.287258+00:00" },
  ],
};
const SUMMARY_AGREE = { verifier: { verdict: "consistent", verified_by: "verifier_agent" } };

describe("shortId / verdictOf", () => {
  it("id panjang dipotong 8 aksara, kosong jadi '—'", () => {
    expect(shortId("e430a0e8-9d9a", 8)).toBe("e430a0e8");
    expect(shortId(null)).toBe("—");
  });

  it("putusan verifikator dipetakan tiga nilai (sisanya 'tidak tersedia')", () => {
    expect(verdictOf(SUMMARY_AGREE)).toBe("agree");
    expect(verdictOf({ verifier: { verdict: "flagged" } })).toBe("disagree");
    expect(verdictOf({ verifier: { verdict: "unavailable" } })).toBe("unavailable");
    expect(verdictOf(null)).toBe("unavailable");
    expect(VERDICT_LABEL.agree).toBe("Setuju");
  });
});

describe("durationLabel", () => {
  it("milidetik, detik, menit ditulis manusiawi; null jadi '—'", () => {
    expect(durationLabel(850)).toBe("< 1 s");
    expect(durationLabel(2340)).toBe("2.3 s");
    expect(durationLabel(180000)).toBe("3 mnt");
    expect(durationLabel(null)).toBe("—");
  });
});

describe("runOf", () => {
  it("menghitung langkah, alat, durasi, dan tandanya diubah manusia", () => {
    const run = runOf(DECISION, TRACE, SUMMARY_AGREE);
    expect(run).toMatchObject({
      shortId: "e430a0e8",
      type: "regional_balance",
      status: "pending_approval",
      steps: 2,
      tools: ["forecast.daily", "supply_balance.propose"],
      durationMs: 2000,
      durationLabel: "2.0 s",
      verdict: "agree",
      verdictLabel: "Setuju",
      fallbackSteps: 0,
      humanChanged: true,
    });
  });

  it("tanpa jejak: langkah null (bukan 0) dan alat kosong", () => {
    const run = runOf({ decision_id: "d1", iteration: 1 }, null, null);
    expect(run.steps).toBe(null);
    expect(run.tools).toEqual([]);
    expect(run.durationMs).toBe(null);
    expect(run.verdict).toBe("unavailable");
    expect(run.humanChanged).toBe(false);
  });

  it("langkah yang jatuh ke fallback dihitung", () => {
    const run = runOf(
      { decision_id: "d2", iteration: 1 },
      { steps: [{ step_name: "PREDICT", tool_called: "forecast.daily", output_summary: { method: "statistical_fallback" } }] },
      null
    );
    expect(run.fallbackSteps).toBe(1);
  });
});

describe("qualityMetrics", () => {
  const runs = [
    runOf(DECISION, TRACE, SUMMARY_AGREE),
    runOf({ decision_id: "d2", decision_type: "safety_disruption", status: "verifier_flagged", iteration: 1 }, TRACE, { verifier: { verdict: "flagged" } }),
    runOf({ decision_id: "d3", decision_type: "regional_balance", status: "proposed", iteration: 1 }, null, null),
  ];

  it("kesesuaian dihitung dari run yang BENAR-benar dinilai", () => {
    const metrics = qualityMetrics(runs);
    expect(metrics).toMatchObject({
      runs: 3,
      totalSteps: 4,
      agree: 1,
      disagree: 1,
      unavailable: 1,
      judged: 2,
      agreementRate: 50,
      humanChanged: 1,
      totalFallbacks: 0,
    });
    expect(percentLabel(metrics.agreementRate)).toBe("50%");
    expect(averageLabel(metrics.avgSteps)).toBe("2.0");
  });

  it("verifikator tidak bicara sama sekali → tingkat kesesuaian null, bukan 0% atau 100%", () => {
    const metrics = qualityMetrics([runOf({ decision_id: "d9", iteration: 1 }, null, null)]);
    expect(metrics.judged).toBe(0);
    expect(metrics.agreementRate).toBe(null);
    expect(percentLabel(metrics.agreementRate)).toBe("—");
  });

  it("tanpa run: semua metrik null/kosong (halaman kosong yang jujur)", () => {
    const metrics = qualityMetrics([]);
    expect(metrics.runs).toBe(0);
    expect(metrics.totalSteps).toBe(null);
    expect(metrics.avgDurationMs).toBe(null);
    expect(metrics.avgDurationLabel).toBe("—");
  });

  it("durasi sub-detik ditulis jujur (stempel waktu hanya sampai detik)", () => {
    expect(durationLabel(0)).toBe("< 1 s");
    expect(durationLabel(999)).toBe("< 1 s");
    expect(durationLabel(1000)).toBe("1.0 s");
  });
});

describe("runOf — kehadiran agen di jejak", () => {
  const TRACE_AGEN = {
    steps: [
      // Langkah pipeline tanpa nama agen: bukan keluaran agen, jangan dihitung.
      { step_name: "DETECT", tool_called: "supply.get+demand.get", output_summary: { gap_kg: "1" } },
      { step_name: "DETECT", tool_called: "agent.supply", agent_name: "supply", output_summary: { facts: { status: "shortage" } } },
      { step_name: "VERIFY", tool_called: "agent.verifier", agent_name: "verifier", output_summary: { facts: { verdict: "consistent" } } },
      { step_name: "SUPERVISE", tool_called: "supervisor.narration", agent_name: null, output_summary: { status: "narrated", summary: "x" } },
      // Baris agen tanpa keluaran: tercatat, tidak "ada keluaran".
      { step_name: "OPTIMIZE", tool_called: "agent.price", agent_name: "price", output_summary: null },
    ],
  };

  it("mencatat agen yang benar-benar punya baris, termasuk supervisor", () => {
    const run = runOf(DECISION, TRACE_AGEN, SUMMARY_AGREE);
    expect(run.agents).toEqual(["supply", "verifier", "supervisor", "price"]);
    expect(run.deliveredAgents).toEqual(["supply", "verifier", "supervisor"]);
  });

  it("langkah pipeline tanpa nama agen tidak dihitung sebagai agen", () => {
    const run = runOf(DECISION, TRACE, SUMMARY_AGREE);
    expect(run.agents).toEqual([]);
    expect(run.deliveredAgents).toEqual([]);
  });

  it("tanpa jejak: daftar agen kosong, bukan karangan", () => {
    const run = runOf(DECISION, null, null);
    expect(run.agents).toEqual([]);
    expect(run.deliveredAgents).toEqual([]);
  });
});

describe("agentQuality — kualitas per agen dari data nyata", () => {
  const TRACE_AGEN = {
    steps: [
      { step_name: "DETECT", tool_called: "agent.supply", agent_name: "supply", output_summary: { facts: {} } },
      { step_name: "VERIFY", tool_called: "agent.verifier", agent_name: "verifier", output_summary: { facts: {} } },
      { step_name: "SUPERVISE", tool_called: "supervisor.narration", output_summary: { status: "narrated" } },
    ],
  };
  const RUNS = [
    runOf({ decision_id: "a1", iteration: 1 }, TRACE_AGEN, { verifier: { verdict: "consistent" } }),
    runOf({ decision_id: "b1", iteration: 1 }, TRACE_AGEN, { verifier: { verdict: "flagged" } }),
    runOf({ decision_id: "c1", iteration: 1 }, { steps: [{ step_name: "DETECT", tool_called: "supply.get" }] }, null),
  ];

  it("sembilan baris berurutan: tujuh worker, supervisor, verifier", () => {
    const rows = agentQuality(RUNS);
    expect(rows).toHaveLength(9);
    expect(rows.map((row) => row.key)).toEqual([
      "supply",
      "demand",
      "freshness",
      "safety",
      "price",
      "logistics",
      "evidence",
      "supervisor",
      "verifier",
    ]);
    expect(rows[7].label).toBe("Supervisor");
    expect(rows[8].label).toBe("Verifier");
  });

  it("menghitung run tercatat, keluaran, dan yang tidak tercatat", () => {
    const rows = agentQuality(RUNS);
    const peta = Object.fromEntries(rows.map((row) => [row.key, row]));
    expect(peta.supply).toMatchObject({ runs: 3, recorded: 2, delivered: 2, missing: 1 });
    expect(peta.supervisor).toMatchObject({ runs: 3, recorded: 2, delivered: 2, missing: 1 });
    // Worker yang tidak pernah muncul: 0 tercatat dari 3 run — bukan "—".
    expect(peta.logistics).toMatchObject({ recorded: 0, delivered: 0, missing: 3 });
  });

  it("rincian putusan verifier dari approval-summary, bukan dari jejak", () => {
    const rows = agentQuality(RUNS);
    const verifier = rows[8];
    expect(verifier.verdicts).toEqual({ agree: 1, disagree: 1, unavailable: 1 });
    expect(verifier.verdictNote).toBe("Setuju 1 · Tidak setuju 1 · Tidak tersedia 1");
    // Agen lain tidak punya putusan; ditulis "—" bukan 0.
    expect(rows[0].verdicts).toBeNull();
    expect(rows[0].verdictNote).toBe("—");
  });

  it("tanpa run: tidak ada baris karangan", () => {
    expect(agentQuality([])).toEqual([]);
  });
});
