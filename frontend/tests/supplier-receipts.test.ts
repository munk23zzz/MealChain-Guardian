// Riwayat penerimaan per pemasok (Dok 05 §8.5, halaman Pemasok).
//
// Yang dikunci di lapisan murni ini — semuanya bisa diperiksa tanpa DB:
//   1. §8.2 tiga angka: dipesan · diterima · nilai diterima, dari `ringkasan`
//      server (bukan dihitung ulang dari halaman yang sudah dipotong `limit`);
//   2. §8.3 asal harga satuan ditulis apa adanya; tanpa harga → tidak ada
//      kalimat, dan nilainya "tidak tercatat" — BUKAN Rp 0;
//   3. kg diterima KOSONG ("—") selama catatan belum disetujui;
//   4. putusan punya label + nada, jadi warna tidak pernah sendirian.

import { describe, expect, it } from "vitest";

import {
  receiptFilterLabel,
  receiptHeadline,
  receiptHistory,
  receiptShortfall,
  receiptStatusLabel,
  receiptTone,
  receiptTotals,
  receiptValue,
} from "../lib/supplier-receipts";

const disetujui = {
  id: "r1",
  batch_id: "0ff8f2b1-f217-5e1e-bb06-63912491a1cb",
  batch_ref: "0ff8f2b1",
  supplier_id: "s1",
  supplier: "CV Hortikultura Subang Lestari",
  commodity: "wortel",
  status: "disetujui",
  recorded_at: "2026-10-27T05:00:00+00:00",
  reviewed_at: "2026-10-27T05:25:00+00:00",
  checked_count: 4,
  ordered_kg: 420,
  received_kg: 420,
  unit_price_idr: 11500,
  po_number: "MC-08E732F618E0",
  estimated_value_idr: 4830000,
  accepted_value_idr: 4830000,
  review_note: null,
};

const menunggu = {
  ...disetujui,
  id: "r2",
  batch_ref: "467caaad",
  status: "menunggu",
  ordered_kg: 540,
  received_kg: null,
  accepted_value_idr: null,
  estimated_value_idr: 6210000,
  recorded_at: "2026-10-28T03:10:00+00:00",
  reviewed_at: null,
};

const ditolak = {
  ...disetujui,
  id: "r3",
  batch_ref: "13950f6a",
  status: "ditolak",
  ordered_kg: 300,
  received_kg: null,
  accepted_value_idr: null,
  estimated_value_idr: 9750000,
  review_note: "Kemasan bocor dan suhu di atas batas saat tiba.",
};

const tanpaHarga = {
  ...menunggu,
  id: "r4",
  unit_price_idr: null,
  po_number: null,
  estimated_value_idr: null,
};

function amplop(items: unknown[], ringkasan: Record<string, unknown>) {
  return { items, ringkasan };
}

describe("Dok 05 §8.2 — tiga angka dari ringkasan server", () => {
  it("menulis dipesan · diterima · nilai diterima", () => {
    const total = receiptTotals(
      amplop(
        [disetujui, menunggu, ditolak],
        {
          total: 3,
          menunggu: 1,
          disetujui: 1,
          ditolak: 1,
          kg_dipesan: 1260,
          kg_diterima: 420,
          nilai_diterima_idr: 4830000,
          nilai_menunggu_idr: 6210000,
          tanpa_harga: 0,
          supplier: 3,
        }
      )
    );
    expect(receiptHeadline(total)).toBe(
      "Dipesan 1.260 kg · Diterima 420 kg · Nilai diterima Rp 4.830.000"
    );
  });

  it("riwayat kosong tidak berbunyi 'Dipesan 0 kg'", () => {
    expect(receiptHeadline(receiptTotals(amplop([], { total: 0 })))).toBeNull();
  });

  it("belum ada yang disetujui: 'belum ada', bukan Rp 0", () => {
    const total = receiptTotals(
      amplop([menunggu], {
        total: 1,
        menunggu: 1,
        kg_dipesan: 540,
        kg_diterima: 0,
        nilai_diterima_idr: 0,
      })
    );
    const kalimat = receiptHeadline(total) ?? "";
    expect(kalimat).toContain("Diterima belum ada");
    expect(kalimat).toContain("Nilai diterima belum ada");
    expect(kalimat).not.toContain("Rp 0");
  });

  it("ringkasan tidak dihitung ulang dari items (limit memotong daftar)", () => {
    const total = receiptTotals(
      amplop([disetujui], {
        total: 12,
        menunggu: 9,
        disetujui: 2,
        ditolak: 1,
        kg_dipesan: 5000,
        kg_diterima: 840,
        nilai_diterima_idr: 9660000,
        supplier: 5,
      })
    );
    expect(total.total).toBe(12);
    expect(total.menunggu).toBe(9);
    expect(total.kgDipesan).toBe(5000);
    expect(receiptHeadline(total)).toBe(
      "Dipesan 5.000 kg · Diterima 840 kg · Nilai diterima Rp 9.660.000"
    );
  });

  it("susut hanya ditulis bila ada kg yang tidak masuk stok", () => {
    const total = receiptTotals(
      amplop([], {
        total: 3,
        disetujui: 1,
        kg_dipesan: 1260,
        kg_diterima: 420,
      })
    );
    expect(receiptShortfall(total)).toContain("840 kg");
    const pas = receiptTotals(
      amplop([], { total: 1, disetujui: 1, kg_dipesan: 420, kg_diterima: 420 })
    );
    expect(receiptShortfall(pas)).toBeNull();
    const belumDiputuskan = receiptTotals(
      amplop([], { total: 1, menunggu: 1, kg_dipesan: 540, kg_diterima: 0 })
    );
    expect(receiptShortfall(belumDiputuskan)).toBeNull();
  });
});

describe("Dok 05 §5.3 — nilai per baris, tidak pernah dikarang", () => {
  it("disetujui: nilai pembukuan tanpa kata perkiraan", () => {
    const nilai = receiptValue(disetujui);
    expect(nilai.status).toBe("tersimpan");
    expect(nilai.nilai).toBe(4830000);
    expect(nilai.label).toBe("Rp 4.830.000");
  });

  it("menunggu: nilai perkiraan DIBERI KATA perkiraan", () => {
    const nilai = receiptValue(menunggu);
    expect(nilai.status).toBe("perkiraan");
    expect(nilai.label).toContain("perkiraan");
  });

  it("tanpa harga PO: 'tidak tercatat', bukan Rp 0", () => {
    const nilai = receiptValue(tanpaHarga);
    expect(nilai.status).toBe("tidak_tercatat");
    expect(nilai.nilai).toBeNull();
    expect(nilai.label).toBe("tidak tercatat");
    expect(nilai.label).not.toBe("Rp 0");
  });

  it("ditolak tidak pernah memakai nilai pembukuan walau angkanya dikirim", () => {
    const nilai = receiptValue({ ...ditolak, accepted_value_idr: 9750000 });
    expect(nilai.status).not.toBe("tersimpan");
  });

  it("ditolak: tidak ada angka rupiah sama sekali (barangnya tidak dibukukan)", () => {
    const nilai = receiptValue({ ...ditolak, estimated_value_idr: 5400000 });
    expect(nilai.status).toBe("tidak_diterima");
    expect(nilai.nilai).toBeNull();
    expect(nilai.label).toBe("—");
  });
});

describe("kg dipesan vs kg diterima (dua kolom, bukan selisih di klien)", () => {
  it("menunggu: diterima '—' supaya tidak terbaca sudah masuk stok", () => {
    const [row] = receiptHistory(amplop([menunggu], {}));
    expect(row.orderedLabel).toBe("540 kg");
    expect(row.receivedLabel).toBe("—");
    expect(row.receivedKg).toBeNull();
  });

  it("disetujui: kedua angka terisi", () => {
    const [row] = receiptHistory(amplop([disetujui], {}));
    expect(row.orderedLabel).toBe("420 kg");
    expect(row.receivedLabel).toBe("420 kg");
  });

  it("baris tanpa kg tidak menghasilkan NaN", () => {
    const [row] = receiptHistory(amplop([{ ...disetujui, ordered_kg: null }], {}));
    expect(row.orderedLabel).toBe("—");
  });
});

describe("Dok 05 §8.3 — asal harga satuan ditulis di tempat", () => {
  it("menyebut kg × Rp per kg dari nomor PO", () => {
    const [row] = receiptHistory(amplop([disetujui], {}));
    expect(row.priceOrigin).toContain("420 kg");
    expect(row.priceOrigin).toContain("Rp 11.500");
    expect(row.priceOrigin).toContain("MC-08E732F618E0");
  });

  it("tanpa harga: tidak ada kalimat (diam lebih baik daripada mengarang)", () => {
    const [row] = receiptHistory(amplop([tanpaHarga], {}));
    expect(row.priceOrigin).toBeNull();
  });
});

describe("putusan: label + nada, bukan warna saja", () => {
  it("tiga putusan punya label dan nada berbeda", () => {
    expect(receiptStatusLabel("disetujui")).toBe("Diterima");
    expect(receiptStatusLabel("ditolak")).toBe("Ditolak");
    expect(receiptStatusLabel("menunggu")).toBe("Menunggu keputusan");
    expect(receiptTone("disetujui")).toBe("ok");
    expect(receiptTone("ditolak")).toBe("danger");
    expect(receiptTone("menunggu")).toBe("warn");
  });

  it("status tak dikenal dibaca 'menunggu' — bukan 'disetujui'", () => {
    expect(receiptStatusLabel("entah")).toBe("Menunggu keputusan");
    expect(receiptStatusLabel(null)).toBe("Menunggu keputusan");
  });

  it("label penyaring memakai bahasa yang sama dengan pil baris", () => {
    expect(receiptFilterLabel("semua")).toBe("Semua");
    expect(receiptFilterLabel("ditolak")).toBe("Ditolak");
  });
});

describe("bentuk baris untuk tabel", () => {
  it("membawa pemasok, komoditas, titik periksa, dan alasan penolakan", () => {
    const rows = receiptHistory(amplop([ditolak], {}));
    const [row] = rows;
    expect(row.supplier).toBe("CV Hortikultura Subang Lestari");
    expect(row.commodity).toBe("wortel");
    expect(row.batchRef).toBe("13950f6a");
    expect(row.checkedLabel).toBe("4 dari 5 titik");
    expect(row.note).toContain("Kemasan bocor");
  });

  it("amplop rusak tidak melempar", () => {
    expect(receiptHistory(null)).toEqual([]);
    expect(receiptHistory({ items: "bukan array" })).toEqual([]);
    expect(receiptTotals(undefined).total).toBe(0);
  });
});
