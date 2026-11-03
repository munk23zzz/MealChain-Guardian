// Kontrak acuan hitung popup detail keputusan (dokumen `01-detail-keputusan.md`).
// Semua angka di sini diambil dari payload NYATA satu keputusan pengadaan
// (purchase 7358754, transport 9592.92, handling 150000, expected_loss 88305.05,
// freshness 0, safety 0, sdc_total 7606651.97, quantity 600 kg) supaya tes
// menangkap salah kutip rumus, bukan sekadar salah tipe.
import { describe, expect, it } from "vitest";

import {
  alurKeputusan,
  jenisKeputusan,
  perbandinganHarga,
  rupiah,
  tahapPo,
  tigaLapisBiaya,
} from "../lib/detail-keputusan";

const COMMERCIAL = {
  purchase_total: "7358754.00",
  transport_total: "9592.92",
  handling_total: "150000.00",
  invoice_total: "7518346.92",
  invoice_unit_price: "12530.58",
  expected_loss: "88305.05",
  freshness_risk: "0.00",
  safety_penalty: "0.00",
  sdc_total: "7606651.97",
  sdc_unit_price: "12677.75",
};

describe("rupiah: nilai kosong bukan nol", () => {
  it("null/undefined/string kosong → null, bukan Rp0", () => {
    expect(rupiah(null)).toBeNull();
    expect(rupiah(undefined)).toBeNull();
    expect(rupiah("")).toBeNull();
  });
  it("nol yang benar-benar ada tetap Rp0", () => {
    expect(rupiah(0)).toBe("Rp0");
    expect(rupiah("0.00")).toBe("Rp0");
  });
  it("memakai pemisah ribuan Indonesia", () => {
    expect(rupiah("7358754.00")).toBe("Rp7.358.754");
    expect(rupiah(7606651.97)).toBe("Rp7.606.652");
  });
});

describe("jenisKeputusan", () => {
  it("memisahkan pembelian, administratif, dan tipe tak dikenal", () => {
    expect(jenisKeputusan("supplier_procurement")).toBe("pembelian");
    expect(jenisKeputusan("regional_balance")).toBe("pembelian");
    expect(jenisKeputusan("supplier_exclusion_restoration")).toBe("administratif");
    expect(jenisKeputusan("price_anomaly")).toBe("administratif");
    expect(jenisKeputusan("sesuatu_baru")).toBe("lain");
  });
});

describe("alurKeputusan: empat langkah pembelian, tiga administratif", () => {
  it("pengadaan menunggu approval berhenti di langkah Approval", () => {
    const { steps, buntu } = alurKeputusan(
      { decision_type: "supplier_procurement", status: "pending_approval" },
      { status: "pending_approval" }
    );
    expect(steps.map((s) => s.label)).toEqual(["Usulan", "Verifikasi", "Approval", "Dibeli"]);
    expect(steps.map((s) => s.state)).toEqual(["selesai", "selesai", "kini", "menunggu"]);
    expect(buntu).toBeNull();
  });

  it("restorasi pemasok (administratif) memakai tiga langkah", () => {
    const { steps } = alurKeputusan(
      { decision_type: "supplier_exclusion_restoration", status: "pending_approval" },
      { status: "pending_approval" }
    );
    expect(steps.map((s) => s.label)).toEqual(["Usulan", "Persetujuan", "Diberlakukan"]);
    expect(steps.map((s) => s.state)).toEqual(["selesai", "kini", "menunggu"]);
  });

  it("selesai berarti seluruh langkah selesai", () => {
    const { steps } = alurKeputusan(
      { decision_type: "supplier_procurement", status: "executed" },
      { status: "executed" }
    );
    expect(steps.every((s) => s.state === "selesai")).toBe(true);
  });

  it("ditolak tidak dipetakan ke langkah: ada chip jalan buntu", () => {
    const { steps, buntu } = alurKeputusan(
      { decision_type: "supplier_procurement", status: "rejected" },
      { status: "rejected" }
    );
    expect(buntu).toBe("Ditolak");
    expect(steps.some((s) => s.state === "kini")).toBe(false);
  });
});

describe("tigaLapisBiaya: tiga lapis, bukan tabel datar", () => {
  const hasil = tigaLapisBiaya(COMMERCIAL, 600);

  it("lapis 1 = yang dibayar ke pemasok, dengan rumus per kg", () => {
    expect(hasil.lapis[0].judul).toBe("Dibayar ke pemasok");
    expect(hasil.lapis[0].nilai).toBe("Rp7.358.754");
    expect(hasil.lapis[0].rumus).toBe("Rp7.358.754 ÷ 600 kg");
  });

  it("lapis 2 = logistik + penanganan", () => {
    expect(hasil.lapis[1].judul).toBe("Tambahan sampai barang tiba");
    expect(hasil.lapis[1].nilai).toBe("Rp159.593");
    expect(hasil.lapis[1].baris.map((b) => b.label)).toEqual(["Logistik", "Penanganan"]);
  });

  it("lapis 3 = susut gudang, dipisah dari risiko", () => {
    expect(hasil.lapis[2].judul).toBe("Susut selama disimpan");
    expect(hasil.lapis[2].nilai).toBe("Rp88.305");
    expect(hasil.lapis[2].baris.map((b) => b.label)).toEqual(["Susut gudang"]);
    // Rumus susut berbasis WAKTU, bukan kesegaran.
    expect(hasil.lapis[2].baris[0].rumus).toContain("hari simpan");
  });

  it("lapis 4 = kesegaran + penalti keamanan (tanpa susut)", () => {
    expect(hasil.lapis[3].judul).toBe("Tambahan karena risiko");
    expect(hasil.lapis[3].baris.map((b) => b.label)).toEqual([
      "Risiko kesegaran",
      "Penalti keamanan",
    ]);
  });

  it("total = biaya terkirim, dan ketiga lapis menjumlah ke sana", () => {
    expect(hasil.total?.nilai).toBe("Rp7.606.652");
    const jumlah =
      7358754 + 9592.92 + 150000 + 88305.05 + 0 + 0;
    expect(Math.round(jumlah)).toBe(7606652);
  });

  it("komponen tak tercatat = null, bukan Rp0", () => {
    const kosong = tigaLapisBiaya({ purchase_total: "1000" }, 10);
    expect(kosong.lapis[1].nilai).toBeNull();
    expect(kosong.lapis[2].nilai).toBeNull();
    expect(kosong.adaData).toBe(true);
  });

  it("tanpa payload biaya sama sekali → tidak ada lapis yang dikarang", () => {
    const kosong = tigaLapisBiaya(null, 600);
    expect(kosong.lapis).toEqual([]);
    expect(kosong.adaData).toBe(false);
  });

  it("quantity 0 tidak menghasilkan rumus 'dibagi 0 kg'", () => {
    const nol = tigaLapisBiaya(COMMERCIAL, 0);
    expect(nol.lapis[0].rumus).toBeNull();
  });
});

describe("perbandinganHarga: acuan kota tujuan vs harga terkirim", () => {
  it("lebih murah saat acuan > terkirim, positif", () => {
    const p = perbandinganHarga({ price_per_kg: 13657.02 }, COMMERCIAL);
    expect(p?.arah).toBe("lebih murah");
    expect(p?.perKg).toBe("Rp979");
    expect(p?.persen).toBe("7,2%");
    expect(p?.acuanPerKg).toBe("Rp13.657");
    expect(p?.kalimat).toContain("Lebih murah");
  });

  it("lebih mahal saat acuan < terkirim", () => {
    const p = perbandinganHarga({ price_per_kg: 10000 }, COMMERCIAL);
    expect(p?.arah).toBe("lebih mahal");
    expect(p?.kalimat).toContain("Lebih mahal");
  });

  it("tanpa harga acuan tidak ada perbandingan (bukan 0%)", () => {
    expect(perbandinganHarga(null, COMMERCIAL)).toBeNull();
    expect(perbandinganHarga({ price_per_kg: null }, COMMERCIAL)).toBeNull();
  });
});

describe("tahapPo: status PO sebagai langkah", () => {
  it("belum terbit: tiga titik menunggu, tanpa nomor", () => {
    const t = tahapPo(null);
    expect(t.terbit).toBe(false);
    expect(t.nomor).toBeNull();
    expect(t.steps.every((s) => s.state === "menunggu")).toBe(true);
  });

  it("draft: terbit, menunggu review", () => {
    const t = tahapPo({ po_number: "MC-B5B391FE89E1", status: "draft" });
    expect(t.nomor).toBe("MC-B5B391FE89E1");
    expect(t.steps.map((s) => s.state)).toEqual(["kini", "menunggu", "menunggu"]);
  });

  it("submitted: sudah terkirim, menunggu SAP", () => {
    const t = tahapPo({ po_number: "MC-B5B391FE89E1", status: "submitted" });
    expect(t.steps.map((s) => s.state)).toEqual(["selesai", "kini", "menunggu"]);
  });

  it("confirmed: seluruh langkah selesai", () => {
    const t = tahapPo({ po_number: "MC-B5B391FE89E1", status: "confirmed" });
    expect(t.steps.every((s) => s.state === "selesai")).toBe(true);
  });
});
