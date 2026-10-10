export type ComplianceStatus = "PASS" | "FAIL" | "NEEDS_VERIFICATION";

export type ComplianceEvidence = {
  id: string;
  evidence_type: string;
  payload?: Record<string, unknown> | null;
  is_consistent?: boolean | null;
  recorded_at?: string | null;
};

export type ComplianceDossier = {
  decision_id: string;
  content_address?: string;
  signature?: Record<string, unknown>;
  verify?: boolean | null;
  decision?: Record<string, unknown>;
  evidence?: ComplianceEvidence[];
  approvals?: unknown[];
  traces?: unknown[];
  [key: string]: unknown;
};

export type EvidenceRow = {
  id: string;
  evidenceType: string;
  status: ComplianceStatus;
  reading: unknown;
  unit: unknown;
  source: unknown;
  provenance: unknown;
  recordedAt: string | null;
  consistency: boolean | null;
  rule: unknown;
  payload: Record<string, unknown>;
};

const STATUS_KEYS = ["status", "safety_status", "outcome_status"] as const;
const READING_KEYS = ["reading", "value", "measurement", "measured_value"] as const;

function statusFrom(value: unknown): ComplianceStatus {
  if (typeof value === "string") {
    const upper = value.toUpperCase();
    if (upper === "PASS" || upper === "FAIL" || upper === "NEEDS_VERIFICATION") return upper;
  }
  // Missing persisted status/measurement is not evidence of safety.
  return "NEEDS_VERIFICATION";
}

export function evidenceRowsFromDossier(dossier: ComplianceDossier): EvidenceRow[] {
  return (dossier.evidence ?? []).map((item) => {
    const payload = item.payload ?? {};
    const statusValue = STATUS_KEYS.map((key) => payload[key]).find((value) => value !== undefined);
    const reading = READING_KEYS.map((key) => payload[key]).find((value) => value !== undefined) ?? null;
    return {
      id: item.id,
      evidenceType: item.evidence_type,
      status: statusFrom(statusValue),
      reading,
      unit: payload.unit ?? null,
      source: payload.source ?? payload.provenance ?? null,
      provenance: payload.provenance ?? payload.source ?? null,
      recordedAt: item.recorded_at ?? null,
      consistency: item.is_consistent ?? null,
      rule: payload.rule ?? null,
      payload,
    };
  });
}
