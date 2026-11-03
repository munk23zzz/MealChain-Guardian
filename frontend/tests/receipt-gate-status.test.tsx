// Fase 9 MG butir 2 & 4 — status penerimaan mengikuti SERVER, bukan hitungan klien.
//
// Kontrak yang dikunci:
//   1. `on_hold` TIDAK menawarkan "Tandai diterima"; ia menawarkan tindakan lain
//      (tahan/karantina) dan menyebut langkah verifikasi berikutnya.
//   2. `quarantined` punya alasan dan langkah yang BERBEDA dari `on_hold`.
//   3. batch `usable` + `can_receive=true` dari server → "Tandai diterima" ada.
//   4. peran non-head read-only: tanpa field server, tidak ada tombol mutasi.
//   5. alasan boleh/tidak dihitung server: `can_receive=false` menang atas status
//      batch yang terlihat layak (bukti klien tidak menyimpulkan sendiri).
//   6. galat 409 menampilkan `detail` server.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import GoodsReceiptDrawer, { GoodsReceiptSheet } from "../components/GoodsReceiptDrawer";
import {
  canDecideReceipt,
  pendingReceipt,
  receiptGateView,
  receiptReason,
  receiptStatusLabel,
  serverDetail,
} from "../lib/goods-receipt";

function gate(over: Record<string, unknown> = {}, batch: Record<string, unknown> = {}) {
  // Server (sejak perbaikan browser 27 Okt) mengirim `next_step` PER BATCH;
  // agregat hanya untuk ringkasan. Fixture lama yang menaruh langkah di level
  // gerbang dipindahkan ke baris batch agar tetap menguji perilaku sebenarnya.
  const baris = {
    batch_id: "b1",
    status: "usable",
    can_receive: true,
    can_quarantine: true,
    receive_reasons: [] as string[],
    quarantine_reasons: [] as string[],
    next_step: (over.next_step as string | undefined) ?? null,
    ...batch,
  };
  return {
    decision_id: "d1",
    can_receive: baris.can_receive,
    can_quarantine: baris.can_quarantine,
    receipt_gate: {
      location_id: "loc-jkt",
      location_name: null,
      batches: [baris],
      can_receive: baris.can_receive,
      can_quarantine: baris.can_quarantine,
      receive_reasons: baris.receive_reasons,
      quarantine_reasons: [],
      next_step: null,
      ...over,
    },
  };
}

/**
 * Panel penerimaan kini berupa DAFTAR baris + POPUP per batch (dokumen 05 §2),
 * jadi markup statis tidak lagi memuat tombol/keputusan. Helper ini merender
 * panel DAN isi popup untuk satu batch sekaligus, supaya kontrak lama (tombol
 * mengikuti server, kode mentah tidak bocor ke layar) tetap terkunci —
 * `batchId` memilih baris yang popup-nya sedang diuji.
 */
function render(summary: unknown, opts: Record<string, unknown> = {}) {
  const { batchId = "b1", ...sisa } = opts as any;
  const tampilan = receiptGateView(summary);
  const baris = tampilan.rows.find((b) => b.batchId === batchId) ?? tampilan.rows[0] ?? null;
  const receipts =
    (sisa.receipts as Record<string, any[]> | undefined) ?? {
      // `verdict` = ceklis sudah dinilai server. Sejak 30 Okt 2026 tombol
      // "Tandai diterima" menunggu syarat ini; baris `menunggu` tanpa penilaian
      // belum boleh ditandai (cek dulu, baru setujui).
      b1: [{ id: "r1", status: "menunggu", verdict: "pass", verdict_label: "Layak diterima" }],
    };
  const catatan = receipts?.[batchId]?.[0] ?? null;
  const panel = renderToStaticMarkup(
    <GoodsReceiptDrawer
      summary={summary}
      token="t"
      role="sppg_head"
      receipts={receipts}
      {...sisa}
    />
  );
  const sheet = baris
    ? renderToStaticMarkup(
        <GoodsReceiptSheet
          baris={baris}
          catatan={catatan}
          bolehPutuskan={canDecideReceipt((sisa.role as string) ?? "sppg_head")}
          busy={false}
          galat={null}
          pesan={null}
        />
      )
    : "";
  return panel + sheet;
}

describe("Fase 9 butir 2 — helper status penerimaan", () => {
  it("tanpa receipt_gate: present=false (tidak menebak 'tidak boleh')", () => {
    const tampilan = receiptGateView({ decision_id: "d1" });
    expect(tampilan.present).toBe(false);
    expect(tampilan.rows).toEqual([]);
    expect(tampilan.blockedSentence).toBeNull();
  });

  it("menerjemahkan kode gerbang dan kode evaluator, kode asing apa adanya", () => {
    expect(receiptReason("safety_pending")).toContain("belum diuji");
    expect(receiptReason("receipt_missing")).toContain("catat hasil terima");
    expect(receiptReason("quarantine_transition_invalid")).toContain("karantina");
    expect(receiptReason("kode_baru_server")).toBe("kode_baru_server");
    expect(receiptStatusLabel("on_hold")).toContain("Tertahan");
    expect(receiptStatusLabel("")).toBe("Status tidak tercatat");
  });

  it("pendingReceipt hanya mengambil catatan berstatus menunggu", () => {
    expect(pendingReceipt([{ id: "a", status: "disetujui" }])).toBeNull();
    expect(pendingReceipt([{ id: "a", status: "menunggu" }])?.id).toBe("a");
    expect(pendingReceipt(undefined)).toBeNull();
  });

  it("peran penyetuju penerimaan = sppg_head (cermin require_roles server)", () => {
    expect(canDecideReceipt("sppg_head")).toBe(true);
    expect(canDecideReceipt("sppg_nutritionist")).toBe(false);
    expect(canDecideReceipt("bgn_monitor")).toBe(false);
  });

  it("galat 409: detail server dipakai, bukan pesan generik", () => {
    expect(serverDetail({ detail: "barang masih berstatus karantina — tidak boleh masuk stok" })).toContain(
      "karantina"
    );
    expect(serverDetail({ message: "jaringan putus" })).toBe("jaringan putus");
  });
});

describe("Fase 9 butir 2 — tombol mengikuti status kelayakan", () => {
  it("batch usable + can_receive=true → 'Tandai diterima' tersedia", () => {
    const html = render(gate());
    expect(html).toContain("Layak masuk stok");
    expect(html).toContain("Tandai diterima");
    expect(html).toContain('data-action="receive"');
  });

  it("on_hold → TIDAK ada 'Tandai diterima', ada langkah verifikasi berikutnya", () => {
    const html = render(
      gate(
        { can_receive: false, can_quarantine: true, next_step: "uji keamanan pangan lalu catat verifikasi" },
        {
          status: "on_hold",
          can_receive: false,
          can_quarantine: true,
          receive_reasons: ["safety_pending"],
        }
      )
    );
    expect(html).not.toContain("Tandai diterima");
    expect(html).not.toContain('data-action="receive"');
    // Kode mentah tidak boleh sampai ke layar.
    expect(html).not.toContain("safety_pending");
    expect(html).toContain("belum diuji");
    expect(html).toContain("uji keamanan pangan lalu catat verifikasi");
    // Tindakan yang berbeda: menahan barang justru sah untuk batch on_hold.
    expect(html).toContain("Tahan (karantina)");
  });

  it("quarantined → alasan & langkah BERBEDA, tanpa tombol terima maupun tahan", () => {
    const html = render(
      gate(
        {
          can_receive: false,
          can_quarantine: false,
          next_step: "lepas karantina atau tolak batch",
        },
        {
          status: "quarantined",
          can_receive: false,
          can_quarantine: false,
          receive_reasons: ["quarantined"],
        }
      )
    );
    expect(html).toContain("Karantina");
    expect(html).not.toContain("Tandai diterima");
    expect(html).not.toContain("Tahan (karantina)");
    expect(html).toContain("masih berstatus karantina");
    expect(html).toContain("lepas karantina atau tolak batch");
  });

  it("server bilang can_receive=false walau status batch 'usable' → tombol tetap tidak ada", () => {
    const html = render(
      gate(
        { can_receive: false, can_quarantine: true, receive_reasons: ["receipt_missing"] },
        { status: "usable", can_receive: false, receive_reasons: ["receipt_missing"] }
      )
    );
    expect(html).toContain("Layak masuk stok");
    expect(html).not.toContain('data-action="receive"');
    expect(html).toContain("catat hasil terima petugas lebih dulu");
  });
});

describe("Fase 9 butir 2 — tindakan quarantined berbeda dari on_hold", () => {
  it("batch yang sudah ditahan menunjuk pelepasan karantina, bukan penahanan ulang", () => {
    const html = render(
      gate(
        { can_receive: false, can_quarantine: false, next_step: "lepas karantina atau tolak batch" },
        {
          status: "quarantined",
          can_receive: false,
          can_quarantine: false,
          receive_reasons: ["quarantined"],
          quarantine_reasons: ["quarantine_transition_invalid"],
        }
      )
    );
    expect(html).toContain('data-action="release-hint"');
    expect(html).toContain("Lepas karantina atau tolak batch lewat papan Keamanan Pangan");
    expect(html).not.toContain('data-action="quarantine-hint"');
    expect(html).not.toContain('data-action="receive"');
  });

  it("on_hold tetap menawarkan penahanan, bukan pelepasan", () => {
    const html = render(
      gate(
        { can_receive: false, can_quarantine: true, next_step: "selesaikan verifikasi verifier" },
        {
          status: "on_hold",
          can_receive: false,
          can_quarantine: true,
          receive_reasons: ["safety_needs_verification"],
        }
      )
    );
    expect(html).toContain('data-action="quarantine-hint"');
    expect(html).not.toContain('data-action="release-hint"');
    expect(html).not.toContain('data-action="receive"');
  });
});

describe("Fase 9 butir 2 — langkah berikutnya per batch", () => {
  it("tiap baris memakai next_step miliknya sendiri, bukan langkah agregat", () => {
    const summary = {
      decision_id: "d1",
      can_receive: false,
      can_quarantine: true,
      receipt_gate: {
        location_id: "loc-jkt",
        location_name: null,
        batches: [
          {
            batch_id: "b-hold",
            status: "on_hold",
            can_receive: false,
            can_quarantine: true,
            receive_reasons: ["safety_needs_verification"],
            quarantine_reasons: [],
            next_step: "selesaikan verifikasi verifier",
          },
          {
            batch_id: "b-exp",
            status: "rejected",
            can_receive: false,
            can_quarantine: false,
            receive_reasons: ["batch_expired"],
            quarantine_reasons: ["safety_fail_not_quarantinable"],
            next_step: "tolak batch — sudah lewat masa layak",
          },
        ],
        can_receive: false,
        can_quarantine: true,
        receive_reasons: ["safety_needs_verification", "batch_expired"],
        quarantine_reasons: [],
        // Agregat sengaja BUKAN langkah baris kedua: komponen harus memakai
        // langkah per baris bila server mengirimnya.
        next_step: "selesaikan verifikasi verifier",
      },
    };
    // Panel boleh meringkas semua alasan; yang diuji di sini adalah ISI DRAWER
    // tiap batch, jadi ambil bagian setelah langkah 1 dimulai.
    const drawer = (html: string) => html.slice(html.indexOf('data-testid="receipt-step-checklist"'));
    // Dua batch, dua drawer: masing-masing hanya memakai langkah miliknya.
    const hold = drawer(render(summary, { receipts: {}, batchId: "b-hold" }));
    expect(hold).toContain("Langkah berikutnya:</strong> selesaikan verifikasi verifier");
    expect(hold).not.toContain("sudah lewat masa layak");

    const expired = drawer(render(summary, { receipts: {}, batchId: "b-exp" }));
    expect(expired).toContain("tolak batch — sudah lewat masa layak");
    expect(expired).not.toContain("selesaikan verifikasi verifier");
    // Kode mentah tidak boleh sampai ke layar di kedua drawer.
    expect(hold).not.toContain("batch_expired");
    expect(expired).not.toContain("batch_expired");
  });

  it("baris siap-terima tanpa langkah sendiri tidak mewarisi langkah agregat", () => {
    const summary = {
      decision_id: "d1",
      can_receive: true,
      can_quarantine: true,
      receipt_gate: {
        location_id: "loc-jkt",
        location_name: null,
        batches: [
          {
            batch_id: "b-siap",
            status: "usable",
            can_receive: true,
            can_quarantine: true,
            receive_reasons: [],
            quarantine_reasons: [],
            next_step: null,
          },
          {
            batch_id: "b-karantina",
            status: "quarantined",
            can_receive: false,
            can_quarantine: false,
            receive_reasons: ["quarantined"],
            quarantine_reasons: ["quarantine_transition_invalid"],
            next_step: "lepas karantina atau tolak batch",
          },
        ],
        can_receive: true,
        can_quarantine: true,
        receive_reasons: ["quarantined"],
        quarantine_reasons: [],
        next_step: "lepas karantina atau tolak batch",
      },
    };
    const receipts = { "b-siap": [{ id: "r1", status: "menunggu", verdict: "pass" }] };
    // Drawer batch siap-terima menampilkan tombolnya, bukan arahan agregat.
    const barisSiap = render(summary, { receipts, batchId: "b-siap" });
    expect(barisSiap).toContain('data-action="receive"');
    expect(barisSiap).not.toContain("lepas karantina atau tolak batch");
    // Drawer batch karantina tetap memakai langkah miliknya sendiri.
    const barisKarantina = render(summary, { receipts, batchId: "b-karantina" });
    expect(barisKarantina).toContain("lepas karantina atau tolak batch");
    expect(barisKarantina).not.toContain('data-action="receive"');
  });
});

describe("Fase 9 butir 2 — peran non-head tetap read-only", () => {
  it("bgn_monitor: tanpa satu pun tombol mutasi", () => {
    const html = render(
      gate(
        { can_receive: false, can_quarantine: false, receive_reasons: ["role_not_head"] },
        { can_receive: false, can_quarantine: false, receive_reasons: ["role_not_head"] }
      ),
      { role: "bgn_monitor" }
    );
    expect(html).not.toContain('data-action="receive"');
    expect(html).not.toContain('data-action="reject"');
    expect(html).toContain("read-only");
    expect(html).toContain("hanya Kepala SPPG");
  });

  it("ahli gizi: boleh menahan (server), tetap tanpa 'Tandai diterima'", () => {
    const html = render(
      gate(
        { can_receive: false, can_quarantine: true, receive_reasons: ["role_not_head"] },
        { can_receive: false, can_quarantine: true, receive_reasons: ["role_not_head"] }
      ),
      { role: "sppg_nutritionist" }
    );
    expect(html).not.toContain('data-action="receive"');
    expect(html).not.toContain("Tandai diterima");
    expect(html).toContain("Tahan (karantina)");
  });
});
