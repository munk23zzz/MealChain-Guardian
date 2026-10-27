// Kontrak render panel sembilan agen: tujuh worker + supervisor + verifier,
// status manusia, dan empty state yang membedakan "belum pilih keputusan" vs
// "keputusan ini belum direview".
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import AgentSwarmPanel from "../components/AgentSwarmPanel";

const RUN = "12345678-1234-4678-9abc-123456789abc";

function step(agent: string, stage = "DETECT", index = 0) {
  return {
    run_id: RUN,
    step_name: stage,
    agent_name: agent,
    duration_ms: 1200,
    confidence: 0.9,
    citations: [{ source: "/x", claim: "x" }],
    step_at: `2026-10-18T10:00:0${index}Z`,
    output_summary: {
      status: "ok",
      summary: `${agent} selesai`,
      warning_count: 0,
      warnings: [],
      facts: { nilai: 1 },
    },
  };
}

function rows() {
  return [
    step("supply", "DETECT", 0),
    step("demand", "PREDICT", 1),
    step("freshness", "VERIFY", 2),
    step("safety", "VERIFY", 3),
    step("price", "OPTIMIZE", 4),
    step("logistics", "OPTIMIZE", 5),
    step("evidence", "TRACE", 6),
    {
      run_id: RUN,
      step_name: "SUPERVISE",
      agent_name: "supervisor",
      step_at: "2026-10-18T10:00:07Z",
      output_summary: {
        status: "narrated",
        narrative: "Review selesai tanpa kontradiksi.",
        safety_veto: false,
        contradiction_count: 0,
      },
    },
    {
      run_id: RUN,
      step_name: "VERIFY",
      agent_name: "verifier",
      duration_ms: 1600,
      confidence: 0.8,
      citations: [{ source: "/audit", claim: "audit" }],
      step_at: "2026-10-18T10:00:08Z",
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

describe("AgentSwarmPanel", () => {
  it("merender tepat 9 kartu — worker, supervisor, verifier — status manusia", () => {
    const html = renderToStaticMarkup(
      <AgentSwarmPanel steps={rows() as any} decisionId="d1" />
    );
    expect(html.match(/class="swarm-card"/g)).toHaveLength(9);
    expect(html).toContain("Pasokan");
    expect(html).toContain("Keamanan Pangan");
    expect(html).toContain("Selesai");
    // Supervisor adalah kartu, bukan hanya blok ringkasan terpisah.
    expect(html).toContain(">Supervisor</h3>");
    expect(html).toContain("Narasi selesai");
    expect(html).toContain("Verifikasi");
    expect(html).toContain("Review selesai tanpa kontradiksi.");
    expect(html).not.toContain(">ok<");
    expect(html).toContain("run 12345678");
    // Teks jumlah agen ikut sembilan: tidak ada sisa "8 agen"/"delapan".
    expect(html).toContain("sembilan agen");
    expect(html).not.toContain("8 agen");
    expect(html).not.toContain("delapan");
    // Veto & kontradiksi tetap terbaca sesudah supervisor jadi kartu.
    expect(html).toContain("Safety veto");
  });

  it("kartu tanpa baris tetap tampil dengan Belum tercatat", () => {
    const html = renderToStaticMarkup(
      <AgentSwarmPanel steps={rows().slice(0, 3) as any} decisionId="d1" />
    );
    expect(html.match(/class="swarm-card"/g)).toHaveLength(9);
    expect(html).toContain("Belum tercatat");
    expect(html).toContain("3/9 tercatat");
  });

  it("dua empty state yang berbeda", () => {
    const tanpaPilihan = renderToStaticMarkup(
      <AgentSwarmPanel steps={[] as any} decisionId={null} />
    );
    expect(tanpaPilihan).toContain("Pilih keputusan dulu");
    const kosong = renderToStaticMarkup(
      <AgentSwarmPanel steps={[] as any} decisionId="d1" />
    );
    expect(kosong).toContain("Belum ada review sembilan agen untuk keputusan ini.");
  });
});
