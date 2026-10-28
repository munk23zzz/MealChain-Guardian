// Halaman "Keamanan Pangan" — meniru halaman /compliance di aplikasi acuan
// (E:\hackathon\HackathonBil\MealchainGuardian), DISESUAIKAN ke data yang
// benar-benar ada di backend repo ini: GET /batches
// (safety_status, freshness_score, usable_until, quantity_kg, location, commodity).
//
// Tidak dipakai: papan CCP per-alat, bank sampel, jejak lot EPCIS, sensor suhu —
// backend ini tidak punya sumbernya, jadi halamannya TIDAK mengarang angka.
// Aturan tampilan: nilai tak diketahui ditulis "—".

import { formatDate, formatDateTime } from "./datetime";
import { formatKg } from "./overview-format";
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
  /**
   * Blok bukti suhu (Fase 3 MG butir 5): profil yang dipakai, hasil observasi,
   * `evidence_state`, dan ASAL log (`source`/`source_label`). Bentuknya milik
   * server (`GET /batches` dan `GET /batches/{id}` mengirim yang sama).
   */
  evidence?: {
    commodity_profile?: Record<string, unknown> | null;
    temperature_observation?: string | null;
    evidence_state?: string | null;
    sample_count?: number | null;
    observed_at?: string | null;
    source?: string | null;
    source_label?: string | null;
    evidence_sufficient?: boolean | null;
    evidence_reasons?: string[] | null;
  } | null;
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
  // Pembulatan jam bisa mencapai 24 (mis. 3 hari − 1 menit). Tanpa dibawa ke
  // satuan hari, layar menulis "2 hari 24 jam" — satuan yang tidak pernah
  // dipakai orang.
  let hari = Math.floor(abs / 24);
  let jam = Math.round(abs % 24);
  if (jam === 24) {
    hari += 1;
    jam = 0;
  }
  const text =
    hari >= 1
      ? jam > 0
        ? `${hari} hari ${jam} jam`
        : `${hari} hari`
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
  /**
   * Skor kesegaran numerik (0..1) untuk MENGURUTKAN. `null` = tidak terbaca —
   * tidak pernah diganti 0, karena 0 berarti "paling tidak segar" dan itu klaim
   * yang tidak pernah dikirim server. Yang tercetak tetap `freshness`.
   */
  freshnessScore: number | null;
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
      freshnessScore: angka(batch?.freshness_score),
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

/**
 * Partisi status uji untuk tile ringkasan.
 *
 * Audit data 26 Okt 2026: lima tile lama bercampur dimensi (status uji +
 * karantina + kedaluwarsa) sehingga bila dijumlah hasilnya 14 dari 15 batch dan
 * pembaca mengira ada batch hilang. Fungsi ini menjaga janji "jumlah tile =
 * total batch": sisa yang tidak masuk empat kategori (mis. batch `pass` yang
 * ditahan) tampil sebagai `leftover`, bukan disembunyikan.
 */
export function safetyStatusPartition(summary: SafetySummary): {
  tiles: { key: string; label: string; value: number }[];
  leftover: number;
} {
  const tiles = [
    { key: "aman", label: "Aman", value: summary.safe },
    { key: "gagal", label: "Gagal uji", value: summary.failed },
    { key: "verifikasi", label: "Perlu verifikasi", value: summary.needsVerification },
    { key: "belum", label: "Belum diuji", value: summary.unchecked },
  ];
  const terjumlah = tiles.reduce((total, tile) => total + tile.value, 0);
  return { tiles, leftover: Math.max(0, summary.total - terjumlah) };
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
 * Jumlah baris kesegaran yang duduk TERBUKA di ringkasan (dokumen
 * `07-safety-evidence.md` §4.2 butir 3). Sisa baris tetap tersedia di dalam satu
 * lipatan — tidak ada baris yang dibuang, dan tabel status di bawah tetap
 * menampilkan semuanya tanpa lipatan.
 */
export const FRESHNESS_OPEN = 3;

/**
 * Kesegaran terendah lebih dulu (yang paling perlu diperiksa lebih dulu).
 *
 * Batch tanpa skor diletakkan PALING AKHIR dan tidak pernah mengisi slot terbuka
 * yang tersisa: skor kosong bukan 0, jadi menaruhnya di daftar "terendah" akan
 * mengklaim kesegaran yang tidak pernah diukur.
 */
export function lowestFreshness(
  rows: SafetyRow[],
  limit: number = FRESHNESS_OPEN
): { open: SafetyRow[]; rest: SafetyRow[] } {
  const urut = [...rows].sort((a, b) => {
    if (a.freshnessScore === null && b.freshnessScore === null) return 0;
    if (a.freshnessScore === null) return 1;
    if (b.freshnessScore === null) return -1;
    return a.freshnessScore - b.freshnessScore;
  });
  const berSkor = urut.filter((row) => row.freshnessScore !== null);
  const tanpaSkor = urut.filter((row) => row.freshnessScore === null);
  const buka = Math.max(0, Math.min(limit, berSkor.length));
  return {
    open: berSkor.slice(0, buka),
    // Sisa baris ber-skor + SEMUA baris tanpa skor tetap dikembalikan.
    rest: [...berSkor.slice(buka), ...tanpaSkor],
  };
}


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
  /** Komoditas yang dihitung — dipakai MENAMAI kiriman supaya tidak ambigu. */
  commodity?: string | null;
  /** Tanggal kebutuhan (`needed_by`) — supaya "Kebutuhan" tidak terbaca hari ini. */
  neededBy?: string | null;
};

/**
 * Jumlah kg kiriman yang menuju lokasi untuk SATU komoditas saja.
 *
 * Audit 26 Okt 2026: sebelumnya kalimat "kiriman 4.750 kg menutup kekurangan
 * (+3.970 kg)" menjumlahkan beras + wortel + ayam + telur, lalu membandingkannya
 * dengan kekurangan TELUR 780 kg. Kiriman komoditas lain tidak menutup
 * kekurangan ini, jadi yang dihitung harus komoditas yang sama.
 */
export function incomingKgForCommodity(
  shipments: IncomingShipment[],
  commodity: string | null | undefined
): number | null {
  const cari = text(commodity)?.toLowerCase();
  if (!cari) return null;
  let total: number | null = null;
  for (const ship of shipments) {
    if ((text(ship.commodity) ?? "").toLowerCase() !== cari) continue;
    if (ship.kg === null) continue;
    total = (total ?? 0) + ship.kg;
  }
  return total;
}

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

  // Audit data 26 Okt 2026: `needed_by` di data bisa 3 hari ke depan, jadi
  // tanggalnya disebut — tanpa itu pembaca mengira angka ini kebutuhan hari ini.
  const perlu = text(input.neededBy);
  const kepala =
    `Kebutuhan ${ribuan(demandKg)} kg${perlu ? ` (perlu ${formatDate(perlu)})` : ""} · ` +
    `tersedia ${ribuan(supplyKg)} kg → kurang ${ribuan(shortageKg)} kg`;

  const kiriman =
    incomingKg !== null && Number.isFinite(incomingKg) && incomingKg > 0 ? incomingKg : null;
  const nama = text(input.commodity);
  const sebut = nama ? `kiriman ${nama}` : "kiriman";
  if (kiriman === null) {
    return `${kepala}; belum ada kiriman ${nama ?? "masuk"} yang menuju lokasi ini.`;
  }
  if (kiriman >= shortageKg) {
    return `${kepala}; ${sebut} ${ribuan(kiriman)} kg menutup kekurangan (+${ribuan(kiriman - shortageKg)} kg).`;
  }
  return `${kepala}; ${sebut} ${ribuan(kiriman)} kg belum menutup (sisa kurang ${ribuan(shortageKg - kiriman)} kg).`;
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
  /** Kapan kebutuhan itu diperlukan (`demand_records.needed_by`), bila ada. */
  demandNeededBy: string | null;
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
      demandNeededBy: text(found["demand_needed_by"]),
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
    // Agregat lintas lokasi: tanggal kebutuhan berbeda-beda, jadi jangan
    // menampilkan satu tanggal yang mengklaim mewakili semuanya.
    demandNeededBy: null,
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
  /**
   * Komoditas keputusan dari `GET /decisions` (`commodity_name`). `null` =
   * server tidak mengirimnya; tidak pernah ditebak dari data batch.
   */
  commodity: string | null;
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
  /** kg keputusan yang masih berlaku (jendela waktu belum lewat). */
  activeKg: number | null;
  /** kg keputusan yang ditolak manusia. */
  rejectedKg: number | null;
  active: number;
  /** Kedaluwarsa TANPA penolakan — tidak ada baris yang dihitung dua kali. */
  expired: number;
  pendingApproval: number;
  rejected: number;
  reproposable: number;
  /** Komoditas yang benar-benar ada di data keputusan keamanan (urut abjad). */
  commodities: string[];
  /** Saringan aktif, atau `null` bila daftar tidak disaring. */
  filteredCommodity: string | null;
  rows: SafetyDecisionRow[];
};

const DECISION_STATUS_LABEL: Record<string, string> = {
  proposed: "Diusulkan",
  pending_approval: "Menunggu persetujuan",
  approved: "Disetujui",
  rejected: "Ditolak",
  executed: "Dieksekusi",
  verified: "Terverifikasi",
  verifier_flagged: "Ditandai verifikator",
  review_only: "Temuan tinjauan",
};

/**
 * Riwayat keputusan KEAMANAN untuk lokasi ini (feed `GET /decisions` sudah
 * ber-scope server-side). Dipisah dari keputusan jenis lain supaya halaman
 * keamanan tidak menghitung pekerjaan yang bukan urusannya.
 *
 * `commodity` (opsional) menyaring daftar ke satu komoditas — tautan dari tabel
 * postur ke gerbang (dokumen `07-safety-evidence.md` §4.2 butir 1). Saringannya
 * bekerja pada data yang SUDAH dimuat klien; `allTotal` tetap menyebut seluruh
 * feed supaya angka yang lebih kecil tidak terbaca sebagai riwayat yang hilang.
 */
export function safetyDecisions(items: unknown, commodity?: string | null): SafetyDecisionSummary {
  const list = Array.isArray(items) ? items : [];
  const keamanan = list.filter((item) => {
    const row = item as Record<string, unknown> | null;
    return row && row["decision_type"] === "safety_disruption";
  });

  // Pilihan saringan dibangun dari SELURUH keputusan keamanan (bukan dari hasil
  // saringan), jadi pilihan tidak saling menghapus saat berpindah komoditas.
  // Array.from, bukan sebaran Set: target TS di repo ini di bawah es2015
  // sehingga `[...set]` ditolak (TS2802).
  const komoditasTersedia = Array.from(
    new Set(
      keamanan
        .map((item) => text((item as Record<string, unknown>)["commodity_name"]))
        .filter((nama): nama is string => Boolean(nama))
    )
  ).sort((a, b) => a.localeCompare(b, "id"));

  const cari = text(commodity)?.toLowerCase() ?? null;
  const terpilih = cari
    ? keamanan.filter(
        (item) => (text((item as Record<string, unknown>)["commodity_name"]) ?? "").toLowerCase() === cari
      )
    : keamanan;
  // Nama kanonik dari data (bukan yang diketik pengguna) supaya kalimat layar
  // menulis ejaan yang sama dengan tabel batch.
  const namaTerpilih = cari
    ? komoditasTersedia.find((nama) => nama.toLowerCase() === cari) ?? text(commodity)
    : null;

  const rows: SafetyDecisionRow[] = terpilih.map((item) => {
    const row = item as Record<string, unknown>;
    const status = text(row["status"]) ?? "unknown";
    const valid = row["valid"] === true;
    const sisa = Number(row["seconds_remaining"]);
    return {
      id: text(row["decision_id"]) ?? DASH,
      status,
      statusLabel: DECISION_STATUS_LABEL[status] ?? status.replace(/_/g, " "),
      commodity: text(row["commodity_name"]),
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

  // Audit data 26 Okt 2026: `expired` dulu = SEMUA baris `!valid`, sehingga satu
  // keputusan yang ditolak muncul dua kali di kalimat ringkasan ("1 ditolak" DAN
  // "1 sudah lewat jendela") dan kg-nya tidak bisa dijumlahkan. Sekarang
  // kedaluwarsa hanya menghitung yang TIDAK ditolak, dan kg dipisah per keadaan.
  const kgDari = (subset: SafetyDecisionRow[]) =>
    subset.reduce<number | null>(
      (total, row) => (row.kg === null ? total : (total ?? 0) + row.kg),
      null
    );
  const berlaku = rows.filter((row) => row.valid);
  const ditolak = rows.filter((row) => row.status === "rejected");
  const kedaluwarsa = rows.filter((row) => !row.valid && row.status !== "rejected");

  return {
    total: rows.length,
    allTotal: list.length,
    totalKg: kg,
    activeKg: kgDari(berlaku),
    rejectedKg: kgDari(ditolak),
    active: berlaku.length,
    expired: kedaluwarsa.length,
    pendingApproval: rows.filter((row) => row.status === "pending_approval").length,
    rejected: ditolak.length,
    reproposable: rows.filter((row) => row.canRepropose).length,
    commodities: komoditasTersedia,
    filteredCommodity: namaTerpilih,
    rows: rows.sort((a, b) => Number(b.canRepropose) - Number(a.canRepropose)),
  };
}

/**
 * Satu kalimat ringkasan keputusan keamanan untuk lokasi ini.
 *
 * Audit data 26 Okt 2026: dulu `expired` menghitung SEMUA baris tidak-berlaku,
 * jadi keputusan yang ditolak muncul dua kali ("1 ditolak" DAN "1 sudah lewat
 * jendela") dan pembaca mengira ada dua keputusan. Sekarang tiap keadaan
 * dihitung sekali dan kg-nya disebut, sehingga angka di layar bisa dijumlahkan.
 */
export function safetyDecisionSummaryLine(s: SafetyDecisionSummary): string {
  const bagian: string[] = [
    `${s.total} keputusan keamanan`,
    `${s.active} masih berlaku${s.activeKg === null ? "" : ` (${formatKg(s.activeKg)})`}`,
  ];
  let ditolak = `${s.rejected} ditolak`;
  if (s.reproposable) ditolak += " (bisa diajukan ulang)";
  if (s.rejectedKg !== null) ditolak += ` (${formatKg(s.rejectedKg)})`;
  bagian.push(ditolak);
  bagian.push(`${s.expired} kedaluwarsa tanpa penolakan`);
  if (s.pendingApproval) bagian.push(`${s.pendingApproval} menunggu persetujuan`);
  const total = s.totalKg === null ? "" : ` · total ${formatKg(s.totalKg)}`;
  // Daftar yang disaring menyebut saringannya lebih dulu: tanpa itu "1 keputusan
  // keamanan" terbaca sebagai seluruh riwayat, padahal ada 3.
  const saring = s.filteredCommodity ? `Disaring ke komoditas ${s.filteredCommodity} · ` : "";
  return `${saring}${bagian.join(" · ")}${total}. Dari ${s.allTotal} keputusan yang menyasar lokasi ini.`;
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
  // "Aman" = boleh dialokasikan. Batch karantina TIDAK masuk meski ujinya
  // lolos — kalau ikut, chip "Aman 3" di tabel bertabrakan dengan ringkasan
  // yang menulis "2 aman · 1 ditahan" untuk data yang sama (terukur 29 Okt).
  if (filter === "aman") return row.tone === "ok" && row.quarantine !== "quarantined";
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


// ── Bukti suhu (Fase 3 MG butir 5) ─────────────────────────────────────────
//
// Backend sekarang mengirim blok `evidence` per batch dari SATU parser
// (`app/core/temperature.parse_temperature_log`), dipakai freshness, safety,
// API, dan Joule. Layar ini TIDAK boleh menyimpulkan kelengkapan bukti sendiri:
// yang dilakukannya hanya menerjemahkan hasil server menjadi kalimat.
//
// Kenapa label asal log penting: repo ini tidak punya satu pun jalur penulisan
// log dari sensor sungguhan. Log ditulis penyemai (`seed`) atau jalur demo
// (`demo`). Menampilkan "sensor aktif" akan menjadi klaim yang tidak bisa
// dipertanggungjawabkan di depan juri.

export type EvidenceState = "sufficient" | "insufficient" | "ambiguous" | "unknown";

const EVIDENCE_VALID: readonly EvidenceState[] = [
  "sufficient",
  "insufficient",
  "ambiguous",
];

/** Keadaan bukti dari server; nilai asing dibaca "unknown", bukan diteruskan. */
export function evidenceStateOf(value: unknown): EvidenceState {
  const key = text(value)?.toLowerCase();
  return EVIDENCE_VALID.find((state) => state === key) ?? "unknown";
}

const EVIDENCE_LABEL: Record<EvidenceState, string> = {
  sufficient: "Bukti cukup",
  insufficient: "Bukti kurang",
  ambiguous: "Bukti bertentangan",
  unknown: "Tidak tercatat",
};

export function evidenceLabel(state: unknown): string {
  return EVIDENCE_LABEL[evidenceStateOf(state)];
}

/** Hanya bukti CUKUP yang boleh berwarna aman. */
export function evidenceTone(state: unknown): SafetyTone {
  switch (evidenceStateOf(state)) {
    case "sufficient":
      return "ok";
    case "insufficient":
    case "ambiguous":
      return "warn";
    default:
      return "muted";
  }
}

/** Label asal log. `unknown` = tidak ada jejak asal, bukan "sensor". */
export function sourceLabelOf(value: unknown): string {
  const key = text(value)?.toLowerCase();
  if (key === "seed" || key === "demo") return "log simulasi";
  if (key === "unrecorded") return "tanpa jejak asal log";
  return "tidak tercatat";
}

/** Label observasi suhu; nilai asing tidak diteruskan mentah. */
const OBSERVATION_LABEL: Record<string, string> = {
  observed: "Teramati",
  missing: "Tidak ada log",
  malformed: "Log tidak terbaca",
  stale: "Log kedaluwarsa",
};

export type EvidenceRow = {
  id: string | null;
  commodity: string;
  /** Kode mentah server: `observed` | `missing` | `malformed` | `stale` | null. */
  observation: string | null;
  observationLabel: string;
  state: EvidenceState;
  stateLabel: string;
  tone: SafetyTone;
  sufficient: boolean;
  sampleCount: number | null;
  observedAt: string | null;
  /** `seed` | `demo` | `unrecorded` | null — asal log APA ADANYA. */
  source: string | null;
  sourceLabel: string;
  profileVersion: string | null;
  policyKind: string | null;
  coldChainRequired: boolean | null;
  /** Alasan dari server, diteruskan apa adanya (bukan diringkas ulang). */
  reasons: string[];
};

/** Satu baris bukti per batch; data lama tanpa blok `evidence` tetap terlihat. */
export function evidenceRows(batches: unknown): EvidenceRow[] {
  const list = Array.isArray(batches)
    ? (batches as SafetyBatch[])
    : Array.isArray((batches as { batches?: unknown })?.batches)
      ? ((batches as { batches: SafetyBatch[] }).batches as SafetyBatch[])
      : [];
  return list.map((batch) => {
    const blok = (batch?.evidence ?? null) as {
      commodity_profile?: { policy_version?: unknown; policy_kind?: unknown; cold_chain_required?: unknown } | null;
      temperature_observation?: unknown;
      evidence_state?: unknown;
      sample_count?: unknown;
      observed_at?: unknown;
      source?: unknown;
      source_label?: unknown;
      evidence_sufficient?: unknown;
      evidence_reasons?: unknown;
    } | null;
    const samples = Number(blok?.sample_count);
    const reasons = Array.isArray(blok?.evidence_reasons)
      ? (blok?.evidence_reasons as unknown[]).map((r) => String(r))
      : [];
    const observationKey = text(blok?.temperature_observation)?.toLowerCase() ?? null;
    const state = blok ? evidenceStateOf(blok.evidence_state) : "unknown";
    const coldChain =
      typeof blok?.commodity_profile?.cold_chain_required === "boolean"
        ? (blok.commodity_profile.cold_chain_required as boolean)
        : null;
    return {
      id: text(batch?.id),
      commodity: text(batch?.commodity) ?? DASH,
      observation: observationKey,
      observationLabel: observationKey
        ? (OBSERVATION_LABEL[observationKey] ?? "tidak tercatat")
        : "tidak tercatat",
      state,
      stateLabel: evidenceLabel(state),
      // Ambient tidak boleh diwarnai peringatan: profilnya tidak punya rentang
      // dingin, jadi tidak ada bukti suhu yang bisa dilanggar.
      tone: coldChain === false ? "muted" : evidenceTone(state),
      // Server sudah memutuskan; klien tidak menghitung ulang "cukup" dari
      // jumlah sampel — dua definisi kelengkapan adalah bug yang Fase 3 tutup.
      sufficient: blok?.evidence_sufficient === true,
      sampleCount: Number.isFinite(samples) ? samples : null,
      observedAt: text(blok?.observed_at),
      source: text(blok?.source),
      sourceLabel: sourceLabelOf(blok?.source),
      profileVersion: text(blok?.commodity_profile?.policy_version),
      policyKind: text(blok?.commodity_profile?.policy_kind),
      coldChainRequired: coldChain,
      reasons,
    };
  });
}

export type EvidenceSummary = {
  total: number;
  sufficient: number;
  insufficient: number;
  ambiguous: number;
  unknown: number;
  /** Bukti belum cukup DAN komoditasnya memang menuntut bukti suhu. */
  perluVerifikasi: number;
};

export function evidenceSummary(rows: readonly EvidenceRow[]): EvidenceSummary {
  const ringkas: EvidenceSummary = {
    total: rows.length,
    sufficient: 0,
    insufficient: 0,
    ambiguous: 0,
    unknown: 0,
    perluVerifikasi: 0,
  };
  for (const row of rows) {
    ringkas[row.state] += 1;
    // Fail-closed: yang dihitung perlu verifikasi adalah setiap batch yang
    // buktinya BELUM cukup, kecuali komoditas ambient yang profilnya memang
    // tidak mewajibkan bukti suhu. `coldChainRequired === null` (komoditas tanpa
    // profil / data lama) IKUT dihitung: "tidak tahu" bukan "aman".
    if (!row.sufficient && row.coldChainRequired !== false) {
      ringkas.perluVerifikasi += 1;
    }
  }
  return ringkas;
}

/**
 * Pembagian EKSKLUSIF untuk baris angka ringkasan.
 *
 * `safetySummaryOfRows` menjawab "berapa aman / gagal / belum" dengan tumpang
 * tindih: batch karantina tidak dihitung aman, tetapi kalau ujinya gagal ia
 * tetap terhitung di `failed` — sehingga empat angka bisa berjumlah lebih atau
 * kurang dari total. Akibatnya bagian Ringkasan butuh bar komposisi,
 * persentase, dan lipatan "cara membaca" hanya untuk menjelaskan selisih itu.
 *
 * Fungsi ini memilih SATU kelompok per baris, dengan urutan keputusan:
 *   1. karantina  — tidak boleh dialokasikan, apa pun hasil ujinya
 *   2. gagal uji
 *   3. perlu verifikasi
 *   4. belum diuji
 *   5. aman
 * Jumlah kelima angka SELALU = jumlah baris yang diperiksa, jadi pembaca tidak
 * perlu menghitung selisih atau membaca legenda.
 */
export type SafetyGroupKey = "ditahan" | "gagal" | "verifikasi" | "belum" | "aman";

export type SafetyGroup = {
  key: SafetyGroupKey;
  label: string;
  value: number;
  tone: SafetyTone;
};

export function safetyStatusGroups(rows: SafetyRow[]): SafetyGroup[] {
  let ditahan = 0;
  let gagal = 0;
  let verifikasi = 0;
  let belum = 0;
  let aman = 0;

  for (const row of rows) {
    if (row.quarantine === "quarantined") {
      ditahan += 1;
    } else if (row.tone === "danger") {
      gagal += 1;
    } else if (row.tone === "warn") {
      verifikasi += 1;
    } else if (row.tone === "ok") {
      aman += 1;
    } else {
      // Tone tak dikenal diperlakukan "belum diuji", bukan "aman": tidak ada
      // dasar untuk menyebutnya lolos.
      belum += 1;
    }
  }

  return [
    { key: "aman", label: "Aman", value: aman, tone: "ok" },
    { key: "gagal", label: "Gagal uji", value: gagal, tone: "danger" },
    { key: "verifikasi", label: "Perlu verifikasi", value: verifikasi, tone: "warn" },
    { key: "belum", label: "Belum diuji", value: belum, tone: "muted" },
    { key: "ditahan", label: "Ditahan", value: ditahan, tone: "warn" },
  ];
}
