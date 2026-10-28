// Ekspor baca-saja modul "Keamanan Pangan" (dokumen `07-safety-evidence.md`
// §4.2 butir 6).
//
// Kenapa modul sendiri:
//  - halaman ini dulu tidak punya jalan unduh sama sekali, padahal seluruh nilai
//    yang dibutuhkan audit sudah ada di layar;
//  - isi berkas harus SAMA dengan yang tercetak (`SafetyRow` sudah berisi label
//    Indonesia dan "—" untuk nilai tak terbaca), bukan enum mentah dari API —
//    supaya tidak ada dua terjemahan untuk satu keadaan;
//  - ekspor tidak boleh memanggil backend baru dan tidak boleh menghitung ulang
//    aturan safety: ringkasan & keputusan diambil dari objek yang sudah dipakai
//    kartu di layar.
//
// Satu penyimpangan yang disengaja pada CSV: kolom `lokasi` memakai nama lokasi
// LENGKAP dari server. Tabel di layar menyingkatnya menjadi kode wilayah (CJR)
// supaya kolom muat; di berkas ekspor singkatan itu justru menghilangkan
// informasi, sedangkan nilainya sama.

import { rowNextSteps } from "./safety-gate";
import { tableToCsv } from "./export";
import type { SafetyDecisionSummary, SafetyRow, SafetySummary } from "./food-safety";
import { formatKg } from "./overview-format";

const DASH = "—";

/** Kepala kolom CSV — satu baris, sama dengan kolom tabel status per batch. */
export const BATCH_CSV_HEADER = [
  "lokasi",
  "komoditas",
  "jumlah",
  "status keamanan",
  "karantina",
  "kesegaran",
  "layak sampai",
  "sisa masa",
  "langkah",
] as const;

function jumlah(row: SafetyRow): string {
  return row.kg === null ? DASH : formatKg(row.kg);
}

/** Langkah verifikasi berikutnya, kalimat yang SAMA dengan sel tabel. */
function langkah(row: SafetyRow): string {
  const next = rowNextSteps(row.safetyStatus, row.quarantine);
  return [next.safety, next.karantina ? `Karantina: ${next.karantina}` : null]
    .filter(Boolean)
    .join(" ");
}

/** Baris ekspor = nilai yang tercetak, ditambah `id` supaya bisa ditelusuri. */
export function safetyExportRows(rows: readonly SafetyRow[]) {
  return rows.map((row) => ({
    id: row.id,
    lokasi: row.location,
    komoditas: row.commodity,
    jumlah: jumlah(row),
    status_keamanan: row.statusLabel,
    karantina: row.quarantineLabel || DASH,
    kesegaran: row.freshness,
    layak_sampai: row.usableUntil,
    sisa_masa: row.hoursLabel,
    langkah: langkah(row) || null,
  }));
}

export function batchesToCsv(rows: readonly SafetyRow[]): string {
  return tableToCsv(
    BATCH_CSV_HEADER,
    rows.map((row) => [
      row.location,
      row.commodity,
      jumlah(row),
      row.statusLabel,
      row.quarantineLabel || DASH,
      row.freshness,
      row.usableUntil,
      row.hoursLabel,
      langkah(row) || DASH,
    ])
  );
}

/**
 * Satu berkas JSON untuk audit: batch yang tampil, ringkasan yang tampil, dan
 * keputusan keamanan yang tampil. Tanpa cap waktu — berkas dibangun murni dari
 * data layar supaya isinya tidak berubah hanya karena jam dibaca ulang.
 */
export function safetyExportJson(input: {
  rows: readonly SafetyRow[];
  summary: SafetySummary;
  decisions: SafetyDecisionSummary;
}): string {
  const { rows, summary, decisions } = input;
  return JSON.stringify(
    {
      modul: "Keamanan Pangan",
      batch: safetyExportRows(rows),
      ringkasan: {
        batch_diperiksa: summary.total,
        aman: summary.safe,
        gagal: summary.failed,
        perlu_verifikasi: summary.needsVerification,
        belum_diuji: summary.unchecked,
        ditahan: summary.quarantined,
        berat_gagal: summary.failedKg === null ? null : formatKg(summary.failedKg),
        berat_ditahan: summary.quarantinedKg === null ? null : formatKg(summary.quarantinedKg),
      },
      keputusan_keamanan: decisions.rows.map((row) => ({
        id: row.id,
        komoditas: row.commodity ?? DASH,
        status: row.statusLabel,
        jumlah: row.kg === null ? DASH : formatKg(row.kg),
        masih_berlaku: row.valid,
        dibuat: row.createdLabel,
      })),
    },
    null,
    2
  );
}

/** Nama berkas — satu tempat, supaya tombol dan umpan balik tidak berbeda. */
export function safetyBatchFileName(ext: "csv" | "json"): string {
  return `keamanan-pangan-batch.${ext}`;
}
