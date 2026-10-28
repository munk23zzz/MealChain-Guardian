// Jejak kepercayaan (Overview) — empat bukti yang bisa diperiksa ulang.
//
// Kartu ini menjawab satu pertanyaan juri/pengguna: "kenapa saya harus percaya
// angka di halaman ini?" Empat jawabannya: rantai ledger utuh, batch yang lolos
// uji, keputusan yang benar-benar tereksekusi, dan node yang melaporkan angka
// (bukan 0 hasil pengisian).
//
// Prinsip yang dipegang (sama dengan lib/overview-bento.ts dan overview-kpi.ts):
//   * data tidak terbaca → "—" + alasannya, BUKAN 0 yang terbaca "tidak ada";
//   * 0 hanya sah bila terukur (contoh: 0 node tanpa catatan);
//   * setiap angka rasio menuliskan totalnya ("101/118") supaya skala yang
//     dibicarakan jelas — termasuk saat peran hanya melihat satu lokasi.
//
// Modul ini murni (tanpa DOM, tanpa fetch) dan diuji di tests/trust-trail.test.ts.
import { tanpaCatatan, type BalanceMapLocation } from "./overview-format";

export type TrustTone = "ok" | "warn" | "plain";

export type TrustMetric = {
  id: "ledger" | "batch" | "eksekusi" | "node";
  label: string;
  /** Angka utama, sudah diformat; "—" bila tidak terbaca. */
  value: string;
  /** Total pembanding ("/118", "blok"); null bila tidak berlaku. */
  unit: string | null;
  /** Kalimat keadaan di bawah angka — sebab, bukan hiasan. */
  foot: string;
  tone: TrustTone;
  /** Kata keadaan pendek untuk pembaca cepat ("utuh", "perlu tinjau"). */
  state: string;
};

export type TrustLedger = {
  valid?: boolean;
  blocks?: number | null;
  broken_at?: number | null;
  entity_blocks?: number | null;
  linked_blocks?: number | null;
  orphan_blocks?: number | null;
  anchor?: { configured?: boolean; match?: boolean | null } | null;
} | null;

export type TrustInput = {
  /** GET /ledger/verify (sudah diserap kegagalannya oleh useToday). */
  ledger?: TrustLedger;
  /** GET /batches — hanya `safety_status` + `quarantine_status` yang dibaca. */
  batches?: readonly unknown[] | null;
  /** Daftar keputusan yang sudah dimuat halaman (GET /decisions). */
  decisions?: readonly { status?: string | null }[] | null;
  /** Baris GET /balance/map untuk komoditas yang sedang dilihat. */
  locations?: readonly BalanceMapLocation[] | null;
};

const DASH = "—";

/** Status yang masih menunggu tindakan manusia (bukan hasil akhir). */
const OPEN_STATUSES = new Set([
  "proposed",
  "pending_approval",
  "approved",
  "verifier_flagged",
  "review_only",
]);

/** Pemisah ribuan gaya Indonesia tanpa bergantung ICU peramban/Node. */
function ribuan(value: number): string {
  const bulat = Math.trunc(Math.abs(value));
  const teks = String(bulat).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return value < 0 ? `-${teks}` : teks;
}

/** Angka dari API; bukan angka → null (tidak diubah jadi 0). */
function angka(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function daftar<T>(value: readonly T[] | null | undefined): T[] | null {
  return Array.isArray(value) ? (value as T[]) : null;
}

function teks(value: unknown): string {
  return value === null || value === undefined ? "" : String(value).trim().toLowerCase();
}

function ledgerMetric(ledger: TrustLedger): TrustMetric {
  const blok = angka(ledger?.blocks);
  if (!ledger || blok === null) {
    return {
      id: "ledger",
      label: "Blok ledger",
      value: DASH,
      unit: null,
      foot: "verifikasi rantai belum termuat",
      tone: "plain",
      state: "menunggu",
    };
  }

  const valid = ledger.valid === true;
  const orphan = angka(ledger.orphan_blocks) ?? 0;
  const tertaut = angka(ledger.linked_blocks);
  const entitas = angka(ledger.entity_blocks);
  const patah = angka(ledger.broken_at);
  const anchor = ledger.anchor ?? null;
  const anchorCocok = anchor?.match === true;
  const anchorBeda = anchor?.match === false;

  const bagian: string[] = [];
  if (!valid) {
    bagian.push(patah !== null ? `putus di blok ${ribuan(patah)}` : "rantai tidak utuh");
  } else if (orphan > 0) {
    bagian.push(`${ribuan(orphan)} blok yatim`);
  } else if (tertaut !== null && entitas !== null) {
    bagian.push(`${ribuan(tertaut)} tertaut ke keputusan`);
  } else {
    bagian.push("genesis sampai kepala rantai");
  }
  if (anchorCocok) bagian.push("checkpoint cocok");
  else if (anchorBeda) bagian.push("checkpoint tidak cocok");
  else if (anchor?.configured === true) bagian.push("checkpoint belum dicek");

  const bersih = valid && orphan === 0 && !anchorBeda;
  return {
    id: "ledger",
    label: "Blok ledger",
    value: ribuan(blok),
    unit: "blok",
    foot: bagian.join(" · "),
    tone: bersih ? "ok" : "warn",
    state: valid ? (bersih ? "utuh" : "sebagian") : "putus",
  };
}

function batchMetric(batches: readonly unknown[] | null | undefined): TrustMetric {
  const rows = daftar(batches);
  if (!rows || rows.length === 0) {
    return {
      id: "batch",
      label: "Batch lolos uji",
      value: DASH,
      unit: null,
      foot: "belum ada batch terbaca",
      tone: "plain",
      state: "menunggu",
    };
  }

  // Kategori di bawah ini saling meniadakan (satu batch masuk tepat satu
  // kategori), jadi `lolos + gagal + perluRuji + ditahan + lain` selalu sama
  // dengan jumlah baris yang ditampilkan sebagai /total. Versi sebelumnya
  // menghitung batch gagal sekaligus sebagai ditahan, sehingga penjelasannya
  // tidak pernah menjumlah ke totalnya.
  let lolos = 0;
  let gagal = 0;
  let perluRuji = 0;
  let ditahan = 0;
  let lain = 0;
  for (const row of rows as { safety_status?: unknown; quarantine_status?: unknown }[]) {
    const status = teks(row?.safety_status);
    if (teks(row?.quarantine_status) === "quarantined") {
      // Batch ditahan BUKAN stok yang boleh dipakai, seberapa pun hasil ujinya.
      ditahan += 1;
    } else if (status === "fail") gagal += 1;
    else if (status === "needs_verification") perluRuji += 1;
    else if (status === "pass") lolos += 1;
    else lain += 1;
  }

  const bagian: string[] = [];
  if (gagal > 0) bagian.push(`${ribuan(gagal)} gagal`);
  if (perluRuji > 0) bagian.push(`${ribuan(perluRuji)} belum diuji`);
  if (ditahan > 0) bagian.push(`${ribuan(ditahan)} ditahan`);
  if (lain > 0) bagian.push(`${ribuan(lain)} tanpa status`);

  const bermasalah = bagian.length > 0;
  return {
    id: "batch",
    label: "Batch lolos uji",
    value: ribuan(lolos),
    unit: `/${ribuan(rows.length)}`,
    foot: bermasalah ? bagian.join(" · ") : "semua batch lolos uji",
    tone: bermasalah ? "warn" : "ok",
    state:
      gagal > 0 ? "perlu tinjau" : ditahan > 0 ? "ada ditahan" : perluRuji > 0 ? "belum diuji" : "bersih",
  };
}

function eksekusiMetric(
  decisions: readonly { status?: string | null }[] | null | undefined
): TrustMetric {
  const rows = daftar(decisions);
  if (!rows || rows.length === 0) {
    return {
      id: "eksekusi",
      label: "Keputusan tereksekusi",
      value: DASH,
      unit: null,
      foot: "belum ada keputusan terbaca",
      tone: "plain",
      state: "menunggu",
    };
  }

  let tereksekusi = 0;
  let menunggu = 0;
  let ditolak = 0;
  let selesaiLain = 0;
  for (const row of rows) {
    const status = teks(row?.status);
    if (status === "executed") tereksekusi += 1;
    else if (status === "rejected") ditolak += 1;
    else if (OPEN_STATUSES.has(status)) menunggu += 1;
    else selesaiLain += 1;
  }

  // Kalimat penjelas harus menutup selisih dengan /total: kalau ada status yang
  // tidak masuk hitungan mana pun, ia disebut ("9 sudah selesai"), bukan dibiarkan
  // menggantung sehingga angka 7/49 tidak bisa dicocokkan pembaca.
  const bagian: string[] = [];
  if (menunggu > 0) bagian.push(`${ribuan(menunggu)} menunggu tindakan`);
  if (ditolak > 0) bagian.push(`${ribuan(ditolak)} ditolak`);
  if (selesaiLain > 0) bagian.push(`${ribuan(selesaiLain)} sudah selesai`);
  const foot = bagian.length > 0 ? bagian.join(" · ") : "tidak ada yang menunggu tindakan";

  return {
    id: "eksekusi",
    label: "Keputusan tereksekusi",
    value: ribuan(tereksekusi),
    unit: `/${ribuan(rows.length)}`,
    foot,
    tone: tereksekusi > 0 ? "ok" : "plain",
    state: tereksekusi > 0 ? "berjalan" : "belum ada",
  };
}

function nodeMetric(
  locations: readonly BalanceMapLocation[] | null | undefined
): TrustMetric {
  const rows = daftar(locations);
  if (!rows || rows.length === 0) {
    return {
      id: "node",
      label: "Node tanpa angka",
      value: DASH,
      unit: null,
      foot: "belum ada node pada komoditas ini",
      tone: "plain",
      state: "menunggu",
    };
  }

  // `tidak_ada_baris` = angka 0 di baris itu hasil pengisian, bukan pengukuran.
  const tanpaCatatanJumlah = rows.filter(
    (row) => tanpaCatatan(row?.supply_state) || tanpaCatatan(row?.demand_state)
  ).length;
  const lengkap = tanpaCatatanJumlah === 0;

  return {
    id: "node",
    label: "Node tanpa angka",
    value: ribuan(tanpaCatatanJumlah),
    unit: `/${ribuan(rows.length)}`,
    foot: lengkap
      ? "semua node melaporkan angka"
      : `${ribuan(tanpaCatatanJumlah)} node tanpa catatan`,
    tone: lengkap ? "ok" : "warn",
    state: lengkap ? "lengkap" : "ada celah",
  };
}

/** Empat metrik jejak kepercayaan, urutan tetap: ledger → batch → eksekusi → node. */
export function trustTrail(input: TrustInput): TrustMetric[] {
  return [
    ledgerMetric(input.ledger ?? null),
    batchMetric(input.batches),
    eksekusiMetric(input.decisions),
    nodeMetric(input.locations),
  ];
}

/**
 * Keadaan satu-kata untuk kepala kartu.
 *
 * Prioritas: ada yang belum terbaca (`plain`) menang atas "perlu tinjau", karena
 * "terverifikasi" tidak boleh ditulis sementara satu bukti belum termuat.
 */
export function trustSummary(metrics: readonly TrustMetric[]): {
  tone: TrustTone;
  label: string;
} {
  if (metrics.some((metric) => metric.tone === "plain")) {
    return { tone: "plain", label: "sebagian belum terbaca" };
  }
  if (metrics.some((metric) => metric.tone === "warn")) {
    return { tone: "warn", label: "perlu tinjau" };
  }
  return { tone: "ok", label: "terverifikasi" };
}
