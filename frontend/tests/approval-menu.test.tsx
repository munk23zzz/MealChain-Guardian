// Test isi popup "Governance & persetujuan" (permintaan Roy 2026-10-14):
// pilihan tindakan approval tidak lagi berupa deretan tombol di dalam kartu
// (kartu jadi tinggi & berdesakan di grid 3 kolom), tetapi di dalam popup yang
// dibuka dari satu tombol pemicu. Kontrak yang TIDAK boleh hilang:
// - design.md §1.3: ringkasan bukti WAJIB tampil sebelum tombol Setuju ada;
// - design.md §1.4: bgn_monitor tidak pernah melihat aksi mutasi apa pun;
// - keputusan `rejected` hanya menawarkan re-propose, bukan approve/execute.
// Komponen ini presentasional (tanpa DOM) supaya bisa diuji di
// environment node — popup-nya sendiri diuji lewat peramban.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import ApprovalMenu from "../components/ApprovalMenu";
import { visibleActions } from "../components/DecisionActions";

const SUMMARY = {
  decision_id: "d1",
  status: "pending_approval",
  decision_type: "redistribution",
  source_location: "Cianjur",
  target_location: "Jakarta",
  commodity: "beras",
  quantity_kg: 600,
  safe_delivered_cost: "16206000.00",
  can_approve: true,
  can_execute: false,
  blocking_reasons: ["approval belum memenuhi requirement"],
  verifier: { verdict: "consistent", verified_by: "verifier_agent" },
  approval_requirement: { min_approvals: 1, required_roles: [["sppg_head"]] },
  approval_state: { collected: 0, missing: [["sppg_head"]] },
  expiry: { valid: true, seconds_remaining: 3600 },
  execution_target: "sap_mock",
  material_number: "MAT-1",
  supplier: { name: "CV Pangan" },
};

function render(extra: Record<string, unknown> = {}) {
  const noop = async () => null;
  return renderToStaticMarkup(
    <ApprovalMenu
      summary={SUMMARY}
      actions={visibleActions("sppg_head", "pending_approval")}
      administrative={false}
      onApprove={noop}
      onReject={noop}
      onVerify={noop}
      onExecute={noop}
      onRepropose={noop}
      onClose={() => {}}
      {...extra}
    />
  );
}

describe("ApprovalMenu (isi popup governance & persetujuan)", () => {
  it("ringkasan bukti tampil lebih dulu — friksi disengaja tetap ada", () => {
    const html = render();
    expect(html).toContain("Konfirmasi Approval");
    expect(html).toContain("600 kg");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("consistent");
    // Ringkasan tidak lagi mengklaim dirinya dialog: popup yang memegang
    // role="dialog"/aria-modal, jadi tidak ada dialog bersarang.
    expect(html).not.toContain('role="dialog"');
  });

  it("pilihan tindakan lengkap untuk approver: Setuju, Tolak, Verifikasi, Eksekusi", () => {
    const html = render();
    for (const label of ["Setuju", "Tolak", "Verifikasi", "Eksekusi"]) {
      expect(html).toContain(label);
    }
  });

  it("bgn_monitor tidak melihat satu pun aksi mutasi", () => {
    const html = render({ actions: visibleActions("bgn_monitor", "pending_approval") });
    expect(html).not.toContain("Eksekusi");
    expect(html).not.toContain("Verifikasi");
    expect(html).not.toContain(">Tolak<");
  });

  it("keputusan rejected hanya menawarkan re-propose", () => {
    const html = render({ actions: visibleActions("sppg_head", "rejected") });
    expect(html).toContain("Minta re-propose");
    expect(html).not.toContain("Eksekusi");
    expect(html).not.toContain(">Tolak<");
  });

  it("tanpa read model → approval ditolak, bukan popup kosong", () => {
    const html = render({ summary: null });
    expect(html).toContain("Tidak ada ringkasan");
  });

  it("eksklusi supplier memakai jalur administratif, bukan re-propose", () => {
    const html = render({
      administrative: true,
      actions: visibleActions("sppg_head", "rejected"),
      summary: { ...SUMMARY, decision_type: "supplier_exclusion" },
    });
    expect(html).toContain("Ajukan ulang melalui panel supplier");
    expect(html).not.toContain("Minta re-propose");
  });

  it("alasan penolakan tidak langsung terbuka — dipilih dulu dari menu", () => {
    const html = render();
    expect(html).toContain("data-action=\"reject\"");
    expect(html).not.toContain("Alasan penolakan (wajib");
  });
});
