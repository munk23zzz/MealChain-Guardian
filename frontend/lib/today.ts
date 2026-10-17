// Langkah 3 (arah Roy 2026-10-11): logika murni halaman "Hari Ini".
//
// Halaman ini merekap operasi hari berjalan dari data NYATA (GET /decisions,
// /batches, /balance/map, /kpi, /ledger/verify). Semua fungsi menerima `now`
// sebagai argumen supaya hasilnya bisa diuji dan tidak menimbulkan selisih
// hidrasi antara HTML server dan render klien.
//
// Dua aturan yang dipegang di seluruh berkas ini:
// 1. Nilai yang tidak diketahui ditulis "—" dan TIDAK PERNAH diganti 0.
// 2. Data yang tanggalnya tidak bisa dibaca tidak diklaim apa pun (tidak
//    dianggap kedaluwarsa, tidak juga aman) — lebih baik hilang dari daftar
//    daripada menyesatkan.
import { ACTIONABLE_STATUSES } from "./topbar";
import { formatKg } from "./overview-format";
import { ZONA_DEFAULT, zonaLabel } from "./jam";

/** Ambang "segera kedaluwarsa" untuk batch (jam). */
export const DUE_SOON_HOURS = 48;

export type TodayDecision = {
  decision_id?: string;
  decision_type?: string | null;
  status?: string | null;
  quantity_kg?: number | string | null;
  expires_at?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
};

export type TodayBatch = {
  id?: string;
  location?: string | null;
  commodity?: string | null;
  quantity_kg?: number | string | null;
  // GET /batches mengirim `safety_status` (backend/app/api/batches.py:53);
  // `food_safety_status` tidak pernah ada dan dulu membuat label safety hilang.
  safety_status?: string | null;
  freshness_score?: number | string | null;
  usable_until?: string | null;
  [key: string]: unknown;
};

export type TodayLocation = {
  location?: string | null;
  region?: string | null;
  status?: string | null;
  shortage_kg?: number | string | null;
  [key: string]: unknown;
};

const ACTIONABLE_SET = new Set<string>(ACTIONABLE_STATUSES);

/** Epoch ms dari nilai tanggal apa pun; null kalau tidak bisa dibaca. */
function timeOf(value: unknown): number | null {
  if (value == null || value === "") return null;
  const ms = new Date(String(value)).getTime();
  return Number.isFinite(ms) ? ms : null;
}

/** Durasi dalam bahasa manusia: "5 mnt", "2 jam 6 mnt", "2 hari 2 jam". */
function humanDuration(ms: number): string {
  if (ms < 60 * 1000) return "kurang dari 1 mnt";
  const minutes = Math.floor(ms / (60 * 1000));
  if (minutes < 60) return `${minutes} mnt`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const restMinutes = minutes % 60;
    return restMinutes ? `${hours} jam ${restMinutes} mnt` : `${hours} jam`;
  }
  const days = Math.floor(hours / 24);
  const restHours = hours % 24;
  return restHours ? `${days} hari ${restHours} jam` : `${days} hari`;
}

/** Sisa waktu ("3 jam lagi") atau keterlambatan ("Lewat 2 jam 5 mnt"). */
export function dueLabel(value: unknown, now: Date): string {
  const ms = timeOf(value);
  if (ms === null) return "—";
  const diff = ms - now.getTime();
  if (diff < 0) return `Lewat ${humanDuration(-diff)}`;
  return `${humanDuration(diff)} lagi`;
}

/** true = keputusan menunggu tindakan manusia (menunggu persetujuan/verifikasi). */
export function isActionable(decision: TodayDecision | null | undefined): boolean {
  const status = String(decision?.status ?? "").toUpperCase();
  return ACTIONABLE_SET.has(status);
}

/**
 * Keputusan yang menunggu tindakan + urutannya.
 * Urutan: yang sudah lewat dulu (paling baru lewat), lalu yang akan datang
 * (paling dekat jatuh tempo), lalu yang tanggalnya tidak terbaca.
 * `nextDue`/`nextDueLabel` = agenda PALING DEKAT yang belum lewat.
 */
export function pendingDecisions(decisions: unknown, now: Date) {
  const list = Array.isArray(decisions) ? (decisions as TodayDecision[]) : [];
  const actionable = list.filter(isActionable);
  const nowMs = now.getTime();
  const scored = actionable.map((decision) => ({ decision, ms: timeOf(decision.expires_at) }));
  const known = scored.filter((s): s is { decision: TodayDecision; ms: number } => s.ms !== null);
  const unknown = scored.filter((s) => s.ms === null);
  const overdue = known
    .filter((s) => s.ms < nowMs)
    .sort((a, b) => b.ms - a.ms)
    .map((s) => s.decision);
  const upcoming = known
    .filter((s) => s.ms >= nowMs)
    .sort((a, b) => a.ms - b.ms)
    .map((s) => s.decision);
  const next = upcoming[0] ?? null;
  return {
    items: [...overdue, ...upcoming, ...unknown.map((s) => s.decision)],
    count: actionable.length,
    overdueCount: overdue.length,
    unknownCount: unknown.length,
    nextDue: next ? String(next.expires_at) : null,
    nextDueLabel: next ? dueLabel(next.expires_at, now) : "—",
  };
}

/** Jumlah kg dari daftar batch; null kalau tidak ada angka yang bisa dijumlahkan. */
function sumKg(batches: TodayBatch[]): number | null {
  const values = batches
    .map((batch) => batch?.quantity_kg)
    // null/"" JANGAN lewat Number() — Number(null) = 0 dan itu angka palsu.
    .filter((value) => value !== null && value !== undefined && value !== "")
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));
  if (values.length === 0) return null;
  return values.reduce((total, value) => total + value, 0);
}

/**
 * Batch yang sudah kedaluwarsa vs yang akan kedaluwarsa dalam `soonHours`.
 * Batch tanpa tanggal terbaca tidak masuk daftar mana pun.
 */
export function batchExpiry(batches: unknown, now: Date, soonHours: number = DUE_SOON_HOURS) {
  const list = Array.isArray(batches) ? (batches as TodayBatch[]) : [];
  const nowMs = now.getTime();
  const horizonMs = soonHours * 60 * 60 * 1000;
  const expired: { batch: TodayBatch; ms: number }[] = [];
  const dueSoon: { batch: TodayBatch; ms: number }[] = [];
  for (const batch of list) {
    const ms = timeOf(batch?.usable_until);
    if (ms === null) continue;
    if (ms < nowMs) expired.push({ batch, ms });
    else if (ms - nowMs <= horizonMs) dueSoon.push({ batch, ms });
  }
  expired.sort((a, b) => a.ms - b.ms);
  dueSoon.sort((a, b) => a.ms - b.ms);
  const expiredBatches = expired.map((entry) => entry.batch);
  const dueSoonBatches = dueSoon.map((entry) => entry.batch);
  return {
    expired: expiredBatches,
    dueSoon: dueSoonBatches,
    expiredKg: sumKg(expiredBatches),
    dueSoonKg: sumKg(dueSoonBatches),
  };
}

/** Skor kesegaran 0..1 → persen. Nilai tak terbaca ditulis "—". */
export function freshnessLabel(score: unknown): string {
  if (score === null || score === undefined || score === "") return "—";
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return "—";
  return `${Math.round(numeric * 100)}%`;
}

/**
 * Lokasi yang berstatus shortage, urut dari kekurangan terbesar.
 * `totalKg` null kalau tidak ada satu pun angka kekurangan yang sah.
 */
export function shortageSummary(locations: unknown) {
  const list = Array.isArray(locations) ? (locations as TodayLocation[]) : [];
  const shortage = list.filter((row) => row?.status === "shortage");
  const scored = shortage.map((row) => {
    const kg = Number(row.shortage_kg);
    return { row, kg: Number.isFinite(kg) ? kg : null };
  });
  scored.sort((a, b) => (b.kg ?? Number.NEGATIVE_INFINITY) - (a.kg ?? Number.NEGATIVE_INFINITY));
  const kgValues = scored.map((entry) => entry.kg).filter((kg): kg is number => kg !== null);
  return {
    items: scored.map((entry) => ({
      location: entry.row.location ?? null,
      region: entry.row.region ?? null,
      shortage_kg: entry.kg,
      label: `kurang ${formatKg(entry.kg)}`,
    })),
    count: scored.length,
    totalKg: kgValues.length ? kgValues.reduce((total, kg) => total + kg, 0) : null,
  };
}

/** Status rantai Merkle dari GET /ledger/verify. */
export function ledgerSummary(ledger: unknown) {
  const payload = (ledger ?? null) as {
    valid?: unknown;
    blocks?: unknown;
    head?: unknown;
    broken_at?: unknown;
  } | null;
  if (!payload || typeof payload !== "object") {
    return { ok: null, statusLabel: "—", blocksLabel: "—", headShort: "—" };
  }
  const ok = typeof payload.valid === "boolean" ? payload.valid : null;
  const brokenAt = Number(payload.broken_at);
  const statusLabel =
    ok === true
      ? "Rantai utuh"
      : ok === false
        ? Number.isFinite(brokenAt)
          ? `Rantai terputus di blok ${brokenAt}`
          : "Rantai terputus"
        : "—";
  const blocks = Number(payload.blocks);
  return {
    ok,
    statusLabel,
    blocksLabel: Number.isFinite(blocks) ? `${blocks.toLocaleString("id-ID")} blok` : "—",
    headShort: typeof payload.head === "string" && payload.head ? payload.head.slice(0, 10) : "—",
  };
}

// ---------------------------------------------------------------------------
// Desain ulang "Hari Ini" (permintaan pemilik 2026-10-17): strip ringkasan.
//
// Kenapa ada: halaman ini dulu menaruh lima kartu berbobot SAMA, sehingga tak
// ada yang bisa dipastikan "normal atau tidak" dalam satu detik. Referensi
// operasional (shieldthemes.com, "Designing operational dashboards people
// actually use", Jul 2025) menetapkan hierarkinya: 3–5 indikator status di atas
// → daftar pengecualian → rincian. Strip ini adalah lapis pertama itu, dan tiap
// tile menunjuk kartunya (`target`) supaya ia jalan pintas, bukan hiasan.
// ---------------------------------------------------------------------------

/** Nada tile: aman / perlu dilihat / bahaya / belum diketahui. */
export type TileTone = "ok" | "warn" | "danger" | "none";

export type SummaryTile = {
  key: "action" | "batches" | "shortage" | "kpi" | "ledger";
  label: string;
  /** Nilai siap tampil; "—" bila datanya memang belum ada (bukan 0). */
  value: string;
  /** Satu baris keterangan; `null` bila tidak ada yang jujur bisa dikatakan. */
  note: string | null;
  tone: TileTone;
  /** id kartu tujuan di halaman — harus sama dengan id yang dipasang kartunya. */
  target: string;
};

export type SummaryInput = {
  pending: ReturnType<typeof pendingDecisions>;
  batch: ReturnType<typeof batchExpiry>;
  /** false = data batch belum termuat: nilai ditulis "—", bukan 0. */
  batchLoaded: boolean;
  shortage: ReturnType<typeof shortageSummary>;
  metrics: { value?: string | null }[] | null;
  ledger: ReturnType<typeof ledgerSummary>;
};

/**
 * Apakah nilai tile boleh dirender dengan font DATA (Fira Code)?
 *
 * Aturan tampilan (perapian 2026-10-17): angka memakai font data supaya digit
 * sejajar (`tabular-nums`), sedangkan FRASA seperti "Rantai utuh" memakai font
 * UI — di bentuk selebar 183 px, frasa dalam font kode terbaca seperti potongan
 * kode dan membuat bentuk itu terlihat berbeda dari empat lainnya.
 * Definisi sengaja sederhana dan bisa diperiksa: nilai dianggap angka bila
 * tidak memuat huruf sama sekali ("15", "5/7", "3.748", "—").
 */
export function nilaiAngka(nilai: string): boolean {
  return !/[A-Za-z]/.test(nilai ?? "");
}

export function summaryTiles(input: SummaryInput): SummaryTile[] {
  const { pending, batch, batchLoaded, shortage, metrics, ledger } = input;

  const action: SummaryTile = {
    key: "action",
    label: "Menunggu tindakan",
    target: "today-action",
    value: String(pending.count),
    tone: pending.overdueCount > 0 ? "danger" : pending.count > 0 ? "warn" : "ok",
    note:
      pending.count === 0
        ? "tidak ada keputusan menunggu tindakan"
        : pending.overdueCount > 0
          ? `${pending.overdueCount} sudah lewat tenggat`
          : pending.nextDueLabel !== "—"
            ? `terdekat ${pending.nextDueLabel}`
            : "tidak ada agenda yang belum lewat tenggat",
  };

  const expired = batch.expired.length;
  const soon = batch.dueSoon.length;
  const batches: SummaryTile = batchLoaded
    ? {
        key: "batches",
        label: "Batch <48 jam",
        target: "today-batches",
        value: String(expired + soon),
        tone: expired > 0 ? "danger" : soon > 0 ? "warn" : "ok",
        note:
          expired || soon
            ? [
                expired ? `kedaluwarsa ${expired} batch (${formatKg(batch.expiredKg)})` : null,
                soon ? `segera ${soon} batch (${formatKg(batch.dueSoonKg)})` : null,
              ]
                .filter(Boolean)
                .join(" · ")
            : "tidak ada batch kedaluwarsa atau <48 jam",
      }
    : {
        key: "batches",
        label: "Batch <48 jam",
        target: "today-batches",
        value: "—",
        tone: "none",
        note: null,
      };

  const shortageTile: SummaryTile = {
    key: "shortage",
    label: "Lokasi shortage",
    target: "today-shortage",
    value: String(shortage.count),
    tone: shortage.count > 0 ? "warn" : "ok",
    note:
      shortage.count === 0
        ? "tidak ada kekurangan untuk komoditas ini"
        : shortage.totalKg === null
          ? `${shortage.count} lokasi kekurangan (besar kekurangan belum terbaca)`
          : `Total kekurangan ${formatKg(shortage.totalKg)}`,
  };

  const daftar = Array.isArray(metrics) ? metrics : null;
  const terisi = daftar
    ? daftar.filter((metric) => metric?.value !== null && metric?.value !== undefined).length
    : 0;
  const kpi: SummaryTile = daftar && daftar.length
    ? {
        key: "kpi",
        label: "KPI terisi",
        target: "today-kpi",
        value: `${terisi}/${daftar.length}`,
        tone: terisi === daftar.length ? "ok" : "warn",
        note:
          terisi === daftar.length
            ? "semua metrik ada"
            : `${daftar.length - terisi} metrik belum ada data`,
      }
    : {
        key: "kpi",
        label: "KPI terisi",
        target: "today-kpi",
        value: "—",
        tone: "none",
        note: "belum ada jawaban /kpi untuk periode ini",
      };

  const ledgerTile: SummaryTile = {
    key: "ledger",
    label: "Rantai audit",
    target: "today-ledger",
    value: ledger.statusLabel,
    tone: ledger.ok === true ? "ok" : ledger.ok === false ? "danger" : "none",
    note: ledger.blocksLabel !== "—" ? ledger.blocksLabel : null,
  };

  return [action, batches, shortageTile, kpi, ledgerTile];
}

const JAM_MENIT = new Intl.DateTimeFormat("id-ID", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: ZONA_DEFAULT,
});

/** "Diperbarui 11.05 WIB" — kapan data yang sedang dilihat diambil. */
export function updatedLabel(now: Date): string {
  return `Diperbarui ${JAM_MENIT.format(now)} ${zonaLabel(ZONA_DEFAULT)}`;
}

const TANGGAL_SINGKAT = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  timeZone: ZONA_DEFAULT,
});

/**
 * "Periode 16 Okt 11.05 → 17 Okt 11.05 WIB" dari `GET /kpi`, atau `null` bila
 * salah satu ujungnya tidak ada — label periode yang setengah jadi akan
 * membuat pembaca menyangka rentangnya lain.
 */
export function kpiPeriodLabel(
  period?: { start?: string | null; end?: string | null } | null,
): string | null {
  const mulai = period?.start ? new Date(String(period.start)) : null;
  const selesai = period?.end ? new Date(String(period.end)) : null;
  if (!mulai || !selesai) return null;
  if (!Number.isFinite(mulai.getTime()) || !Number.isFinite(selesai.getTime())) return null;
  const teks = (d: Date) => `${TANGGAL_SINGKAT.format(d)} ${JAM_MENIT.format(d)}`;
  return `Periode ${teks(mulai)} → ${teks(selesai)} ${zonaLabel(ZONA_DEFAULT)}`;
}
