import { describe, expect, it } from "vitest";

import {
  evidenceRowsFromDossier,
  type ComplianceDossier,
} from "../lib/evidence";

const dossier: ComplianceDossier = {
  decision_id: "dec-1",
  decision: { status: "executed" },
  evidence: [
    {
      id: "ev-1",
      evidence_type: "temperature",
      payload: { value: 4, unit: "C", source: "sensor-7", status: "PASS" },
      is_consistent: true,
      recorded_at: "2026-10-10T01:02:03Z",
    },
    {
      id: "ev-2",
      evidence_type: "human_inspection",
      payload: { status: "NEEDS_VERIFICATION" },
      is_consistent: null,
      recorded_at: null,
    },
  ],
};

describe("compliance evidence adapter", () => {
  it("preserves backend status, readings, provenance and timestamps", () => {
    expect(evidenceRowsFromDossier(dossier)).toEqual([
      expect.objectContaining({
        id: "ev-1",
        status: "PASS",
        reading: 4,
        unit: "C",
        source: "sensor-7",
        recordedAt: "2026-10-10T01:02:03Z",
      }),
      expect.objectContaining({
        id: "ev-2",
        status: "NEEDS_VERIFICATION",
        reading: null,
        recordedAt: null,
      }),
    ]);
  });

  it("does not turn missing measurements into zero or PASS", () => {
    const [row] = evidenceRowsFromDossier({
      decision_id: "dec-2",
      evidence: [{ id: "ev", evidence_type: "temperature", payload: {} }],
    });
    expect(row.reading).toBeNull();
    expect(row.status).toBe("NEEDS_VERIFICATION");
  });

  it("does not conflate an inconsistent record with a safety FAIL", () => {
    const [row] = evidenceRowsFromDossier({
      decision_id: "dec-3",
      evidence: [{ id: "ev", evidence_type: "temperature", payload: {}, is_consistent: false }],
    });
    expect(row.status).toBe("NEEDS_VERIFICATION");
    expect(row.consistency).toBe(false);
  });

  it("keeps provenance distinct and reports unavailable fields as null", () => {
    const [row] = evidenceRowsFromDossier({
      decision_id: "dec-4",
      evidence: [{ id: "ev", evidence_type: "temperature", payload: { provenance: "MOCK" } }],
    });
    expect(row.source).toBe("MOCK");
    expect(row.provenance).toBe("MOCK");
    expect(row.recordedAt).toBeNull();
  });
});
