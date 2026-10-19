// Dokumen PO (PDF) di panel Purchase order — pagar, umpan balik, dan nama berkas.
//
// Yang dipaku di sini, dan alasannya:
//
// 1. **Tombol hanya untuk yang sudah disetujui.** Baris dengan keputusan
//    `approved`/`executed` mendapat tombol; baris lain mendapat KALIMAT
//    sebabnya. Ini cermin pagar backend (`services/po_document.py`): tombol
//    yang selalu ada padahal 409 = janji palsu, tombol yang hilang tanpa
//    penjelasan = fitur yang dikira rusak.
// 2. **Nama berkas satu aturan dengan backend.** Backend menulis
//    `Content-Disposition: filename="PO-<nomor>.pdf"`; frontend menyalin aturan
//    yang sama karena header itu tidak terbaca lintas-origin tanpa CORS.
// 3. **Galat server sampai ke layar.** Penolakan 409 ("keputusan menunggu
//    persetujuan") harus dibaca pengguna, bukan berubah jadi "gagal".
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import PurchaseOrderList, {
  PDF_DECISION_STATUS,
  bolehUnduhPdf,
  pdfHint,
  type PurchaseOrderRow,
} from "../components/PurchaseOrderList";
import { downloadPoPdf, poFileName } from "../lib/export";

function po(overrides: Partial<PurchaseOrderRow> = {}): PurchaseOrderRow {
  return {
    po_number: "MC-AAAAAAAAAAAA",
    status: "submitted",
    created_at: "2026-10-19T03:00:00+00:00",
    decision_id: "11111111-1111-1111-1111-111111111111",
    decision_status: "executed",
    location_id: "22222222-2222-2222-2222-222222222222",
    location_name: "Jakarta",
    supplier_id: "33333333-3333-3333-3333-333333333333",
    supplier_name: "CV Sumber Ayam",
    material_number: "MAT-AYAM",
    ordered_quantity_kg: 100,
    price_per_kg: 35000,
    total_value: 3500000,
    source: "mock_sap_table",
    origin: "execution",
    ...overrides,
  };
}

const payload = (items: PurchaseOrderRow[]) => ({
  items,
  count: items.length,
  limit: 50,
  scope: "lokasi",
  source: "mock_sap_table",
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("pagar dokumen PO", () => {
  it("hanya menerima keputusan yang sudah disetujui", () => {
    expect(PDF_DECISION_STATUS).toEqual(["approved", "executed"]);
    expect(bolehUnduhPdf("approved")).toBe(true);
    expect(bolehUnduhPdf("executed")).toBe(true);
    expect(bolehUnduhPdf("EXECUTED")).toBe(true);
    for (const status of [
      "proposed",
      "pending_approval",
      "verifier_flagged",
      "rejected",
      "review_only",
      null,
      undefined,
      "",
    ]) {
      expect(bolehUnduhPdf(status)).toBe(false);
    }
  });

  it("menjelaskan sebab baris tanpa tombol, tanpa menebak", () => {
    expect(pdfHint(po())).toBeNull();
    expect(pdfHint(po({ decision_id: null, decision_status: null }))).toBe(
      "PDF hanya untuk PO yang lahir dari keputusan yang sudah disetujui"
    );
    expect(pdfHint(po({ decision_status: "pending_approval" }))).toBe(
      "PDF tersedia setelah keputusan disetujui (kini: menunggu persetujuan)"
    );
    // Status asing ditampilkan apa adanya (tidak diterjemahkan dengan menebak).
    expect(pdfHint(po({ decision_status: "entah" }))).toContain("entah");
  });

  it("memberi nama berkas dengan aturan backend", () => {
    expect(poFileName("MC-ABCDEF123456")).toBe("PO-MC-ABCDEF123456.pdf");
    expect(poFileName("4500000001")).toBe("PO-4500000001.pdf");
    expect(poFileName("a/b c")).toBe("PO-a-b-c.pdf");
  });
});

describe("panel menampilkan aksi sesuai status", () => {
  it("menaruh tombol pada baris yang disetujui dan kalimat pada yang belum", () => {
    const markup = renderToStaticMarkup(
      <PurchaseOrderList
        token="token-uji"
        data={payload([
          po(),
          po({
            po_number: "PYTEST-PENDING",
            decision_status: "pending_approval",
          }),
          po({
            po_number: "4500000001",
            decision_id: null,
            decision_status: null,
            origin: "demo",
          }),
        ])}
        summary={{ by_status: { submitted: 2, confirmed: 1 }, count: 3, total_value: 9000000 }}
      />
    );

    // Satu tombol untuk satu PO yang disetujui.
    expect(markup.match(/po-pdf-button/g) ?? []).toHaveLength(1);
    expect(markup).toContain("Unduh PDF");
    expect(markup).toContain("Unduh dokumen PDF untuk PO MC-AAAAAAAAAAAA");
    // Baris belum disetujui: sebabnya disebut, tombolnya tidak ada.
    expect(markup).toContain("PDF tersedia setelah keputusan disetujui (kini: menunggu persetujuan)");
    expect(markup).toContain("PDF hanya untuk PO yang lahir dari keputusan yang sudah disetujui");
  });

  it("mematikan tombol saat sesi tidak punya token", () => {
    const markup = renderToStaticMarkup(
      <PurchaseOrderList token={null} data={payload([po()])} summary={null} />
    );
    expect(markup).toContain("po-pdf-button");
    expect(markup).toMatch(/disabled/);
    expect(markup).toContain("Sesi tidak aktif");
  });
});

describe("unduhan dokumen PO", () => {
  it("meminta endpoint PDF dengan kredensial sesi lalu mengunduh berkasnya", async () => {
    const blob = new Blob(["%PDF-1.7"], { type: "application/pdf" });
    const fetchStub = vi.fn(async () => ({ ok: true, blob: async () => blob }));
    const klik = vi.fn();
    vi.stubGlobal("fetch", fetchStub);
    vi.stubGlobal("URL", { createObjectURL: () => "blob:uji", revokeObjectURL: () => {} });
    vi.stubGlobal("document", { createElement: () => ({ click: klik }) });

    const nama = await downloadPoPdf("MC-ABCDEF123456", "token-uji");

    expect(nama).toBe("PO-MC-ABCDEF123456.pdf");
    expect(klik).toHaveBeenCalledTimes(1);
    const [url, init] = fetchStub.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/sap/purchase-orders/MC-ABCDEF123456/pdf");
    expect((init.headers as Record<string, string>).Authorization).toContain("token-uji");
  });

  it("meneruskan alasan penolakan server, bukan pesan generik", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        json: async () => ({ detail: "keputusan menunggu persetujuan — PDF PO diterbitkan setelah keputusan disetujui" }),
      }))
    );
    await expect(downloadPoPdf("MC-ABCDEF123456", "token-uji")).rejects.toMatchObject({
      status: 409,
      detail: "keputusan menunggu persetujuan — PDF PO diterbitkan setelah keputusan disetujui",
    });
  });
});
