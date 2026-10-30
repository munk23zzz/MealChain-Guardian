// Dokumen 05 §8 di repo ini — tiga angka, asal harga satuan, dan titik periksa.
//
// Yang dikunci:
//   1. §8.2 angka yang tampil dipilih dari payload server (`estimated_value_idr`
//      sebelum keputusan, `accepted_value_idr` sesudahnya) — klien tidak pernah
//      mengalikan kg × harga sendiri.
//   2. §8.3 asal harga satuan ditulis apa adanya dari PO; bila server tidak
//      mengirim harga, kalimatnya TIDAK dikarang (`null` → baris tidak tampil).
//   3. §8.1 jumlah titik periksa yang ditandai == yang tersimpan di `checked`.
//   4. Panel menampilkan daftar batch dengan tombol buka popup; isi popup
//      memuat tiga langkah berurutan.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import GoodsReceiptDrawer, {
  GoodsReceiptSheet,
  ReceiptFigures,
} from "../components/GoodsReceiptDrawer";
import {
  checkpointState,
  receiptFigures,
  valueOrigin,
} from "../lib/goods-receipt";

const catatanMenunggu = {
  id: "r1",
  batch_id: "b1",
  status: "menunggu",
  checked: { kemasan: true, suhu: true, timbang: true },
  // Skor & putusan dinilai SERVER (Dok 05 §3–§5). Sejak 30 Okt 2026 drawer
  // menampilkan angka ini, bukan hitungan "x dari 5 titik" buatan layar.
  score: 85,
  verdict: "needs_verification",
  verdict_label: "Perlu verifikasi",
  advice: "Skor 85 dari 100 — boleh masuk hanya setelah dicek ulang ahli gizi.",
  points: [
    {
      kunci: "suhu",
      label: "Suhu wadah",
      opsi: "sesuai",
      opsi_label: "Sesuai",
      bobot: 30,
      faktor: 1,
      poin: 30,
      max_points: 30,
      kritis: false,
      perlu_cek: false,
    },
    {
      kunci: "kemasan",
      label: "Kemasan utuh",
      opsi: "ragu",
      opsi_label: "Ragu",
      bobot: 20,
      faktor: 0.6,
      poin: 12,
      max_points: 20,
      kritis: false,
      perlu_cek: true,
    },
  ],
  other_note: null,
  batch_quantity_kg: 130,
  stock_kg: null,
  accepted_value_idr: null,
  unit_price_idr: 26200,
  po_number: "4500000001",
  estimated_value_idr: 3406000,
};

const catatanDisetujui = {
  ...catatanMenunggu,
  status: "disetujui",
  stock_kg: 130,
  accepted_value_idr: 3065400,
  batch_quantity_kg: 117,
  unit_price_idr: 26200,
};

const baris = {
  batchId: "b1",
  status: "usable",
  statusLabel: "Layak masuk stok",
  canReceive: true,
  canQuarantine: true,
  reasons: [],
  nextStep: null,
};

function gate() {
  return {
    decision_id: "d1",
    can_receive: true,
    can_quarantine: true,
    receipt_gate: {
      location_id: "loc-jkt",
      location_name: null,
      batches: [
        {
          batch_id: "b1",
          status: "usable",
          can_receive: true,
          can_quarantine: true,
          receive_reasons: [],
          quarantine_reasons: [],
          next_step: null,
        },
      ],
      can_receive: true,
      can_quarantine: true,
      receive_reasons: [],
      quarantine_reasons: [],
      next_step: null,
    },
  };
}

describe("Dok 05 §8.2 — angka yang dipilih klien berasal dari server", () => {
  it("sebelum keputusan: nilai = perkiraan server, ditandai sementara", () => {
    const angka = receiptFigures(catatanMenunggu);
    expect(angka.nilaiIdr).toBe(3406000);
    expect(angka.nilaiSementara).toBe(true);
    expect(angka.statusNilai).toBe("perkiraan");
    expect(angka.masukStokKg).toBeNull();
    expect(angka.kuantitasKg).toBe(130);
  });

  it("sesudah disetujui: nilai pembukuan menang atas perkiraan", () => {
    const angka = receiptFigures(catatanDisetujui);
    expect(angka.nilaiIdr).toBe(3065400);
    expect(angka.nilaiSementara).toBe(false);
    expect(angka.statusNilai).toBe("tersimpan");
    expect(angka.masukStokKg).toBe(130);
  });

  it("tanpa harga PO: tidak tercatat, bukan Rp 0", () => {
    const angka = receiptFigures({
      ...catatanMenunggu,
      unit_price_idr: null,
      estimated_value_idr: null,
    });
    expect(angka.nilaiIdr).toBeNull();
    expect(angka.statusNilai).toBe("tidak_tercatat");
  });

  it("catatan belum ada: semua angka kosong, tidak menebak", () => {
    const angka = receiptFigures(null);
    expect(angka.kuantitasKg).toBeNull();
    expect(angka.masukStokKg).toBeNull();
    expect(angka.nilaiIdr).toBeNull();
  });
});

describe("Dok 05 §8.3 — asal harga satuan", () => {
  it("menyebut kg × Rp per kg dari nomor PO", () => {
    const asal = valueOrigin(catatanMenunggu);
    expect(asal).toContain("130 kg");
    expect(asal).toContain("Rp 26.200");
    expect(asal).toContain("PO 4500000001");
  });

  it("tanpa harga: tidak ada kalimat (lebih baik diam daripada mengarang)", () => {
    expect(valueOrigin({ ...catatanMenunggu, unit_price_idr: null })).toBeNull();
    expect(valueOrigin(null)).toBeNull();
  });
});

describe("Dok 05 §8.1 — titik periksa yang tersimpan", () => {
  it("menghitung yang benar-benar ditandai dari lima titik", () => {
    const titik = checkpointState(catatanMenunggu);
    expect(titik.total).toBe(5);
    expect(titik.done).toBe(3);
    expect(titik.items.filter((i) => i.checked).map((i) => i.id)).toEqual([
      "kemasan",
      "suhu",
      "timbang",
    ]);
  });

  it("tanpa catatan: 0 dari 5, semua tidak ditandai", () => {
    const titik = checkpointState(null);
    expect(titik.done).toBe(0);
    expect(titik.items.every((i) => i.checked === false)).toBe(true);
  });
});

describe("Dok 05 §1–§2 — panel daftar + drawer tiga langkah", () => {
  it("panel menampilkan tombol buka popup per batch", () => {
    const html = renderToStaticMarkup(
      <GoodsReceiptDrawer summary={gate()} token="t" role="sppg_head" receipts={{}} />
    );
    expect(html).toContain("Buka penerimaan");
    expect(html).toContain("Layak masuk stok");
  });

  it("isi drawer: tiga langkah berurutan dan tiga angka", () => {
    const html = renderToStaticMarkup(
      <GoodsReceiptSheet
        baris={baris}
        catatan={catatanMenunggu}
        bolehPutuskan
        busy={false}
        galat={null}
        pesan={null}
      />
    );
    const i1 = html.indexOf("Periksa kondisi barang");
    const i2 = html.indexOf("Nilai dan putusan batch");
    const i3 = html.indexOf("Tandai barang");
    expect(i1).toBeGreaterThan(-1);
    expect(i2).toBeGreaterThan(i1);
    expect(i3).toBeGreaterThan(i2);
    expect(html).toContain(">85<");
    expect(html).toContain(">/100<");
    expect(html).toContain("Perlu verifikasi");
    expect(html).toContain("30/30");
    expect(html).toContain("Rp 3.406.000");
    expect(html).toContain("perkiraan");
    expect(html).toContain("× Rp 26.200");
  });

  it("nilai pembukuan tampil tanpa label perkiraan setelah disetujui", () => {
    const html = renderToStaticMarkup(
      <GoodsReceiptSheet
        baris={{ ...baris, canReceive: false }}
        catatan={catatanDisetujui}
        bolehPutuskan
        busy={false}
        galat={null}
        pesan={null}
      />
    );
    expect(html).toContain("Rp 3.065.400");
    expect(html).not.toContain("perkiraan");
    expect(html).toContain("130 kg");
  });

  it("tanpa harga PO: 'tidak tercatat', bukan Rp 0 dan tanpa asal harga", () => {
    const html = renderToStaticMarkup(
      <ReceiptFigures
        catatan={{ ...catatanMenunggu, unit_price_idr: null, estimated_value_idr: null }}
      />
    );
    expect(html).toContain("tidak tercatat");
    expect(html).not.toContain("Rp 0");
    expect(html).not.toContain("receipt-value-origin");
  });

  it("peran non-head tidak mendapat tombol terima walau batch layak", () => {
    const html = renderToStaticMarkup(
      <GoodsReceiptSheet
        baris={{ ...baris, canQuarantine: false }}
        catatan={catatanMenunggu}
        bolehPutuskan={false}
        busy={false}
        galat={null}
        pesan={null}
      />
    );
    expect(html).not.toContain('data-action="receive"');
    expect(html).toContain("read-only");
  });

  it("galat 409 server ditampilkan apa adanya", () => {
    const html = renderToStaticMarkup(
      <GoodsReceiptSheet
        baris={baris}
        catatan={catatanMenunggu}
        bolehPutuskan
        busy={false}
        galat="barang masih berstatus karantina — tidak boleh masuk stok"
        pesan={null}
      />
    );
    expect(html).toContain("masih berstatus karantina");
  });
});
