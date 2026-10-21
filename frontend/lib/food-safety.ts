// Halaman "Keamanan Pangan" — meniru halaman /compliance di aplikasi acuan
// (E:\hackathon\HackathonBil\MealchainGuardian), DISESUAIKAN ke data yang
// benar-benar ada di backend repo ini: GET /batches
// (safety_status, freshness_score, usable_until, quantity_kg, location, commodity).
//
// Tidak dipakai: papan CCP per-alat, bank sampel, jejak lot EPCIS, sensor suhu —
// backend ini tidak punya sumbernya, jadi halamannya TIDAK mengarang angka.
// Aturan tampilan: nilai tak diketahui ditulis "—".

import { formatDate, formatDateTime } from "./datetime";
import { roadKmLabel, supplierRoutes } from "./supplier-routes";

const DASH = "—";

export type SafetyBatch = {
  id?: string | null;
  location?: string | null;
  commodity?: string | null;
  quantity_kg?: number | string | null;
  safety_status?: string | null;
  freshness_score?: number | string | null;
  usable_until?: string | null;
  /** Kolom baru (migrasi 019); data lama tidak punya → dianggap "none". */
  quarantine_status?: string | null;
  /** Status catatan penerimaan terakhir (`GET /batches`, 20 Okt 2026). */
  receipt_status?: string | null;
};

export type SafetyTone = "ok" | "warn" | "danger" | "muted";

/** Status keamanan batch → label manusia. */
export const SAFETY_LABEL: Record<string, string> = {
  pass: "Aman",
  fail: "Gagal uji",
  needs_verification: "Perlu verifikasi",
  pending: "Belum diuji",
};

export function safetyLabel(status: unknown): string {
  const key = text(status)?.toLowerCase() ?? "";
  if (!key) return DASH;
  return SAFETY_LABEL[key] ?? key.replace(/_/g, " ");
}

export function safetyTone(status: unknown): SafetyTone {
  switch (text(status)?.toLowerCase()) {
    case "pass":
      return "ok";
    case "fail":
      return "danger";
    case "needs_verification":
      return "warn";
    case "pending":
      return "muted";
    default:
      return "muted";
  }
}

/** Status karantina: batch ditahan tidak boleh dipakai menyusun alokasi. */
export type QuarantineStatus = "none" | "quarantined" | "released" | "failed";

const QUARANTINE_VALID: readonly QuarantineStatus[] = [
  "none",
  "quarantined",
  "released",
  "failed",
];

/** Nilai tak dikenal (data lama) diperlakukan "none", tidak diteruskan mentah. */
export function quarantineStatus(value: unknown): QuarantineStatus {
  const key = text(value)?.toLowerCase();
  return QUARANTINE_VALID.find((status) => status === key) ?? "none";
}

export function quarantineLabel(status: QuarantineStatus): string {
  switch (status) {
    case "quarantined":
      return "Ditahan";
    case "released":
      return "Dilepas";
    case "failed":
      return "Gagal";
    default:
      return "";
  }
}

export function quarantineTone(status: QuarantineStatus): SafetyTone {
  if (status === "quarantined" || status === "failed") return "danger";
  return "muted";
}

/** Sisa jam sampai `usable_until`. null kalau tanggalnya tidak ada/tak terbaca. */
export function hoursLeft(usableUntil: unknown, now: Date): number | null {
  const parsed = Date.parse(String(usableUntil ?? ""));
  if (!Number.isFinite(parsed)) return null;
  const hours = (parsed - now.getTime()) / 3_600_000;
  return Number.isFinite(hours) ? hours : null;
}

export function hoursLabel(hours: number | null): string {
  if (hours === null) return DASH;
  const abs = Math.abs(hours);
  const text =
    abs >= 24
      ? `${Math.floor(abs / 24)} hari ${Math.round(abs % 24)} jam`
      : `${Math.round(abs)} jam`;
  return hours >= 0 ? `${text} lagi` : `lewat ${text}`;
}

export type SafetyRow = {
  id: string | null;
  location: string;
  commodity: string;
  kg: number | null;
  statusLabel: string;
  tone: SafetyTone;
  freshness: string;
  usableUntil: string;
  hoursLeft: number | null;
  hoursLabel: string;
  /** Karantina: batch ditahan tidak boleh dipakai menyusun alokasi. */
  quarantine: QuarantineStatus;
  quarantineLabel: string;
  /** Catatan penerimaan terakhir; null = belum pernah dicatat. */
  receiptStatus: string | null;
  /** Status keamanan mentah (`pending` = belum diuji). */
  safetyStatus: string | null;
};

/** Skor kesegaran 0..1 → persen (dipakai bersama halaman lain). */
export function freshnessPercent(score: unknown): string {
  if (score === null || score === undefined || score === "") return DASH;
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return DASH;
  return `${Math.round(numeric * 100)}%`;
}

/**
 * Tanggal layak pakai ringkas, mis. "19 Mar 2027, 01.00" (WIB).
 *
 * Tahun SELALU ditulis (audit 20 Okt 2026): tanpa tahun, batch beras yang layak
 * sampai Maret tahun berikutnya tampil "19 Mar" — terbaca seolah bulan depan,
 * dan di kartu penerimaan itu dipakai untuk memilih batch yang mana. Menulis
 * tahun juga membuat fungsi ini deterministik: hasilnya tidak bergantung pada
 * tahun berjalan saat halaman dibuka.
 */
export function usableLabel(usableUntil: unknown): string {
  const parsed = Date.parse(String(usableUntil ?? ""));
  if (!Number.isFinite(parsed)) return DASH;
  return new Date(parsed).toLocaleString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  });
}

export function safetyRows(batches: unknown, now: Date): SafetyRow[] {
  const list = Array.isArray(batches) ? (batches as SafetyBatch[]) : [];
  return list.map((batch) => {
    const kg = Number(batch?.quantity_kg);
    const hours = hoursLeft(batch?.usable_until, now);
    const karantina = quarantineStatus(batch?.quarantine_status);
    return {
      id: text(batch?.id),
      location: text(batch?.location) ?? DASH,
      commodity: text(batch?.commodity) ?? DASH,
      kg: Number.isFinite(kg) ? kg : null,
      statusLabel: safetyLabel(batch?.safety_status),
      tone: safetyTone(batch?.safety_status),
      freshness: freshnessPercent(batch?.freshness_score),
      usableUntil: usableLabel(batch?.usable_until),
      hoursLeft: hours,
      hoursLabel: hoursLabel(hours),
      quarantine: karantina,
      quarantineLabel: quarantineLabel(karantina),
      receiptStatus: text(batch?.receipt_status),
      safetyStatus: text(batch?.safety_status)?.toLowerCase() ?? null,
    };
  });
}

export type SafetySummary = {
  total: number;
  safe: number;
  failed: number;
  needsVerification: number;
  unchecked: number;
  failedKg: number | null;
  failedLocations: string[];
  /** Batch yang sedang DITAHAN: stoknya ada, tetapi tidak layak dialokasikan. */
  quarantined: number;
  quarantinedKg: number | null;
  hasFail: boolean;
};

export function safetySummary(batches: unknown): SafetySummary {
  return safetySummaryOfRows(safetyRows(batches, new Date(0)));
}

/**
 * Ringkasan dari baris yang SUDAH dinormalkan — dipakai halaman yang menampilkan
 * cakupan lebih sempit dari data yang dimuat (mis. hanya lokasi sendiri), supaya
 * angka di layar selalu bercerita tentang baris yang benar-benar terlihat.
 */
export function safetySummaryOfRows(rows: SafetyRow[]): SafetySummary {
  const failed = rows.filter((row) => row.tone === "danger");
  const ditahan = rows.filter((row) => row.quarantine === "quarantined");
  const quarantinedKg = ditahan.reduce<number | null>(
    (total, row) => (row.kg === null ? total : (total ?? 0) + row.kg),
    null
  );
  const failedKg = failed.reduce<number | null>(
    (total, row) => (row.kg === null ? total : (total ?? 0) + row.kg),
    null
  );
  return {
    total: rows.length,
    // Batch yang ditahan tidak dihitung "aman": secara operasional ia bukan
    // stok yang boleh dipakai, seberapa pun bagus skor kesegarannya.
    safe: rows.filter((row) => row.tone === "ok" && row.quarantine !== "quarantined").length,
    failed: failed.length,
    needsVerification: rows.filter((row) => row.tone === "warn").length,
    unchecked: rows.filter((row) => row.tone === "muted").length,
    failedKg,
    failedLocations: failed.map((row) => row.location),
    quarantined: ditahan.length,
    quarantinedKg,
    hasFail: failed.length > 0,
  };
}

function text(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  return raw ? raw : null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Fase 11 — halaman ini dipakai KEPALA SPPG (satu lokasi), bukan hanya pengawas
// nasional. Semua fungsi di bawah menurunkan tampilan dari data server; tidak
// ada angka yang dikarang di UI. Ambang waktu eksplisit dan bisa diuji.
// ─────────────────────────────────────────────────────────────────────────────

/** Batas "harus segera dipakai" — sama dengan kartu lama (2 hari). */
export const URGENT_HOURS = 48;
/** Batas "perlu dipantau" — satu minggu. */
export const WATCH_HOURS = 24 * 7;

/**
 * Pemisah ribuan gaya Indonesia tanpa bergantung ICU peramban/Node, supaya
 * kalimat yang dilihat pengguna dan yang diuji tidak bisa berbeda.
 */
function ribuan(value: number): string {
  const bulat = Math.round(value);
  const tanda = bulat < 0 ? "-" : "";
  return tanda + String(Math.abs(bulat)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** Baris milik lokasi sendiri. Lokasi kosong/null = peran nasional → semua baris. */
export function ownLocationRows(rows: SafetyRow[], own: string | null | undefined): SafetyRow[] {
  const ownNorm = text(own)?.toLowerCase();
  if (!ownNorm) return rows;
  return rows.filter((row) => row.location.trim().toLowerCase() === ownNorm);
}

/** Paling mendesak di atas (kedaluwarsa lebih dulu); tanpa tanggal paling akhir. */
export function sortByDeadline(rows: SafetyRow[]): SafetyRow[] {
  return [...rows].sort((a, b) => {
    if (a.hoursLeft === null && b.hoursLeft === null) return 0;
    if (a.hoursLeft === null) return 1;
    if (b.hoursLeft === null) return -1;
    return a.hoursLeft - b.hoursLeft;
  });
}

export type ExpiryKey = "expired" | "urgent" | "watch" | "ok" | "unknown";
export type ExpiryState = { key: ExpiryKey; label: string; detail: string };

/**
 * Keadaan masa layak — supaya batch lewat tanggal tidak cuma tampil sebagai
 * "kesegaran 0%" (dua cara membaca hal yang sama, tanpa tindakan yang jelas).
 * Tanpa tanggal: "—" dan TIDAK diklaim aman.
 */
export function expiryState(hours: number | null): ExpiryState {
  if (hours === null) return { key: "unknown", label: DASH, detail: DASH };
  const detail = hoursLabel(hours);
  if (hours < 0) return { key: "expired", label: "Kedaluwarsa", detail };
  if (hours <= URGENT_HOURS) return { key: "urgent", label: `≤ ${URGENT_HOURS} jam`, detail };
  if (hours <= WATCH_HOURS) return { key: "watch", label: `≤ ${WATCH_HOURS / 24} hari`, detail };
  return { key: "ok", label: "Aman", detail };
}

export type IncomingShipment = {
  id: string;
  supplierName: string;
  destination: string;
  commodity: string | null;
  kg: number | null;
  safetyLabel: string;
  tone: SafetyTone;
  roadKm: number | null;
  roadKmLabel: string;
  durationMin: number | null;
  durationLabel: string;
  ratio: number | null;
  ratioLabel: string | null;
  usableLabel: string;
  hoursLeft: number | null;
  hoursLabel: string;
};

/**
 * Kiriman yang sedang menuju lokasi ini — dibaca dari `GET /supplier-routes`
 * memakai normalizer yang sama dengan peta/kolom Pemasok (`supplierRoutes`),
 * jadi tidak ada logika parsing kedua.
 */
export function incomingShipments(raw: unknown, now: Date): IncomingShipment[] {
  return supplierRoutes(raw)
    .map((row) => {
      const hours = hoursLeft(row.usableUntil, now);
      const road = row.road;
      return {
        id: row.id,
        supplierName: row.supplierName,
        destination: row.destinationName,
        commodity: row.commodity,
        kg: row.quantityKg,
        safetyLabel: safetyLabel(row.safetyStatus),
        tone: safetyTone(row.safetyStatus),
        roadKm: road ? road.distanceKm : null,
        roadKmLabel: roadKmLabel(road ? road.distanceKm : null),
        durationMin: road ? road.durationMin : null,
        durationLabel: road ? `± ${Math.round(road.durationMin)} menit` : DASH,
        ratio: road ? road.ratioVsStraight : null,
        ratioLabel:
          road && road.ratioVsStraight !== null
            ? `${road.ratioVsStraight.toFixed(2).replace(".", ",")}× jarak lurus`
            : null,
        usableLabel: usableLabel(row.usableUntil),
        hoursLeft: hours,
        hoursLabel: hoursLabel(hours),
      };
    })
    .sort((a, b) => {
      if (a.hoursLeft === null && b.hoursLeft === null) return 0;
      if (a.hoursLeft === null) return 1;
      if (b.hoursLeft === null) return -1;
      return a.hoursLeft - b.hoursLeft;
    });
}

export type CoverageInput = {
  demandKg: number | null;
  supplyKg: number | null;
  shortageKg: number | null;
  incomingKg: number | null;
};

/**
 * Satu kalimat keputusan untuk kepala SPPG: kebutuhan vs yang ada vs yang
 * sedang datang. `null` kalau angka dasarnya tidak lengkap — lebih baik diam
 * daripada menampilkan kekurangan yang dikarang.
 */
export function coverageSentence(input: CoverageInput): string | null {
  const { demandKg, supplyKg, shortageKg, incomingKg } = input;
  if (demandKg === null || supplyKg === null || shortageKg === null) return null;
  if (![demandKg, supplyKg, shortageKg].every((n) => Number.isFinite(n))) return null;

  if (shortageKg <= 0) return "Tidak ada kekurangan pada data saat ini.";

  const kepala =
    `Kebutuhan ${ribuan(demandKg)} kg · tersedia ${ribuan(supplyKg)} kg ` +
    `→ kurang ${ribuan(shortageKg)} kg`;

  const kiriman =
    incomingKg !== null && Number.isFinite(incomingKg) && incomingKg > 0 ? incomingKg : null;
  if (kiriman === null) return `${kepala}; belum ada kiriman masuk yang menuju lokasi ini.`;
  if (kiriman >= shortageKg) {
    return `${kepala}; kiriman ${ribuan(kiriman)} kg menutup kekurangan (+${ribuan(kiriman - shortageKg)} kg).`;
  }
  return `${kepala}; kiriman ${ribuan(kiriman)} kg belum menutup (sisa kurang ${ribuan(shortageKg - kiriman)} kg).`;
}

/**
 * Batch milik sendiri yang akan diperiksa saat kiriman tiba. Cocokkan nama
 * komoditas; kalau jumlah kiriman diketahui, utamakan batch dengan berat yang
 * sama. Tanpa kandidat → null supaya tombolnya tidak muncul.
 */
export function incomingBatchId(
  rows: SafetyRow[],
  shipment: { commodity: string | null; kg: number | null }
): string | null {
  const komoditas = text(shipment.commodity)?.toLowerCase();
  if (!komoditas) return null;
  const kandidat = rows.filter(
    (row) => row.id && row.commodity.trim().toLowerCase() === komoditas
  );
  if (kandidat.length === 0) return null;
  const kg = shipment.kg;
  if (kg !== null && Number.isFinite(kg)) {
    const persis = kandidat.find((row) => row.kg !== null && Math.abs(row.kg - kg) < 0.5);
    if (persis) return persis.id;
  }
  const terbesar = [...kandidat].sort((a, b) => (b.kg ?? -1) - (a.kg ?? -1))[0];
  return terbesar ? terbesar.id : null;
}

export type BalanceSlice = {
  commodity: string | null;
  locationLabel: string;
  demandKg: number | null;
  supplyKg: number | null;
  shortageKg: number | null;
  surplusKg: number | null;
  isAggregate: boolean;
};

/**
 * Potongan `GET /balance/map` yang relevan untuk halaman ini: lokasi sendiri
 * (peran SPPG) atau jumlah seluruh lokasi (peran nasional — ditandai agregat
 * supaya tidak terbaca sebagai angka satu kota).
 */
export function balanceForLocation(raw: unknown, own: string | null | undefined): BalanceSlice | null {
  const payload = raw as { commodity?: unknown; locations?: unknown } | null;
  const list = Array.isArray(payload?.locations) ? (payload?.locations as Record<string, unknown>[]) : [];
  if (list.length === 0) return null;
  const commodity = text(payload?.commodity);
  const ownNorm = text(own)?.toLowerCase();

  if (ownNorm) {
    const found = list.find(
      (row) => (text(row["location"]) ?? "").toLowerCase() === ownNorm
    );
    if (!found) return null;
    // Asal nilai (PLAN-023): perbandingan kebutuhan-vs-kiriman hanya bermakna
    // bila KEDUA sisinya tercatat. Sebelum ini sisi yang tidak ada diisi 0,
    // sehingga kalimatnya bisa mengklaim surplus/kekurangan yang tak terukur;
    // sekarang nilainya `null` (laporan repo: "null → —", bukan angka karangan).
    const tanpaSisi =
      found["supply_state"] === "tidak_ada_baris" ||
      found["demand_state"] === "tidak_ada_baris";
    return {
      commodity,
      locationLabel: text(found["location"]) ?? DASH,
      demandKg: tanpaSisi ? null : angka(found["demand_kg"]),
      supplyKg: tanpaSisi ? null : angka(found["supply_kg"]),
      shortageKg: tanpaSisi ? null : angka(found["shortage_kg"]),
      surplusKg: tanpaSisi ? null : angka(found["surplus_kg"]),
      isAggregate: false,
    };
  }

  // Agregat (pengawas nasional): hanya lokasi yang KEDUA sisinya tercatat yang
  // boleh masuk jumlah — angka 0 hasil pengisian tidak dihitung sebagai fakta.
  const terukur = list.filter(
    (row) =>
      row["supply_state"] !== "tidak_ada_baris" &&
      row["demand_state"] !== "tidak_ada_baris"
  );
  return {
    commodity,
    locationLabel: "Seluruh lokasi",
    demandKg: jumlah(terukur, "demand_kg"),
    supplyKg: jumlah(terukur, "supply_kg"),
    shortageKg: jumlah(terukur, "shortage_kg"),
    surplusKg: jumlah(terukur, "surplus_kg"),
    isAggregate: true,
  };
}

function angka(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

/** Jumlahkan sebuah kolom; null kalau ada baris yang nilainya tidak diketahui. */
function jumlah(rows: Record<string, unknown>[], key: string): number | null {
  let total = 0;
  for (const row of rows) {
    const value = angka(row[key]);
    if (value === null) return null;
    total += value;
  }
  return total;
}

export type SafetyDecisionRow = {
  id: string;
  status: string;
  statusLabel: string;
  kg: number | null;
  valid: boolean;
  secondsRemaining: number | null;
  createdLabel: string;
  canRepropose: boolean;
};

export type SafetyDecisionSummary = {
  total: number;
  allTotal: number;
  totalKg: number | null;
  active: number;
  expired: number;
  pendingApproval: number;
  rejected: number;
  reproposable: number;
  rows: SafetyDecisionRow[];
};

const DECISION_STATUS_LABEL: Record<string, string> = {
  proposed: "Diusulkan",
  pending_approval: "Menunggu persetujuan",
  approved: "Disetujui",
  rejected: "Ditolak",
  executed: "Dieksekusi",
  verified: "Terverifikasi",
  verifier_flagged: "Ditandai verifier",
  review_only: "Tinjauan (review-only)",
};

/**
 * Riwayat keputusan KEAMANAN untuk lokasi ini (feed `GET /decisions` sudah
 * ber-scope server-side). Dipisah dari keputusan jenis lain supaya halaman
 * keamanan tidak menghitung pekerjaan yang bukan urusannya.
 */
export function safetyDecisions(items: unknown): SafetyDecisionSummary {
  const list = Array.isArray(items) ? items : [];
  const keamanan = list.filter((item) => {
    const row = item as Record<string, unknown> | null;
    return row && row["decision_type"] === "safety_disruption";
  });

  const rows: SafetyDecisionRow[] = keamanan.map((item) => {
    const row = item as Record<string, unknown>;
    const status = text(row["status"]) ?? "unknown";
    const valid = row["valid"] === true;
    const sisa = Number(row["seconds_remaining"]);
    return {
      id: text(row["decision_id"]) ?? DASH,
      status,
      statusLabel: DECISION_STATUS_LABEL[status] ?? status.replace(/_/g, " "),
      kg: Number.isFinite(Number(row["quantity_kg"])) ? Number(row["quantity_kg"]) : null,
      valid,
      secondsRemaining: Number.isFinite(sisa) ? sisa : null,
      createdLabel: formatDate(String(row["created_at"] ?? "")),
      // Kontrak backend (backend/app/api/actions.py:541): /actions/repropose
      // menolak 409 kecuali statusnya "rejected" DAN ada alasan penolakan.
      // Keputusan yang cuma kedaluwarsa TIDAK bisa diajukan ulang dari sini —
      // tombolnya jangan dipasang, supaya layar tidak menjanjikan yang 409.
      canRepropose: status === "rejected",
    };
  });

  const kg = rows.reduce<number | null>(
    (total, row) => (row.kg === null ? total : (total ?? 0) + row.kg),
    null
  );

  return {
    total: rows.length,
    allTotal: list.length,
    totalKg: kg,
    active: rows.filter((row) => row.valid).length,
    expired: rows.filter((row) => !row.valid).length,
    pendingApproval: rows.filter((row) => row.status === "pending_approval").length,
    rejected: rows.filter((row) => row.status === "rejected").length,
    reproposable: rows.filter((row) => row.canRepropose).length,
    rows: rows.sort((a, b) => Number(b.canRepropose) - Number(a.canRepropose)),
  };
}

// ── Penerimaan barang (kartu "Penerimaan barang") ───────────────────────────
// Titik periksa ini WORKFLOW PETUGAS: isinya pendapat orang di dapur, bukan
// pengukuran mesin. Sejak migrasi `016_batch_receipts` snapshot-nya DISIMPAN
// (`batch_receipts.checked`, JSONB) apa adanya, bersama isian "Lainnya" dan
// pencatatnya — server tidak menafsirkan dan tidak mengubah status keamanan dari
// sini (itu tugas `/safety/evaluate` + `/freshness/evaluate`). Karena itu daftar
// di bawah boleh berubah tanpa menulis ulang baris lama: tiap baris menyimpan
// keadaan saat dicatat.
//
// Batas suhu di label suhu BUKAN karangan: `_SAFE_TEMP_BY_COMMODITY` di
// `backend/app/api/freshness.py` memakai 0–8 °C untuk telur/ayam/wortel dan
// 15–30 °C untuk beras (bawaan `safe_temp_min_c`/`safe_temp_max_c` = 0/8).
export const RECEIVING_CHECKS: { id: string; label: string }[] = [
  { id: "kemasan", label: "Kemasan utuh, tidak sobek atau bocor" },
  { id: "suhu", label: "Suhu wadah dalam rentang aman — 0–8 °C (beras 15–30 °C)" },
  { id: "bau_warna", label: "Bau & warna normal" },
  { id: "timbang", label: "Timbangan ulang cocok dengan surat jalan" },
  { id: "lot", label: "Nomor lot & tanggal dicatat" },
];

/**
 * Titik periksa yang DISESUAIKAN dengan komoditas (permintaan pemilik
 * 20 Okt 2026: "titik periksa mungkin bisa disesuaikan ceklisnya dengan
 * komoditasnya"). Id titik TETAP lima yang sama — `kemasan`, `suhu`,
 * `bau_warna`, `timbang`, `lot` — supaya catatan lama tetap terbaca dan
 * `receivingState`/`checkedForReceipt` tidak perlu tabel baru; yang berubah
 * hanya kalimatnya: wadah apa yang diperiksa, rentang suhu, dan ciri khas
 * komoditas (telur retak, beras apek, sayur layu).
 *
 * Rentang suhu mengikuti `_SAFE_TEMP_BY_COMMODITY` di
 * `backend/app/api/freshness.py` (ayam/telur/wortel 0–8 °C, beras 15–30 °C),
 * bukan angka karangan layar.
 */
const PROFIL_PERIKSA: Record<
  string,
  { kemasan: string; suhu: [number, number]; kualitas: string }
> = {
  ayam: {
    kemasan: "Kemasan/segel utuh, tidak sobek atau bocor",
    suhu: [0, 8],
    kualitas: "Tidak berbau asam/amis menyimpang; warna tidak pucat",
  },
  telur: {
    kemasan: "Rak/tray utuh, telur tidak pecah",
    suhu: [0, 8],
    kualitas: "Telur tidak retak atau pecah; permukaan bersih",
  },
  beras: {
    kemasan: "Karung utuh, tidak sobek atau bocor",
    suhu: [15, 30],
    kualitas: "Tidak berjamur, tidak berbau apek; butir tidak berkutu",
  },
  wortel: {
    kemasan: "Krat/kemasan utuh, tidak sobek atau bocor",
    suhu: [0, 8],
    kualitas: "Tidak layu, tidak berlendir; warna cerah",
  },
};

const PROFIL_BAWAAN = {
  kemasan: "Kemasan utuh, tidak sobek atau bocor",
  suhu: [0, 8] as [number, number],
  kualitas: "Bau & warna normal",
};

export function receivingChecks(commodity: string | null | undefined): {
  id: string;
  label: string;
}[] {
  const kunci = (commodity ?? "").trim().toLowerCase();
  const profil = PROFIL_PERIKSA[kunci] ?? PROFIL_BAWAAN;
  return [
    { id: "kemasan", label: profil.kemasan },
    {
      id: "suhu",
      label: `Suhu wadah dalam rentang aman — ${profil.suhu[0]}–${profil.suhu[1]} °C`,
    },
    { id: "bau_warna", label: profil.kualitas },
    { id: "timbang", label: "Timbangan ulang cocok dengan surat jalan" },
    { id: "lot", label: "Nomor lot & tanggal dicatat" },
  ];
}

export type ReceivingState = { done: number; total: number; allDone: boolean };

/** Hitung titik yang benar-benar ditandai (hanya nilai boolean yang dihitung). */
export function receivingState(checked: unknown): ReceivingState {
  const peta = (checked ?? null) as Record<string, unknown> | null;
  const done = RECEIVING_CHECKS.filter((item) => peta?.[item.id] === true).length;
  return { done, total: RECEIVING_CHECKS.length, allDone: done === RECEIVING_CHECKS.length };
}

/**
 * Satu kalimat jujur: berapa titik yang benar-benar ditandai, dan apa artinya.
 *
 * Kalimat lama berakhiran "tandai sisanya sebelum barang dipakai" — perintah
 * yang tidak pernah ditegakkan layar ini (tombolnya aktif di 0/5, server menerima
 * snapshot kosong). Kalimat yang menjanjikan gerbang palsu lebih buruk daripada
 * tidak ada kalimat, jadi yang ditulis sekarang hanya keadaan + izin mencatat
 * sebagian, dan sisa titik disebut apa adanya.
 */
export function receivingSentence(state: ReceivingState): string {
  if (state.allDone) {
    return `${state.done} dari ${state.total} titik periksa sudah ditandai — semuanya sesuai.`;
  }
  const sisa = state.total - state.done;
  return `${state.done} dari ${state.total} titik periksa sudah ditandai — ${sisa} belum diperiksa. Boleh disimpan sebagian.`;
}

/**
 * Kalimat SESUDAH menyimpan. Dipisah dari `receivingSentence` karena memakai
 * "sudah ditandai" di pesan sukses membuat layar menyuruh menandai ulang tepat
 * setelah catatannya tersimpan (terukur: "Catatan penerimaan tersimpan. 0 dari 5
 * titik periksa sudah ditandai — tandai sisanya…").
 */
export function receiptSavedSentence(state: ReceivingState): string {
  if (state.allDone) {
    return `Catatan tersimpan: ${state.done} dari ${state.total} titik tercatat, semuanya sesuai.`;
  }
  const sisa = state.total - state.done;
  return `Catatan tersimpan: ${state.done} dari ${state.total} titik tercatat, ${sisa} belum diperiksa.`;
}

/**
 * Opsi "Lainnya" (permintaan pemilik 2026-10-16): tempat petugas menuliskan
 * keadaan yang tidak ada di daftar periksa. Ia BUKAN titik periksa — karena itu
 * berdiri sendiri di luar `RECEIVING_CHECKS` dan tidak ikut dihitung pada
 * "N dari 5 titik". Isinya disimpan apa adanya di `batch_receipts.other_note`.
 */
export const RECEIVING_OTHER = {
  id: "lainnya",
  label: "Lainnya — tuliskan keadaan yang tidak ada di daftar",
  hint: "karung lapis kedua basah, timbangan tidak tersedia, kendaraan tanpa pendingin",
};

/**
 * Opsi "Batch yang diterima" — SELALU milik dapur sendiri.
 *
 * Audit 20 Okt 2026: daftar ini dulu memakai baris yang sudah disaring cakupan
 * tabel, jadi saat cakupan diubah ke "Semua lokasi (pengawasan)" dropdown
 * menawarkan 50+ batch kota lain. Memilih salah satunya berakhir 403 — "lokasi
 * batch di cakupan lokasi di luar SPPG Anda" — karena barang diterima di dapur
 * sendiri (ruling 2026-10-14, `assert_in_scope` di `POST /receipts`). Pilihan
 * yang dijamin gagal bukan pilihan.
 *
 * Penyaring lokasi di sini SENGAJA tidak membaca `scope`: cakupan tabel adalah
 * alat pengawasan, sedangkan penerimaan barang adalah tindakan fisik di satu
 * dapur. Baris tanpa id juga dibuang karena tidak bisa dikirim ke server.
 */
export function receivingBatchOptions(
  rows: SafetyRow[],
  ownLocation: string | null | undefined
): SafetyRow[] {
  const milik = ownLocation ? ownLocationRows(rows, ownLocation) : rows;
  const berkas = milik.filter((row) => Boolean(row.id));
  // HANYA barang yang BELUM dinilai (permintaan pemilik 20 Okt 2026, pilihan
  // eksplisit: batch berstatus "Belum diuji"/`pending`). Batch yang sudah punya
  // hasil — Aman, Gagal uji, Perlu verifikasi — tidak muncul: penilaiannya
  // sudah ada, jadi bukan pekerjaan penerimaan lagi. Catatan `menunggu` juga
  // tidak muncul; ia diputuskan dari kartu "Menunggu persetujuan".
  const perluDicatat = berkas.filter(
    (row) => row.safetyStatus === "pending" && row.receiptStatus === null
  );
  // Batch yang MASIH layak didahulukan: urutan tenggat menaruh nilai negatif
  // (sudah kedaluwarsa) paling atas, sehingga pilihan default bisa jatuh ke
  // batch kedaluwarsa — bukan sasaran yang masuk akal untuk "barang datang
  // hari ini". Batch kedaluwarsa tetap bisa dipilih (kiriman bisa terlambat),
  // hanya diletakkan di bawah.
  const layak = perluDicatat.filter((row) => row.hoursLeft === null || row.hoursLeft >= 0);
  const lewat = perluDicatat.filter(
    (row) => row.hoursLeft !== null && row.hoursLeft < 0
  );
  return [...sortByDeadline(layak), ...sortByDeadline(lewat)];
}

export type CommodityBatchGroup = {
  commodity: string;
  /** Batch komoditas ini, urut tenggat (yang paling mendesak lebih dulu). */
  rows: SafetyRow[];
  /** Total berat yang bisa diterima; null bila tak satu pun punya kg. */
  totalKg: number | null;
};

/**
 * Kelompokkan pilihan penerimaan per KOMODITAS (permintaan pemilik 20 Okt 2026:
 * "pilih komoditasnya baru memilih batch-nya"). Urutan kelompok mengikuti
 * kemunculan pertama di daftar batch — jadi komoditas yang paling mendesak
 * tetap di atas, bukan diacak abjad.
 */
export function receivingCommodityGroups(
  rows: SafetyRow[],
  ownLocation: string | null | undefined
): CommodityBatchGroup[] {
  const opsi = receivingBatchOptions(rows, ownLocation);
  const peta = new Map<string, SafetyRow[]>();
  for (const row of opsi) {
    const kunci = (row.commodity ?? "").trim() || "—";
    const isi = peta.get(kunci);
    if (isi) isi.push(row);
    else peta.set(kunci, [row]);
  }
  return Array.from(peta.entries()).map(([commodity, isi]) => ({
    commodity,
    rows: isi,
    totalKg: isi.some((row) => row.kg !== null)
      ? isi.reduce((jumlah, row) => jumlah + (row.kg ?? 0), 0)
      : null,
  }));
}

export type ReceiptStatus = "menunggu" | "disetujui" | "ditolak";

/** Kalimat singkat: apakah batch ini masih perlu dicatat? (20 Okt 2026) */
export function receiptNeedLabel(status: string | null | undefined): string {
  if (status === "ditolak") return "ditolak — dinilai ulang";
  if (status === "menunggu") return "sudah dicatat, menunggu persetujuan";
  if (status === "disetujui") return "sudah disetujui";
  return "belum dinilai";
}

export type ReceiptCardRow = {
  id: string;
  note: string | null;
  checkedCount: number | null;
  byName: string | null;
  waktuLabel: string;
  // ---- keputusan (migrasi 026) ----
  status: ReceiptStatus;
  statusLabel: string;
  statusNada: "warn" | "ok" | "danger";
  reviewedByName: string | null;
  reviewedLabel: string | null;
  reviewNote: string | null;
  stockKg: number | null;
};

/** Label + nada badge untuk satu status penerimaan. */
/** Saringan daftar batch (redesign 20 Okt 2026): pengguna memilih PRIORITAS,
 *  bukan menggulir 30 baris. "tindakan" = apa pun yang belum beres (gagal,
 *  perlu verifikasi, atau ditahan) — sasaran pertama kepala SPPG. */
export type SafetyFilter = "semua" | "tindakan" | "gagal" | "verifikasi" | "aman";

export function matchesSafetyFilter(row: SafetyRow, filter: SafetyFilter): boolean {
  if (filter === "semua") return true;
  if (filter === "gagal") return row.tone === "danger";
  if (filter === "verifikasi") return row.tone === "warn";
  if (filter === "aman") return row.tone === "ok";
  return row.tone === "danger" || row.tone === "warn" || row.quarantine !== "none";
}

/** Saring berdasarkan keadaan + pencarian lokasi/komoditas (tanpa peduli huruf). */
export function filterSafetyRows(
  rows: readonly SafetyRow[],
  filter: SafetyFilter,
  query: string
): SafetyRow[] {
  const cari = query.trim().toLowerCase();
  return rows.filter((row) => {
    if (!matchesSafetyFilter(row, filter)) return false;
    if (!cari) return true;
    return `${row.location} ${row.commodity}`.toLowerCase().includes(cari);
  });
}

/** Jumlah per saringan — ditampilkan di chip supaya pengguna tahu isinya dulu. */
export function safetyFilterCounts(rows: readonly SafetyRow[]): Record<SafetyFilter, number> {
  return {
    semua: rows.length,
    tindakan: rows.filter((r) => matchesSafetyFilter(r, "tindakan")).length,
    gagal: rows.filter((r) => matchesSafetyFilter(r, "gagal")).length,
    verifikasi: rows.filter((r) => matchesSafetyFilter(r, "verifikasi")).length,
    aman: rows.filter((r) => matchesSafetyFilter(r, "aman")).length,
  };
}

export function receiptStatusLabel(status: unknown): {
  label: string;
  nada: "warn" | "ok" | "danger";
} {
  const nilai = text(status)?.toLowerCase();
  if (nilai === "disetujui") return { label: "Disetujui", nada: "ok" };
  if (nilai === "ditolak") return { label: "Ditolak", nada: "danger" };
  return { label: "Menunggu persetujuan", nada: "warn" };
}

/**
 * Snapshot titik periksa yang boleh dikirim ke server: HANYA id titik periksa
 * yang dikenal, nilainya dipaksa boolean. Kunci asing (mis. "lainnya") tidak
 * ikut — catatan bebas dikirim lewat `other_note`, bukan sebagai titik periksa.
 */
export function checkedForReceipt(centang: unknown): Record<string, boolean> {
  const peta = (centang ?? null) as Record<string, unknown> | null;
  const keluar: Record<string, boolean> = {};
  for (const item of RECEIVING_CHECKS) {
    keluar[item.id] = peta?.[item.id] === true;
  }
  return keluar;
}

/**
 * Riwayat catatan penerimaan dari `GET /receipts` → bentuk tampilan. Catatan
 * yang hanya berisi spasi dianggap TIDAK ada (server juga menyimpannya NULL),
 * supaya layar bisa membedakan "petugas tidak menulis apa-apa" dari "menulis".
 */
export function receiptRows(payload: unknown): ReceiptCardRow[] {
  const items = (payload as { items?: unknown } | null)?.items;
  if (!Array.isArray(items)) return [];
  return items.map((mentah) => {
    const row = (mentah ?? null) as Record<string, unknown> | null;
    const jumlah = Number(row?.["checked_count"]);
    // `Number(null)` = 0 — untuk stok, null berarti "belum masuk stok",
    // bukan "0 kg". Paksa NaN agar tampil kosong, bukan nol palsu.
    const stokMentah = row?.["stock_kg"];
    const stok = stokMentah === null || stokMentah === undefined ? NaN : Number(stokMentah);
    const status = receiptStatusLabel(row?.["status"]);
    const diputuskan = text(row?.["reviewed_at"])
      ? formatDateTime(String(row?.["reviewed_at"]))
      : null;
    return {
      id: text(row?.["id"]) ?? DASH,
      note: text(row?.["other_note"]) ?? null,
      checkedCount: Number.isFinite(jumlah) ? jumlah : null,
      byName: text(row?.["recorded_by_name"]) ?? null,
      waktuLabel: formatDateTime(String(row?.["recorded_at"] ?? "")),
      // Baris lama (sebelum migrasi 026) tidak punya status → dianggap
      // "menunggu", sama dengan default kolom di DB.
      status: (text(row?.["status"])?.toLowerCase() ?? "menunggu") as ReceiptStatus,
      statusLabel: status.label,
      statusNada: status.nada,
      reviewedByName: text(row?.["reviewed_by_name"]) ?? null,
      reviewedLabel: diputuskan,
      reviewNote: text(row?.["review_note"]) ?? null,
      stockKg: Number.isFinite(stok) ? stok : null,
    };
  });
}
