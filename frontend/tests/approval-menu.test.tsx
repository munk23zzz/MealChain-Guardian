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
  can_reject: true,
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

  it("pilihan tindakan lengkap saat server MENGIZINKAN eksekusi", () => {
    // can_execute: true → semua tindakan tersedia (lihat tes pagar di bawah).
    const html = render({ summary: { ...SUMMARY, can_execute: true } });
    for (const label of ["Setuju", "Tolak", "Verifikasi", "Eksekusi"]) {
      expect(html).toContain(label);
    }
  });

  // WS-B (QA 16 Okt): "Eksekusi" dulu selalu ditawarkan selama peran+status
  // cocok, padahal server SUDAH mengirim `can_execute` di read model yang sama.
  // Klik tombol itu berakhir 409 "decision expired" (backend app/api/actions.py
  // `/actions/execute`). ApprovalModal sampai menghitung `canExecute` untuk
  // maksud ini lalu tidak pernah memakainya — variabel mati.
  it("Eksekusi TIDAK ditawarkan saat server bilang can_execute false", () => {
    // Diperiksa dari KONTROL-nya (data-action), bukan dari kata "Eksekusi":
    // catatan alasan di bawah tetap menyebut nama aksinya supaya orang tahu
    // apa yang hilang dan kenapa.
    const html = render(); // SUMMARY.can_execute = false
    expect(html).not.toContain('data-action="execute"');
    expect(html).toContain("server belum mengizinkan");
  });

  it("Verifikasi TIDAK ikut terkunci oleh can_execute", () => {
    // can_execute memuat banyak penghalang sekaligus (approval belum terpenuhi,
    // belum terverifikasi, safety gagal). Verifikasi justru LANGKAH yang
    // menghilangkan sebagian penghalang itu, jadi ia tidak boleh ikut terkunci —
    // pagarnya sendiri hanya kedaluwarsa (lihat tes berikutnya).
    const html = render();
    expect(html).toContain('data-action="verify"');
  });

  // Keputusan owner 2026-10-16 (2b): /actions/verify DULU tidak memeriksa
  // kedaluwarsa sama sekali, jadi membiarkan tombolnya aktif itu benar. Setelah
  // penjaganya disamakan dengan /actions/propose, menawarkan tombol ini pada
  // keputusan kedaluwarsa kembali menjadi janji palsu → 409.
  it("Verifikasi tidak ditawarkan saat keputusan sudah kedaluwarsa", () => {
    const html = render({ summary: { ...SUMMARY, expiry: { valid: false } } });
    expect(html).not.toContain('data-action="verify"');
    expect(html).toContain("sudah lewat tenggat");
  });

  it("Verifikasi tetap ditawarkan saat belum kedaluwarsa", () => {
    const html = render({
      summary: { ...SUMMARY, expiry: { valid: true, seconds_remaining: 60 } },
    });
    expect(html).toContain('data-action="verify"');
  });

  // Keputusan owner 2026-10-16 (3b): "Tolak" memakai endpoint yang SAMA dengan
  // approve (approve_action dengan approved=false), jadi kelayakannya juga milik
  // server. Dulu UI menebaknya dari peran+status karena read model tidak punya
  // field-nya; sekarang `can_reject` yang menyatakan.
  it("Tolak tidak ditawarkan saat server bilang can_reject false", () => {
    const html = render({ summary: { ...SUMMARY, can_reject: false } });
    expect(html).not.toContain('data-action="reject"');
    expect(html).toContain("Penolakan belum tersedia");
  });

  it("Tolak tetap ditawarkan saat server bilang can_reject true", () => {
    const html = render(); // SUMMARY.can_reject = true
    expect(html).toContain('data-action="reject"');
  });

  it("re-propose tidak ditawarkan saat keputusan sudah kedaluwarsa", () => {
    // /actions/propose menolak keputusan kedaluwarsa tanpa syarat
    // (actions.py:129), jadi menawarkannya hanya mengantar ke 409.
    const html = render({
      actions: visibleActions("sppg_head", "rejected"),
      summary: { ...SUMMARY, status: "rejected", expiry: { valid: false } },
    });
    expect(html).not.toContain('data-action="repropose"');
  });

  it("re-propose tetap ditawarkan saat belum kedaluwarsa", () => {
    const html = render({
      actions: visibleActions("sppg_head", "rejected"),
      summary: { ...SUMMARY, status: "rejected", expiry: { valid: true, seconds_remaining: 3600 } },
    });
    expect(html).toContain('data-action="repropose"');
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
