// Penanda "lewat tenggat" di kolom Kedaluwarsa (UI-1, 29 Okt 2026).
//
// Keputusan yang sudah disetujui/dieksekusi/ditolak TIDAK ditandai meski
// tanggalnya lewat: itu riwayat, bukan tunggakan. Tanpa `now`, tabel tidak
// menandai apa pun (dipakai saat jam klien belum siap).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import DecisionAuditTable from "../components/DecisionAuditTable";
import type { AuditDecision } from "../lib/decision-table";

const NOW = new Date("2026-10-29T05:00:00.000Z");

function row(over: Partial<AuditDecision>): AuditDecision {
  return {
    decision_id: "aaaaaaaa-1111-2222-3333-444444444444",
    decision_type: "supplier_procurement",
    status: "pending_approval",
    expires_at: "2026-10-28T05:00:00.000Z",
    created_at: "2026-10-27T05:00:00.000Z",
    ...over,
  } as AuditDecision;
}

function render(rows: AuditDecision[], now: Date | null = NOW) {
  return renderToStaticMarkup(
    <DecisionAuditTable
      rows={rows}
      total={rows.length}
      page={1}
      onPage={() => {}}
      selectedId={null}
      onSelect={() => {}}
      summary="tes"
      now={now}
    />
  );
}

describe("penanda lewat tenggat", () => {
  it("menandai keputusan yang masih menunggu tindakan", () => {
    expect(render([row({ status: "pending_approval" })])).toContain("lewat tenggat");
    expect(render([row({ status: "verifier_flagged" })])).toContain("lewat tenggat");
  });

  it("tidak menandai keputusan yang sudah selesai", () => {
    for (const status of ["approved", "executed", "rejected"]) {
      const html = render([row({ status, expires_at: "2026-10-01T05:00:00.000Z" })]);
      expect(html).not.toContain("lewat tenggat");
    }
  });

  it("tanpa jam acuan tidak ada penanda", () => {
    expect(render([row({ status: "pending_approval" })], null)).not.toContain("lewat tenggat");
  });

  it("tenggat yang belum lewat tidak ditandai", () => {
    expect(render([row({ expires_at: "2026-11-05T05:00:00.000Z" })])).not.toContain(
      "lewat tenggat"
    );
  });
});
