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
  materialLabel,
  originLabel,
  progressNote,
  sourceNote,
  statusLabel,
  varianceLabel,
  varianceNada,
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
      origin: "execution",
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
      origin: "demo",
      // Realisasi nyata: 40 kg dipesan Rp 27.000/kg = Rp 1.080.000, barang
      // masuk 25 kg = Rp 675.000 → kurang Rp 405.000 (−37,5%).
      received_kg: 25,
      received_value_idr: 675000,
      variance_idr: -405000,
      variance_pct: -37.5,
      received_batch_count: 1,
      received_basis: "inspection_binding",
    },
    {
      // PO yang belum punya ikatan bukti penerimaan: semua angka realisasi
      // `null` — bukan 0 kg dan bukan Rp 0.
      po_number: "DEMO-PO-JAKA-BERAS",
      status: "submitted",
      decision_status: null,
      location_id: null,
      location_name: null,
      supplier_id: null,
      supplier_name: null,
      material_number: "MAT-003",
      ordered_quantity_kg: 100,
      price_per_kg: 12000,
      total_value: 1200000,
      source: "mock_sap_table",
      origin: "demo",
      received_kg: null,
      received_value_idr: null,
      variance_idr: null,
      variance_pct: null,
      received_batch_count: 0,
      received_basis: null,
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
  // 20 Okt 2026: panel ini kini memegang keadaan unduhan (PDF per PO), jadi ia
  // WAJIB dirender sebagai elemen React. Memanggilnya sebagai fungsi biasa
  // (`PurchaseOrderList({...})`) membuat hook berjalan di luar renderer dan
  // React melempar "Cannot read properties of null (reading 'useState')".
  return renderToStaticMarkup(
    <PurchaseOrderList data={PAYLOAD} summary={RINGKAS} {...(props as any)} />
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

  it("kalimat sumber menyebut simulasi dan menolak klaim SAP nyata", () => {
    const lokasi = sourceNote("lokasi");
    expect(lokasi).toContain("SAP simulasi");
    expect(lokasi).toContain("bukan SAP S/4HANA");
    expect(lokasi).not.toContain("DB demo");
    expect(lokasi).not.toContain("tabel transaksi");
    const nasional = sourceNote("nasional");
    expect(nasional).toContain("seluruh lokasi");
  });

  it("membedakan PO yang terbit dari keputusan dan baris impor SAP", () => {
    // 18 Okt: semua baris dulu tampil seolah "terbit dari eksekusi". Padahal
    // baris seed (DEMO-PO-*, 4500000001) tidak pernah melewati approval.
    // 19 Okt: "dari eksekusi" juga keliru — seeder demo menulis PO MC-* dengan
    // decision_id tanpa lewat eksekusi, jadi kata yang benar adalah "dari
    // keputusan" (fakta yang memang bisa dibuktikan) bukan klaim eksekusi.
    expect(originLabel("execution")).toBe("dari keputusan");
    expect(originLabel("demo")).toBe("impor SAP");
    expect(originLabel(null)).toBe("asal tidak tercatat");
  });

  it("bahan memakai nama komoditas dari DB, kode mentah hanya bila tak ada", () => {
    // Jangan menebak dari kode: `MAT-BERA` (seeder memotong 4 huruf) bukan kata.
    expect(materialLabel("Beras", "MAT-BERA")).toBe("Beras");
    expect(materialLabel(null, "MAT-BERA")).toBe("MAT-BERA");
    expect(materialLabel(null, "1000")).toBe("Bahan 1000");
    expect(materialLabel(null, null)).toBe("bahan tidak tercatat");
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
    expect(html).toContain("SAP simulasi");
    // Judul harus berbunyi seperti aplikasi, bukan demo; penanda simulasi
    // tetap ada di chip + kalimat sumber (aturan jujur repo ini).
    expect(html).not.toContain("mock lokal");
    expect(html).not.toContain("DB demo");
    expect(html).not.toContain("Purchase order (mock SAP)");
  });

  it("status tanpa baris tidak dipamerkan sebagai hitungan nol", () => {
    // "draf 0" adalah status hantu: tidak ada satu pun penulis di backend yang
    // pernah menulis status draft. Menampilkannya membuat pembaca mengira ada
    // antrean draf yang menunggu sesuatu.
    const html = render();
    expect(html).not.toContain("draf 0");
    const tanpaKirim = render({
      summary: { ...RINGKAS, by_status: { draft: 0, submitted: 0, confirmed: 2 } },
    });
    expect(tanpaKirim).not.toContain("terkirim 0");
    expect(tanpaKirim).toContain("terkonfirmasi");
  });

  it("menjelaskan arti status terkonfirmasi tanpa mengaku aplikasi yang mengonfirmasi", () => {
    const html = render();
    expect(html).toContain("diimpor");
    expect(html).toContain("Terkirim");
  });

  it("setiap baris menyebut asalnya: dari keputusan atau impor SAP", () => {
    const html = render();
    expect(html).toContain("dari keputusan");
    expect(html).toContain("impor SAP");
  });

  it("PO untuk keputusan yang sedang dibuka ditandai, bukan disamarkan", () => {
    const html = render({ decisionId: "11111111-1111-1111-1111-111111111111" });
    expect(html).toContain("keputusan ini");
    const lain = render({ decisionId: "99999999-9999-9999-9999-999999999999" });
    expect(lain).not.toContain("keputusan ini");
  });

  it("ringkasan yang belum termuat tidak ditulis sebagai Rp 0,00", () => {
    const html = render({ summary: null });
    expect(html).not.toContain("Rp 0,00");
    expect(html).toContain("DEMO-PO-JAKA-AYAM");
  });

  it("daftar yang terpotong batas limit mengatakannya", () => {
    expect(progressNote(2, 2)).toBeNull();
    expect(progressNote(200, 1234)).toContain("200");
    expect(progressNote(200, 1234)).toContain("1.234");
    const html = render({
      data: { ...PAYLOAD, limit: 200 },
      summary: { ...RINGKAS, count: 1234, total_value: 5719250 },
    });
    expect(html).toContain("dari 1.234");
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


describe("realisasi PO: nilai PO vs nilai barang masuk (Dok 05 §9)", () => {
  it("menampilkan dua angka berlabel berdampingan dalam satu baris", () => {
    const html = render();
    const iNilaiPo = html.indexOf("Nilai PO");
    const iDiterima = html.indexOf("Diterima");
    expect(iNilaiPo).toBeGreaterThan(-1);
    expect(iDiterima).toBeGreaterThan(iNilaiPo);
    // Angka server dipakai apa adanya: Rp 1.080.000,00 dan Rp 675.000,00.
    expect(html).toContain("Rp 1.080.000,00");
    expect(html).toContain("Rp 675.000,00");
  });

  it("selisih diberi tanda arah dan nada, bukan warna saja", () => {
    const html = render();
    expect(html).toContain("−Rp 405.000,00 (−37,5%)");
    expect(html).toContain("po-variance-kurang");

    expect(varianceNada(8300000)).toBe("lebih");
    expect(varianceNada(-405000)).toBe("kurang");
    expect(varianceNada(0)).toBe("pas");
    expect(varianceNada(null)).toBe("belum");
    expect(varianceLabel(null, null)).toBe("belum ada barang tercatat");
    expect(varianceLabel(0, 0)).toBe("sama dengan nilai PO");
    expect(varianceLabel(8300000, 33.33)).toBe("+Rp 8.300.000,00 (+33,33%)");
  });

  it("PO tanpa barang tercatat menulis kalimat, tidak pernah Rp 0", () => {
    const html = render();
    const barisBeras = html.split("DEMO-PO-JAKA-BERAS")[1] ?? "";
    expect(barisBeras).toContain("belum ada barang tercatat");
    expect(barisBeras).toContain("po-variance-belum");
    // Nilai PO baris itu tetap tampil (Rp 1.200.000,00); yang absen hanya
    // sisi "Diterima", ditandai em dash lewat formatRupiahOpsional.
    expect(barisBeras).toContain("Rp 1.200.000,00");
    expect(barisBeras).not.toContain("Diterima</span><span class=\"po-value\">Rp 0,00");
  });
});
