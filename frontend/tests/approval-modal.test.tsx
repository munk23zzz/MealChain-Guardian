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
    // S4-04: shape kanonik — verdict dari read model (verifier.verdict).
    const html = renderToStaticMarkup(
      <ApprovalModal
        summary={{
          quantity_kg: 600,
          safe_delivered_cost: "16206000.00",
          verifier: { verdict: "consistent", verified_by: "verifier_agent" },
        }}
      />
    );
    expect(html).toContain("600 kg");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("Konsisten");
  });

  it("tanpa ringkasan → menolak approval (tidak ada approve-all)", () => {
    const html = renderToStaticMarkup(<ApprovalModal summary={null} />);
    expect(html).toContain("Tidak ada ringkasan");
  });

  it("S4-05 regression: Setuju di-gate can_approve, BUKAN can_execute", () => {
    // Bug rehearsal 2026-10-08: tombol Setuju terkunci pada can_execute
    // (syarat pasca-approval terpenuhi) — pada 0 approval can_execute
    // selalu false → approval tak pernah bisa dikirim (deadlock).
    // Kontrak: can_approve independen dari satisfaction (p8); can_execute
    // hanya untuk tombol eksekusi setelah approval terpenuhi.
    const summary = {
      decision_id: "d1",
      status: "pending_approval",
      can_approve: true,
      can_execute: false, // approval belum terpenuhi — masih boleh approve
      blocking_reasons: ["approval belum memenuhi requirement (missing/rejected)"],
      verifier: { verdict: null, verified_by: null },
    };
    const html = renderToStaticMarkup(<ApprovalModal summary={summary} />);
    expect(html).toContain("Setuju");
    expect(html).not.toContain("disabled"); // tombol approve aktif
  });

  it("Setuju nonaktif saat can_approve false (fail-closed)", () => {
    const html = renderToStaticMarkup(
      <ApprovalModal
        summary={{
          decision_id: "d1",
          status: "pending_approval",
          can_approve: false,
          can_execute: false,
          blocking_reasons: ["decision expired"],
          verifier: { verdict: null, verified_by: null },
        }}
      />
    );
    expect(html).toContain("disabled");
  });
});

describe("visibleActions (role scope murni, design.md §1.4)", () => {
  it("bgn_monitor tidak pernah melihat aksi mutasi", () => {
    expect(visibleActions("bgn_monitor", "pending_approval")).toEqual({
      approve: false,
      verify: false,
      execute: false,
      propose: false,
      repropose: false,
      readOnly: true,
    });
  });

  it("sppg_head bisa approve+verifikasi saat menunggu approval, belum eksekusi", () => {
    expect(visibleActions("sppg_head", "pending_approval")).toEqual({
      approve: true,
      verify: true,
      execute: false,
      propose: false,
      repropose: false,
      readOnly: false,
    });
  });

  it("keputusan `proposed` hanya menawarkan Ajukan, dan itu milik Kepala", () => {
    expect(visibleActions("sppg_head", "proposed")).toEqual({
      approve: false,
      verify: true,
      execute: false,
      propose: true,
      repropose: false,
      readOnly: false,
    });
    // Ahli Gizi boleh verifikasi, tetapi tidak boleh mengajukan.
    expect(visibleActions("sppg_nutritionist", "proposed").propose).toBe(false);
  });

  it("kuorum penuh (`approved`) → hanya Eksekusi, dan hanya untuk Head", () => {
    expect(visibleActions("sppg_head", "approved")).toEqual({
      approve: false,
      verify: false,
      execute: true,
      propose: false,
      repropose: false,
      readOnly: false,
    });
    expect(visibleActions("sppg_nutritionist", "approved").execute).toBe(false);
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
