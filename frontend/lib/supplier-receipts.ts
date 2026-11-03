// Riwayat penerimaan barang per pemasok (Dok 05 §8.5) — lapisan murni.
//
// Kenapa berkas ini ada: halaman Pemasok hanya punya daftar pemasok, papan
// kiriman, dan register eksklusi. Pertanyaan audit "berapa yang benar-benar
// diterima dari pemasok ini, dan berapa nilainya" tidak bisa dijawab di sana,
// padahal catatannya sudah tersimpan di `batch_receipts`. Endpoint
// `GET /receipts/riwayat` mengirim barisnya; berkas ini memilih ANGKA MANA yang
// ditampilkan dan menulis kalimatnya — tanpa satu pun perkalian rupiah di
// peramban (Dok 05 §8.2: nilai selalu dari server).
//
// Aturan yang dipegang:
// - `diterima_kg` kosong (null) selama catatan belum disetujui: barang yang
//   belum masuk stok tidak boleh terbaca sebagai sudah diterima;
// - nilai `null` ditulis "tidak tercatat" — BUKAN Rp 0, karena Rp 0 berarti
//   barang gratis, sedangkan "tidak tercatat" berarti acuan harganya belum ada;
// - angka perkiraan (baris yang masih menunggu keputusan) selalu diberi kata
//   "perkiraan" supaya tidak tertukar dengan nilai pembukuan.

import { formatRupiah } from "./decision-economics";
import { formatDateTime } from "./datetime";
import { valueOrigin } from "./goods-receipt";

/** Putusan penerimaan yang dikenal layar. Nilai lain = data rusak → "menunggu". */
export const RECEIPT_VERDICTS = ["menunggu", "disetujui", "ditolak"] as const;
export type ReceiptVerdict = (typeof RECEIPT_VERDICTS)[number];

export type ReceiptTone = "ok" | "warn" | "danger" | "plain";

export function receiptVerdict(status: unknown): ReceiptVerdict {
  const teks = String(status ?? "");
  return (RECEIPT_VERDICTS as readonly string[]).includes(teks)
    ? (teks as ReceiptVerdict)
    : "menunggu";
}

export function receiptStatusLabel(status: unknown): string {
  switch (receiptVerdict(status)) {
    case "disetujui":
      return "Diterima";
    case "ditolak":
      return "Ditolak";
    default:
      return "Menunggu keputusan";
  }
}

/** Nada pil putusan. Bukan warna-saja: labelnya selalu ikut ditulis. */
export function receiptTone(status: unknown): ReceiptTone {
  switch (receiptVerdict(status)) {
    case "disetujui":
      return "ok";
    case "ditolak":
      return "danger";
    default:
      return "warn";
  }
}

export type ReceiptValueStatus =
  | "tersimpan"
  | "perkiraan"
  | "tidak_diterima"
  | "tidak_tercatat";

export type ReceiptHistoryRow = {
  id: string;
  batchId: string;
  batchRef: string;
  at: string;
  supplier: string;
  supplierId: string;
  commodity: string;
  status: ReceiptVerdict;
  statusLabel: string;
  tone: ReceiptTone;
  /** Kuantitas batch yang dipesan pemasok (kg). */
  orderedKg: number | null;
  /** Kg yang BENAR-BENAR masuk stok; null selama belum disetujui. */
  receivedKg: number | null;
  /** Label siap tulis: "420 kg" atau "—". */
  orderedLabel: string;
  receivedLabel: string;
  valueIdr: number | null;
  valueStatus: ReceiptValueStatus;
  /** Nilai siap tulis + kata "perkiraan" bila belum dibukukan. */
  valueLabel: string;
  /** Asal harga satuan (Dok 05 §8.3); null bila server tidak mengirim harga. */
  priceOrigin: string | null;
  /** "4 dari 5 titik" — bukti yang tersimpan, bukan skor karangan. */
  checkedLabel: string;
  note: string | null;
};

function angka(nilai: unknown): number | null {
  if (nilai === null || nilai === undefined || nilai === "") return null;
  const n = Number(nilai);
  return Number.isFinite(n) ? n : null;
}

function kgLabel(nilai: number | null): string {
  if (nilai === null) return "—";
  const formatter = new Intl.NumberFormat("id-ID", {
    maximumFractionDigits: 2,
  });
  return `${formatter.format(nilai)} kg`;
}

/**
 * Nilai yang ditampilkan satu baris, dipilih dari payload server.
 *
 * Urutannya penting: nilai pembukuan (`accepted_value_idr`) menang atas
 * perkiraan (`estimated_value_idr`). Keduanya dikirim server, jadi klien tidak
 * pernah mengalikan kg × harga sendiri.
 */
export function receiptValue(row: Record<string, any> | null | undefined): {
  nilai: number | null;
  status: ReceiptValueStatus;
  label: string;
} {
  const putusan = receiptVerdict(row?.status);
  const tersimpan = putusan === "disetujui" ? angka(row?.accepted_value_idr) : null;
  if (tersimpan !== null) {
    return { nilai: tersimpan, status: "tersimpan", label: formatRupiah(tersimpan) };
  }
  // Barang yang DITOLAK tidak pernah dibukukan: menampilkan perkiraan rupiahnya
  // di sini terbaca seperti uang yang keluar untuk barang yang tidak diterima.
  if (putusan === "ditolak") {
    return { nilai: null, status: "tidak_diterima", label: "—" };
  }
  const perkiraan = angka(row?.estimated_value_idr);
  if (perkiraan !== null) {
    return {
      nilai: perkiraan,
      status: "perkiraan",
      label: `${formatRupiah(perkiraan)} perkiraan`,
    };
  }
  return { nilai: null, status: "tidak_tercatat", label: formatRupiah(null) };
}

/** Baris siap render dari amplop `GET /receipts/riwayat`. */
export function receiptHistory(payload: unknown): ReceiptHistoryRow[] {
  const items = (payload as { items?: unknown } | null)?.items;
  if (!Array.isArray(items)) return [];
  return items.map((mentah) => {
    const row = (mentah ?? {}) as Record<string, any>;
    const nilai = receiptValue(row);
    const orderedKg = angka(row.ordered_kg);
    const receivedKg = angka(row.received_kg);
    const dicek = Number(row.checked_count);
    const totalTitik = 5; // RECEIVING_CHECKS di lib/goods-receipt.ts
    return {
      id: String(row.id ?? ""),
      batchId: String(row.batch_id ?? ""),
      batchRef: String(row.batch_ref ?? String(row.batch_id ?? "").slice(0, 8)),
      at: formatDateTime(row.recorded_at ?? null),
      supplier: String(row.supplier ?? "Pemasok tidak tercatat"),
      supplierId: String(row.supplier_id ?? ""),
      commodity: String(row.commodity ?? "—"),
      status: receiptVerdict(row.status),
      statusLabel: receiptStatusLabel(row.status),
      tone: receiptTone(row.status),
      orderedKg,
      receivedKg,
      orderedLabel: kgLabel(orderedKg),
      receivedLabel: kgLabel(receivedKg),
      valueIdr: nilai.nilai,
      valueStatus: nilai.status,
      valueLabel: nilai.label,
      priceOrigin:
        nilai.status === "tidak_diterima"
          ? null
          : valueOrigin({
              // `valueOrigin()` (lib/goods-receipt.ts) membaca `batch_quantity_kg`;
              // endpoint riwayat mengirim kunci itu juga, tetapi baris dari sumber
              // lain hanya membawa `ordered_kg` — disamakan di sini supaya kalimat
              // asal harga tidak pernah berbunyi "— × Rp …".
              ...row,
              batch_quantity_kg: row.batch_quantity_kg ?? row.ordered_kg,
            }),
      checkedLabel: Number.isFinite(dicek)
        ? `${dicek} dari ${totalTitik} titik`
        : `— dari ${totalTitik} titik`,
      note: row.review_note ? String(row.review_note) : null,
    };
  });
}

export type ReceiptTotals = {
  total: number;
  menunggu: number;
  disetujui: number;
  ditolak: number;
  kgDipesan: number;
  kgDiterima: number;
  nilaiDiterimaIdr: number;
  nilaiMenungguIdr: number;
  tanpaHarga: number;
  supplier: number;
};

const TOTALS_KOSONG: ReceiptTotals = {
  total: 0,
  menunggu: 0,
  disetujui: 0,
  ditolak: 0,
  kgDipesan: 0,
  kgDiterima: 0,
  nilaiDiterimaIdr: 0,
  nilaiMenungguIdr: 0,
  tanpaHarga: 0,
  supplier: 0,
};

/**
 * Ringkasan dari `ringkasan` server. Angka ini dihitung server dari SELURUH
 * baris dalam cakupan, jadi tidak boleh dihitung ulang dari `items` (yang bisa
 * sudah dipotong `limit`).
 */
export function receiptTotals(payload: unknown): ReceiptTotals {
  const r = (payload as { ringkasan?: Record<string, unknown> } | null)?.ringkasan;
  if (!r) return { ...TOTALS_KOSONG };
  const ambil = (kunci: string) => {
    const n = Number(r[kunci]);
    return Number.isFinite(n) ? n : 0;
  };
  return {
    total: ambil("total"),
    menunggu: ambil("menunggu"),
    disetujui: ambil("disetujui"),
    ditolak: ambil("ditolak"),
    kgDipesan: ambil("kg_dipesan"),
    kgDiterima: ambil("kg_diterima"),
    nilaiDiterimaIdr: ambil("nilai_diterima_idr"),
    nilaiMenungguIdr: ambil("nilai_menunggu_idr"),
    tanpaHarga: ambil("tanpa_harga"),
    supplier: ambil("supplier"),
  };
}

/**
 * Tiga angka berdampingan (Dok 05 §8.2): "Dipesan 500 kg · Diterima 480 kg ·
 * Nilai diterima Rp 13.844.198".
 *
 * `null` bila tidak ada satu baris pun — kepala yang berbunyi "Dipesan 0 kg"
 * untuk riwayat kosong adalah angka yang tidak ada.
 */
export function receiptHeadline(totals: ReceiptTotals): string | null {
  if (!totals.total) return null;
  const diterima =
    totals.disetujui > 0 ? kgLabel(totals.kgDiterima) : "belum ada";
  const nilai =
    totals.disetujui > 0 ? formatRupiah(totals.nilaiDiterimaIdr) : "belum ada";
  return `Dipesan ${kgLabel(totals.kgDipesan)} · Diterima ${diterima} · Nilai diterima ${nilai}`;
}

/** Kalimat susut: hanya ditulis bila memang ada kg yang tidak masuk stok. */
export function receiptShortfall(totals: ReceiptTotals): string | null {
  if (!totals.total || totals.disetujui === 0) return null;
  const selisih = Number((totals.kgDipesan - totals.kgDiterima).toFixed(2));
  if (selisih <= 0) return null;
  return `${kgLabel(selisih)} dari yang dipesan belum masuk stok (ditolak atau masih menunggu).`;
}

/** Penyaring status untuk tabel: "semua" + tiga putusan. */
export function receiptFilterLabel(status: ReceiptVerdict | "semua"): string {
  if (status === "semua") return "Semua";
  return receiptStatusLabel(status);
}
