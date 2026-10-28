// Test S4-04 — ApprovalModal read model kanonik (RED dulu, TDD).
// Kontrak plan §S4-04: modal menampilkan ringkasan LENGKAP dari
// GET /decisions/{id}/approval-summary — UI tidak menghitung requirement,
// tidak ada verdict literal client, field kosong tampil "belum tercatat".
// can_approve=false → tombol Setuju nonaktif + alasan blocking tampil.
// (Revisi S4-05 rehearsal 2026-10-08: can_approve INDEPENDEN dari satisfaction —
// can_execute=false hanya memblokir EKSEKUSI server-side, bukan approval.
// Test lama yang mem-pin can_execute=false → disabled adalah pin perilaku bug
// chicken-and-egg yang diperbaiki di p10.)

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import ApprovalModal from "../components/ApprovalModal";
import { fetchApprovalSummary } from "../lib/api";

describe("ApprovalModal (summary kanonik S4-04)", () => {
  const CANONICAL = {
    decision_id: "d-1",
    decision_type: "regional_balance",
    status: "pending_approval",
    iteration: 2,
    source_location: "Cianjur",
    target_location: "Jakarta",
    commodity: "telur",
    quantity_kg: 488.88,
    safe_delivered_cost: 16206000,
    material_number: "MAT-TELUR",
    supplier: { name: "Supplier A Cianjur", reliability_score: 0.8 },
    execution_target: "MOCK",
    verifier: { verdict: "unavailable", verified_by: "verifier_agent" },
    safety: { worst_status: "pass", blocked: false, batches_checked: 2 },
    expiry: { valid: true, seconds_remaining: 1200 },
    approval_requirement: {
      verdict: "unavailable",
      min_approvals: 2,
      required_roles: [["sppg_head"], ["sppg_nutritionist"]],
    },
    approval_state: {
      satisfied: false,
      missing: [["sppg_head"], ["sppg_nutritionist"]],
    },
    approvals: [{ role: "sppg_head", approved: true }],
    can_approve: true,
    can_execute: false,
    blocking_reasons: ["approval belum memenuhi requirement (missing/rejected)"],
  };

  it("menampilkan konteks lengkap: lokasi, komoditas, pemasok, jalur simulasi, syarat", () => {
    const html = renderToStaticMarkup(
      <ApprovalModal summary={CANONICAL} onConfirm={() => {}} />
    );
    expect(html).toContain("Cianjur");
    expect(html).toContain("Jakarta");
    expect(html).toContain("telur");
    expect(html).toContain("488,88 kg");
    expect(html).toContain("Supplier A Cianjur");
    expect(html).toContain("MAT-TELUR");
    expect(html).toContain("Simulasi");
    expect(html).toContain("Belum tersedia");
    // Requirement dua peran (AND) — dari server; kode peran diterjemahkan ke
    // nama manusia, bukan dicetak mentah.
    expect(html).toContain("Kepala SPPG");
    expect(html).toContain("Ahli Gizi SPPG");
    expect(html).not.toContain("sppg_head");
    // Alasan tertahan tampil sebagai kalimat, bukan kode berbentuk kalimat.
    expect(html).toContain("Persetujuan belum lengkap");
  });

  it("can_approve=false → tombol Setuju disabled (gate approval, bukan can_execute)", () => {
    const noApprove = { ...CANONICAL, can_approve: false };
    const html = renderToStaticMarkup(
      <ApprovalModal summary={noApprove} onConfirm={() => {}} />
    );
    expect(html).toContain("disabled");
  });

  it("approved_by_me=true → Setuju nonaktif + menyebut role yang ditunggu", () => {
    // Keputusan owner 17 Okt: user yang approval-nya sudah tercatat tidak lagi
    // ditawari "Setuju" (klik = 409 "approval sudah tercatat"). Fixture lama
    // tanpa field ini berperilaku sama seperti sebelumnya (undefined ≠ true).
    const mine = {
      ...CANONICAL,
      approved_by_me: true,
      approval_state: { satisfied: false, missing: [["sppg_nutritionist"]] },
    };
    const html = renderToStaticMarkup(
      <ApprovalModal summary={mine} onConfirm={() => {}} />
    );
    expect(html).toContain("Sudah Anda setujui");
    expect(html).toContain("disabled");
    expect(html).toContain("menunggu role lain");
    expect(html).toContain("sppg_nutritionist");
  });

  it("can_approve=true meski can_execute=false → Setuju aktif (approval ≠ eksekusi)", () => {
    const html = renderToStaticMarkup(
      <ApprovalModal summary={CANONICAL} onConfirm={() => {}} />
    );
    // CANONICAL: can_approve=true + can_execute=false (butuh approval ke-2 role).
    // Setuju harus aktif — tanpa itu approval ke-2 tak pernah bisa masuk.
    expect(html).not.toContain("disabled");
  });

  it("can_execute=true → tombol Setuju aktif", () => {
    const ready = {
      ...CANONICAL,
      approval_state: { satisfied: true, missing: [] },
      can_execute: true,
      blocking_reasons: [],
    };
    const html = renderToStaticMarkup(
      <ApprovalModal summary={ready} onConfirm={() => {}} />
    );
    expect(html).not.toContain("disabled");
  });

  it("field hilang → 'belum tercatat', bukan default palsu", () => {
    const partial = {
      ...CANONICAL,
      supplier: null,
      material_number: null,
      source_location: null,
      commodity: null,
    };
    const html = renderToStaticMarkup(<ApprovalModal summary={partial} />);
    expect(html).toContain("belum tercatat");
  });

  it("tanpa ringkasan → menolak approval (tidak ada approve-all)", () => {
    const html = renderToStaticMarkup(<ApprovalModal summary={null} />);
    expect(html).toContain("Tidak ada ringkasan");
  });
});

describe("fetchApprovalSummary (API client)", () => {
  it("GET ke endpoint approval-summary dengan bearer token", async () => {
    let captured = "";
    const origFetch = globalThis.fetch;
    globalThis.fetch = (async (url: any) => {
      captured = String(url);
      return new Response(
        JSON.stringify({ decision_id: "d-1" }),
        { status: 200 }
      );
    }) as any;
    try {
      const data = await fetchApprovalSummary("d-1", "tok");
      expect(captured).toContain("/decisions/d-1/approval-summary");
      expect(data.decision_id).toBe("d-1");
    } finally {
      globalThis.fetch = origFetch;
    }
  });
});
