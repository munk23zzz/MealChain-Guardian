// Kontrak AgentTraceViewer: satu langkah dengan waktu kosong/tidak sah TIDAK
// boleh menjatuhkan seluruh jejak agen (new Date(undefined).toISOString()
// melempar RangeError saat render). Nilai yang tak terbaca ditulis "—",
// sejalan dengan lib/datetime.ts.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import AgentTraceViewer from "../components/AgentTraceViewer";

const LANGKAH_VALID = {
  step_name: "PLAN",
  step_at: "2026-10-10T18:16:47.844642+00:00",
  tool_called: "balance_engine",
  output_summary: { ok: true },
};

describe("AgentTraceViewer — waktu langkah", () => {
  it("step_at kosong (undefined) tidak menjatuhkan trace", () => {
    const steps = [LANGKAH_VALID, { step_name: "SUPERVISE", step_at: undefined, tool_called: null }];
    const html = renderToStaticMarkup(<AgentTraceViewer steps={steps as any} />);
    expect(html).toContain("PLAN");
    expect(html).toContain("SUPERVISE");
    expect(html).toContain("—");
  });

  it("step_at berisi teks tak sah tidak melempar RangeError", () => {
    const steps = [{ step_name: "VERIFY", step_at: "bukan-tanggal", tool_called: null }];
    const html = renderToStaticMarkup(<AgentTraceViewer steps={steps as any} />);
    expect(html).toContain("VERIFY");
    expect(html).toContain("—");
  });

  it("waktu UTC normal tetap tercetak sebagai jam:menit:detik UTC", () => {
    const html = renderToStaticMarkup(<AgentTraceViewer steps={[LANGKAH_VALID] as any} />);
    expect(html).toContain("18:16:47 UTC");
  });
});
