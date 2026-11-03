/**
 * Riwayat kejadian per kiriman — logika MURNI, tanpa React/DOM.
 *
 * Menutup kesenjangan #12 riset (`docs/research/informasi-pengiriman-industri.md`
 * §2 & §5 no. 4): "riwayat kejadian per kiriman: panen → berangkat → uji mutu →
 * tiba, terbaru dulu, bertanggal", pola yang dipakai Oracle (kejadian terbaru di
 * baris paling atas) dan NN/g #11 ("tampilkan pembaruan sebelumnya lengkap dengan
 * tanggal").
 *
 * ATURAN YANG DIPEGANG (dan diuji):
 * 1. Hanya kejadian yang PUNYA WAKTU di server yang masuk daftar. Model kita
 *    belum menyimpan waktu uji keamanan (`safety_status` ada, waktunya tidak),
 *    jadi "uji mutu" TIDAK dikarang tanggalnya — mutu tetap tampil sebagai
 *    keadaan di kartu, bukan sebagai kejadian berwaktu di riwayat. Waktu
 *    penghitungan jalur (log sistem) juga bukan kejadian: ia jadi catatan kaki
 *    `shipmentRouteAudit()`.
 * 2. Bedakan "terjadi" dari "rencana". Estimasi tiba ditandai `kind: "rencana"`
 *    supaya tidak terbaca seolah barangnya sudah tiba.
 * 3. Terbaru dulu, dan setiap baris bertanggal lengkap (`formatDateTime`).
 */
import { formatDateTime } from "./datetime";
import { formatKg } from "./overview-format";
import { durationLabel, type SupplierRoute } from "./supplier-routes";

/** `terjadi` = sudah dilaporkan server; `rencana` = perkiraan yang belum terjadi. */
export type ShipmentEventKind = "terjadi" | "rencana";

export type ShipmentEvent = {
  key: "panen" | "berangkat" | "tiba" | "estimasi-tiba";
  /** Waktu kejadian (ISO) — selalu ada; kejadian tanpa waktu tidak ikut daftar. */
  at: string;
  /** Waktu lengkap siap tampil (WIB). */
  atLabel: string;
  title: string;
  detail: string | null;
  kind: ShipmentEventKind;
  tone: "ok" | "info";
};

/** Urutan kepentingan bila dua kejadian punya waktu sama (lebih besar = lebih dulu). */
const PRIORITAS: Record<ShipmentEvent["key"], number> = {
  tiba: 3,
  "estimasi-tiba": 2,
  berangkat: 1,
  panen: 0,
};

/**
 * Kejadian per kiriman, TERBARU DULU.
 *
 * Kosong bila server tidak melaporkan satu pun waktu — lebih baik tidak ada
 * blok riwayat daripada blok kosong berisi teka-teki.
 */
export function shipmentEvents(row: SupplierRoute): ShipmentEvent[] {
  const journey = row.journey;
  const daftar: ShipmentEvent[] = [];

  const tambah = (
    key: ShipmentEvent["key"],
    at: string | null | undefined,
    title: string,
    detail: string | null,
    kind: ShipmentEventKind,
    tone: ShipmentEvent["tone"]
  ) => {
    if (!at) return;
    const atLabel = formatDateTime(at);
    // Waktu yang tidak terbaca jangan masuk daftar: labelnya akan "—" dan
    // barisnya menyesatkan.
    if (atLabel === "—") return;
    daftar.push({ key, at, atLabel, title, detail, kind, tone });
  };

  tambah("panen", row.harvestedAt, "Panen dicatat", shipmentLoadLabel(row), "terjadi", "info");

  tambah(
    "berangkat",
    journey?.dispatchedAt,
    "Berangkat dari pemasok",
    row.road ? `Jalur jalan ${row.road.source.toUpperCase()}` : null,
    "terjadi",
    "info"
  );

  if (journey?.state === "sudah_tiba") {
    tambah("tiba", journey.etaAt, "Tiba di tujuan", "Perjalanan selesai.", "terjadi", "ok");
  } else if (journey?.etaAt) {
    tambah(
      "estimasi-tiba",
      journey.etaAt,
      "Estimasi tiba",
      journey.travelMin !== null ? `Waktu tempuh jalur ± ${durationLabel(journey.travelMin)}` : null,
      "rencana",
      "info"
    );
  }

  return daftar.sort((a, b) => {
    const waktu = Date.parse(b.at) - Date.parse(a.at);
    if (Number.isFinite(waktu) && waktu !== 0) return waktu;
    return PRIORITAS[b.key] - PRIORITAS[a.key];
  });
}

/** Kalimat jumlah untuk kepala blok riwayat. */
export function shipmentTimelineLabel(events: readonly ShipmentEvent[]): string {
  const terjadi = events.filter((e) => e.kind === "terjadi").length;
  const rencana = events.length - terjadi;
  if (!events.length) return "Belum ada kejadian yang tercatat server.";
  const bagian = [`${terjadi} kejadian tercatat`];
  if (rencana > 0) bagian.push(`${rencana} perkiraan`);
  return bagian.join(" · ");
}

/** Ringkasan muatan untuk baris riwayat panen (dipakai bila perlu). */
export function shipmentLoadLabel(row: SupplierRoute): string | null {
  if (row.quantityKg === null) return null;
  const komoditas = row.commodity ? ` ${row.commodity}` : "";
  return `${formatKg(row.quantityKg)}${komoditas}`;
}

/**
 * Catatan kaki audit geometri — SENGAJA bukan baris kejadian.
 *
 * Waktu ini adalah kapan SERVER menghitung angka jalur, bukan kejadian di
 * lapangan: pada demo ia selalu "hari ini", sehingga kalau dijadikan baris
 * kejadian ia akan duduk di ATAS kejadian "Tiba" yang bertanggal lebih awal dan
 * membuat garis waktu terbaca seolah rusak. Nilainya tetap dibuka (riset:
 * "kapan angka dihitung" itu bagian dari jejak audit) tapi di tempatnya.
 */
export function shipmentRouteAudit(row: SupplierRoute): string | null {
  const road = row.road;
  if (!road) return null;
  const atLabel = formatDateTime(road.fetchedAt);
  if (atLabel === "—") return null;
  const km = road.distanceKm.toFixed(1).replace(".", ",");
  return `Angka jalur dihitung server ${atLabel} · ${road.source.toUpperCase()} ${km} km`;
}
