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
    expect(html).toContain("forecast.daily");
    expect(html).toContain("supply_balance.propose");
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

  it("cakupan sampel ditulis apa adanya, tanpa catatan metode internal", () => {
    const html = render();
    expect(html).not.toContain("Cara kami menilai");
    expect(html).not.toContain("/decisions/{id}/traces");
    expect(html).toContain("8 keputusan terakhir");
  });

  it("galat pemuatan dijelaskan", () => {
    expect(render({ error: "traces 500" })).toContain("Tidak bisa memuat jejak agen");
  });

  it("skor agregat jadi kartu metrik dengan meter dari persennya", () => {
    const html = render();
    expect(html).toContain("class=\"quality-stat quality-stat-hero\"");
    // Kesesuaian verifier 1 dari 2 = 50% → meter 50, bukan angka lain.
    expect(html).toContain("data-meter=\"50\"");
    expect(html).toContain("quality-meter-fill");
  });

  it("putusan verifikator jadi bar bertumpuk + legenda berlabel", () => {
    const html = render();
    expect(html).toContain("role=\"img\"");
    expect(html).toContain(
      "Komposisi putusan verifikator: 1 setuju, 1 tidak setuju, 0 tidak tersedia dari 2 run."
    );
    expect(html).toContain("quality-verdict-seg-ok");
    expect(html).toContain("quality-legend-dot-danger");
  });

  it("tanpa run, bar putusan ditandai kosong (bukan segmen palsu)", () => {
    const html = render({ runs: [] });
    expect(html).toContain("data-empty=\"true\"");
    expect(html).not.toContain("quality-verdict-seg-ok");
  });

  it("status & putusan jadi lencana bertone, kata statusnya tetap apa adanya", () => {
    const html = render();
    expect(html).toContain("data-status-tone=\"warn\""); // pending_approval
    expect(html).toContain("data-status-tone=\"danger\""); // verifier_flagged
    expect(html).toContain("pending approval");
    expect(html).toContain("verifier flagged");
  });

  it("persen legenda tidak dibulatkan sendiri-sendiri (jumlahnya tetap 100%)", () => {
    const three = [
      runOf({ decision_id: "a1", iteration: 1 }, TRACE, { verifier: { verdict: "consistent" } }),
      runOf({ decision_id: "b1", iteration: 1 }, TRACE, null),
      runOf({ decision_id: "c1", iteration: 1 }, TRACE, null),
    ];
    const html = render({ runs: three });
    // 1/3 dan 2/3: dibulatkan penuh akan jadi 33% + 67% (tetap 100), tetapi
    // satu desimal lebih jujur dan tetap berjumlah 100,0%.
    expect(html).toContain("1 · 33.3%");
    expect(html).toContain("2 · 66.7%");
  });
});
