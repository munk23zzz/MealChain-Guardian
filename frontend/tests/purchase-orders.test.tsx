// Purchase order mock SAP terbaca (W-5 · 2026-10-17) — kontrak tampilan.
//
// Yang dipaku di sini, dan alasannya:
//
// 1. Panel menyebut SUMBERNYA apa adanya: "tabel transaksi mock di DB demo,
//    bukan SAP S/4HANA nyata". Endpoint mengirim `source = "mock_sap_table"`;
//    UI tidak boleh mengubahnya jadi klaim SAP sungguhan.
// 2. Status diterjemahkan, bukan ditampilkan mentah (`submitted` → "terkirim").
// 3. PO yang punya keputusan menaut ke `?keputusan=<id>` (deep link yang sudah
//    berlaku), sedangkan PO tanpa keputusan (baris seed/adapter) menulis
//    "tanpa keputusan" dan TIDAK menaut ke mana pun.
// 4. Daftar kosong berbeda dari 0 rupiah: tidak ada baris berarti kalimat
//    "belum ada purchase order", bukan "Rp 0".
// 5. Galat ditampilkan sebagai galat — bukan layar kosong yang bisa dibaca
//    sebagai "tidak ada PO".
// 6. Trace `ACT` menyebut nomor PO-nya; sebelumnya `AgentTraceViewer` hanya
//    menampilkan nama tool sehingga nomor PO hilang dari layar.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import AgentTraceViewer from "../components/AgentTraceViewer";
import PurchaseOrderList, {
  formatKg,
  formatRupiah,
  sourceNote,
  statusLabel,
} from "../components/PurchaseOrderList";

const PAYLOAD = {
  scope: "lokasi",
  source: "mock_sap_table",
  count: 2,
  limit: 50,
  items: [
    {
      po_number: "DEMO-PO-JAKA-AYAM",
      status: "confirmed",
      created_at: "2026-10-17T02:00:00+00:00",
      decision_id: "11111111-1111-1111-1111-111111111111",
      decision_status: "executed",
      location_id: "22222222-2222-2222-2222-222222222222",
      location_name: "Jakarta",
      supplier_id: "33333333-3333-3333-3333-333333333333",
      supplier_name: "CV Sumber Ayam",
      material_number: "MAT-001",
      ordered_quantity_kg: 120.5,
      price_per_kg: 38500,
      total_value: 4639250,
      source: "mock_sap_table",
    },
    {
      po_number: "4500000001",
      status: "submitted",
      created_at: "2026-10-16T02:00:00+00:00",
      decision_id: null,
      decision_status: null,
      location_id: null,
      location_name: null,
      supplier_id: "44444444-4444-4444-4444-444444444444",
      supplier_name: "PT Telur Nusantara",
      material_number: "MAT-002",
      ordered_quantity_kg: 40,
      price_per_kg: 27000,
      total_value: 1080000,
      source: "mock_sap_table",
    },
  ],
};

const RINGKAS = {
  scope: "lokasi",
  source: "mock_sap_table",
  by_status: { draft: 0, submitted: 1, confirmed: 1 },
  count: 2,
  total_value: 5719250,
};

function render(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    PurchaseOrderList({ data: PAYLOAD, summary: RINGKAS, ...props } as any)
  );
}

describe("label & format", () => {
  it("menerjemahkan status apa adanya, tanpa mengarang status baru", () => {
    expect(statusLabel("draft")).toBe("draf");
    expect(statusLabel("submitted")).toBe("terkirim");
    expect(statusLabel("confirmed")).toBe("terkonfirmasi");
    expect(statusLabel("lainnya")).toBe("lainnya");
  });

  it("rupiah memakai format Indonesia dan tidak membulatkan diam-diam", () => {
    expect(formatRupiah(45238305.84)).toBe("Rp 45.238.305,84");
    expect(formatRupiah(0)).toBe("Rp 0,00");
  });

  it("kilogram menampilkan satu desimal tanpa memalsukan nol", () => {
    expect(formatKg(120.5)).toBe("120,5 kg");
    expect(formatKg(40)).toBe("40 kg");
  });

  it("kalimat sumber menyebut mock dan menolak klaim SAP nyata", () => {
    const lokasi = sourceNote("lokasi");
    expect(lokasi).toContain("tabel transaksi mock");
    expect(lokasi).toContain("bukan SAP S/4HANA");
    const nasional = sourceNote("nasional");
    expect(nasional).toContain("seluruh lokasi");
  });
});

describe("panel purchase order", () => {
  it("menampilkan nomor PO, pemasok, nilai, dan jumlah per status", () => {
    const html = render();
    expect(html).toContain("DEMO-PO-JAKA-AYAM");
    expect(html).toContain("CV Sumber Ayam");
    expect(html).toContain("Rp 4.639.250,00");
    expect(html).toContain("terkirim");
    expect(html).toContain("terkonfirmasi");
    expect(html).toContain("Rp 5.719.250,00"); // total ringkasan
    expect(html).toContain("tabel transaksi mock");
  });

  it("PO berkeputusan menaut ke deep link, PO tanpa keputusan tidak", () => {
    const html = render();
    expect(html).toContain("?keputusan=11111111-1111-1111-1111-111111111111");
    expect(html).toContain("tanpa keputusan");
    // baris tanpa keputusan tidak boleh punya tautan ?keputusan= untuk dirinya
    const baris = html.split("<li").filter((b) => b.includes("4500000001"));
    expect(baris.length).toBe(1);
    expect(baris[0]).not.toContain("?keputusan=");
  });

  it("daftar kosong menulis kalimat, bukan Rp 0", () => {
    const html = render({
      data: { ...PAYLOAD, items: [], count: 0 },
      summary: { ...RINGKAS, by_status: { draft: 0, submitted: 0, confirmed: 0 }, count: 0, total_value: 0 },
    });
    expect(html).toContain("Belum ada purchase order");
    expect(html).not.toContain("Rp 0,00 untuk");
  });

  it("galat ditampilkan sebagai galat, bukan daftar kosong", () => {
    const html = render({ data: null, summary: null, error: "HTTP 500: /sap/purchase-orders" });
    expect(html).toContain("HTTP 500");
    expect(html).not.toContain("Belum ada purchase order");
  });
});

describe("trace ACT menyebut nomor PO", () => {
  it("menampilkan po_number dari output_summary", () => {
    const html = renderToStaticMarkup(
      AgentTraceViewer({
        steps: [
          {
            step_name: "ACT",
            tool_called: "sap_mock.create_purchase_order",
            step_at: "2026-10-17T02:00:00+00:00",
            output_summary: { po_number: "MC-54EDFCA1EF77", status: "submitted" },
          },
        ],
        decisionId: "11111111-1111-1111-1111-111111111111",
      } as any)
    );
    expect(html).toContain("MC-54EDFCA1EF77");
    expect(html).toContain("PO");
  });
});
