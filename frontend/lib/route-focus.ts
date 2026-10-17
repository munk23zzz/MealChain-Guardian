/**
 * Memilih SATU kiriman untuk disorot (Arah C riset 16 Okt 2026) — logika MURNI.
 *
 * Riset §6: "Pilih jalur di peta → panel kanan berisi stepper + rincian + riwayat;
 * garis jalur disorot, segmen yang belum ditempuh digambar putus-putus".
 *
 * Modul ini hanya menjawab "kiriman mana yang sedang disorot" dan "bagaimana
 * menuliskan pilihannya". Visualnya memakai ulang kartu yang SUDAH ada
 * (stepper + rincian + riwayat) — tidak ada penyaji angka kedua.
 *
 * Aturan yang dipegang:
 * 1. Gagal-tertutup: id tak dikenal / kosong = tampilan SEMUA, bukan tebakan
 *    "kiriman pertama" (pola yang sama dengan `activeLocation` peta).
 * 2. Pilihan "semua" ditulis sebagai jumlah yang sebenarnya ("Semua (3)"),
 *    bukan kata "semua" tanpa angka.
 * 3. Urutan pilihan mengikuti urutan mendesak yang sudah dipakai kartu/papan,
 *    supaya tiga tempat tidak menyusun daftar dengan cara berbeda.
 */
import { lineSplit, type LngLat } from "./route-line-split";
import { shipmentHeadline, shipmentTitle, shipmentUrgency } from "./shipment-card";
import { supplierRoutes, type RouteJourneyTone, type SupplierRoute } from "./supplier-routes";

/** Penanda "tanpa fokus" — sama dengan konvensi pemilih lokasi di top bar. */
export const FOCUS_ALL = "__all__";

export type FocusOption = {
  id: string;
  /** "Supplier A → Jakarta" */
  label: string;
  /** Keadaan perjalanan apa adanya dari server ("Di jalan · 20 menit lagi"). */
  state: string;
  tone: RouteJourneyTone;
};

export function focusLabel(row: SupplierRoute): string {
  return shipmentTitle(row);
}

/** Baris kiriman yang bisa dipilih, urut mendesak (bukan urut alfabet/kedatangan data). */
export function focusRows(routes: unknown): SupplierRoute[] {
  const rows = supplierRoutes(routes);
  return [...rows].sort((a, b) => {
    const mendesak = shipmentUrgency(a) - shipmentUrgency(b);
    if (mendesak !== 0) return mendesak;
    const namaA = focusLabel(a);
    const namaB = focusLabel(b);
    return namaA.localeCompare(namaB, "id");
  });
}

/** Opsi pemilih: satu baris per kiriman (tanpa opsi "semua" — itu tombol tersendiri). */
export function focusOptions(routes: unknown): FocusOption[] {
  return focusRows(routes).map((row) => {
    const headline = shipmentHeadline(row);
    return {
      id: row.id,
      label: focusLabel(row),
      state: headline.label,
      tone: headline.tone,
    };
  });
}

/**
 * Kiriman yang disorot.
 *
 * `null` bila id-nya "semua", kosong, atau TIDAK ada di data (gagal-tertutup) —
 * UI lalu menampilkan seluruh kiriman, bukan berpura-pura ada yang terpilih.
 */
export function focusPick(routes: unknown, id: string | null | undefined): SupplierRoute | null {
  if (!id || id === FOCUS_ALL) return null;
  return focusRows(routes).find((row) => row.id === id) ?? null;
}

/** Kalimat penghubung antara pemilih di peta dan kartu yang menampilkan hasilnya. */
export function focusNote(row: SupplierRoute | null, total: number): string {
  if (!row) {
    return total === 1
      ? "Menampilkan satu-satunya kiriman di jaringan."
      : `Menampilkan semua ${total} kiriman di jaringan.`;
  }
  const judul = focusLabel(row);
  const sisa = Math.max(0, total - 1);
  const lain = sisa === 0 ? "tidak ada kiriman lain" : `${sisa} kiriman lain disembunyikan`;
  return `Menampilkan kiriman terpilih di peta: ${judul} (${lain}).`;
}

/** Nama tombol pelepas saringan — satu kata yang sama di semua tempat. */
export const FOCUS_CLEAR_LABEL = "Lepas";

/**
 * Teks chip saringan di atas kanvas (celah C8, langkah 7b-2; riset §5).
 *
 * Kenapa perlu: begitu satu kiriman disorot, peta MENYEMBUNYIKAN kiriman lain —
 * dan itu satu-satunya keadaan di mana orang bisa mencari pin yang tidak ada.
 * Riset menyebut penanda keadaan saringan sebagai keharusan ("a small chip
 * above the map"), karena tanpa itu pengguna mengira datanya hilang.
 *
 * Dua aturan penulisannya:
 * 1. namanya diambil dari `focusLabel` (sumber yang sama dengan pil pemilih &
 *    kartu) — bukan dirangkai ulang, supaya tiga tempat tidak beda sebut;
 * 2. teksnya PENDEK: hanya nama kiriman. Keadaan perjalanan & jumlah yang
 *    disembunyikan sudah ada di pil pemilih dan catatan kartu di bawah peta —
 *    mengulanginya di chip membuat baris ini membungkus di ponsel.
 */
export function focusFilterText(row: SupplierRoute): string {
  return `Menyaring: ${focusLabel(row)}`;
}

/**
 * Geometri garis SOROTAN (Arah C): bagian yang sudah ditempuh padat, sisanya
 * putus-putus.
 *
 * Dua aturan penting:
 * 1. Kiriman yang SUDAH TIBA digambar penuh padat walau angka `progress` tidak
 *    ada — keadaan itu datang dari server dan artinya tidak ambigu ("seluruh
 *    jalur sudah ditempuh"), sedangkan menebak 0% akan menggambar jalur yang
 *    sudah selesai sebagai "belum ditempuh".
 * 2. Tanpa angka `progress` (dan belum tiba) garis utuh digambar sebagai
 *    "belum ditempuh" — sama dengan garis dasar peta yang memang putus-putus.
 *    Tidak ada klaim sudah berjalan.
 */
export type FocusLineFeature = {
  type: "Feature";
  geometry: { type: "LineString"; coordinates: LngLat[] };
  properties: { kind: "done" | "todo"; tone: "ok" | "fail" };
};

export type FocusLineCollection = { type: "FeatureCollection"; features: FocusLineFeature[] };

const KOSONG: FocusLineCollection = { type: "FeatureCollection", features: [] };

function garis(coordinates: LngLat[], kind: "done" | "todo", tone: "ok" | "fail"): FocusLineFeature {
  return {
    type: "Feature",
    geometry: { type: "LineString", coordinates },
    properties: { kind, tone },
  };
}

export function focusLineFeatures(row: SupplierRoute | null): FocusLineCollection {
  if (!row?.road) return KOSONG;
  const tone: "ok" | "fail" = row.safetyStatus === "fail" ? "fail" : "ok";
  const journey = row.journey;
  const progress = journey?.state === "sudah_tiba" ? 1 : journey?.progress ?? null;
  const split = lineSplit(row.road.coordinates, progress);
  if (!split) {
    return { type: "FeatureCollection", features: [garis(row.road.coordinates, "todo", tone)] };
  }
  const features: FocusLineFeature[] = [];
  if (split.done.length >= 2) features.push(garis(split.done, "done", tone));
  if (split.todo.length >= 2) features.push(garis(split.todo, "todo", tone));
  return { type: "FeatureCollection", features };
}
