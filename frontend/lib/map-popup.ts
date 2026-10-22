/**
 * Model tampilan popup peta — MURNI (tanpa DOM), supaya isi popup bisa diuji
 * tanpa memasang MapLibre.
 *
 * Latar (permintaan pemilik 21 Okt 2026): popup SPPG/pemasok/kiriman tampil
 * sebagai gelembung teks polos. Tiga jenis penanda itu membawa cerita berbeda,
 * jadi tiap popup sekarang punya "kicker", angka utama, metrik pendek, dan
 * maksimal tiga fakta pendukung — hirarki yang sama, warna aksen yang berbeda.
 *
 * Aturan yang dipegang:
 *  - Angka tetap dari data server; di sini hanya cara menuliskannya.
 *  - Warna tidak pernah satu-satunya penanda: setiap nada punya kata (chip).
 *  - Popup = jawaban pendek; rincian panjang tetap di panel halaman.
 */
import { formatClockWib, formatDate } from "./datetime";
import {
  dataSourceNote,
  formatBalanceGap,
  formatBalanceStatus,
  formatKg,
  type BalanceMapLocation,
} from "./overview-format";
import { pinTone } from "./map-console";
import {
  certificationLabel,
  distanceLabel,
  reachLabel,
  reliabilityLabel,
  type SupplierPinRow,
} from "./supplier-pins";
import {
  MISSING_REASON_LABEL,
  roadKmLabel,
  routePopupLines,
  type SupplierRoute,
} from "./supplier-routes";

export type MapPopupKind = "sppg" | "supplier" | "truck" | "route";
export type MapPopupTone = "danger" | "safe" | "warning" | "neutral" | "accent";

export type MapPopupMetric = { label: string; value: string };

export type MapPopupView = {
  kind: MapPopupKind;
  kicker: string;
  title: string;
  chip: string;
  tone: MapPopupTone;
  /** Angka utama popup + labelnya. */
  hero: { label: string; value: string };
  metrics: MapPopupMetric[];
  /** Bar 0–100 + kalimat pendek di bawahnya. */
  meter: { pct: number; text: string } | null;
  /** Kotak sorot: kiriman aktif, exclusion, atau peringatan mutu. */
  callout: { text: string; tone: "accent" | "danger" | "warning" } | null;
  facts: string[];
  note: string | null;
  /** Nama aksesibel untuk pembaca layar (marker memakai teks yang sama). */
  aria: string;
};

function angka(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function toneSPPG(status: string): MapPopupTone {
  const tone = pinTone(status);
  if (tone === "shortage") return "danger";
  if (tone === "surplus") return "safe";
  if (tone === "balanced") return "warning";
  return "neutral";
}

/** Popup SPPG: keadaan neraca + dua angka yang membentuknya. */
export function sppgPopupView(location: BalanceMapLocation): MapPopupView {
  const supply = angka(location.supply_kg);
  const demand = angka(location.demand_kg);
  const pct =
    supply !== null && demand !== null && demand > 0
      ? Math.max(0, Math.min(100, Math.round((supply / demand) * 100)))
      : 0;
  const note = dataSourceNote(location);
  return {
    kind: "sppg",
    kicker: `SPPG · ${location.region?.trim() || "lokasi jaringan"}`,
    title: location.location,
    chip: formatBalanceStatus(location.status),
    tone: toneSPPG(location.status),
    hero: { label: "Selisih pasokan", value: formatBalanceGap(location) },
    metrics: [
      { label: "Pasokan", value: formatKg(location.supply_kg) },
      { label: "Permintaan", value: formatKg(location.demand_kg) },
    ],
    meter:
      supply !== null && demand !== null && demand > 0
        ? { pct, text: `Pasokan menutup ${pct}% kebutuhan` }
        : null,
    callout: null,
    facts: [],
    note,
    aria: `${location.location}: ${formatKg(location.supply_kg)} pasokan, ${formatKg(
      location.demand_kg
    )} permintaan, ${formatBalanceGap(location)}${note ? `, ${note}` : ""}`,
  };
}

/** Popup pemasok: keandalan, sertifikasi, jangkauan, dan kiriman aktifnya. */
export function supplierPopupView(
  row: SupplierPinRow,
  reachKm: number | null
): MapPopupView {
  const reliabilitas = reliabilityLabel(row.reliability);
  const jangkauan = reachLabel(row, reachKm);
  const callout: MapPopupView["callout"] = row.excludedAtHub
    ? {
        text:
          row.excludedScopes.length > 0
            ? `Dikecualikan di: ${row.excludedScopes.join(", ")}`
            : "Dikecualikan pada SPPG ini",
        tone: "danger",
      }
    : row.shipping
      ? {
          text: `Sedang mengirim ${row.shipping.count} kiriman · ${formatKg(
            row.shipping.totalKg
          )}${row.shipping.commodities.length ? ` ${row.shipping.commodities.join(", ")}` : ""}`,
          tone: "accent",
        }
      : null;
  return {
    kind: "supplier",
    kicker: `Pemasok · hub ${row.hub}`,
    title: row.name,
    chip: row.excludedAtHub ? "Dikecualikan" : row.shipping ? "Sedang mengirim" : "Aktif",
    tone: row.excludedAtHub ? "danger" : "accent",
    hero: { label: "Keandalan pengiriman", value: reliabilitas },
    metrics: [
      { label: "Komoditas", value: row.commodity ?? "—" },
      { label: "Sertifikasi", value: certificationLabel(row.certification) },
      { label: "Jarak", value: distanceLabel(row.distanceKm) },
    ],
    meter:
      row.reliability !== null
        ? {
            pct: Math.max(0, Math.min(100, Math.round(row.reliability * 100))),
            text: `Skor keandalan ${reliabilitas}`,
          }
        : null,
    callout,
    facts: [],
    note: null,
    aria: `${row.name}, pemasok ${row.commodity ?? "tanpa komoditas"} di hub ${row.hub}, keandalan ${reliabilitas}, ${jangkauan}`,
  };
}

function progressPct(row: SupplierRoute): number | null {
  const progress = row.journey?.progress;
  if (progress === null || progress === undefined || !Number.isFinite(progress)) return null;
  return Math.max(0, Math.min(100, Math.round(progress * 100)));
}

/** Fakta versi ringkas untuk popup truk: metrik di atas sudah memuat jarak
 *  dan ETA, jadi jangan diulang — popup harus muat di peta pendek. */
function factsTrukRingkas(row: SupplierRoute): string[] {
  const facts: string[] = [];
  // "Sisa ± N menit" sudah ditulis meter; mengulanginya di fakta membuat
  // kartu tinggi tanpa informasi baru (terukur: popup 293 → 273 px).
  if (!row.road) {
    const reason = row.missingReason
      ? MISSING_REASON_LABEL[row.missingReason] ?? row.missingReason
      : "belum disinkronkan";
    facts.push(`Jalur jalan: belum ada — ${reason}`);
  }
  if (row.usableUntil) facts.push(`Layak dipakai s/d ${formatDate(row.usableUntil)}`);
  return facts;
}

/** Popup truk: posisi perjalanan + muatan; titik beratnya progres, bukan kg. */
export function truckPopupView(row: SupplierRoute): MapPopupView {
  const pct = progressPct(row);
  const journey = row.journey;
  const sisaMenit = journey?.remainingMin ?? null;
  const keadaan = journey?.stateLabel ?? "keadaan belum tersedia";
  const callout: MapPopupView["callout"] =
    row.safetyStatus === "fail"
      ? { text: "Mutu kiriman: GAGAL UJI keamanan — dilaporkan apa adanya", tone: "danger" }
      : journey?.state === "belum_berangkat"
        ? { text: "Belum berangkat — barang masih di pemasok", tone: "warning" }
        : journey?.state === "sudah_tiba"
          ? { text: "Sudah tiba di SPPG tujuan", tone: "accent" }
          : null;
  return {
    kind: "truck",
    kicker: `Kiriman · ${keadaan}`,
    title: `${row.supplierName} → ${row.destinationName}`,
    chip: row.commodity ?? "Kiriman",
    tone: row.safetyStatus === "fail" ? "danger" : "accent",
    hero: { label: "Perjalanan", value: pct === null ? "—" : `${pct}%` },
    metrics: [
      { label: "Muatan", value: formatKg(row.quantityKg) },
      { label: "Jarak", value: roadKmLabel(row.road?.distanceKm ?? null) },
      {
        label: "Estimasi tiba",
        value: journey?.etaAt ? `${formatClockWib(journey.etaAt)} WIB` : "—",
      },
    ],
    meter:
      pct === null
        ? null
        : {
            pct,
            text:
              sisaMenit !== null && sisaMenit > 0
                ? `Sisa ± ${Math.round(sisaMenit)} menit`
                : `${pct}% perjalanan ditempuh`,
          },
    callout,
    facts: factsTrukRingkas(row),
    note: null,
    aria: `Mobil kiriman ${row.supplierName} menuju ${row.destinationName}, ${keadaan}${
      pct === null ? "" : `, ${pct}% perjalanan`
    }`,
  };
}

/** Popup garis jalur: fakta lengkap yang sudah ada, dibingkai seperti truk. */
export function routePopupView(row: SupplierRoute): MapPopupView {
  const truk = truckPopupView(row);
  return {
    ...truk,
    kind: "route",
    kicker: `Jalur kiriman · ${row.journey?.stateLabel ?? "keadaan belum tersedia"}`,
    facts: routePopupLines(row),
    aria: `Jalur ${row.supplierName} menuju ${row.destinationName}`,
  };
}
