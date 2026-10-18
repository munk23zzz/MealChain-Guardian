// Data panel review 7 agen — kartu tidak mengarang nilai yang tidak ada.
import { describe, expect, it } from "vitest";

import {
  confidenceLabel,
  citationsLabel,
  latestSwarmRun,
  shortRunId,
  statusLabel,
  supervisorSummary,
  swarmCards,
  vetoLabel,
  warningCountOf,
} from "../lib/agent-swarm";

const RUN = "12345678-1234-4678-9abc-123456789abc";

function row(agent: string, extra: Record<string, unknown> = {}) {
  return {
    run_id: RUN,
    step_name: "DETECT",
    agent_name: agent,
    duration_ms: 1500,
    confidence: 0.87,
    citations: [{ source: "/x", claim: "x" }],
    output_summary: {
      status: "ok",
      summary: `${agent} selesai`,
      warning_count: 0,
      warnings: [],
      facts: {},
    },
    ...extra,
  };
}

function runRows() {
  return [
    row("supply"),
    row("demand"),
    row("freshness"),
    row("safety"),
    row("price"),
    row("logistics"),
    row("evidence"),
    row("supervisor", {
      step_name: "SUPERVISE",
      confidence: null,
      citations: [],
      output_summary: {
        status: "completed",
        narrative: "Review selesai.",
        safety_veto: false,
        contradiction_count: 0,
      },
    }),
  ];
}

describe("latestSwarmRun — pilih putaran terbaru", () => {
  it("memilih run dengan step_at terbaru, bukan urutan array", () => {
    const old = row("supply", {
      run_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      step_at: "2026-10-18T10:00:00Z",
    });
    const newest = row("supply", {
      run_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      step_at: "2026-10-18T11:00:00Z",
    });
    const run = latestSwarmRun([old, newest]);
    expect(run?.runId).toBe("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb");
  });

  it("baris tanpa run_id (trace lama) tidak dianggap review", () => {
    expect(latestSwarmRun([{ step_name: "DETECT" }])).toBeNull();
    expect(latestSwarmRun([])).toBeNull();
    expect(latestSwarmRun(null)).toBeNull();
  });
});

describe("swarmCards — tepat tujuh kartu, nilai null jadi —", () => {
  it("tujuh kartu berurutan dan label manusia", () => {
    const run = latestSwarmRun(runRows());
    const cards = swarmCards(run!);
    expect(cards).toHaveLength(7);
    expect(cards.map((card) => card.key)).toEqual([
      "supply",
      "demand",
      "freshness",
      "safety",
      "price",
      "logistics",
      "evidence",
    ]);
    expect(cards[0].label).toBe("Pasokan");
    expect(cards[0].statusLabel).toBe("Selesai");
    expect(cards[0].duration).toBe("1,5 dtk");
    expect(cards[0].confidence).toBe("87%");
    expect(cards[0].citations).toBe("1 sitasi");
    expect(cards[0].warningCount).toBe(0);
  });

  it("kartu yang tidak tercatat tetap tujuh, tanpa angka palsu", () => {
    const run = latestSwarmRun(runRows().slice(0, 3));
    const cards = swarmCards(run!);
    expect(cards).toHaveLength(7);
    expect(cards[6].row).toBeNull();
    expect(cards[6].statusLabel).toBe("Belum tercatat");
    expect(cards[6].confidence).toBe("—");
    expect(cards[6].citations).toBe("—");
  });

  it("supervisor: status/narrative/veto/kontradiksi apa adanya", () => {
    const run = latestSwarmRun(runRows());
    const summary = supervisorSummary(run!);
    expect(summary.status).toBe("Selesai");
    expect(summary.narrative).toBe("Review selesai.");
    expect(summary.veto).toBe("Tidak");
    expect(summary.contradictions).toBe("0");
  });
});

describe("label nilai — tidak menampilkan enum mentah", () => {
  it("status dikenal → label; tak dikenal → 'Tidak dikenal'; kosong → —", () => {
    expect(statusLabel("ok")).toBe("Selesai");
    expect(statusLabel("error")).toBe("Gagal");
    expect(statusLabel("degraded")).toBe("Terbatas");
    expect(statusLabel("SESUATU_BARU")).toBe("Tidak dikenal");
    expect(statusLabel(null)).toBe("—");
  });

  it("confidence hanya 0..1; di luar itu —", () => {
    expect(confidenceLabel(0)).toBe("0%");
    expect(confidenceLabel(0.875)).toBe("88%");
    expect(confidenceLabel(1)).toBe("100%");
    expect(confidenceLabel(null)).toBe("—");
    expect(confidenceLabel(1.2)).toBe("—");
  });

  it("sitasi array/kosong/bukan array", () => {
    expect(citationsLabel([])).toBe("0 sitasi");
    expect(citationsLabel([{}, {}])).toBe("2 sitasi");
    expect(citationsLabel(null)).toBe("—");
  });

  it("warning count memakai angka eksplisit, fallback array", () => {
    expect(warningCountOf({ output_summary: { warning_count: 0 } })).toBe(0);
    expect(warningCountOf({ output_summary: { warnings: ["a", "b"] } })).toBe(2);
    expect(warningCountOf({ output_summary: {} })).toBeNull();
  });

  it("veto hanya boolean nyata; null bukan false", () => {
    expect(vetoLabel(true)).toBe("Ya");
    expect(vetoLabel(false)).toBe("Tidak");
    expect(vetoLabel(null)).toBe("—");
  });

  it("short run id kosong jadi —", () => {
    expect(shortRunId(RUN)).toBe("12345678");
    expect(shortRunId(null)).toBe("—");
  });
});
