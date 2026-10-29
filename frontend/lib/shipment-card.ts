/**
 * Kartu "Informasi pengiriman" (Arah A) — logika MURNI, tanpa React/DOM.
 *
 * Sumber keputusan: `docs/research/informasi-pengiriman-industri.md` (riset 16 Okt
 * 2026). Yang diambil dari pembanding industri:
 * - stepper tahap seperti aplikasi kurir (Gojek membuang peta live demi stepper),
 * - pil status ramping + sisa waktu dalam bahasa manusia,
 * - informasi terbaru paling menonjol, sisanya di balik panel,
 * - jarak JALAN vs jarak lurus selalu berdampingan (jejak audit; pola Oracle
 *   "garis antar-simpul memuat jarak + waktu").
 *
 * Yang TIDAK diambil: simpangan "terlambat N menit" — model kita belum punya
 * waktu tiba yang dijanjikan, jadi angka simpangan apa pun akan karangan.
 *
 * Aturan repo yang dipegang modul ini (dan diuji di tests/shipment-card.test.ts):
 * 1. Tidak ada angka karangan: geometri jalur hilang → sebut sebab dari server
 *    (`road_missing_reason`), jangan tulis "0 km".
 * 2. "Belum ada data" ≠ "terlambat": keadaan tak pasti dapat nada netral.
 * 3. Keadaan perjalanan diambil apa adanya dari server (`journey.state`), tidak
 *    diterjemahkan ulang di klien.
 */
import { kodeWilayah } from "./wilayah";
import { formatClockWib, formatDate, formatDateTime, formatMomentWib } from "./datetime";
import { formatKg } from "./overview-format";
import {
  durationLabel,
  journeyTone,
  MISSING_REASON_LABEL,
  roadKmLabel,
  type RouteJourneyTone,
  type SupplierRoute,
} from "./supplier-routes";

export type ShipmentStepKey = "harvest" | "dispatch" | "transit" | "arrive";
export type ShipmentStepState = "done" | "active" | "todo" | "unknown";

export type ShipmentStep = {
  key: ShipmentStepKey;
  label: string;
  state: ShipmentStepState;
  /** Keterangan pendek di bawah tahap (jam berangkat, persentase jalur). */
  note: string | null;
};

export type ShipmentHeadline = { tone: RouteJourneyTone; label: string };
export type ShipmentFactRow = { label: string; value: string };
export type ShipmentSafetyChip = { tone: "fail"; label: string };

const STEP_LABELS: Record<ShipmentStepKey, string> = {
  harvest: "Dipanen",
  dispatch: "Berangkat",
  transit: "Di jalan",
  arrive: "Tiba",
};

/** Judul kotak: "CV Cipinang Boga Utama → SPPG JKT". */
export function shipmentTitle(row: SupplierRoute): string {
  return `${row.supplierName} → ${kodeWilayah(row.destinationName)}`;
}

/** Alasan jalur belum ada dalam bahasa pengguna (fallback: apa yang server kirim). */
function alasanJalur(row: SupplierRoute): string {
  const kode = row.missingReason;
  if (!kode) return "rute jalan belum tersedia";
  return MISSING_REASON_LABEL[kode] ?? kode;
}

/**
 * Pil status: keadaan + sisa waktu.
 *
 * "Belum berangkat" sengaja TIDAK diberi jam tiba — jam itu tidak ada di basis
 * data, dan menuliskannya akan terbaca seolah barangnya sudah di jalan.
 */
export function shipmentHeadline(
  row: SupplierRoute,
  now: Date = new Date()
): ShipmentHeadline {
  const journey = row.journey;
  if (!journey) {
    return { tone: "unknown", label: "Perjalanan belum dilaporkan" };
  }
  const tone = journeyTone(journey.state);
  switch (journey.state) {
    case "di_jalan": {
      const sisa = journey.remainingMin !== null ? ` · ${durationLabel(journey.remainingMin)} lagi` : "";
      return { tone, label: `Di jalan${sisa}` };
    }
    case "sudah_tiba":
      return {
        tone,
        label: journey.etaAt
          ? `Sudah tiba ${formatMomentWib(journey.etaAt, now)}`
          : "Sudah tiba",
      };
    case "belum_berangkat":
      return { tone, label: "Belum berangkat" };
    default:
      return { tone, label: journey.stateLabel || "Perjalanan belum bisa dipastikan" };
  }
}

/** Persentase jalur — hanya bila server mengirimnya (bukan 0% karangan). */
export function shipmentProgressLabel(row: SupplierRoute): string | null {
  const journey = row.journey;
  if (!journey || journey.state !== "di_jalan" || journey.progress === null) return null;
  return `${Math.round(journey.progress * 100)}% jalur`;
}

function transitState(row: SupplierRoute): ShipmentStepState {
  const journey = row.journey;
  if (!journey) return "unknown";
  if (journey.state === "di_jalan") return "active";
  if (journey.state === "sudah_tiba") return "done";
  if (journey.state === "belum_berangkat") return "todo";
  return "unknown";
}

function transitNote(row: SupplierRoute): string | null {
  const journey = row.journey;
  if (!journey) return "perjalanan belum dilaporkan";
  const persen = shipmentProgressLabel(row);
  if (persen) return persen;
  if (journey.state === "di_jalan") {
    return journey.etaAt ? `tiba ± ${formatClockWib(journey.etaAt)}` : null;
  }
  if (journey.state === "tidak_diketahui") return "estimasi tiba belum ada";
  // "sudah tiba" & "belum berangkat" tidak butuh keterangan di stepper: pil
  // status sudah menyebutnya, dan kalimat keputusan menjelaskan sebabnya.
  return null;
}

/** Empat tahap perjalanan; keadaan tak pasti ditandai `unknown`, bukan diklaim. */
export function shipmentSteps(row: SupplierRoute): ShipmentStep[] {
  const journey = row.journey;
  const berangkat = Boolean(journey?.dispatchedAt);
  const states: ShipmentStepState[] = [
    row.harvestedAt ? "done" : "todo",
    berangkat ? "done" : "todo",
    transitState(row),
    journey?.state === "sudah_tiba" ? "done" : "todo",
  ];
  return (Object.keys(STEP_LABELS) as ShipmentStepKey[]).map((key, index) => ({
    key,
    label: STEP_LABELS[key],
    state: states[index],
    note: key === "transit" ? transitNote(row) : null,
  }));
}

/**
 * Satu baris angka kunci. Tanpa geometri jalan, yang ditulis adalah jarak LURUS
 * dengan labelnya sendiri — garis lurus yang menyamar sebagai rute jalan akan
 * menyesatkan (aturan yang sama dipakai lapisan peta).
 */
export function shipmentKeyFacts(row: SupplierRoute): string[] {
  const facts: string[] = [];
  if (row.road) {
    facts.push(`${roadKmLabel(row.road.distanceKm)} jalan`);
    facts.push(`± ${durationLabel(row.road.durationMin)}`);
  } else if (row.straightKm !== null) {
    facts.push(`${roadKmLabel(row.straightKm)} lurus (jarak udara)`);
  }
  if (row.quantityKg !== null) {
    const komoditas = row.commodity ? ` ${row.commodity}` : "";
    facts.push(`${formatKg(row.quantityKg)}${komoditas}`);
  }
  return facts;
}

/** Kalimat keputusan di bawah angka kunci (satu kalimat, bukan tiga baris). */
export function shipmentVerdict(
  row: SupplierRoute,
  now: Date = new Date()
): string {
  const journey = row.journey;
  if (!journey) {
    return "Perjalanan belum dilaporkan — waktu berangkat dan estimasi tiba belum bisa dipastikan.";
  }
  if (!row.road) {
    return `Jalur jalan ${alasanJalur(row)} — jarak tempuh & estimasi tiba belum bisa dipastikan.`;
  }
  if (journey.state === "sudah_tiba") {
    return journey.etaAt
      ? `Tiba ${formatMomentWib(journey.etaAt, now)} — perjalanan selesai.`
      : "Perjalanan selesai.";
  }
  if (journey.state === "di_jalan" && journey.etaAt) {
    const dasar = `Tiba ± ${formatClockWib(journey.etaAt)} WIB`;
    if (journey.arrivesBeforeUsableUntil === true && journey.usableUntil) {
      return `${dasar}, masih sebelum batas layak ${formatDate(journey.usableUntil)}.`;
    }
    if (journey.arrivesBeforeUsableUntil === false) {
      return `${dasar}, melewati batas layak pakai (dilaporkan apa adanya).`;
    }
    return `${dasar}.`;
  }
  if (journey.state === "belum_berangkat") {
    const tempuh =
      journey.travelMin !== null
        ? ` Waktu tempuh jalur ± ${durationLabel(journey.travelMin)} (OSRM).`
        : "";
    return `Barang masih di pemasok — jam berangkat belum tercatat, jadi estimasi tiba belum ada.${tempuh}`;
  }
  return "Sudah berangkat, tetapi jalur jalannya belum ada — estimasi tiba belum bisa dipastikan.";
}

/** Rincian di balik panel lipat: jejak audit jalur, muatan, dan waktu. */
export function shipmentDetails(row: SupplierRoute): ShipmentFactRow[] {
  const journey = row.journey;
  const rows: ShipmentFactRow[] = [];
  rows.push({
    label: "Jalur jalan",
    value: row.road
      ? `${roadKmLabel(row.road.distanceKm)} · ± ${durationLabel(row.road.durationMin)} (${row.road.source.toUpperCase()})`
      : `belum ada — ${alasanJalur(row)}`,
  });
  const rasio =
    row.road && row.road.ratioVsStraight !== null
      ? ` · jalur ${row.road.ratioVsStraight.toFixed(2).replace(".", ",")}× jarak lurus`
      : "";
  rows.push({
    label: "Jarak lurus",
    value: row.straightKm !== null ? `${roadKmLabel(row.straightKm)}${rasio}` : "belum ada",
  });
  rows.push({
    label: "Muatan",
    value:
      row.quantityKg !== null
        ? `${formatKg(row.quantityKg)}${row.commodity ? ` ${row.commodity}` : ""}`
        : "belum dilaporkan",
  });
  rows.push({ label: "Batch", value: row.batchId ?? "belum ada" });
  rows.push({
    label: "Panen",
    value: row.harvestedAt ? formatDateTime(row.harvestedAt) : "belum ada",
  });
  rows.push({
    label: "Berangkat",
    value: journey?.dispatchedAt
      ? formatDateTime(journey.dispatchedAt)
      : "belum berangkat (barang masih di pemasok)",
  });
  rows.push({
    label: "Estimasi tiba",
    value: journey?.etaAt ? formatDateTime(journey.etaAt) : "belum ada",
  });
  rows.push({
    label: "Masa layak",
    value: row.usableUntil ? formatDate(row.usableUntil) : "belum ada",
  });
  if (row.safetyStatus === "fail") {
    rows.push({ label: "Mutu kiriman", value: "GAGAL UJI keamanan (dilaporkan apa adanya)" });
  }
  return rows;
}

/** Mutu kiriman hanya muncul saat bermasalah — tidak menambah keramaian. */
export function shipmentSafetyChip(row: SupplierRoute): ShipmentSafetyChip | null {
  if (row.safetyStatus !== "fail") return null;
  return { tone: "fail", label: "Gagal uji keamanan" };
}

/** Urutan mendesak: yang sedang bergerak dulu, yang sudah tiba paling akhir. */
export function shipmentUrgency(row: SupplierRoute): number {
  switch (row.journey?.state) {
    case "di_jalan":
      return 0;
    case "belum_berangkat":
      return 1;
    case "tidak_diketahui":
      return 2;
    case "sudah_tiba":
      return 3;
    default:
      return 4;
  }
}

function etaMillis(row: SupplierRoute): number {
  const eta = row.journey?.etaAt;
  if (!eta) return Number.POSITIVE_INFINITY;
  const waktu = new Date(eta).getTime();
  return Number.isFinite(waktu) ? waktu : Number.POSITIVE_INFINITY;
}

/**
 * Pilih kiriman paling perlu dibaca lebih dulu, dibatasi `maks` baris.
 *
 * `hanya` (opsional) menyaring LEBIH DULU: baris di luar cakupan (mis. bukan
 * menuju lokasi yang sedang dibuka) tidak relevan, jadi ia TIDAK dihitung
 * sebagai "disembunyikan" — angka `hidden` hanya berbicara tentang baris yang
 * memang termasuk cakupan tapi tidak ditampilkan.
 *
 * Sisanya dihitung (`hidden`), bukan dihapus diam-diam — aturan yang sama dengan
 * kotak "Info map" yang sudah ada.
 */
export function pickShipments(
  rows: readonly SupplierRoute[],
  maks: number,
  hanya?: (row: SupplierRoute) => boolean
): { rows: SupplierRoute[]; hidden: number } {
  const cakupan = hanya ? rows.filter((row) => hanya(row)) : rows;
  const urut = [...cakupan].sort((a, b) => {
    const mendesak = shipmentUrgency(a) - shipmentUrgency(b);
    if (mendesak !== 0) return mendesak;
    const gagalA = a.safetyStatus === "fail" ? 0 : 1;
    const gagalB = b.safetyStatus === "fail" ? 0 : 1;
    if (gagalA !== gagalB) return gagalA - gagalB;
    return etaMillis(a) - etaMillis(b);
  });
  const batas = Math.max(0, maks);
  return { rows: urut.slice(0, batas), hidden: Math.max(0, urut.length - batas) };
}
