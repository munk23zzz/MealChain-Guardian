// Kontrak render kartu "Riwayat penerimaan" di halaman Pemasok (Dok 05 §8.5).
//
// Yang dikunci di markup:
//   1. tiga angka (dipesan · diterima · nilai diterima) tampil di kepala kartu;
//   2. kg dipesan dan kg diterima DUA baris di satu sel — tidak dikurangkan;
//   3. nilai tanpa acuan harga tertulis "tidak tercatat", dan tidak ada "Rp 0";
//   4. setiap putusan membawa label teks (bukan warna saja);
//   5. asal harga satuan (§8.3) tertulis di bawah nilai;
//   6. riwayat kosong menulis kalimat, bukan tabel kosong.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplierReceipts from "../components/SupplierReceipts";

const disetujui = {
  id: "r1",
  batch_id: "0ff8f2b1-f217-5e1e-bb06-63912491a1cb",
  batch_ref: "0ff8f2b1",
  supplier_id: "s1",
  supplier: "CV Hortikultura Subang Lestari",
  commodity: "wortel",
  status: "disetujui",
  recorded_at: "2026-10-27T05:00:00+00:00",
  checked_count: 4,
  ordered_kg: 420,
  received_kg: 420,
  batch_quantity_kg: 420,
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
  batch_quantity_kg: 540,
  accepted_value_idr: null,
  estimated_value_idr: 6210000,
  recorded_at: "2026-10-28T03:10:00+00:00",
};

const ditolak = {
  ...disetujui,
  id: "r3",
  batch_ref: "13950f6a",
  supplier: "UD H. Ujang Serang",
  commodity: "ayam",
  status: "ditolak",
  ordered_kg: 300,
  received_kg: null,
  batch_quantity_kg: 300,
  accepted_value_idr: null,
  estimated_value_idr: 5400000,
  unit_price_idr: 15000,
  po_number: "MC-08E732F618E0",
  review_note: "Kemasan bocor dan suhu di atas batas saat tiba.",
};

const ringkasan = {
  total: 3,
  menunggu: 1,
  disetujui: 1,
  ditolak: 1,
  kg_dipesan: 1260,
  kg_diterima: 420,
  nilai_diterima_idr: 4830000,
  nilai_menunggu_idr: 6210000,
  tanpa_harga: 1,
  supplier: 2,
};

function render(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <SupplierReceipts riwayat={{ items: [disetujui, menunggu, ditolak], ringkasan }} {...props} />
  );
}

describe("kartu Riwayat penerimaan", () => {
  it("menampilkan tiga angka di kepala kartu (§8.2)", () => {
    const html = render();
    expect(html).toContain("Dipesan 1.260 kg");
    expect(html).toContain("Diterima 420 kg");
    expect(html).toContain("Nilai diterima Rp 4.830.000");
  });

  it("memisahkan kg dipesan dan kg diterima, tanpa mengurangkan di klien", () => {
    const html = render();
    expect(html).toContain("540 kg");
    expect(html).toContain("diterima —");
    expect(html).toContain("840 kg"); // kalimat susut, dari ringkasan server
  });

  it("menyebut pemasok, komoditas, dan batch tiap baris", () => {
    const html = render();
    expect(html).toContain("CV Hortikultura Subang Lestari");
    expect(html).toContain("wortel · batch 0ff8f2b1");
    expect(html).toContain("UD H. Ujang Serang");
  });

  it("putusan membawa label teks, bukan warna saja", () => {
    const html = render();
    expect(html).toContain("Diterima");
    expect(html).toContain("Menunggu keputusan");
    expect(html).toContain("Ditolak");
    expect(html).toContain('data-tone="ok"');
    expect(html).toContain('data-tone="warn"');
    expect(html).toContain('data-tone="danger"');
  });

  it("nilai perkiraan diberi katanya; tanpa harga tertulis tidak tercatat", () => {
    const html = render();
    expect(html).toContain("Rp 6.210.000 perkiraan");
    // Baris yang DITOLAK tidak menampilkan rupiah: barangnya tidak dibukukan.
    expect(html).not.toContain("Rp 5.400.000");
    expect(html).not.toContain("Rp 0");
  });

  it("asal harga satuan ditulis di bawah nilai (§8.3)", () => {
    const html = render();
    expect(html).toContain("420 kg × Rp 11.500 per kg dari PO MC-08E732F618E0");
  });

  it("baris tanpa acuan harga: 'tidak tercatat' dan tanpa kalimat asal harga", () => {
    const html = renderToStaticMarkup(
      <SupplierReceipts
        riwayat={{
          items: [
            {
              ...menunggu,
              id: "rx",
              unit_price_idr: null,
              po_number: null,
              estimated_value_idr: null,
            },
          ],
          ringkasan: { ...ringkasan, total: 1, menunggu: 1, disetujui: 0, ditolak: 0 },
        }}
      />
    );
    expect(html).toContain("tidak tercatat");
    expect(html).not.toContain("per kg dari PO");
  });

  it("alasan penolakan terbaca di barisnya", () => {
    expect(render()).toContain("Kemasan bocor dan suhu di atas batas saat tiba.");
  });

  it("penyaring menyebut jumlah tiap putusan", () => {
    const html = render();
    expect(html).toContain("Semua");
    expect(html).toContain("3 catatan");
  });

  it("riwayat kosong menulis kalimat, bukan tabel kosong", () => {
    const html = renderToStaticMarkup(
      <SupplierReceipts
        riwayat={{
          items: [],
          ringkasan: { ...ringkasan, total: 0, menunggu: 0, disetujui: 0, ditolak: 0 },
        }}
      />
    );
    expect(html).toContain("Belum ada penerimaan tercatat");
    expect(html).not.toContain("<table");
    expect(html).not.toContain("Dipesan");
  });

  it("belum dimuat / gagal: kalimat jujur, tanpa angka", () => {
    const html = renderToStaticMarkup(<SupplierReceipts riwayat={null} loading />);
    expect(html).toContain("Memuat riwayat penerimaan");
    const gagal = renderToStaticMarkup(
      <SupplierReceipts riwayat={null} error="HTTP 500: /receipts/riwayat" />
    );
    expect(gagal).toContain("tidak bisa dibaca");
    expect(gagal).not.toContain("Dipesan");
  });
});
