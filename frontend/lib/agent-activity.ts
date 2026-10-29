// Model murni "Agent Activity" (dokumen `06-agent-log.md`, 28 Okt 2026).
//
// Modul ini punya satu tugas sempit: melaporkan APA yang tercatat, tanpa
// mengubah "tidak ada catatan" menjadi "berhasil". Karena itu semua keputusan
// tampilan yang berbahaya secara fakta dikurung di sini, bukan di komponen:
//
// - `null` (belum dimuat) ≠ `[]` (backend menjawab kosong) ≠ ada langkah.
// - ACT boleh "tercatat" lewat dua rumah: baris `agent_traces` ATAU blok
//   ledger `action = 'execute'`. Yang kedua tidak boleh ditampilkan sebagai
//   "belum tercatat" — itu kesalahan fakta.
// - Status supervisor TIDAK ditempel ke keadaan trace: dua fakta berbeda.
// - Penilaian benar/salah bukan urusan modul ini; kalimat di banner selalu
//   menunjuk modul Safety & Evidence.

/** Satu baris trace keputusan, apa adanya dari `GET /decisions/{id}/traces`. */
export interface TraceStep {
  step_name: string;
  step_at: string;
  tool_called?: string | null;
  duration_ms?: number | null;
  agent_name?: string | null;
}

/** Satu blok ledger milik keputusan ini (`GET /decisions/{id}/ledger`). */
export interface LedgerBlockView {
  height: number;
  action: string;
  created_at: string;
}

import { PIPELINE_STAGES, stageMeta } from "./pipeline-stages";

export type StageState = "present" | "ledger" | "absent" | "not_loaded";

export interface StageView {
  code: string;
  label: string;
  tool: string;
  state: StageState;
  /** Waktu kejadian tahap ini; `null` bila tidak ada yang tercatat. */
  at: string | null;
  /** Langkah ini mencolok lambat (jarak ke langkah sebelumnya atau durasinya). */
  slow: boolean;
  /** Catatan pendek untuk rincian; tidak pernah mengarang angka. */
  note: string;
}

// Metadata tahap hidup di `pipeline-stages.ts` (satu sumber untuk chip,
// rincian, dan tes). Diekspor ulang di sini supaya pemanggil lama tetap sah.
export { PIPELINE_STAGES, stageMeta, STAGE_CODES } from "./pipeline-stages";
export type { StageMeta } from "./pipeline-stages";

/** Ambang "mencolok": 45 detik jarak antar langkah, 45 detik durasi satu langkah. */
export const SLOW_GAP_MS = 45_000;
export const SLOW_STEP_MS = 45_000;

const LABEL_STATE: Record<StageState, string> = {
  present: "tercatat",
  ledger: "tercatat di Ledger",
  absent: "belum tercatat",
  not_loaded: "belum dimuat",
};

/**
 * Label chip. Sembilan kolom hanya selebar ~120px, jadi teks panjang dipotong
 * ("tercatat di L…"). Label pendek mempertahankan makna; teks penuh tetap ada
 * di `title` dan di rincian tahap.
 */
const LABEL_PENDEK: Record<StageState, string> = {
  present: "tercatat",
  ledger: "di Ledger",
  // "belum" saja terlalu terse di chip; "belum ada" tetap pendek tapi utuh.
  absent: "belum ada",
  not_loaded: "belum dimuat",
};

export function stageStateLabel(state: StageState): string {
  return LABEL_STATE[state];
}

export function stageStateShort(state: StageState): string {
  return LABEL_PENDEK[state];
}

function waktu(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isFinite(t) ? t : null;
}

/** Langkah trace milik satu tahap pipeline (nama langkah = kode tahap). */
export function langkahUntuk(
  steps: ReadonlyArray<TraceStep>,
  code: string
): TraceStep[] {
  const target = code.toLowerCase();
  return steps.filter(
    (s) => (s.step_name ?? "").toLowerCase() === target
  );
}

/** Selisih waktu antar dua langkah berurutan > ambang → langkah kedua lambat. */
function penandaLambat(
  steps: ReadonlyArray<TraceStep>,
  slowGapMs: number,
  slowStepMs: number
): Map<string, string[]> {
  const urut = [...steps].sort(
    (a, b) => (waktu(a.step_at) ?? 0) - (waktu(b.step_at) ?? 0)
  );
  const hasil = new Map<string, string[]>();
  let sebelumnya: number | null = null;

  for (const s of urut) {
    const alasan: string[] = [];
    const t = waktu(s.step_at);
    if (t !== null && sebelumnya !== null && t - sebelumnya > slowGapMs) {
      alasan.push("jeda");
    }
    if (
      typeof s.duration_ms === "number" &&
      Number.isFinite(s.duration_ms) &&
      s.duration_ms > slowStepMs
    ) {
      alasan.push("durasi");
    }
    if (t !== null) sebelumnya = t;
    if (alasan.length > 0) {
      const kunci = `${(s.step_name ?? "").toLowerCase()}@${s.step_at}`;
      hasil.set(kunci, alasan);
    }
  }
  return hasil;
}

export function slowSteps(
  steps: ReadonlyArray<TraceStep> | null | undefined,
  opsi: { slowGapMs?: number; slowStepMs?: number } = {}
): { step_name: string; at: string; reasons: string[] }[] {
  if (!steps || steps.length === 0) return [];
  const lambat = penandaLambat(
    steps,
    opsi.slowGapMs ?? SLOW_GAP_MS,
    opsi.slowStepMs ?? SLOW_STEP_MS
  );
  const hasil: { step_name: string; at: string; reasons: string[] }[] = [];
  for (const s of steps) {
    const kunci = `${(s.step_name ?? "").toLowerCase()}@${s.step_at}`;
    const alasan = lambat.get(kunci);
    if (alasan) {
      hasil.push({ step_name: s.step_name, at: s.step_at, reasons: alasan });
    }
  }
  return hasil;
}

export function buildPipeline({
  steps,
  ledger,
  slowGapMs = SLOW_GAP_MS,
  slowStepMs = SLOW_STEP_MS,
}: {
  steps: ReadonlyArray<TraceStep> | null | undefined;
  ledger: ReadonlyArray<LedgerBlockView> | null | undefined;
  slowGapMs?: number;
  slowStepMs?: number;
}): StageView[] {
  const dimuat = Array.isArray(steps);
  const daftar = (steps ?? []) as ReadonlyArray<TraceStep>;
  const lambat = penandaLambat(daftar, slowGapMs, slowStepMs);
  const blokEksekusi = (ledger ?? []).filter((b) => b.action === "execute");
  const ledgerDimuat = Array.isArray(ledger);

  return PIPELINE_STAGES.map((tahap) => {
    const baris = langkahUntuk(daftar, tahap.code);

    if (!dimuat) {
      return {
        ...tahap,
        state: "not_loaded" as StageState,
        at: null,
        slow: false,
        note: "Trace keputusan ini belum dimuat.",
      };
    }

    if (baris.length > 0) {
      const pertama = baris
        .map((b) => b.step_at)
        .sort((a, b) => (waktu(a) ?? 0) - (waktu(b) ?? 0))[0];
      const lambatDi = baris.some((b) =>
        lambat.has(`${(b.step_name ?? "").toLowerCase()}@${b.step_at}`)
      );
      return {
        ...tahap,
        state: "present" as StageState,
        at: pertama,
        slow: lambatDi,
        note:
          baris.length === 1
            ? `1 langkah tercatat${baris[0].tool_called ? ` · ${baris[0].tool_called}` : ""}.`
            : `${baris.length} langkah tercatat untuk tahap ini.`,
      };
    }

    if (tahap.code === "ACT" && blokEksekusi.length > 0) {
      const blok = blokEksekusi[blokEksekusi.length - 1];
      return {
        ...tahap,
        state: "ledger" as StageState,
        at: blok.created_at,
        slow: false,
        note: `ACT tercatat di Ledger (blok #${blok.height}).`,
      };
    }

    if (tahap.code === "ACT" && !ledgerDimuat) {
      return {
        ...tahap,
        state: "absent" as StageState,
        at: null,
        slow: false,
        note: "Blok ledger keputusan ini belum dimuat, jadi eksekusi belum bisa dipastikan.",
      };
    }

    return {
      ...tahap,
      state: "absent" as StageState,
      at: null,
      slow: false,
      note:
        tahap.code === "ACT"
          ? "ACT belum tercatat, keputusan belum dieksekusi."
          : "Belum ada langkah tercatat untuk tahap ini.",
    };
  });
}

/**
 * Ringkasan di atas strip. "0 dari 9" DILARANG: nol tahap selalu berarti
 * belum dimuat atau tidak tercatat, dan dua hal itu bukan angka.
 */
/** Kalimat pendamping ringkasan — dipakai sebagai `title`, bukan teks tercetak. */
export function pipelineCaveat(stages: ReadonlyArray<StageView>): string {
  const total = stages.length;
  if (stages.every((s) => s.state === "not_loaded")) {
    return "Belum ada jawaban untuk tahap mana pun; ini bukan nol tahap.";
  }
  const punya = stages.filter(
    (s) => s.state === "present" || s.state === "ledger"
  ).length;
  return punya === total
    ? "Semua tahap punya jejak tercatat."
    : "Tahap tanpa jejak bukan berarti gagal — bisa belum dijalankan atau jejaknya tersimpan di tempat lain.";
}

export function pipelineSummary(stages: ReadonlyArray<StageView>): string {
  const total = stages.length;
  if (stages.every((s) => s.state === "not_loaded")) {
    return `${total} tahap, trace belum dimuat`;
  }
  const punya = stages.filter(
    (s) => s.state === "present" || s.state === "ledger"
  ).length;
  return `${punya} dari ${total} tahap punya jejak tercatat`;
}

export type BannerState = "no_decision" | "not_loaded" | "missing" | "present";

export interface TraceBannerView {
  state: BannerState;
  label: string;
  /** Kalimat kejujuran; tidak boleh dipendekkan jadi badge. */
  sentence: string;
  tone: "neutral" | "warning" | "danger";
}

export function traceBanner(
  decisionId: string | null | undefined,
  steps: ReadonlyArray<TraceStep> | null | undefined
): TraceBannerView {
  if (!decisionId) {
    return {
      state: "no_decision",
      label: "Belum ada keputusan dipilih",
      sentence:
        "Pilih satu keputusan di atas. Selama belum ada yang dipilih, belum ada trace yang bisa dibaca.",
      tone: "neutral",
    };
  }
  if (!Array.isArray(steps)) {
    return {
      state: "not_loaded",
      label: "Trace belum dimuat",
      sentence:
        "Belum ada jawaban, jangan dibaca sebagai hasil.",
      tone: "neutral",
    };
  }
  if (steps.length === 0) {
    return {
      state: "missing",
      label: "Belum ada trace tersimpan",
      sentence:
        "Tidak ada langkah tercatat. Ini BUKAN tanda keputusan berhasil, hanya berarti jejaknya tidak ada.",
      tone: "warning",
    };
  }
  return {
    state: "present",
    label: `${steps.length} langkah tercatat`,
    sentence:
      "Trace menunjukkan APA yang dijalankan agent, bukan bahwa hasilnya benar. Penilaian benar atau salah ada di modul Safety & Evidence.",
    tone: "neutral",
  };
}

/** Jam WIB ringkas untuk penanda chip/rincian. */
export function jamWib(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return null;
  return new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Jakarta",
    hour: "2-digit",
    minute: "2-digit",
  }).format(t);
}

/** "3 langkah · pertama 08.12 · terakhir 08.14" — hanya bila ada langkah. */
export function provenanceLine(
  steps: ReadonlyArray<TraceStep> | null | undefined
): string | null {
  if (!steps || steps.length === 0) return null;
  const urut = [...steps].sort(
    (a, b) => (waktu(a.step_at) ?? 0) - (waktu(b.step_at) ?? 0)
  );
  const awal = jamWib(urut[0].step_at);
  const akhir = jamWib(urut[urut.length - 1].step_at);
  const bagian = [`${steps.length} langkah`];
  if (awal) bagian.push(`pertama ${awal}`);
  if (akhir) bagian.push(`terakhir ${akhir}`);
  return bagian.join(" · ");
}

/* ------------------------------------------------------------------ *
 *  Dua agent yang bekerja (dokumen §2.2)
 * ------------------------------------------------------------------ */

export interface AgentCard {
  key: string;
  name: string;
  role: string;
  work: string;
  /** Dari mana klaim ini dibaca — bukan tebakan UI. */
  source: string;
}

export const AGENTS: ReadonlyArray<AgentCard> = [
  {
    key: "supervisor",
    name: "Supervisor Agent",
    role: "Agent penalar utama",
    work: "Memilih tool, menyusun usulan penyeimbangan, menarasikannya untuk manusia.",
    source: "tahap SUPERVISE di agent_traces",
  },
  {
    key: "verifier",
    name: "Verifier Agent",
    role: "Audit independen",
    work:
      "Memeriksa usulan Supervisor dengan persona skeptis sebelum usulan disebut layak.",
    source: "tahap VERIFY di agent_traces",
  },
];

/* ------------------------------------------------------------------ *
 *  Status supervisor (dokumen §2.8) — sengaja lepas dari keadaan trace
 * ------------------------------------------------------------------ */

export interface SupervisorHealth {
  status?: string | null;
  live?: boolean | null;
  model?: string | null;
  detail?: string | null;
  slots?: number;
}

export interface SupervisorView {
  label: string;
  detail: string;
  tone: "safe" | "warning" | "danger" | "neutral";
}

/**
 * Peta status → kalimat. Aturannya dari dokumen: `ok|healthy|up` = aman,
 * kosong = peringatan, selain itu bahaya, belum dimuat = netral.
 *
 * Dua nilai tambahan dari endpoint build ini: `configured` (rantai model ada
 * tetapi belum diuji hidup) sengaja NETRAL, bukan hijau — invarian 4 melarang
 * hijau tanpa bukti live; `unconfigured` = peringatan, bukan bahaya, karena
 * tidak ada yang rusak — hanya belum diisi.
 */
export function supervisorView(
  health: SupervisorHealth | null | undefined
): SupervisorView {
  if (!health) {
    return {
      label: "Status supervisor belum dimuat",
      detail: "Belum ada jawaban; jangan dibaca sebagai sehat.",
      tone: "neutral",
    };
  }
  const status = (health.status ?? "").trim();
  if (!status) {
    return {
      label: "Supervisor menjawab tanpa status",
      detail: "Jawaban datang, tetapi tidak menyebut status. Itu bukan bukti hidup.",
      tone: "warning",
    };
  }
  const rendah = status.toLowerCase();
  if (rendah === "ok" || rendah === "healthy" || rendah === "up") {
    return {
      label: "Supervisor aktif",
      detail: health.model ? `Model ${health.model}.` : "Provider menjawab.",
      tone: "safe",
    };
  }
  if (rendah === "configured") {
    return {
      label: "Supervisor terkonfigurasi, belum diuji hidup",
      detail:
        health.detail ??
        "Rantai model ada, tetapi jalur status tidak memanggil provider.",
      tone: "neutral",
    };
  }
  if (rendah === "unconfigured") {
    return {
      label: "Supervisor belum dikonfigurasi",
      detail:
        health.detail ??
        "Belum ada model supervisor di env; jawaban memakai tool deterministik.",
      tone: "warning",
    };
  }
  return {
    label: `Supervisor: ${status}`,
    detail: health.detail ?? "Status di luar daftar yang dikenal.",
    tone: "danger",
  };
}

/* ------------------------------------------------------------------ *
 *  Tanya-jawab supervisor (dokumen §2.9)
 * ------------------------------------------------------------------ */

export interface AskAnswer {
  mode?: string;
  tool?: string;
  writes?: boolean;
  answer?: string;
  data?: unknown;
}

/** Baris sumber jawaban: mode + tool + penegasan tidak menulis apa pun. */
export function askProvenance(answer: AskAnswer | null | undefined): string {
  if (!answer) return "Belum ada jawaban.";
  const bagian: string[] = [];
  bagian.push(answer.mode === "deterministic" ? "tool deterministik" : "model");
  if (answer.tool) bagian.push(answer.tool);
  bagian.push(answer.writes === false ? "tidak menulis apa pun" : "menulis data");
  return bagian.join(" · ");
}
