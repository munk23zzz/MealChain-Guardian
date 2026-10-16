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
};

/** Skor kesegaran 0..1 → persen (dipakai bersama halaman lain). */
export function freshnessPercent(score: unknown): string {
  if (score === null || score === undefined || score === "") return DASH;
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return DASH;
  return `${Math.round(numeric * 100)}%`;
}

/** Tanggal layak pakai ringkas (YYYY-MM-DD HH:MM WIB). */
export function usableLabel(usableUntil: unknown): string {
  const parsed = Date.parse(String(usableUntil ?? ""));
  if (!Number.isFinite(parsed)) return DASH;
  return new Date(parsed).toLocaleString("id-ID", {
    day: "numeric",
    month: "short",
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
  const failedKg = failed.reduce<number | null>(
    (total, row) => (row.kg === null ? total : (total ?? 0) + row.kg),
    null
  );
  return {
    total: rows.length,
    safe: rows.filter((row) => row.tone === "ok").length,
    failed: failed.length,
    needsVerification: rows.filter((row) => row.tone === "warn").length,
    unchecked: rows.filter((row) => row.tone === "muted").length,
    failedKg,
    failedLocations: failed.map((row) => row.location),
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
    return {
      commodity,
      locationLabel: text(found["location"]) ?? DASH,
      demandKg: angka(found["demand_kg"]),
      supplyKg: angka(found["supply_kg"]),
      shortageKg: angka(found["shortage_kg"]),
      surplusKg: angka(found["surplus_kg"]),
      isAggregate: false,
    };
  }

  return {
    commodity,
    locationLabel: "Seluruh lokasi",
    demandKg: jumlah(list, "demand_kg"),
    supplyKg: jumlah(list, "supply_kg"),
    shortageKg: jumlah(list, "shortage_kg"),
    surplusKg: jumlah(list, "surplus_kg"),
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
// Titik periksa ini WORKFLOW PETUGAS — bukan data dari server, dan sengaja
// tidak dipersistensikan: backend tidak punya kolom untuk hasil pemeriksaan
// manual, jadi mengarang penyimpanan hanya akan berbohong. Yang TERSIMPAN di
// database adalah hasil hitung ulang keamanan/kesegaran yang dipicu tombolnya.
export const RECEIVING_CHECKS: { id: string; label: string }[] = [
  { id: "kemasan", label: "Kemasan utuh, tidak sobek atau bocor" },
  { id: "suhu", label: "Suhu wadah sesuai (tidak hangat, tidak beku)" },
  { id: "warna", label: "Bau & warna normal" },
  { id: "timbang", label: "Timbangan ulang cocok dengan surat jalan" },
  { id: "lot", label: "Nomor lot & tanggal dicatat" },
];

export type ReceivingState = { done: number; total: number; allDone: boolean };

/** Hitung titik yang benar-benar ditandai (hanya nilai boolean yang dihitung). */
export function receivingState(checked: unknown): ReceivingState {
  const peta = (checked ?? null) as Record<string, unknown> | null;
  const done = RECEIVING_CHECKS.filter((item) => peta?.[item.id] === true).length;
  return { done, total: RECEIVING_CHECKS.length, allDone: done === RECEIVING_CHECKS.length };
}

/** Satu kalimat jujur: berapa titik diperiksa, dan apakah semuanya sesuai. */
export function receivingSentence(state: ReceivingState): string {
  const awal = `${state.done} dari ${state.total} titik periksa sudah ditandai`;
  return state.allDone
    ? `${awal} — semuanya sesuai.`
    : `${awal} — tandai sisanya sebelum barang dipakai.`;
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

export type ReceiptCardRow = {
  id: string;
  note: string | null;
  checkedCount: number | null;
  byName: string | null;
  waktuLabel: string;
};

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
    return {
      id: text(row?.["id"]) ?? DASH,
      note: text(row?.["other_note"]) ?? null,
      checkedCount: Number.isFinite(jumlah) ? jumlah : null,
      byName: text(row?.["recorded_by_name"]) ?? null,
      waktuLabel: formatDateTime(String(row?.["recorded_at"] ?? "")),
    };
  });
}
