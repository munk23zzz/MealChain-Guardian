// Data panel review sembilan agen — kartu tidak mengarang nilai yang tidak ada.
//
// Sembilan = tujuh worker + supervisor + verifier. Supervisor adalah kelas
// pertama: kartunya dibangun dari `run.supervisor`, bukan dari baris worker.
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
    {
      run_id: RUN,
      step_name: "VERIFY",
      agent_name: "verifier",
      duration_ms: 1600,
      confidence: 0.9,
      citations: [{ source: "/audit", claim: "audit" }],
      output_summary: {
        status: "ok",
        summary: "Audit sepakat.",
        warning_count: 0,
        warnings: [],
        facts: { verdict: "consistent" },
      },
    },
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

describe("swarmCards — tepat sembilan kartu: worker → supervisor → verifier", () => {
  it("sembilan kartu berurutan dan label manusia", () => {
    const run = latestSwarmRun(runRows());
    const cards = swarmCards(run!);
    expect(cards).toHaveLength(9);
    expect(cards.map((card) => card.key)).toEqual([
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
    // Urutan pipeline: worker → SUPERVISE → audit.
    expect(cards[7].label).toBe("Supervisor");
    expect(cards[7].stage).toBe("SUPERVISE");
    expect(cards[8].label).toBe("Verifikasi");
    expect(cards[8].stage).toBe("VERIFY");
    expect(cards[0].label).toBe("Pasokan");
    expect(cards[0].statusLabel).toBe("Selesai");
    expect(cards[0].duration).toBe("1,5 dtk");
    expect(cards[0].confidence).toBe("87%");
    expect(cards[0].citations).toBe("1 sitasi");
    expect(cards[0].warningCount).toBe(0);
    // Verifier tetap kartu kelas satu dengan datanya sendiri.
    expect(cards[8].row).not.toBeNull();
    expect(cards[8].statusLabel).toBe("Selesai");
    expect(cards[8].duration).toBe("1,6 dtk");
    expect(cards[8].citations).toBe("1 sitasi");
  });

  it("kartu supervisor diambil dari run.supervisor, bukan dari baris worker", () => {
    // Baris supervisor sengaja TIDAK ada di `rows`: kartu hanya bisa terisi
    // kalau ia benar-benar membaca `run.supervisor`.
    const run = {
      runId: RUN,
      rows: [row("supply"), row("demand")],
      supervisor: {
        run_id: RUN,
        step_name: "SUPERVISE",
        agent_name: "supervisor",
        duration_ms: 2500,
        citations: [],
        output_summary: {
          status: "narrated",
          narrative: "Narasi dari supervisor.",
          summary: "Ringkas dari supervisor.",
          safety_veto: false,
          contradiction_count: 0,
        },
      },
    };
    const cards = swarmCards(run);
    const sup = cards[7];
    expect(sup.row).not.toBeNull();
    // `narrated` adalah status narasi supervisor, bukan enum mentah di layar.
    expect(sup.status).toBe("ok");
    expect(sup.statusLabel).toBe("Narasi selesai");
    expect(sup.summary).toBe("Narasi dari supervisor.");
    expect(sup.duration).toBe("2,5 dtk");
    // Supervisor tidak punya confidence → "—", bukan 0. Sitasi array kosong
    // tetap dihitung apa adanya (0 sitasi), bukan disembunyikan.
    expect(sup.confidence).toBe("—");
    expect(sup.citations).toBe("0 sitasi");
  });

  it("supervisor belum tercatat: kartu tetap ada, nilai tetap —/Belum tercatat", () => {
    const run = latestSwarmRun([row("supply"), row("demand")]);
    const cards = swarmCards(run!);
    expect(cards).toHaveLength(9);
    const sup = cards[7];
    expect(sup.row).toBeNull();
    expect(sup.statusLabel).toBe("Belum tercatat");
    expect(sup.duration).toBe("—");
    expect(sup.summary).toBe("—");
    expect(sup.warningCount).toBeNull();
  });

  it("kartu yang tidak tercatat tetap sembilan, tanpa angka palsu", () => {
    const run = latestSwarmRun([row("supply")]);
    const cards = swarmCards(run!);
    expect(cards).toHaveLength(9);
    expect(cards[8].row).toBeNull();
    expect(cards[8].statusLabel).toBe("Belum tercatat");
    expect(cards[8].confidence).toBe("—");
    expect(cards[8].citations).toBe("—");
  });

  it("supervisor: status/narrative/veto/kontradiksi apa adanya", () => {
    const run = latestSwarmRun(runRows());
    const summary = supervisorSummary(run!);
    expect(summary.status).toBe("Selesai");
    expect(summary.narrative).toBe("Review selesai.");
    expect(summary.veto).toBe("Tidak");
    expect(summary.contradictions).toBe("0");
  });

  it("narasi supervisor tidak tersedia tetap dilaporkan apa adanya", () => {
    const run = {
      runId: RUN,
      rows: [],
      supervisor: {
        run_id: RUN,
        step_name: "SUPERVISE",
        output_summary: { status: "unavailable" },
      },
    };
    const card = swarmCards(run)[7];
    expect(card.status).toBe("degraded");
    expect(card.statusLabel).toBe("Narasi tidak tersedia");
    expect(card.summary).toBe("—");
  });

  it("verifier yang menulis run terpisah tetap terbaca sebagai auditan keputusan ini", () => {
    // Data nyata: `agent.verifier` menulis barisnya di run_id audit SENDIRI
    // (verify.py punya run sendiri), sedangkan worker menulis di run pipeline.
    // Tanpa toleransi ini kartu verifier selalu "Belum tercatat" padahal audit
    // benar-benar terjadi untuk keputusan yang sama.
    const AUDIT_RUN = "9f9f9f9f-9999-4999-8999-999999999999";
    const run = latestSwarmRun([
      row("supply"),
      row("demand"),
      {
        run_id: AUDIT_RUN,
        step_name: "VERIFY",
        agent_name: "verifier",
        duration_ms: 9000,
        citations: [{ source: "/audit", claim: "audit" }],
        output_summary: { status: "ok", summary: "Audit sepakat." },
      },
    ]);
    const cards = swarmCards(run!);
    expect(cards[8].row).not.toBeNull();
    expect(cards[8].statusLabel).toBe("Selesai");
    expect(cards[8].summary).toBe("Audit sepakat.");
    expect(cards[8].duration).toBe("9,0 dtk");
    // Baris worker tetap dari run yang dipilih, bukan dicampur.
    expect(cards[0].row?.run_id).toBe(RUN);
  });
});

describe("label nilai — tidak menampilkan enum mentah", () => {
  it("status dikenal → label; tak dikenal → 'Tidak dikenal'; kosong → —", () => {
    expect(statusLabel("ok")).toBe("Selesai");
    expect(statusLabel("error")).toBe("Gagal");
    expect(statusLabel("degraded")).toBe("Terbatas");
    // Status run yang mencerminkan veto guardian (agent/contracts.py) tidak
    // boleh muncul sebagai enum mentah di layar.
    expect(statusLabel("vetoed")).toBe("Diblokir");
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
