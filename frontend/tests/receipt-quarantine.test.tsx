// Fase 4 MG, poin 7 (`MG/phase-04-safety-gates.md` baris 7) — TDD.
//
// Kontrak yang dikunci di sini:
//  1. tombol Eksekusi mengikuti SERVER (`can_execute`), bukan hitungan klien.
//     Saat server tidak mengizinkan, alasannya tampil sebagai KALIMAT Indonesia
//     yang berasal dari peta kode stabil di `lib/` — bukan kode mentah seperti
//     `safety_pending` dan bukan `blocking_reasons[0]` apa adanya;
//  2. status `on_hold` (pending / needs_verification / bukti suhu kurang) dan
//     `quarantined` tampil bersama LANGKAH VERIFIKASI berikutnya;
//  3. ceklis penerimaan (`POST /receipts`) TIDAK disamakan dengan karantina
//     (`POST /batches/{id}/quarantine`): label dan akibatnya berbeda;
//  4. non-head tetap read-only — tidak ada tombol yang bisa memanggil endpoint
//     mutasi.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import ApprovalMenu from "../components/ApprovalMenu";
import ApprovalModal from "../components/ApprovalModal";
import DecisionActions, { visibleActions } from "../components/DecisionActions";
import FoodSafetyBoard from "../components/FoodSafetyBoard";
import { batchGateView } from "../lib/safety-gate";

const NOW = new Date("2026-10-27T08:00:00Z");

const SUMMARY = {
  decision_id: "d1",
  decision_type: "supplier_procurement",
  status: "approved",
  iteration: 1,
  source_location: null,
  target_location: "Jakarta",
  commodity: "telur",
  quantity_kg: 300,
  safe_delivered_cost: 9000000,
  material_number: "MAT-TELUR",
  supplier: { id: "s1", name: "UD Sumber Rejeki Telur" },
  execution_target: "MOCK",
  verifier: { verdict: "consistent", verified_by: "verifier_agent" },
  safety: { worst_status: "pass", blocked: false, batches_checked: 1, reason: null },
  expiry: { expires_at: "2026-10-27T09:00:00+00:00", valid: true, seconds_remaining: 3600 },
  approval_requirement: { min_approvals: 2, required_roles: [["sppg_head"], ["sppg_nutritionist"]] },
  approval_state: { satisfied: true, missing: [], approved_roles: ["sppg_head", "sppg_nutritionist"] },
  can_approve: false,
  can_reject: false,
  can_execute: true,
  blocking_reasons: [] as string[],
};

function menu(over: Record<string, unknown> = {}, role = "sppg_head", status = "approved") {
  const noop = async () => null;
  return renderToStaticMarkup(
    <ApprovalMenu
      summary={{ ...SUMMARY, ...over }}
      actions={visibleActions(role, status)}
      administrative={false}
      onApprove={noop}
      onReject={noop}
      onVerify={noop}
      onPropose={noop}
      onExecute={noop}
      onRepropose={noop}
      onClose={() => {}}
    />
  );
}

describe("MG/phase-04 poin 7 — tombol eksekusi mengikuti server", () => {
  it("can_execute=false: kontrol eksekusi tidak ditawarkan, alasan tampil sebagai kalimat", () => {
    const html = menu({
      can_execute: false,
      safety: {
        worst_status: "pending",
        blocked: false,
        batches_checked: 1,
        reason: null,
      },
      blocking_reasons: ["safety_pending"],
    });
    expect(html).not.toContain('data-action="execute"');
    // Kode mentah tidak boleh sampai ke layar.
    expect(html).not.toContain("safety_pending");
    // Kalimat dari peta kode (lib) yang tampil, bukan blocking_reasons[0] mentah.
    expect(html).toContain("belum diuji keamanan pangan");
  });

  it("can_execute=true: kontrol eksekusi ditawarkan tanpa catatan penahan", () => {
    const html = menu();
    expect(html).toContain('data-action="execute"');
    expect(html).not.toContain("Server belum mengizinkan");
  });

  it("status sudah dieksekusi: eksekusi tidak ditawarkan walau server mengirim can_execute=true", () => {
    const html = menu({ status: "executed" }, "sppg_head", "executed");
    expect(html).not.toContain('data-action="execute"');
  });

  it("alasan dari safety.reason ikut diterjemahkan, tidak hanya blocking_reasons", () => {
    const html = menu({
      can_execute: false,
      status: "approved",
      safety: {
        worst_status: "fail",
        blocked: true,
        batches_checked: 2,
        reason: "safety revalidation gagal: batch sumber kini FAIL",
      },
      blocking_reasons: ["safety revalidation gagal: batch sumber kini FAIL"],
    });
    expect(html).not.toContain('data-action="execute"');
    expect(html).not.toContain("FAIL");
    expect(html).toContain("gagal uji keamanan pangan");
  });
});

describe("MG/phase-04 poin 7 — on_hold & karantina tampil dengan langkah berikutnya", () => {
  function modal(over: Record<string, unknown>) {
    return renderToStaticMarkup(<ApprovalModal summary={{ ...SUMMARY, ...over }} />);
  }

  it("needs_verification: status + langkah 'Selesaikan verifikasi verifier'", () => {
    const html = modal({
      can_execute: false,
      safety: { worst_status: "needs_verification", blocked: false, batches_checked: 1, reason: null },
      blocking_reasons: ["safety_needs_verification"],
    });
    expect(html).toContain("Perlu verifikasi");
    expect(html).toContain("Selesaikan verifikasi verifier");
    expect(html).not.toContain("safety_needs_verification");
  });

  it("pending: langkah 'Uji keamanan pangan … lalu catat verifikasi'", () => {
    const html = modal({
      can_execute: false,
      safety: { worst_status: "pending", blocked: false, batches_checked: 1, reason: null },
      blocking_reasons: ["safety_pending"],
    });
    expect(html).toContain("Uji keamanan pangan");
    expect(html).toContain("catat verifikasi");
    expect(html).not.toContain("safety_pending");
  });

  it("bukti suhu kurang: on_hold dengan langkah melengkapi log suhu", () => {
    const html = modal({
      can_execute: false,
      safety: { worst_status: "needs_verification", blocked: false, batches_checked: 1, reason: null },
      blocking_reasons: ["temperature_evidence_incomplete"],
    });
    expect(html).toContain("Bukti suhu");
    expect(html).toContain("Log suhu");
    expect(html).not.toContain("temperature_evidence_incomplete");
  });

  it("karantina: langkah 'Lepas karantina atau nyatakan gagal'", () => {
    const html = modal({
      can_execute: false,
      safety: { worst_status: "fail", blocked: true, batches_checked: 1, reason: "batch sumber dikarantina/gagal" },
      blocking_reasons: ["quarantined"],
    });
    expect(html).toContain("karantina");
    expect(html).toContain("Lepas karantina atau nyatakan gagal");
    expect(html).not.toContain(">quarantined<");
  });

  it("batchGateView memisahkan on_hold, karantina, dan siap", () => {
    expect(batchGateView({ can_execute: true, status: "approved", blocking_reasons: [] }).kind).toBe("siap");
    expect(
      batchGateView({
        can_execute: false,
        status: "approved",
        safety: { worst_status: "pending" },
        blocking_reasons: ["safety_pending"],
      }).kind
    ).toBe("on_hold");
    expect(
      batchGateView({
        can_execute: false,
        status: "approved",
        safety: { worst_status: "fail", blocked: true },
        blocking_reasons: ["quarantined"],
      }).kind
    ).toBe("quarantined");
    // Kode tak dikenal tidak dikarang: tampil apa adanya, tetapi tetap satu kalimat.
    expect(batchGateView({ can_execute: false, blocking_reasons: ["kode_baru_server"] }).reasons).toEqual([
      "kode_baru_server",
    ]);
  });
});

describe("MG/phase-04 poin 7 — ceklis penerimaan ≠ karantina", () => {
  const BATCHES = [
    {
      id: "b-tahan",
      location: "Jakarta",
      commodity: "telur",
      quantity_kg: 120,
      safety_status: "needs_verification",
      freshness_score: 0.9,
      usable_until: "2026-10-29T06:00:00Z",
      quarantine_status: "quarantined",
      receipt_status: "menunggu",
    },
    {
      id: "b-baru",
      location: "Jakarta",
      commodity: "ayam",
      quantity_kg: 80,
      safety_status: "pending",
      freshness_score: 0.9,
      usable_until: "2026-10-29T06:00:00Z",
      quarantine_status: "none",
      receipt_status: null,
    },
  ];

  function board(props: Record<string, unknown> = {}) {
    return renderToStaticMarkup(
      <FoodSafetyBoard
        batches={BATCHES}
        now={NOW}
        ownLocation="Jakarta"
        canMutate
        onRecheck={async () => ({}) as never}
        onRecordReceipt={async () => ({})}
        loadReceipts={async () => ({ items: [] })}
        onKarantina={async () => {}}
        {...props}
      />
    );
  }

  it("kartu penerimaan menyatakan dirinya bukan karantina", () => {
    const html = board();
    expect(html).toContain("bukan karantina");
    expect(html).toContain("tidak menahan batch");
    // Label ceklis tetap milik penerimaan, bukan karantina. Sejak Dok 05 §2
    // formulirnya pindah ke popup, jadi yang tersisa di kartu adalah tombol
    // pembukanya — bukan tombol simpan ceklis.
    expect(html).toContain("daftar periksa petugas");
    expect(html).toContain("Periksa &amp; catat kiriman");
    expect(html).not.toContain("Catat hasil terima");
  });

  it("baris batch ditahan menawarkan akibat karantina, terpisah dari ceklis", () => {
    const html = board();
    expect(html).toContain("Lepas karantina atau nyatakan gagal");
    expect(html).toContain(">Lepas<");
    expect(html).toContain(">Gagal<");
  });

  it("baris on_hold menyebut langkah verifikasi berikutnya", () => {
    const html = board();
    expect(html).toContain("Selesaikan verifikasi verifier");
    expect(html).toContain("Uji keamanan pangan");
    // Tidak ada kode mentah di layar.
    expect(html).not.toContain("needs_verification");
    expect(html).not.toContain("safety_status");
  });
});

describe("MG/phase-04 poin 7 — non-head tetap read-only", () => {
  it("Ahli Gizi tidak mendapat eksekusi (eksekusi milik Kepala SPPG)", () => {
    expect(visibleActions("sppg_nutritionist", "approved").execute).toBe(false);
    const html = menu({}, "sppg_nutritionist", "approved");
    expect(html).not.toContain('data-action="execute"');
  });

  it("bgn_monitor: popup tanpa satu pun tombol mutasi", () => {
    const html = menu({}, "bgn_monitor", "approved");
    for (const aksi of ["execute", "verify", "reject", "propose", "repropose"]) {
      expect(html).not.toContain(`data-action="${aksi}"`);
    }
  });

  it("bgn_monitor: papan keamanan pangan tanpa tombol karantina / catat terima", () => {
    const html = renderToStaticMarkup(
      <FoodSafetyBoard
        batches={[
          {
            id: "b1",
            location: "Jakarta",
            commodity: "telur",
            quantity_kg: 100,
            safety_status: "pending",
            freshness_score: 0.8,
            usable_until: "2026-10-29T06:00:00Z",
            quarantine_status: "none",
            receipt_status: null,
          },
        ]}
        now={NOW}
        ownLocation="Jakarta"
        canMutate={false}
        onRecheck={async () => ({}) as never}
        onRecordReceipt={async () => ({})}
        onKarantina={async () => {}}
      />
    );
    expect(html).not.toContain(">Tahan<");
    expect(html).not.toContain("Catat hasil terima");
    expect(html).toContain("Hanya kepala SPPG dan ahli gizi");
  });

  it("DecisionActions bgn_monitor hanya menyatakan read-only", () => {
    const html = renderToStaticMarkup(
      <DecisionActions decisionId="d1" role="bgn_monitor" status="approved" token="t" summary={SUMMARY} />
    );
    expect(html).toContain("read-only");
    expect(html).not.toContain("Kelola persetujuan");
    expect(html).not.toContain("Eksekusi");
  });
});
