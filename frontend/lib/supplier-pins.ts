// Fase 3 (permintaan pemilik proyek 2026-10-14): layer pemasok di peta.
//
// Modul MURNI (tanpa React, tanpa DOM, tanpa MapLibre) — aturan tampilan layer
// pemasok diuji di tests/supplier-pins.test.ts tanpa perlu WebGL.
//
// Sumber data: `GET /suppliers` (endpoint Fase 2). Aturan yang dipegang:
// - Baris tanpa koordinat TIDAK dipasang di peta. Menaruhnya di 0,0 (Teluk
//   Guinea) akan tampak seperti data nyata padahal bukan.
// - Pemasok tanpa fokus komoditas tidak dicocokkan ke komoditas mana pun saat
//   filter komoditas aktif — lebih baik tidak tampil daripada menebak.
// - Keandalan yang tidak diketahui punya nada sendiri ("unknown"), bukan
//   diam-diam dianggap normal.

/** Ambang "keandalan rendah" — sama untuk pin, legenda, dan kartu ringkasan. */
export const LOW_RELIABILITY = 0.6;

/**
 * Ambang "terjangkau" peran SPPG (Fase 7b, keputusan pemilik 2026-10-15).
 *
 * Ini aturan RELEVANSI, bukan scope: peran SPPG tetap boleh membaca data
 * pemasok lintas daerah (Ruling 2026-10-14 §4), tetapi yang ditampilkan
 * sebagai "pemasok kita" hanya yang benar-benar mungkin dijangkau. Angka
 * 150 km sama dengan `REACH_KM_MAX` di `app/seed/suppliers_demo.py` dan sama
 * dengan nilai yang dikirim UI saat memakai penyaring server `?max_distance_km=`.
 */
export const SUPPLIER_REACH_KM = 150;

/** Peran yang tampilannya dibatasi jangkauan (peran SPPG), selain itu nasional. */
export const SPPG_ROLES: readonly string[] = ["sppg_head", "sppg_nutritionist"];

/**
 * Ambang jangkauan untuk sebuah peran: 150 km untuk peran SPPG, `null` (tanpa
 * ambang/nasional) untuk `bgn_monitor` dan sesi yang belum diketahui.
 */
export function supplierReachKmForRole(role: string | null | undefined): number | null {
  const value = (role ?? "").trim().toLowerCase();
  return SPPG_ROLES.includes(value) ? SUPPLIER_REACH_KM : null;
}

/**
 * Pin pemasok (berbentuk titik) muncul mulai zoom ini. Pada zoom peta
 * Indonesia penuh (±4,5) pin kota akan menumpuk dan menutupi pin SPPG.
 */
export const SUPPLIER_PIN_MIN_ZOOM = 6;

/**
 * Label NAMA pemasok baru muncul mulai zoom ini. Di antara dua ambang ini pin
 * tampil sebagai titik saja: pada tampilan jaringan (zoom ±6,5) sepuluh label
 * kota di Jawa akan saling menimpa, tetapi menyembunyikan pin sepenuhnya
 * membuat lapisan tampak rusak di mata pengguna.
 */
export const SUPPLIER_LABEL_MIN_ZOOM = 8;

/** Tab yang memang memuat data pemasok (peta ada di Overview). */
const SUPPLIER_TABS = new Set(["overview", "suppliers"]);

export function shouldLoadSuppliers(tab: string, token?: string | null): boolean {
  if (!tab || !SUPPLIER_TABS.has(tab)) return false;
  return token === undefined ? true : Boolean(token);
}

export type SupplierPinTone = "excluded" | "far" | "low" | "ok" | "unknown";

export type SupplierPinRow = {
  id: string;
  name: string;
  hub: string;
  commodity: string | null;
  certification: string | null;
  reliability: number | null;
  latitude: number;
  longitude: number;
  /** Jarak dari titik rujukan yang dilaporkan server (`distance_reference`). */
  distanceKm: number | null;
  excludedAtHub: boolean;
  excludedScopes: string[];
};

function text(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  return raw ? raw : null;
}

function number(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

/**
 * Normalisasi payload `GET /suppliers` (amplop `{items}` atau array langsung)
 * menjadi baris pin. Baris tanpa nama atau tanpa koordinat dibuang.
 */
export function supplierPinRows(raw: unknown): SupplierPinRow[] {
  const list = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as { items?: unknown } | null)?.items)
      ? ((raw as { items: unknown[] }).items as unknown[])
      : [];
  const rows: SupplierPinRow[] = [];
  for (const item of list) {
    const record = (item ?? {}) as Record<string, unknown>;
    const name = text(record.name);
    const latitude = number(record.latitude);
    const longitude = number(record.longitude);
    if (!name || latitude === null || longitude === null) continue;
    const scopes = Array.isArray(record.excluded_scope_locations)
      ? record.excluded_scope_locations.map((s) => text(s)).filter((s): s is string => Boolean(s))
      : [];
    rows.push({
      id: text(record.id) ?? name,
      name,
      hub: text(record.location) ?? "—",
      commodity: text(record.commodity),
      certification: text(record.certification_status),
      reliability: number(record.reliability_score),
      latitude,
      longitude,
      distanceKm: number(record.distance_km),
      excludedAtHub: record.excluded_at_hub === true || scopes.includes(text(record.location) ?? ""),
      excludedScopes: scopes,
    });
  }
  return rows;
}

/** Pemasok yang relevan untuk komoditas terpilih (tanpa menebak). */
export function suppliersForCommodity(
  rows: readonly SupplierPinRow[],
  commodity?: string | null
): SupplierPinRow[] {
  const needle = text(commodity)?.toLowerCase() ?? null;
  if (!needle) return [...rows];
  return rows.filter((row) => row.commodity?.toLowerCase() === needle);
}

export type SupplierDistanceReference = {
  location: string;
  latitude: number;
  longitude: number;
};

export type SupplierReachMeta = {
  /** Ambang yang benar-benar dipakai server saat menyusun payload ini. */
  maxDistanceKm: number | null;
  /** Berapa baris yang dibuang server karena di luar jangkauan. */
  excludedOutOfReach: number;
  /** Berapa baris yang dibuang server karena jaraknya tidak bisa dihitung. */
  excludedUnknownDistance: number;
};

/**
 * Blok `reach` dari respons server — supaya UI bisa menyebut berapa pemasok yang
 * TIDAK dikirim (penyaringan di server tidak boleh jadi penyembunyian diam-diam).
 */
export function supplierReachMeta(raw: unknown): SupplierReachMeta {
  const kosong: SupplierReachMeta = {
    maxDistanceKm: null,
    excludedOutOfReach: 0,
    excludedUnknownDistance: 0,
  };
  if (Array.isArray(raw) || raw === null || typeof raw !== "object") return kosong;
  const reach = (raw as Record<string, unknown>).reach;
  if (reach === null || reach === undefined || typeof reach !== "object") return kosong;
  const fields = reach as Record<string, unknown>;
  return {
    maxDistanceKm: number(fields.max_distance_km),
    excludedOutOfReach: number(fields.excluded_out_of_reach) ?? 0,
    excludedUnknownDistance: number(fields.excluded_unknown_distance) ?? 0,
  };
}

/**
 * Titik rujukan jarak yang dilaporkan server (`distance_reference`).
 *
 * Dipakai UI hanya untuk MENYEBUT rujukannya ("dari SPPG Jakarta"), bukan untuk
 * menghitung ulang jarak: perhitungannya milik server, supaya angka di layar
 * tidak pernah berbeda dari angka di respons.
 */
export function supplierDistanceReference(raw: unknown): SupplierDistanceReference | null {
  if (Array.isArray(raw) || raw === null || typeof raw !== "object") return null;
  const record = (raw as Record<string, unknown>).distance_reference;
  if (record === null || record === undefined || typeof record !== "object") return null;
  const fields = record as Record<string, unknown>;
  const location = text(fields.location);
  const latitude = number(fields.latitude);
  const longitude = number(fields.longitude);
  if (location === null || latitude === null || longitude === null) return null;
  return { location, latitude, longitude };
}

/** Jarak (km) dalam gaya id-ID, atau "—" bila server tidak melaporkannya. */
export function distanceLabel(km: number | null): string {
  if (km === null || !Number.isFinite(km)) return "—";
  const rounded = km >= 100 ? Math.round(km) : Math.round(km * 10) / 10;
  return `${String(rounded).replace(".", ",")} km`;
}

/**
 * True bila pemasok berada dalam ambang jangkauan.
 *
 * `reachKm` null = tanpa ambang (tampilan nasional) → selalu true.
 * Jarak yang TIDAK diketahui tidak dianggap dalam jangkauan: itu klaim yang
 * tidak bisa dibuktikan, dan justru itu yang membuat pemasok Medan dulu tampil
 * sebagai "pemasok SPPG Jakarta".
 */
export function isWithinReach(row: SupplierPinRow, reachKm?: number | null): boolean {
  return withinReachKm(row.distanceKm, reachKm);
}

/** Versi jarak-mentah dari `isWithinReach` — dipakai halaman Pemasok (tabel). */
export function withinReachKm(km: number | null, reachKm?: number | null): boolean {
  if (reachKm === null || reachKm === undefined) return true;
  if (!Number.isFinite(reachKm)) return true;
  if (km === null || !Number.isFinite(km)) return false;
  return km <= reachKm;
}

/** Kalimat jujur untuk satu baris: dalam/ luar jangkauan, atau jarak tak diketahui. */
export function reachLabel(row: SupplierPinRow, reachKm?: number | null): string {
  return distanceReachLabel(row.distanceKm, reachKm);
}

/** Versi jarak-mentah dari `reachLabel` — satu kamus kalimat untuk peta & tabel. */
export function distanceReachLabel(km: number | null, reachKm?: number | null): string {
  if (km === null || !Number.isFinite(km)) return "jarak tidak diketahui";
  const distance = distanceLabel(km);
  if (reachKm === null || reachKm === undefined || !Number.isFinite(reachKm)) {
    return `jarak ${distance}`;
  }
  return withinReachKm(km, reachKm)
    ? `dalam jangkauan (${distance})`
    : `di luar jangkauan (${distance})`;
}

export function supplierPinTone(
  row: SupplierPinRow,
  reachKm?: number | null
): SupplierPinTone {
  if (row.excludedAtHub) return "excluded";
  if (!isWithinReach(row, reachKm)) return "far";
  if (row.reliability === null) return "unknown";
  return row.reliability < LOW_RELIABILITY ? "low" : "ok";
}

export function supplierPinClass(
  row: SupplierPinRow,
  showLabels = true,
  reachKm?: number | null
): string {
  return `map-pin map-pin-supplier map-pin-supplier-${supplierPinTone(row, reachKm)}${
    showLabels ? "" : " map-pin-supplier-compact"
  }`;
}

export function reliabilityLabel(score: number | null): string {
  return score === null ? "tidak diketahui" : `${Math.round(score * 100)}%`;
}

/** Enum sertifikasi backend → kata yang bisa dibaca manusia (tanpa enum bocor). */
export function certificationLabel(value: string | null): string {
  switch ((value ?? "").toLowerCase()) {
    case "haccp":
      return "HACCP";
    case "hygiene":
      return "Higienis";
    case "none":
      return "Tidak bersertifikat";
    default:
      return "—";
  }
}

export function supplierAccessibleLabel(
  row: SupplierPinRow,
  reachKm?: number | null
): string {
  const parts = [
    row.commodity ? `pemasok ${row.commodity}` : "pemasok tanpa fokus komoditas",
    `keandalan ${reliabilityLabel(row.reliability)}`,
    `hub ${row.hub}`,
  ];
  if (row.distanceKm !== null) parts.push(reachLabel(row, reachKm));
  const suffix =
    row.excludedAtHub && row.excludedScopes.length
      ? ` (dikecualikan di ${row.excludedScopes.join(", ")})`
      : "";
  return `${row.name} — ${parts.join(", ")}${suffix}`;
}

export type SupplierPopup = { title: string; lines: string[] };

export function supplierPopupLines(
  row: SupplierPinRow,
  reachKm?: number | null
): SupplierPopup {
  const lines = [
    `Komoditas: ${row.commodity ?? "—"}`,
    `Hub: ${row.hub}`,
    `Keandalan: ${reliabilityLabel(row.reliability)}`,
    `Sertifikasi: ${certificationLabel(row.certification)}`,
  ];
  if (row.distanceKm !== null) lines.push(`Jarak: ${reachLabel(row, reachKm)}`);
  if (row.excludedAtHub && row.excludedScopes.length) {
    lines.push(`Dikecualikan di: ${row.excludedScopes.join(", ")}`);
  }
  return { title: row.name, lines };
}

export type SupplierLayerSummary = {
  total: number;
  excluded: number;
  far: number;
  low: number;
  ok: number;
  unknown: number;
};

/**
 * Hitungan per predikat — sengaja TIDAK memakai nada pin yang saling menutup:
 * pemasok skor rendah yang juga dikecualikan tetap muncul di kolom "low" dan
 * "excluded", karena keduanya fakta berbeda yang sama-sama perlu terlihat.
 * `far` hanya dihitung bila ada ambang jangkauan (tampilan nasional: 0).
 */
export function supplierLayerSummary(
  rows: readonly SupplierPinRow[],
  reachKm?: number | null
): SupplierLayerSummary {
  return {
    total: rows.length,
    excluded: rows.filter((row) => row.excludedAtHub).length,
    far: rows.filter((row) => !isWithinReach(row, reachKm)).length,
    low: rows.filter((row) => row.reliability !== null && row.reliability < LOW_RELIABILITY).length,
    ok: rows.filter((row) => row.reliability !== null && row.reliability >= LOW_RELIABILITY).length,
    unknown: rows.filter((row) => row.reliability === null).length,
  };
}

/**
 * Baris yang dipasang di peta: tanpa ambang jangkauan = semua baris (nasional).
 *
 * Dipisah dari `isWithinReach` supaya aturannya bisa diuji tanpa MapLibre, dan
 * supaya penyaring TIDAK pernah membuang baris tanpa koordinat (itu urusan
 * `supplierPinRows`, yang sudah membuangnya lebih dulu).
 */
export function supplierPinsForMap(
  rows: readonly SupplierPinRow[],
  reachKm?: number | null
): SupplierPinRow[] {
  if (reachKm === null || reachKm === undefined || !Number.isFinite(reachKm)) {
    return [...rows];
  }
  return rows.filter((row) => isWithinReach(row, reachKm));
}

/**
 * Kalimat status layer pemasok. Menyebut rujukan dan jumlah yang disembunyikan
 * supaya penyaringan tidak pernah jadi penyembunyian diam-diam.
 */
export function supplierReachNote(
  rows: readonly SupplierPinRow[],
  reachKm?: number | null,
  reference?: string | null,
  hiddenByServer = 0
): string {
  if (reachKm === null || reachKm === undefined || !Number.isFinite(reachKm)) {
    return `${rows.length} pemasok ditampilkan (nasional, tanpa ambang jarak)`;
  }
  const within = rows.filter((row) => isWithinReach(row, reachKm)).length;
  const dari = reference ? ` dari ${reference}` : "";
  const total = rows.length + hiddenByServer;
  const tersembunyi = total - within;
  const ekor =
    tersembunyi > 0
      ? ` · ${tersembunyi} di luar jangkauan tidak dipasang di peta`
      : "";
  return `${within} dari ${total} pemasok dalam jangkauan ${reachKm} km${dari}${ekor}`;
}

export function supplierToggleLabel(rows: readonly SupplierPinRow[], show: boolean): string {
  return `${show ? "Sembunyikan" : "Tampilkan"} pemasok (${rows.length})`;
}

export function supplierPinsVisible(zoom: number): boolean {
  return Number.isFinite(zoom) && zoom >= SUPPLIER_PIN_MIN_ZOOM;
}

/** Nama pemasok hanya pada zoom dekat; di antaranya pin tampil sebagai titik. */
export function supplierLabelsVisible(zoom: number): boolean {
  return Number.isFinite(zoom) && zoom >= SUPPLIER_LABEL_MIN_ZOOM;
}

/** Legenda layer pemasok — makna yang benar-benar dipakai nada pin. */
export const SUPPLIER_PIN_LEGEND: readonly { tone: SupplierPinTone; label: string }[] = [
  { tone: "ok", label: "Pemasok" },
  { tone: "low", label: "Keandalan rendah" },
  { tone: "excluded", label: "Dikecualikan" },
  { tone: "far", label: "Di luar jangkauan" },
] as const;
