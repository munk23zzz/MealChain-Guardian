// Dokumen `07-safety-evidence.md` §4.2 butir 2 — lencana putusan safety
// menyebut jumlah batch yang diperiksa.
//
// Di repo ini putusan safety satu keputusan tinggal DI DALAM daftar fakta kartu
// "Keamanan & pemasok" (`safetyFacts`), dan jumlah batch-nya baris kecil di
// bawahnya. Untuk peran ahli gizi angka itu bagian dari putusan, jadi ia naik
// ke lencana — TANPA mengurangi sumbernya: `safety.worst_status` dan
// `safety.batches_checked` tetap dibaca dari `GET /decisions/{id}/approval-summary`.
//
// Aturan yang dikunci:
//  - angka hanya dicetak kalau server benar-benar mengirimnya (> 0). Backend
//    mengirim `batches_checked: 0` juga saat status tidak terdefinisi
//    (`approval_summary._safety_view`), jadi 0 TIDAK boleh berbunyi
//    "0 batch diperiksa" — itu akan terbaca seolah sudah diperiksa;
//  - ringkasan belum ada → tidak ada lencana (bukan lencana kosong);
//  - angka yang sama tidak dicetak dua kali (lencana + baris fakta) di kartu
//    yang sama.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DecisionEvidence from "../components/DecisionEvidence";
import { safetyBadge } from "../lib/evidence";

const NOW = new Date("2026-10-29T03:00:00Z");

const SELECTED = {
  decision_id: "d1",
  decision_type: "supplier_procurement",
  status: "pending_approval",
  quantity_kg: 300,
  safe_delivered_cost: 9000000,
  created_at: "2026-10-29T02:30:00Z",
  expires_at: "2026-10-29T09:00:00+00:00",
  iteration: 1,
};

const DECISIONS = [SELECTED];

function summary(safety: unknown) {
  return {
    decision_id: "d1",
    decision_type: "supplier_procurement",
    status: "pending_approval",
    iteration: 1,
    commodity: "telur",
    quantity_kg: 300,
    safe_delivered_cost: 9000000,
    supplier: { id: "s1", name: "UD Sumber Rejeki Telur" },
    verifier: { verdict: "consistent", verified_by: "verifier_agent" },
    safety,
    approval_requirement: { verdict: "consistent", min_approvals: 2, requirement: "2 dari 2" },
    approvals: [],
    can_approve: true,
    can_execute: false,
    blocking_reasons: [],
    approver_roles: ["sppg_head", "sppg_nutritionist"],
  };
}

function render(safety: unknown) {
  return renderToStaticMarkup(
    <DecisionEvidence
      decisions={DECISIONS as never}
      selected={SELECTED}
      selectedId="d1"
      onSelect={() => {}}
      chain={[]}
      summary={summary(safety)}
      supplierContext={null}
      role="sppg_nutritionist"
      token="t"
      now={NOW}
    />
  );
}

describe("safetyBadge — putusan + jumlah batch diperiksa", () => {
  it("gagal dengan tiga batch: nada bahaya dan angkanya ikut di lencana", () => {
    expect(safetyBadge({ safety: { worst_status: "fail", blocked: true, batches_checked: 3 } })).toEqual({
      tone: "danger",
      label: "Gagal",
      detail: "3 batch diperiksa",
      text: "Gagal · 3 batch diperiksa",
    });
  });

  it("lolos: nada aman, angkanya tetap disebut", () => {
    const badge = safetyBadge({ safety: { worst_status: "pass", blocked: false, batches_checked: 1 } });
    expect(badge?.tone).toBe("ok");
    expect(badge?.text).toBe("Lolos · 1 batch diperiksa");
  });

  it("perlu verifikasi: nada peringatan, bukan hijau", () => {
    const badge = safetyBadge({
      safety: { worst_status: "needs_verification", blocked: true, batches_checked: 2 },
    });
    expect(badge?.tone).toBe("warn");
    expect(badge?.label).toBe("Perlu verifikasi");
  });

  it("batches_checked 0 tidak pernah menjadi angka di layar", () => {
    const badge = safetyBadge({ safety: { worst_status: "fail", blocked: true, batches_checked: 0 } });
    expect(badge?.detail).toBe(null);
    expect(badge?.text).toBe("Gagal");
  });

  it("status tidak dikenal / ringkasan kosong: tidak mengarang", () => {
    expect(safetyBadge({ safety: { worst_status: null, blocked: false, batches_checked: 0 } })).toBe(null);
    expect(safetyBadge({})).toBe(null);
    expect(safetyBadge(null)).toBe(null);
    expect(safetyBadge({ safety: { worst_status: "SOMETHING_NEW", blocked: false, batches_checked: 1 } })?.label).toBe(
      "SOMETHING_NEW"
    );
  });
});

describe("lencana putusan di kartu Keamanan & pemasok", () => {
  it("mencetak lencana berisi putusan + jumlah batch", () => {
    const html = render({ worst_status: "fail", blocked: true, batches_checked: 3 });
    expect(html).toContain("Keamanan &amp; pemasok");
    expect(html).toContain("Gagal · 3 batch diperiksa");
    expect(html).toContain("board-badge-danger");
  });

  it("angka yang sudah ada di lencana tidak diulang sebagai baris fakta", () => {
    const html = render({ worst_status: "fail", blocked: true, batches_checked: 3 });
    expect(html).not.toContain("Batch diperiksa");
  });

  it("tanpa jumlah dari server: lencana hanya putusan, baris fakta tetap ada", () => {
    const html = render({ worst_status: "fail", blocked: true, batches_checked: 0 });
    expect(html).toContain("Gagal");
    expect(html).not.toContain("batch diperiksa");
    expect(html).toContain("Batch diperiksa");
  });
});
