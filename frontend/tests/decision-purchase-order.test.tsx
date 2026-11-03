// Tes komponen PO-dossier (rencana langkah 5, bagian "Jejak & hasil").
//
// Aturan yang dikunci: halaman Decision & Evidence TIDAK boleh menampilkan
// daftar PO jaringan. Yang tampil hanya PO milik keputusan yang sedang dibuka,
// dan bila belum ada, sebabnya ditulis.
//
// Gaya tes di repo ini: `renderToStaticMarkup` (tanpa jsdom/@testing-library),
// sama seperti tests/location-network-board.test.tsx.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DecisionPurchaseOrder from "../components/DecisionPurchaseOrder";

const daftar = [
  { po_number: "MC-B5B391FE89E1", status: "submitted", decision_id: "d1", created_at: "2026-10-28T10:00:00Z" },
  { po_number: "MC-LAIN-1", status: "submitted", decision_id: "d9", created_at: "2026-10-28T11:00:00Z" },
];

function render(props: Parameters<typeof DecisionPurchaseOrder>[0]): string {
  return renderToStaticMarkup(<DecisionPurchaseOrder {...props} />);
}

describe("DecisionPurchaseOrder", () => {
  it("menampilkan hanya PO milik keputusan ini", () => {
    const html = render({ purchaseOrders: daftar, decisionId: "d1" });
    expect(html).toContain("MC-B5B391FE89E1");
    expect(html).not.toContain("MC-LAIN-1");
  });

  it("menulis sebab ketika keputusan belum punya PO", () => {
    const html = render({ purchaseOrders: daftar, decisionId: "d7" });
    expect(html).toMatch(/belum ada PO untuk keputusan ini/i);
    // Daftar jaringan tidak bocor sebagai penghibur.
    expect(html).not.toContain("MC-LAIN-1");
    expect(html).not.toContain("MC-B5B391FE89E1");
  });

  it("tidak mengarang apa pun ketika keputusan belum dipilih", () => {
    const html = render({ purchaseOrders: daftar, decisionId: null });
    expect(html).toMatch(/belum ada keputusan yang dibuka/i);
  });

  it("memakai label status kanonik, bukan status mentah backend", () => {
    const html = render({ purchaseOrders: daftar, decisionId: "d1" });
    // Label kanonik dari lib/detail-keputusan.tahapPo.
    expect(html).toContain("Terkirim ke SAP");
    expect(html).not.toMatch(/>\s*submitted\s*</);
  });

  it("menandai PO draft sebagai menunggu review", () => {
    const html = render({
      purchaseOrders: [{ po_number: "MC-DRAFT", status: "draft", decision_id: "d1" }],
      decisionId: "d1",
    });
    expect(html).toMatch(/draf, menunggu review/i);
  });

  it("menyebut bahwa daftar jaringan ada di halaman Pemasok", () => {
    const html = render({ purchaseOrders: daftar, decisionId: "d1" });
    expect(html).toMatch(/halaman Pemasok/);
  });
});

describe("DecisionPurchaseOrder — dokumen PO bisa diunduh (29 Okt 2026)", () => {
  // Laporan pemilik: "harusnya setelah eksekusi bisa dapat download PDF PO".
  // Sejak kartu ini dibangun ulang (rencana decision-evidence-rebuild §3) menjadi
  // ringkasan satu PO, tombol Unduh PDF yang dulu ada di daftar PO ikut hilang —
  // padahal justru di sinilah dokumennya dicari. Aturannya sama dengan server:
  // PDF sah untuk keputusan yang sudah disetujui/dieksekusi.
  const po = [{ po_number: "MC-BEF077A8A935", status: "submitted", decision_id: "d1" }];

  it("keputusan dieksekusi: tombol Unduh PDF tersedia", () => {
    const html = render({ purchaseOrders: po, decisionId: "d1", token: "t", decisionStatus: "executed" });
    expect(html).toContain('data-unduh-po="MC-BEF077A8A935"');
    expect(html).toContain("Unduh PDF");
  });

  it("keputusan yang belum disetujui: tidak ada tombol, sebabnya ditulis", () => {
    const html = render({ purchaseOrders: po, decisionId: "d1", token: "t", decisionStatus: "pending_approval" });
    expect(html).not.toContain("data-unduh-po");
    expect(html).toMatch(/PDF terbit setelah keputusan disetujui/i);
  });

  it("tanpa sesi: tombol tidak ditawarkan", () => {
    const html = render({ purchaseOrders: po, decisionId: "d1", token: null, decisionStatus: "executed" });
    expect(html).not.toContain("data-unduh-po");
  });
});
