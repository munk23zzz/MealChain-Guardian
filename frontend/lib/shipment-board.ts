/**
 * "Papan kiriman" (Arah B riset 16 Okt 2026) — logika MURNI, tanpa React/DOM.
 *
 * Sumber bentuk: `docs/research/informasi-pengiriman-industri.md` §6 Arah B —
 * tabel semua kiriman (Pemasok · Tujuan · Muatan · Jalur · Berangkat · ETA ·
 * Sisa · Masa layak · Mutu · Keadaan) dengan pengurutan "paling mendesak"
 * (sisa waktu vs batas layak). Menggantikan peran kolom teks "Jalur kirim" yang
 * hanya satu kalimat panjang per pemasok: papan ini satu baris per KIRIMAN.
 *
 * Aturan repo yang dipegang (sama seperti modul kartu kiriman):
 * 1. Tanpa geometri jalan, sel Jalur menulis jarak LURUS berlabel + sebabnya
 *    (`road_missing_reason`) — tidak menulis "0 km".
 * 2. Tanpa waktu tiba/berangkat yang tercatat, selnya "—" dan barisnya
 *    diurutkan PALING BELAKANG, bukan dianggap paling awal.
 * 3. "Belum ada data" ≠ "terlambat": nada netral, bukan merah.
 */
import { formatClockWib, formatDate, formatDateTime } from "./datetime";
import { formatKg } from "./overview-format";
import { shipmentUrgency } from "./shipment-card";
import {
  durationLabel,
  journeyTone,
  MISSING_REASON_LABEL,
  roadKmLabel,
  type RouteJourneyTone,
  type SupplierRoute,
} from "./supplier-routes";

export type BoardSort = "mendesak" | "eta" | "layak";

/** Pilihan urutan papan. Label = bahasa pengguna, bukan istilah basis data. */
export const BOARD_SORTS: readonly { id: BoardSort; label: string }[] = [
  { id: "mendesak", label: "Paling mendesak" },
  { id: "eta", label: "Estimasi tiba" },
  { id: "layak", label: "Batas layak" },
];

const DASH = "—";

/** Alasan jalur dalam bahasa pengguna (fallback: apa yang server kirim). */
function alasanJalur(row: SupplierRoute): string {
  if (!row.missingReason) return "rute jalan belum tersedia";
  return MISSING_REASON_LABEL[row.missingReason] ?? row.missingReason;
}

/** Muatan: "800 kg telur". Komoditas tak ada → tetap sebut beratnya; tanpa berat → "—". */
export function boardMuatan(row: SupplierRoute): string {
  const komoditas = row.commodity ? ` ${row.commodity}` : "";
  if (row.quantityKg === null) return row.commodity ?? DASH;
  return `${formatKg(row.quantityKg)}${komoditas}`;
}

/**
 * Jalur: jalur JALAN lebih dulu (itu yang ditempuh), lalu cadangan jarak lurus
 * berlabel bila geometri belum ada. Tidak pernah "0 km".
 */
export function boardJalur(row: SupplierRoute): string {
  if (row.road) return `${roadKmLabel(row.road.distanceKm)} jalan · ± ${durationLabel(row.road.durationMin)}`;
  if (row.straightKm !== null) return `${roadKmLabel(row.straightKm)} lurus — ${alasanJalur(row)}`;
  // Tanpa geometri jalan DAN tanpa jarak lurus: sel tetap "—" (tidak mengarang
  // jarak), tetapi sebabnya tetap ditulis kalau server memberikannya — pembaca
  // berhak tahu kenapa kosong.
  return row.missingReason ? `${DASH} (${alasanJalur(row)})` : DASH;
}

/** Rasio jalur terhadap garis lurus — jejak audit, hanya bila server mengirimnya. */
export function boardRasio(row: SupplierRoute): string | null {
  if (!row.road || row.road.ratioVsStraight === null) return null;
  return `${row.road.ratioVsStraight.toFixed(2).replace(".", ",")}× jarak lurus`;
}

/** Sumber geometri (OSRM/cache) — supaya angka jalur bisa ditelusuri. */
export function boardSumber(row: SupplierRoute): string | null {
  return row.road ? row.road.source.toUpperCase() : null;
}

/**
 * Tanggal+jam ringkas untuk sel tabel: "8 Okt 18.00".
 *
 * Tahunnya SENGAJA tidak ditulis di sini: papan ini memuat kiriman AKTIF
 * (perjalanan hitungan jam, bukan tahun), dan tahun lengkap tetap ada di kolom
 * "Masa layak" serta di tooltip sel (`boardWaktuPenuh`). Sepuluh kolom tidak muat
 * di layar 1440 px kalau setiap sel menulis tahun + WIB — dan kolom yang
 * terpotong lebih buruk daripada tahun yang tidak diulang.
 */
export function boardWaktuRingkas(iso: string | null | undefined): string {
  const tanggal = formatDate(iso);
  if (tanggal === DASH) return DASH;
  return `${tanggal.replace(/\s\d{4}$/, "")} ${formatClockWib(iso)}`;
}

/** Waktu lengkap untuk tooltip sel — tidak ada informasi yang benar-benar hilang. */
export function boardWaktuPenuh(iso: string | null | undefined): string {
  return formatDateTime(iso);
}

export function boardBerangkat(row: SupplierRoute): string {
  const waktu = row.journey?.dispatchedAt;
  return waktu ? boardWaktuRingkas(waktu) : "belum berangkat";
}

export function boardEta(row: SupplierRoute): string {
  const waktu = row.journey?.etaAt;
  return waktu ? boardWaktuRingkas(waktu) : DASH;
}

/** Jam tiba/berangkat lengkap (dipakai sebagai tooltip sel). */
export function boardEtaPenuh(row: SupplierRoute): string {
  return boardWaktuPenuh(row.journey?.etaAt);
}

export function boardBerangkatPenuh(row: SupplierRoute): string {
  return row.journey?.dispatchedAt ? boardWaktuPenuh(row.journey.dispatchedAt) : "belum berangkat";
}

/**
 * Sisa waktu: hanya bila server mengirim `remaining_min` (bukan hitungan UI).
 * Tanpa kata "lagi" — kepala kolomnya sudah "Sisa", dan kata itu memakan lebar
 * yang dibutuhkan kolom terakhir.
 */
export function boardSisa(row: SupplierRoute): string {
  const journey = row.journey;
  if (!journey) return DASH;
  // Sisa waktu hanya bermakna untuk perjalanan yang SEDANG berjalan. Kiriman
  // yang sudah tiba atau belum berangkat tidak punya "sisa" — dan menampilkan
  // angka sisa yang tersimpan di data lama akan menyesatkan (kolom "Keadaan" di
  // sebelahnya sudah menjelaskan keadaannya).
  if (journey.state !== "di_jalan") return DASH;
  const sisa = journey.remainingMin;
  if (sisa === null || sisa === undefined) return DASH;
  return durationLabel(sisa);
}

export function boardMasaLayak(row: SupplierRoute): string {
  return row.usableUntil ? formatDate(row.usableUntil) : DASH;
}

/**
 * Catatan masa layak: apakah kiriman ini akan tiba SEBELUM batasnya.
 * `null` = server belum bisa memastikan (jangan mengarang "aman").
 */
export function boardLayakNote(row: SupplierRoute): { text: string; tone: "ok" | "danger" } | null {
  const tiba = row.journey?.arrivesBeforeUsableUntil;
  if (tiba === true) return { text: "tiba sebelum batas", tone: "ok" };
  if (tiba === false) return { text: "tiba MELEWATI batas", tone: "danger" };
  return null;
}

/** Mutu kiriman: hanya dua nilai yang bermakna; selain itu apa adanya. */
export function boardMutu(row: SupplierRoute): string {
  const status = row.safetyStatus;
  if (!status) return DASH;
  if (status === "fail") return "Gagal uji";
  if (status === "pass") return "Lolos uji";
  return String(status);
}

export type BoardState = { label: string; tone: RouteJourneyTone };

/** Keadaan perjalanan apa adanya dari server — tidak diterjemahkan ulang di klien. */
export function boardKeadaan(row: SupplierRoute): BoardState {
  const journey = row.journey;
  if (!journey) return { label: "Belum dilaporkan", tone: "unknown" };
  return { label: journey.stateLabel || "Tidak diketahui", tone: journeyTone(journey.state) };
}

/** Jam tiba ringkas untuk ringkasan (mis. "Sudah tiba 19.24"). */
export function boardTibaRingkas(row: SupplierRoute): string | null {
  const journey = row.journey;
  if (!journey || journey.state !== "sudah_tiba" || !journey.etaAt) return null;
  return formatClockWib(journey.etaAt);
}

/** Satu kalimat jumlah: "3 kiriman · 1 di jalan · 2 sudah tiba". */
export function boardCounts(rows: readonly SupplierRoute[]): string {
  if (!rows.length) return "Tidak ada kiriman";
  const bagian: string[] = [`${rows.length} kiriman`];
  const hitung = (uji: (row: SupplierRoute) => boolean, teks: (n: number) => string) => {
    const n = rows.filter(uji).length;
    if (n > 0) bagian.push(teks(n));
  };
  hitung((r) => r.journey?.state === "di_jalan", (n) => `${n} di jalan`);
  hitung((r) => r.journey?.state === "belum_berangkat", (n) => `${n} belum berangkat`);
  hitung((r) => r.journey?.state === "sudah_tiba", (n) => `${n} sudah tiba`);
  hitung((r) => !r.journey || r.journey.state === "tidak_diketahui", (n) => `${n} tanpa laporan server`);
  return bagian.join(" · ");
}

/** Waktu untuk mengurutkan; `null` (tanpa data) selalu di belakang. */
function menitAman(nilai: string | null | undefined): number {
  const waktu = nilai ? Date.parse(nilai) : Number.NaN;
  return Number.isFinite(waktu) ? waktu : Number.POSITIVE_INFINITY;
}

/**
 * Bandingkan dua angka dengan aman.
 *
 * Ditulis begini karena dua baris TANPA data sama-sama bernilai `Infinity`, dan
 * `Infinity - Infinity` = `NaN` — pembanding yang mengembalikan `NaN` membuat
 * urutan hasil `sort` bergantung mesin. Kesamaan dikembalikan eksplisit.
 */
function banding(a: number, b: number): number {
  if (a === b) return 0;
  return a < b ? -1 : 1;
}

/**
 * Urutkan baris papan. SEMUA cara menaruh baris tanpa data di belakang, lalu
 * memakai nama pemasok sebagai pemutus terakhir supaya hasilnya tidak berubah
 * setiap render (urutan harus bisa diprediksi petugas).
 */
export function boardSort(rows: readonly SupplierRoute[], cara: BoardSort): SupplierRoute[] {
  const dasar = (a: SupplierRoute, b: SupplierRoute) =>
    a.supplierName.localeCompare(b.supplierName) || a.destinationName.localeCompare(b.destinationName);
  const urut = [...rows];
  if (cara === "eta") {
    return urut.sort(
      (a, b) =>
        banding(menitAman(a.journey?.etaAt), menitAman(b.journey?.etaAt)) ||
        banding(shipmentUrgency(a), shipmentUrgency(b)) ||
        dasar(a, b)
    );
  }
  if (cara === "layak") {
    return urut.sort(
      (a, b) =>
        banding(menitAman(a.usableUntil), menitAman(b.usableUntil)) ||
        banding(shipmentUrgency(a), shipmentUrgency(b)) ||
        dasar(a, b)
    );
  }
  return urut.sort(
    (a, b) =>
      banding(shipmentUrgency(a), shipmentUrgency(b)) ||
      banding(a.safetyStatus === "fail" ? 0 : 1, b.safetyStatus === "fail" ? 0 : 1) ||
      banding(menitAman(a.journey?.etaAt), menitAman(b.journey?.etaAt)) ||
      dasar(a, b)
  );
}
