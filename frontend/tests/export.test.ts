import { describe, expect, it } from "vitest";

import { dossierToCsv, dossierToJson } from "../lib/export";

const dossier = {
  decision_id: "dec-1",
  content_address: "mc1-real",
  signature: { state: "unsigned", reason: "key unavailable" },
  decision: { status: "proposed" },
  evidence: [
    {
      id: "e1",
      evidence_type: "temperature",
      payload: { source: "=CMD()", value: 4 },
      is_consistent: true,
      recorded_at: "2026-10-10T00:00:00Z",
    },
  ],
  traces: [],
};

describe("secure dossier export", () => {
  it("exports the complete authorized dossier as JSON without token fields", () => {
    const parsed = JSON.parse(dossierToJson(dossier));
    expect(parsed).toEqual(dossier);
    expect(JSON.stringify(parsed)).not.toContain("Bearer");
    expect(JSON.stringify(parsed)).not.toMatch(/private.?key|credential|token/i);
  });

  it("escapes CSV formula cells and preserves evidence rows", () => {
    const csv = dossierToCsv(dossier);
    expect(csv).toContain("decision_id,content_address,signature_state,signature,signature_public_key,evidence_id");
    expect(csv).toContain("'=CMD()");
    expect(csv).toContain("e1");
    expect(csv).not.toContain(",=CMD()");
  });

  it("guards formula injection after whitespace and exports integrity metadata", () => {
    const csv = dossierToCsv({
      ...dossier,
      signature: { state: "signed", signature: "sig-1", public_key: "pk-1" },
      evidence: [{ ...dossier.evidence[0], payload: { source: "\t=SUM(1,1)", provenance: "MOCK" } }],
    });
    expect(csv).toContain('"\'\t=SUM(1,1)"');
    expect(csv).toContain("\"mc1-real\",\"signed\",\"sig-1\",\"pk-1\"");
    expect(csv).toContain("\"MOCK\"");
  });
});
