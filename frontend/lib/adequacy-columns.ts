// Model kolom BAR VERTIKAL untuk kartu "Kecukupan pasokan" di Overview
// (28 Okt 2026 — permintaan pemilik: "bar chart berdiri, ukuran tidak terlalu
// besar, redesign lebih soft ui").
//
// Kenapa modul murni sendiri, bukan langsung di komponen:
// - angka, urutan, dan tinggi batang harus bisa diuji tanpa DOM;
// - bentuk kolom dipakai DUA isi yang berbeda (empat komoditas untuk satu SPPG,
//   dan lokasi-lokasi untuk monitor nasional), jadi tinggi batang & porsi segmen
//   dihitung di sini — bukan di dalam JSX yang bercabang.
//
// Aturan kejujuran yang diwarisi dari grafik lama dan TIDAK boleh longgar:
// - segmen = batch aman/layak (bukan `supply_kg` catatan pasokan);
// - baris tanpa kebutuhan terukur tetap tampil dengan angka "—" dan tanpa
//   segmen, di urutan paling belakang — bukan 0% yang menakutkan;
// - tinggi 0 hanya sah bila kg-nya memang 0.

import {
  metricFor,
  gapFor,
  formatCoverage,
  formatSignedKg,
  sortAdequacyRows,
  type AdequacyLens,
  type CommodityAdequacy,
  type SupplyTone,
} from "./supply-adequacy";
import {
  buildLocationBalanceRows,
  locationStatusLabel,
  sortLocationBalanceRows,
  type LocationBalanceRow,
} from "./location-balance";
import { formatKg, type BalanceMapLocation } from "./overview-format";

export type ColumnSegmentTone =
  | "fresh"
  | "near"
  | "unsafe"
  | "unverified"
  | "pasokan";

export type ColumnSegment = {
  tone: ColumnSegmentTone;
  kg: number;
};

export type AdequacyColumn = {
  key: string;
  /** Nama komoditas atau nama lokasi. */
  label: string;
  /** Baris kecil di bawah nama: stok layak / keadaan lokasi. */
  note: string | null;
  /** Kebutuhan (kg) — garis penanda; null = belum tercatat. */
  demandKg: number | null;
  /** Segmen dari BAWAH ke atas. */
  segments: ColumnSegment[];
  coverage: string;
  coverageLabel: string;
  /** Kg yang DIPAKAI HITUNG pada lensa aktif (layak, atau segar). */
  numeratorKg: number;
  /** Selisih bertanda, mis. "−139 kg". */
  gap: string;
  gapTone: SupplyTone;
  /** Keterangan kebutuhan untuk tooltip/aria; null bila tidak terukur. */
  demandLabel: string | null;
  /** Satu kalimat lengkap untuk pembaca layar. */
  aria: string;
  /** Nada batang tunggal (mode lokasi); null untuk mode komoditas. */
  barTone: SupplyTone | null;
};

export type ColumnsView = {
  columns: AdequacyColumn[];
};

/** Jumlah kg yang benar-benar digambar pada satu kolom. */
export function columnTotalKg(column: AdequacyColumn): number {
  return column.segments.reduce((jumlah, seg) => jumlah + seg.kg, 0);
}

/**
 * Tinggi batang = yang dihitung lensa (layak / segar) dibagi kebutuhan kolom itu
 * sendiri (0–100). SATU arti per batang: tinggi == angka besar di atasnya.
 *
 * Riwayat: versi sebelumnya menggambar SELURUH stok (termasuk yang tidak layak)
 * sehingga tinggi batang dan angka cakupan bisa berbeda, lalu perbedaannya
 * dijelaskan garis putus-putus kedua di dalam batang. Pemilik menilai itu sulit
 * dipahami (28 Okt 2026) — dua arti dalam satu batang + dua garis putus-putus.
 * Sekarang komposisi kualitas hanya hidup di tooltip/aria, bukan di geometri.
 *
 * Tanpa kebutuhan terukur tidak ada pembanding, jadi tidak ada batang (0) —
 * bukan 100% yang mengarang "cukup".
 */
export function columnFillPct(column: AdequacyColumn): number {
  const kebutuhan = Number(column.demandKg);
  if (!Number.isFinite(kebutuhan) || kebutuhan <= 0) return 0;
  if (column.numeratorKg <= 0) return 0;
  return Math.min(100, (column.numeratorKg / kebutuhan) * 100);
}

/**
 * Bagian kotak yang MASIH KOSONG = kekurangan (0–100). Digambar sebagai jalur
 * pucat di atas batang, supaya "berapa yang belum ada" terlihat sebagai ruang,
 * bukan sekadar kotak kosong tanpa arti.
 */
export function columnMissingPct(column: AdequacyColumn): number {
  if (column.demandKg === null) return 0;
  return Math.max(0, 100 - columnFillPct(column));
}

/** true bila pasokan melebihi kebutuhan (batang mentok 100%, angkanya bisa >100%). */
export function columnOverflow(column: AdequacyColumn): boolean {
  const kebutuhan = Number(column.demandKg);
  if (!Number.isFinite(kebutuhan) || kebutuhan <= 0) return false;
  return column.numeratorKg > kebutuhan;
}

/**
 * Empat komoditas untuk satu lokasi. `lens` hanya mengubah angka yang DIBACA
 * (cakupan/selisih/label) dan urutannya — segmennya tetap batch yang sama,
 * sama seperti grafik lamanya (aturannya diuji di supply-adequacy.test.ts).
 */
export function commodityColumns(
  rows: readonly CommodityAdequacy[],
  lens: AdequacyLens
): ColumnsView {
  const urut = sortAdequacyRows(rows, lens);
  const labelLens = lens === "freshness" ? "segar" : "cakupan";
  const columns: AdequacyColumn[] = urut.map((row) => {
    const nilai = metricFor(row, lens);
    const selisih = gapFor(row, lens);
    const segments: ColumnSegment[] = [];
    if (row.buckets.freshKg > 0) segments.push({ tone: "fresh", kg: row.buckets.freshKg });
    if (row.buckets.nearKg > 0) segments.push({ tone: "near", kg: row.buckets.nearKg });
    if (row.buckets.unsafeKg > 0) segments.push({ tone: "unsafe", kg: row.buckets.unsafeKg });
    if (row.buckets.unverifiedKg > 0)
      segments.push({ tone: "unverified", kg: row.buckets.unverifiedKg });

    // Baris tanpa kebutuhan DAN tanpa batch tidak boleh menulis "0 kg layak":
    // itu terbaca seperti stok habis, padahal artinya belum ada catatan.
    const kosong = row.demandKg === null && row.buckets.usableKg === 0;
    const note = kosong
      ? "belum tercatat"
      : lens === "freshness"
        ? row.buckets.freshKg === row.buckets.usableKg
          ? `${formatKg(row.buckets.freshKg)} segar`
          : `${formatKg(row.buckets.freshKg)} segar · ${formatKg(row.buckets.usableKg)} layak`
        : `${formatKg(row.buckets.usableKg)} layak`;

    const demandLabel =
      row.demandKg === null ? null : `kebutuhan ${formatKg(row.demandKg)}`;

    return {
      key: row.commodity,
      label: row.commodity,
      note,
      demandKg: row.demandKg,
      segments,
      coverage: formatCoverage(nilai),
      coverageLabel: labelLens,
      numeratorKg: lens === "freshness" ? row.buckets.freshKg : row.buckets.usableKg,
      gap: formatSignedKg(selisih),
      gapTone: lens === "freshness" ? row.freshTone : row.tone,
      demandLabel,
      // Rincian kualitas tidak lagi digambar sebagai segmen (geometri batang
      // dibuat satu arti), jadi komposisinya wajib tetap terbaca di sini.
      aria: [
        `${row.commodity}: ${
          lens === "freshness"
            ? `stok segar ${formatKg(row.buckets.freshKg)} (layak ${formatKg(row.buckets.usableKg)})`
            : `stok layak ${formatKg(row.buckets.usableKg)}`
        } dari ${demandLabel ?? "kebutuhan yang belum tercatat"}`,
        `${labelLens} ${formatCoverage(nilai)}`,
        `selisih ${formatSignedKg(selisih)}`,
        row.buckets.unsafeKg > 0
          ? `${formatKg(row.buckets.unsafeKg)} tidak layak`
          : null,
        row.buckets.unverifiedKg > 0
          ? `${formatKg(row.buckets.unverifiedKg)} belum terverifikasi`
          : null,
        row.buckets.nearKg > 0
          ? `${formatKg(row.buckets.nearKg)} sisa masa layak ≤48 jam`
          : null,
      ]
        .filter(Boolean)
        .join(". "),
      barTone: null,
    };
  });
  return { columns };
}

/**
 * Satu komoditas di banyak lokasi (monitor nasional). Batang = pasokan
 * tercatat, garis = kebutuhan; warna batang mengikuti nada cakupan supaya
 * pembaca melihat "siapa yang kurang" tanpa membaca angka.
 */
export function locationColumns(
  locations: readonly BalanceMapLocation[] | null | undefined
): ColumnsView {
  const rows: LocationBalanceRow[] = sortLocationBalanceRows(
    buildLocationBalanceRows(locations)
  );
  const columns: AdequacyColumn[] = rows.map((row) => {
    const segments: ColumnSegment[] =
      row.supplyKg !== null && row.supplyKg > 0
        ? [{ tone: "pasokan", kg: row.supplyKg }]
        : [];
    const demandLabel =
      row.demandKg === null ? null : `kebutuhan ${formatKg(row.demandKg)}`;
    return {
      key: row.location,
      label: row.location,
      note: locationStatusLabel(row),
      demandKg: row.demandKg,
      segments,
      coverage: formatCoverage(row.coverage),
      coverageLabel: "cakupan",
      numeratorKg: row.supplyKg ?? 0,
      gap: formatSignedKg(row.gapKg),
      gapTone: row.tone,
      demandLabel,
      aria: [
        `${row.location}: ${locationStatusLabel(row)}`,
        `pasokan ${row.supplyKg === null ? "belum tercatat" : formatKg(row.supplyKg)}`,
        `kebutuhan ${demandLabel ?? "belum tercatat"}`,
        `${formatCoverage(row.coverage)} cakupan`,
      ].join(". "),
      barTone: row.tone,
    };
  });
  return { columns };
}
