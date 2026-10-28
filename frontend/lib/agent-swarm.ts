/**
 * Data panel review sembilan agen untuk Agent Log (P5).
 *
 * Trace worker disimpan sebagai baris `agent_traces` dengan `run_id`,
 * `agent_name`, `confidence`, dan `citations`. Modul ini murni: memilih satu
 * putaran TERBARU dan membentuk sembilan kartu — tujuh worker, supervisor
 * (dari `run.supervisor`, bukan dari baris worker), lalu verifier. Nilai yang
 * tidak ada tetap "—", bukan 0 atau enum mentah.
 */

import { stepDurationLabel } from "./agent-trace";

export type SwarmAgentKey =
  | "supply"
  | "demand"
  | "freshness"
  | "safety"
  | "price"
  | "logistics"
  | "evidence"
  | "supervisor"
  | "verifier";

// Nama agen ditulis ENGLISH: ini nama PERAN dalam sistem multi-agen (dipakai
// laporan, jejak Agent Log, dan dokumen arsitektur), bukan kata benda sehari-
// hari. Menerjemahkannya membuat satu agen punya dua nama di dua layar.
export const SWARM_AGENTS: ReadonlyArray<{
  key: SwarmAgentKey;
  label: string;
  stage: string;
}> = [
  { key: "supply", label: "Supply", stage: "DETECT" },
  { key: "demand", label: "Demand", stage: "PREDICT" },
  { key: "freshness", label: "Freshness", stage: "VERIFY" },
  { key: "safety", label: "Food Safety", stage: "VERIFY" },
  { key: "price", label: "Price", stage: "OPTIMIZE" },
  { key: "logistics", label: "Logistics", stage: "OPTIMIZE" },
  { key: "evidence", label: "Evidence", stage: "TRACE" },
  // Agen ke-8: supervisor. Merangkum temuan worker menjadi satu narasi; ia
  // kartu sendiri karena datanya datang dari `run.supervisor`, bukan worker.
  { key: "supervisor", label: "Supervisor", stage: "SUPERVISE" },
  // Agen ke-9: auditor. Dijalankan setelah narasi supervisor, tampil sebagai
  // kartu sendiri supaya juri melihat siapa yang mengaudit siapa.
  { key: "verifier", label: "Verifier", stage: "VERIFY" },
];

const AGENT_KEYS = new Set<string>(SWARM_AGENTS.map((agent) => agent.key));
const SUPERVISOR = "supervisor";

const STATUS_LABELS: Record<string, string> = {
  ok: "Selesai",
  completed: "Selesai",
  degraded: "Terbatas",
  error: "Gagal",
  skipped: "Dilewati",
  stub: "Belum aktif",
  // Status run yang mencerminkan veto guardian (agent/contracts.py RunStatus).
  // Tanpa label ini UI menampilkan "Tidak dikenal" untuk putaran yang diblokir.
  vetoed: "Diblokir",
};

/**
 * Status narasi supervisor: `narrated`/`unavailable` bukan status worker, jadi
 * ia punya label sendiri. Tanpa peta ini kartu supervisor menampilkan
 * "Tidak dikenal" untuk putaran yang justru berhasil.
 */
const SUPERVISOR_LABELS: Record<string, string> = {
  narrated: "Narasi selesai",
  unavailable: "Narasi tidak tersedia",
};

/** `data-state` kartu supervisor: hanya dua keadaan narasi yang definitif. */
const SUPERVISOR_STATES: Record<string, string> = {
  narrated: "ok",
  unavailable: "degraded",
};


export type SwarmRun = {
  runId: string;
  rows: any[];
  /** Semua baris agen di jejak keputusan ini (lintas run_id), urutan asli. */
  allRows?: any[];
  supervisor: any | null;
};

export type SwarmCard = {
  key: SwarmAgentKey;
  label: string;
  stage: string;
  row: any | null;
  status: string;
  statusLabel: string;
  duration: string;
  confidence: string;
  citations: string;
  warningCount: number | null;
  summary: string;
};

function text(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function agentOf(row: any): string | null {
  return text(row?.agent_name)?.toLowerCase() ?? null;
}

function runOf(row: any): string | null {
  return text(row?.run_id);
}

function dateValue(value: unknown): number | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.getTime();
}

function isKnownRow(row: any): boolean {
  const agent = agentOf(row);
  return Boolean(runOf(row) && agent && (AGENT_KEYS.has(agent) || agent === SUPERVISOR));
}

/**
 * Pilih putaran review terbaru. Urutan memakai timestamp `step_at`; jika
 * timestamp tidak terbaca, urutan kemunculan dipakai apa adanya.
 *
 * Satu keputusan bisa punya LEBIH DARI SATU run_id: `agent.verifier` menulis
 * auditnya di run sendiri (verify.py), terpisah dari run pipeline yang menulis
 * ketujuh worker. Karena itu run utama dipilih dari grup dengan baris TERBANYAK
 * (tie → yang terbaru) — kalau hanya "yang terbaru" yang dipakai, grup audit
 * yang cuma berisi satu baris bisa menutupi seluruh review.
 */
export function latestSwarmRun(steps: any[] | null | undefined): SwarmRun | null {
  if (!Array.isArray(steps) || steps.length === 0) return null;
  const groups = new Map<
    string,
    { rows: any[]; latestAt: number | null; lastIndex: number }
  >();
  const allRows: any[] = [];

  steps.forEach((row, index) => {
    if (!isKnownRow(row)) return;
    allRows.push(row);
    const runId = runOf(row) as string;
    const group = groups.get(runId) ?? {
      rows: [],
      latestAt: null,
      lastIndex: -1,
    };
    group.rows.push(row);
    group.lastIndex = index;
    const at = dateValue(row?.step_at);
    if (at !== null && (group.latestAt === null || at > group.latestAt)) {
      group.latestAt = at;
    }
    groups.set(runId, group);
  });

  if (groups.size === 0) return null;
  const [runId, chosen] = Array.from(groups.entries()).sort((a, b) => {
    if (a[1].rows.length !== b[1].rows.length) {
      return b[1].rows.length - a[1].rows.length;
    }
    const atA = a[1].latestAt ?? -1;
    const atB = b[1].latestAt ?? -1;
    if (atA !== atB) return atB - atA;
    return b[1].lastIndex - a[1].lastIndex;
  })[0];
  return {
    runId,
    rows: chosen.rows,
    allRows,
    supervisor:
      chosen.rows.find(
        (row) => agentOf(row) === SUPERVISOR || row?.step_name === "SUPERVISE"
      ) ?? null,
  };
}

export function statusLabel(value: unknown): string {
  const key = text(value)?.toLowerCase();
  if (!key) return "—";
  return STATUS_LABELS[key] ?? "Tidak dikenal";
}

function statusKey(value: unknown): string {
  const key = text(value)?.toLowerCase();
  return key && STATUS_LABELS[key] ? key : "unknown";
}

export function confidenceLabel(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  if (value < 0 || value > 1) return "—";
  return `${Math.round(value * 100)}%`;
}

export function citationsLabel(value: unknown): string {
  if (!Array.isArray(value)) return "—";
  return `${value.length} sitasi`;
}

export function warningCountOf(row: any): number | null {
  const raw = row?.output_summary?.warning_count;
  if (typeof raw === "number" && Number.isFinite(raw) && raw >= 0) {
    return raw;
  }
  const warnings = row?.output_summary?.warnings;
  return Array.isArray(warnings) ? warnings.length : null;
}

export function vetoLabel(value: unknown): string {
  if (typeof value !== "boolean") return "—";
  return value ? "Ya" : "Tidak";
}

export function countLabel(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return "—";
  }
  return String(value);
}

export function shortRunId(runId: string | null | undefined): string {
  const value = text(runId);
  return value ? value.slice(0, 8) : "—";
}

/**
 * Kartu supervisor. Datanya dari `run.supervisor` (baris SUPERVISE pada run
 * yang sama), BUKAN dari baris worker: narrative/status narasi tidak pernah
 * hidup di baris worker, jadi mengambilnya dari `rows` akan selalu kosong.
 */
function supervisorCard(run: SwarmRun): SwarmCard {
  const row = run.supervisor ?? null;
  const agent = SWARM_AGENTS[SWARM_AGENTS.findIndex((a) => a.key === SUPERVISOR)];
  const rawStatus = text(row?.output_summary?.status)?.toLowerCase() ?? null;
  // Narasi yang belum tercatat bukan "Tidak dikenal": kartunya tetap ada dengan
  // keadaan jujur "Belum tercatat" supaya jumlah kartu tidak berubah-ubah.
  const state = !row
    ? "not_recorded"
    : rawStatus
      ? (SUPERVISOR_STATES[rawStatus] ?? statusKey(rawStatus))
      : "not_recorded";
  const label = !row
    ? "Belum tercatat"
    : rawStatus
      ? (SUPERVISOR_LABELS[rawStatus] ?? statusLabel(rawStatus))
      : "Belum tercatat";
  return {
    ...agent,
    row,
    status: state,
    statusLabel: label,
    duration: stepDurationLabel(row) ?? "—",
    confidence: confidenceLabel(row?.confidence),
    citations: citationsLabel(row?.citations),
    warningCount: warningCountOf(row),
    summary:
      text(row?.output_summary?.narrative) ??
      text(row?.output_summary?.summary) ??
      "—",
  };
}

export function swarmCards(run: SwarmRun): SwarmCard[] {
  const byAgent = new Map<string, any>();
  for (const row of run.rows) {
    const agent = agentOf(row);
    if (agent && AGENT_KEYS.has(agent) && agent !== SUPERVISOR) {
      byAgent.set(agent, row);
    }
  }
  // Verifier menulis auditnya di run_id SENDIRI (verify.py), jadi barisnya
  // sering tidak ada di run pipeline yang dipilih. Ambil yang terbaru dari
  // jejak keputusan yang sama — auditnya nyata, hanya beda run_id. Worker
  // TIDAK memakai cadangan ini: baris worker yang hilang berarti worker itu
  // memang tidak melapor di putaran ini.
  const verifierFallback = (run.allRows ?? [])
    .filter((row) => agentOf(row) === "verifier")
    .pop();
  return SWARM_AGENTS.map((agent) => {
    if (agent.key === SUPERVISOR) return supervisorCard(run);
    const row =
      byAgent.get(agent.key) ??
      (agent.key === "verifier" ? verifierFallback ?? null : null);
    const rawStatus = row?.output_summary?.status;
    return {
      ...agent,
      row,
      status: row ? statusKey(rawStatus) : "not_recorded",
      statusLabel: row ? statusLabel(rawStatus) : "Belum tercatat",
      duration: stepDurationLabel(row) ?? "—",
      confidence: confidenceLabel(row?.confidence),
      citations: citationsLabel(row?.citations),
      warningCount: warningCountOf(row),
      summary: text(row?.output_summary?.summary) ?? "—",
    };
  });
}

export function supervisorSummary(run: SwarmRun): {
  status: string;
  narrative: string;
  veto: string;
  contradictions: string;
} {
  const row = run.supervisor;
  return {
    status: row ? statusLabel(row?.output_summary?.status) : "—",
    narrative: text(row?.output_summary?.narrative) ?? "—",
    veto: vetoLabel(row?.output_summary?.safety_veto),
    contradictions: countLabel(row?.output_summary?.contradiction_count),
  };
}

/**
 * P4: keputusan mana yang harus dibuka saat tab Agent Log pertama kali dilihat.
 *
 * Aturannya sederhana dan tidak mengarang: pertahankan pilihan pengguna bila
 * keputusan itu punya review; kalau tidak, ambil keputusan terbaru yang PUNYA
 * review (`has_agent_review` dihitung backend dari `agent_traces`). Bila tak ada
 * satu pun punya review, kembalikan pilihan semula supaya pesan "Belum ada
 * review 8 agen" tetap jujur — bukan menyembunyikannya.
 */
export function defaultAgentLogId(
  decisions:
    | Array<{ decision_id?: string; has_agent_review?: boolean | null }>
    | null
    | undefined,
  currentId: string | null
): string | null {
  const daftar = (decisions ?? []).filter(
    (d): d is { decision_id: string; has_agent_review?: boolean | null } =>
      typeof d?.decision_id === "string" && d.decision_id.length > 0
  );
  if (currentId) {
    const sekarang = daftar.find((d) => d.decision_id === currentId);
    if (sekarang?.has_agent_review === true) return currentId;
  }
  const kandidat = daftar.find((d) => d.has_agent_review === true);
  return kandidat ? kandidat.decision_id : (currentId ?? null);
}
