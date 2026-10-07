// Test ApprovalModal + role scope (S3-12, TDD).
// Kontrak design.md:
// - §1.3 approval = friksi disengaja: ringkasan WAJIB tampil sebelum
//   approve; tanpa ringkasan → approval ditolak (tidak ada approve-all).
// - §1.4 role scope: bgn_monitor TIDAK pernah melihat aksi mutasi;
//   execute hanya untuk status yang memenuhi syarat di backend.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import ApprovalModal from "../components/ApprovalModal";
import { visibleActions } from "../components/DecisionActions";
import DecisionActions from "../components/DecisionActions";

describe("ApprovalModal (friksi disengaja)", () => {
  it("menampilkan ringkasan: jumlah, biaya, verdict", () => {
    const html = renderToStaticMarkup(
      <ApprovalModal
        summary={{
          quantity_kg: 600,
          safe_delivered_cost: "16206000.00",
          verdict: "CONSISTENT",
        }}
      />
    );
    expect(html).toContain("600 kg");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("CONSISTENT");
  });

  it("tanpa ringkasan → menolak approval (tidak ada approve-all)", () => {
    const html = renderToStaticMarkup(<ApprovalModal summary={null} />);
    expect(html).toContain("Tidak ada ringkasan");
  });
});

describe("visibleActions (role scope murni, design.md §1.4)", () => {
  it("bgn_monitor tidak pernah melihat aksi mutasi", () => {
    expect(visibleActions("bgn_monitor", "pending_approval")).toEqual({
      approve: false,
      execute: false,
      repropose: false,
      readOnly: true,
    });
  });

  it("sppg_head melihat approve+execute pada status yang memenuhi syarat", () => {
    expect(visibleActions("sppg_head", "pending_approval")).toEqual({
      approve: true,
      execute: true,
      repropose: false,
      readOnly: false,
    });
  });

  it("status executed/rejected → tanpa aksi", () => {
    expect(visibleActions("sppg_head", "executed").execute).toBe(false);
    expect(visibleActions("sppg_head", "rejected").approve).toBe(false);
  });
});

describe("DecisionActions render", () => {
  it("bgn_monitor → catatan read-only, tanpa tombol", () => {
    const html = renderToStaticMarkup(
      <DecisionActions
        decisionId="d1"
        role="bgn_monitor"
        status="pending_approval"
        token="t"
      />
    );
    expect(html).toContain("read-only");
    expect(html).not.toContain(">Approve<");
  });
});
