// Kontrak markup halaman "Kualitas Agen" (halaman sidebar acuan /quality).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import AgentQualityBoard from "../components/AgentQualityBoard";
import { runOf } from "../lib/agent-quality";

const TRACE = {
  steps: [
    { step_name: "PREDICT", tool_called: "forecast.daily", output_summary: { method: "provider_forecast" }, step_at: "2026-10-11T05:16:46Z" },
    { step_name: "DECIDE", tool_called: "supply_balance.propose", output_summary: { sdc: 1 }, step_at: "2026-10-11T05:16:48Z" },
  ],
};

const RUNS = [
  runOf({ decision_id: "e430a0e8-9d9a", decision_type: "regional_balance", status: "pending_approval", iteration: 3 }, TRACE, { verifier: { verdict: "consistent" } }),
  runOf({ decision_id: "b24f509d-decc", decision_type: "safety_disruption", status: "verifier_flagged", iteration: 1 }, TRACE, { verifier: { verdict: "flagged" } }),
];

function render(props: Partial<Parameters<typeof AgentQualityBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <AgentQualityBoard runs={RUNS} evaluatedCount={8} totalDecisions={95} {...props} />
  );
}

describe("AgentQualityBoard", () => {
  it("judul + skor agregat dari run nyata", () => {
    const html = render();
    expect(html).toContain("Kualitas Agen");
    expect(html).toContain("Skor agregat");
    expect(html).toContain("Kesesuaian verifier");
    expect(html).toContain("50%");
    expect(html).toContain("1 dari 2 yang dinilai");
  });

  it("tabel per run memuat langkah, alat, verifikator, durasi, iterasi", () => {
    const html = render();
    expect(html).toContain("Rincian per run");
    expect(html).toContain("forecast.daily, supply_balance.propose");
    expect(html).toContain("Setuju");
    expect(html).toContain("Tidak setuju");
    expect(html).toContain("2.0 s");
    expect(html).toContain("e430a0e8");
  });

  it("kesesuaian tanpa penilaian verifikator ditulis '—', bukan 0%", () => {
    const html = render({ runs: [runOf({ decision_id: "d1", iteration: 1 }, TRACE, null)] });
    expect(html).toContain("belum ada penilaian verifikator");
    expect(html).toContain("—");
  });

  it("keadaan kosong dijelaskan, bukan tabel hampa", () => {
    const html = render({ runs: [] });
    expect(html).toContain("Belum ada run agen yang tercatat");
  });

  it("catatan metode + cakupan pemindaian ditulis apa adanya", () => {
    const html = render();
    expect(html).toContain("Cara kami menilai");
    expect(html).toContain("8 keputusan terakhir");
  });

  it("galat pemuatan dijelaskan", () => {
    expect(render({ error: "traces 500" })).toContain("Tidak bisa memuat jejak agen");
  });
});
