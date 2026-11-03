import { afterEach, describe, expect, it, vi } from "vitest";

import { triggerSafetyDisruption } from "../lib/api";

// Kontrak payload POST /events/safety-disruption.
//
// Backend memakai `model_config = ConfigDict(extra="forbid")` dengan field
// batch_id / target_location_id / operation_key (+ previous_decision_id
// opsional). ChaosPanel dulu mengirim `severity_hint_pct` yang tidak dikenal
// model → SETIAP "Picu Event 3" dari UI membalas 422 dan tidak ada keputusan
// safety_disruption yang bisa dibuat. Tes ini mengunci bentuk body-nya.

describe("POST /events/safety-disruption — kontrak payload", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("mengirim hanya field yang diterima backend", async () => {
    const panggilan: Array<{ url: string; init: RequestInit }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        panggilan.push({ url, init });
        return new Response(
          JSON.stringify({ status: "no_disruption", decision_id: null }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      })
    );

    await triggerSafetyDisruption("batch-1", "lokasi-1", "op-1", "token-1");

    expect(panggilan).toHaveLength(1);
    expect(panggilan[0].url).toContain("/events/safety-disruption");
    const body = JSON.parse(String(panggilan[0].init.body));
    expect(Object.keys(body).sort()).toEqual([
      "batch_id",
      "operation_key",
      "target_location_id",
    ]);
    expect(body.batch_id).toBe("batch-1");
    expect(body.target_location_id).toBe("lokasi-1");
  });
});
