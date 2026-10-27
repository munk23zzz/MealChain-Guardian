/**
 * Data panel review 8 agen untuk Agent Log (P5).
 *
 * Trace worker disimpan sebagai baris `agent_traces` dengan `run_id`,
 * `agent_name`, `confidence`, dan `citations`. Modul ini murni: memilih satu
 * putaran TERBARU dan membentuk delapan kartu. Nilai yang tidak ada tetap "—",
 * bukan 0 atau enum mentah.
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
  | "verifier";

export const SWARM_AGENTS: ReadonlyArray<{
  key: SwarmAgentKey;
  label: string;
  stage: string;
}> = [
  { key: "supply", label: "Pasokan", stage: "DETECT" },
  { key: "demand", label: "Permintaan", stage: "PREDICT" },
  { key: "freshness", label: "Kesegaran", stage: "VERIFY" },
  { key: "safety", label: "Keamanan Pangan", stage: "VERIFY" },
  { key: "price", label: "Harga", stage: "OPTIMIZE" },
  { key: "logistics", label: "Logistik", stage: "OPTIMIZE" },
  { key: "evidence", label: "Bukti", stage: "TRACE" },
  // Agent ke-8: auditor. Dijalankan setelah narasi supervisor, tampil sebagai
  // kartu sendiri supaya juri melihat siapa yang mengaudit siapa.
  { key: "verifier", label: "Verifikasi", stage: "VERIFY" },
];

const WORKER_KEYS = new Set<string>(SWARM_AGENTS.map((agent) => agent.key));
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

export type SwarmRun = {
  runId: string;
  rows: any[];
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
  return Boolean(runOf(row) && agent && (WORKER_KEYS.has(agent) || agent === SUPERVISOR));
}

/**
 * Pilih putaran review terbaru. Urutan memakai timestamp `step_at`; jika
 * timestamp tidak terbaca, urutan kemunculan dipakai apa adanya.
 */
export function latestSwarmRun(steps: any[] | null | undefined): SwarmRun | null {
  if (!Array.isArray(steps) || steps.length === 0) return null;
  const groups = new Map<
    string,
    { rows: any[]; latestAt: number | null; lastIndex: number }
  >();

  steps.forEach((row, index) => {
    if (!isKnownRow(row)) return;
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
    const atA = a[1].latestAt ?? -1;
    const atB = b[1].latestAt ?? -1;
    if (atA !== atB) return atB - atA;
    return b[1].lastIndex - a[1].lastIndex;
  })[0];
  return {
    runId,
    rows: chosen.rows,
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

export function swarmCards(run: SwarmRun): SwarmCard[] {
  const byAgent = new Map<string, any>();
  for (const row of run.rows) {
    const agent = agentOf(row);
    if (agent && WORKER_KEYS.has(agent)) byAgent.set(agent, row);
  }
  return SWARM_AGENTS.map((agent) => {
    const row = byAgent.get(agent.key) ?? null;
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
