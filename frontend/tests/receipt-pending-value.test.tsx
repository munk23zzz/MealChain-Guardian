// Dok 05 §8.2–§8.3 di kartu "Menunggu persetujuan" (halaman Keamanan Pangan).
//
// Kenapa berkas ini ada: kepala SPPG memutuskan setuju/tolak penerimaan, dan
// yang ia pertimbangkan bukan hanya kg tetapi NILAI rupiah yang akan masuk
// stok. Sebelum perubahan ini baris antrean hanya menyebut komoditas, kg,
// lokasi, jumlah titik, dan waktu — nilai sama sekali tidak terbaca.
//
// Yang dikunci di sini:
//   1. Bentuk payload `/receipts/menunggu` (klien) membaca `estimated_value_idr`,
//      `unit_price_idr`, `po_number`, `batch_quantity_kg` — bukan menghitung.
//   2. Tanpa ikatan PO: "tidak tercatat", BUKAN Rp 0.
//   3. Kartu benar-benar memakai helper itu (tes wiring sumber), dan nilai
//      pembukuan `accepted_value_idr` tidak pernah dibaca untuk baris menunggu.
//   4. Waktu observasi bukti suhu tidak lagi mencetak ISO mentah.

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { receiptFigures, valueOrigin } from "../lib/goods-receipt";

/** Satu baris `/receipts/menunggu` setelah server mengirim konteks nilai. */
const barisAntrean = {
  id: "r1",
  batch_id: "b1",
  commodity: "wortel",
  quantity_kg: 420,
  location: "Jakarta",
  safety_status: "pass",
  checked_count: 3,
  recorded_by_name: "Petugas Dapur",
  recorded_at: "2026-10-29T00:55:00+00:00",
  batch_quantity_kg: 420,
  po_number: "4500000007",
  unit_price_idr: 23600,
  estimated_value_idr: 9912000,
  accepted_value_idr: null,
};

const sumber = readFileSync(
  join(__dirname, "..", "components", "FoodSafetyBoard.tsx"),
  "utf8"
);

describe("Dok 05 §8.2 — nilai pada baris antrean persetujuan", () => {
  it("baris menunggu: nilai = perkiraan server, ditandai perkiraan", () => {
    const angka = receiptFigures(barisAntrean);
    expect(angka.nilaiIdr).toBe(9912000);
    expect(angka.nilaiSementara).toBe(true);
    expect(angka.statusNilai).toBe("perkiraan");
    // Belum disetujui = belum ada kg yang masuk stok.
    expect(angka.masukStokKg).toBeNull();
  });

  it("tanpa ikatan PO: tidak tercatat, bukan Rp 0", () => {
    const angka = receiptFigures({
      ...barisAntrean,
      po_number: null,
      unit_price_idr: null,
      estimated_value_idr: null,
    });
    expect(angka.nilaiIdr).toBeNull();
    expect(angka.statusNilai).toBe("tidak_tercatat");
    expect(valueOrigin({ ...barisAntrean, unit_price_idr: null })).toBeNull();
  });

  it("asal harga menyebut kg, harga per kg, dan nomor PO", () => {
    const asal = valueOrigin(barisAntrean) ?? "";
    expect(asal).toContain("420 kg");
    expect(asal).toContain("Rp 23.600");
    expect(asal).toContain("PO 4500000007");
  });
});

describe("Dok 05 §8.2 — kartu Keamanan Pangan memakai helper itu", () => {
  it("baris antrean merender label + angka + asal harga", () => {
    expect(sumber).toContain("NilaiAntrean");
    expect(sumber).toContain('data-testid="receipt-pending-value"');
    expect(sumber).toContain("Nilai bila disetujui");
    expect(sumber).toContain("receiptFigures(row)");
    expect(sumber).toContain("valueOrigin(row)");
    // Nilai pembukuan TIDAK dibaca untuk baris yang belum diputuskan: hanya
    // helper server (`estimated_value_idr`) yang dipakai.
    expect(sumber).not.toContain(".accepted_value_idr");
  });

  it("waktu observasi bukti suhu diformat, bukan ISO mentah", () => {
    expect(sumber).toContain("formatMomentWib(buktiTerpilih.observedAt)");
  });
});
