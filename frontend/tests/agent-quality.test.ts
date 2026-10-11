// Kontrak halaman "Kualitas Agen" (halaman sidebar acuan /quality).
import { describe, expect, it } from "vitest";

import {
  AGENT_QUALITY_METHOD_NOTE,
  VERDICT_LABEL,
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

  it("catatan metode menyebut cara penilaian dan yang belum ada", () => {
    expect(AGENT_QUALITY_METHOD_NOTE).toContain("consistent");
    expect(AGENT_QUALITY_METHOD_NOTE).toContain("LLM-as-judge belum ada");
  });

  it("durasi sub-detik ditulis jujur (stempel waktu hanya sampai detik)", () => {
    expect(durationLabel(0)).toBe("< 1 s");
    expect(durationLabel(999)).toBe("< 1 s");
    expect(durationLabel(1000)).toBe("1.0 s");
  });
});
