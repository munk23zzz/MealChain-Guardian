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
    // 29 Okt 2026: verdict "consistent" TIDAK lagi dicetak sebagai baris —
    // ia keadaan normal; mengulanginya di setiap approval mendorong masa berlaku
    // dan tombol Setuju ke bawah. Yang tetap dicetak: verdict yang perlu dibaca.
    expect(html).not.toContain("Konsisten");
  });

  it("verdict yang PERLU DIBACA tetap dicetak (flagged / belum tersedia)", () => {
    // Pelengkap tes di atas: yang dibuang hanya keadaan normal. Temuan
    // verifikator tetap tampil di baris yang sama.
    const flagged = renderToStaticMarkup(
      <ApprovalModal summary={{ quantity_kg: 600, verifier: { verdict: "flagged", verified_by: "verifier_agent" } }} />
    );
    expect(flagged).toContain("Hasil verifier");
    expect(flagged).toContain("Ditandai perlu diperiksa");
    const belum = renderToStaticMarkup(<ApprovalModal summary={{ quantity_kg: 600, verifier: {} }} />);
    expect(belum).toContain("Belum tersedia");
  });

  // 29 Okt 2026 (laporan pemilik): kotak "Tertahan" berbunyi
  // "Persetujuan belum lengkap — masih ada peran yang belum menyetujui." —
  // dua klausa dengan tanda pisah ganda, dan klausa keduanya tidak memberi
  // tahu SIAPA yang ditunggu padahal server mengirim daftarnya. Kotaknya juga
  // merah pekat padahal menunggu rekan adalah keadaan normal, bukan kegagalan.
  const tertahan = (over: Record<string, unknown> = {}) =>
    renderToStaticMarkup(
      <ApprovalModal
        summary={{
          quantity_kg: 780,
          can_approve: true,
          approval_requirement: { min_approvals: 2, required_roles: [["sppg_head"], ["sppg_nutritionist"]] },
          approval_state: { missing: [["sppg_nutritionist"]], approved_roles: [] },
          blocking_reasons: ["approval belum memenuhi requirement (missing/rejected)"],
          ...over,
        }}
      />
    );

  it("kotak penahan menyebut peran yang ditunggu, dengan namanya", () => {
    const html = tertahan();
    expect(html).toContain("Belum bisa dieksekusi");
    // 29 Okt 2026 (lanjutan): nama peran tampil sebagai chip di barisnya
    // sendiri, bukan diselipkan ke dalam kalimat sebab.
    expect(html).toContain("Persetujuan belum lengkap.");
    expect(html).toContain('class="blocker-chip"');
    expect(html).toContain("Ahli Gizi SPPG");
    // Kode peran mentah tidak boleh muncul di layar berbahasa Indonesia.
    expect(html).not.toContain("sppg_nutritionist");
    expect(html).not.toContain("masih ada peran yang belum menyetujui");
    // Dua klausa bertanda pisah ganda juga hilang.
    expect(html).not.toContain("lengkap — masih ada");
  });

  it("menunggu rekan bertanda peringatan; alasan final tetap bahaya", () => {
    expect(tertahan()).toContain('data-tone="warn"');
    expect(tertahan({ blocking_reasons: ["decision ditolak"] })).toContain('data-tone="danger"');
  });

  it("alasan server yang dikenal tidak dicetak setengah Indonesia", () => {
    const html = tertahan({ blocking_reasons: ["decision expired"] });
    expect(html).toContain("Jendela berlaku keputusan sudah lewat");
    expect(html).not.toContain("Decision expired");
  });

  it("catatan setelah menyetujui menamai peran, bukan kode mentah", () => {
    const html = renderToStaticMarkup(
      <ApprovalModal
        summary={{
          quantity_kg: 780,
          can_approve: true,
          approved_by_me: true,
          approval_requirement: { min_approvals: 2, required_roles: [["sppg_head"], ["sppg_nutritionist"]] },
          approval_state: { missing: [["sppg_nutritionist"]], approved_roles: ["sppg_head"] },
        }}
      />
    );
    expect(html).toContain("menunggu Ahli Gizi SPPG");
    expect(html).not.toContain("role lain");
    expect(html).not.toContain("sppg_nutritionist");
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
