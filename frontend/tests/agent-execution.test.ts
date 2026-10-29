import { describe, expect, it } from "vitest";

import {
  executionOverview,
  isOverdue,
  needsAttention,
} from "../lib/agent-execution";
import type { AuditDecision } from "../lib/decision-table";

const NOW = new Date("2026-10-29T05:00:00.000Z");

function row(over: Partial<AuditDecision>): AuditDecision {
  return {
    decision_id: "id-0000",
    decision_type: "supplier_procurement",
    status: "pending_approval",
    created_at: "2026-10-28T05:00:00.000Z",
    expires_at: "2026-10-30T05:00:00.000Z",
    ...over,
  } as AuditDecision;
}

describe("executionOverview", () => {
  it("menghitung keadaan yang benar-benar ada di daftar keputusan", () => {
    const rows = [
      row({ decision_id: "a", has_agent_review: true }),
      row({ decision_id: "b", has_agent_review: false }),
      row({ decision_id: "c", status: "approved", has_agent_review: true }),
      row({ decision_id: "d", status: "rejected" }),
      row({ decision_id: "e", status: "verifier_flagged" }),
      row({ decision_id: "f", status: "executed", expires_at: "2026-10-01T05:00:00.000Z" }),
    ];

    expect(executionOverview(rows, NOW)).toEqual({
      total: 6,
      reviewed: 2,
      waiting: 3,
      rejected: 1,
      flagged: 1,
      overdue: 0,
      attention: 1,
    });
  });

  it("daftar kosong menghasilkan nol, bukan undefined", () => {
    expect(executionOverview([], NOW)).toEqual({
      total: 0,
      reviewed: 0,
      waiting: 0,
      rejected: 0,
      flagged: 0,
      overdue: 0,
      attention: 0,
    });
  });

  it("hanya keputusan yang masih menunggu tindakan yang bisa lewat tenggat", () => {
    const lewat = "2026-10-28T00:00:00.000Z";
    expect(isOverdue(row({ status: "pending_approval", expires_at: lewat }), NOW)).toBe(true);
    expect(isOverdue(row({ status: "approved", expires_at: lewat }), NOW)).toBe(false);
    expect(isOverdue(row({ status: "executed", expires_at: lewat }), NOW)).toBe(false);
    expect(isOverdue(row({ status: "rejected", expires_at: lewat }), NOW)).toBe(false);
    // Tepat pada waktu kedaluwarsa belum dihitung lewat: batasnya "<", bukan "<=".
    expect(isOverdue(row({ expires_at: NOW.toISOString() }), NOW)).toBe(false);
  });

  it("tanggal kedaluwarsa kosong atau rusak tidak pernah dibaca sebagai lewat", () => {
    expect(isOverdue(row({ expires_at: null }), NOW)).toBe(false);
    expect(isOverdue(row({ expires_at: "" }), NOW)).toBe(false);
    expect(isOverdue(row({ expires_at: "bukan tanggal" }), NOW)).toBe(false);
  });

  it("keputusan yang ditandai verifikator DAN lewat tenggat dihitung sekali", () => {
    const rows = [row({ status: "verifier_flagged", expires_at: "2026-10-01T00:00:00.000Z" })];
    const hasil = executionOverview(rows, NOW);
    expect(hasil.flagged).toBe(1);
    expect(hasil.overdue).toBe(1);
    expect(hasil.attention).toBe(1);
    expect(needsAttention(rows[0], NOW)).toBe(true);
  });

  it("has_agent_review hanya dihitung bila benar-benar true", () => {
    const rows = [
      row({ decision_id: "a", has_agent_review: true }),
      row({ decision_id: "b" }),
      row({ decision_id: "c", has_agent_review: false }),
    ];
    expect(executionOverview(rows, NOW).reviewed).toBe(1);
  });
});
