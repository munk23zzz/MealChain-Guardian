// Halaman "Kualitas Agen" — meniru halaman /quality di aplikasi acuan
// (E:\hackathon\HackathonBil\MealchainGuardian) yang memakai MOCK_AGENT_RUNS.
// Di repo ini angkanya dari data NYATA:
//   GET /decisions/{id}/traces            → langkah agen (step_name, agent_name, tool_called, step_at)
//   GET /decisions/{id}/approval-summary  → putusan verifikator (verdict)
//   GET /decisions                        → status + iterasi (dipakai manusia)
//
// Kualitas diukur, bukan diklaim: kalau verifikator tidak pernah bicara, itu
// ditulis "tidak tersedia", bukan dihitung sebagai sepakat.
//
// Supervisor dan verifier adalah agen kelas satu: agenQuality() menghitung
// berapa run yang benar-benar memuat barisnya (worker dari `agent_name`,
// supervisor dari tahap SUPERVISE) dan merinci putusan verifier.

import { SWARM_AGENTS } from "./agent-swarm";

const DASH = "—";

export type QualityDecision = {
  decision_id?: string | null;
  decision_type?: string | null;
  status?: string | null;
  iteration?: number | string | null;
};

export type QualityStep = {
  step_name?: string | null;
  tool_called?: string | null;
  /** Nama agen penulis baris (`supply`..`verifier`); langkah pipeline: null. */
  agent_name?: string | null;
  output_summary?: unknown;
  step_at?: string | null;
};

export type QualityVerdict = "agree" | "disagree" | "unavailable";

export type QualityRun = {
  id: string;
  shortId: string;
  type: string;
  status: string;
  iteration: number | null;
  steps: number | null;
  tools: string[];
  durationMs: number | null;
  durationLabel: string;
  verdict: QualityVerdict;
  verdictLabel: string;
  fallbackSteps: number;
  humanChanged: boolean;
  /** Kunci agen yang PUNYA baris jejak pada run ini (termasuk supervisor). */
  agents: string[];
  /** Kunci agen yang barisnya membawa keluaran (output_summary berisi). */
  deliveredAgents: string[];
};

export const VERDICT_LABEL: Record<QualityVerdict, string> = {
  agree: "Setuju",
  disagree: "Tidak setuju",
  unavailable: "Tidak tersedia",
};

export function shortId(id: unknown, length = 8): string {
  const raw = typeof id === "string" ? id.trim() : "";
  if (!raw) return DASH;
  return raw.slice(0, length);
}

/** Putusan verifikator → tiga nilai yang bisa dihitung. */
export function verdictOf(summary: unknown): QualityVerdict {
  const verdict = String(
    (summary as { verifier?: { verdict?: unknown } } | null)?.verifier?.verdict ?? ""
  )
    .trim()
    .toLowerCase();
  if (verdict === "consistent" || verdict === "agree") return "agree";
  if (verdict === "flagged" || verdict === "disagree") return "disagree";
  return "unavailable";
}

export function durationLabel(ms: number | null): string {
  if (ms === null) return DASH;
  // Stempel waktu langkah hanya sampai detik, jadi durasi <1 detik berarti
  // "langkah-langkahnya di detik yang sama" — bukan 0 ms yang presisi palsu.
  if (ms < 1000) return "< 1 s";
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms / 60_000)} mnt`;
}

function isFallbackStep(step: QualityStep): boolean {
  try {
    return /fallback/i.test(JSON.stringify(step?.output_summary ?? ""));
  } catch {
    return false;
  }
}

const AGENT_KEY_SET = new Set<string>(SWARM_AGENTS.map((agent) => agent.key));

/**
 * Kunci agen pemilik satu baris jejak.
 *
 * Worker & verifier menulis `agent_name`; supervisor TIDAK (barisnya hanya
 * bertahap SUPERVISE / beralat `supervisor.*`). Langkah pipeline biasa
 * (`DETECT` dari supply.get) tidak dihitung sebagai keluaran agen — kalau
 * dihitung, kolom "tercatat" jadi karangan.
 */
function agentKeyOf(step: QualityStep): string | null {
  const nama = String(step?.agent_name ?? "").trim().toLowerCase();
  if (nama && AGENT_KEY_SET.has(nama)) return nama;
  const tahap = String(step?.step_name ?? "").trim().toUpperCase();
  const alat = String(step?.tool_called ?? "").trim().toLowerCase();
  if (tahap === "SUPERVISE" || alat.startsWith("supervisor.")) return "supervisor";
  return null;
}

/** Baris yang membawa keluaran nyata — bukan baris kosong berstatus saja. */
function hasOutput(step: QualityStep): boolean {
  const keluaran = step?.output_summary;
  if (!keluaran || typeof keluaran !== "object") return false;
  return Object.keys(keluaran as Record<string, unknown>).length > 0;
}

/** Satu "run" = satu keputusan yang punya jejak agen. */
export function runOf(
  decision: QualityDecision | null | undefined,
  trace: { steps?: QualityStep[] } | null | undefined,
  summary: unknown
): QualityRun {
  const steps = Array.isArray(trace?.steps) ? trace!.steps! : null;
  const times = (steps ?? [])
    .map((step) => Date.parse(String(step?.step_at ?? "")))
    .filter((value) => Number.isFinite(value));
  const durationMs = times.length > 1 ? Math.max(...times) - Math.min(...times) : null;
  const tools = Array.from(
    new Set((steps ?? []).map((step) => String(step?.tool_called ?? "").trim()).filter(Boolean))
  );
  const verdict = verdictOf(summary);
  const iteration = Number(decision?.iteration);
  const agents: string[] = [];
  const deliveredAgents: string[] = [];
  for (const step of steps ?? []) {
    const key = agentKeyOf(step);
    if (!key) continue;
    if (!agents.includes(key)) agents.push(key);
    if (hasOutput(step) && !deliveredAgents.includes(key)) deliveredAgents.push(key);
  }
  return {
    id: typeof decision?.decision_id === "string" ? decision.decision_id : "",
    shortId: shortId(decision?.decision_id),
    type: String(decision?.decision_type ?? "").trim() || DASH,
    status: String(decision?.status ?? "").trim() || DASH,
    iteration: Number.isFinite(iteration) ? iteration : null,
    steps: steps ? steps.length : null,
    tools,
    durationMs,
    durationLabel: durationLabel(durationMs),
    verdict,
    verdictLabel: VERDICT_LABEL[verdict],
    fallbackSteps: (steps ?? []).filter(isFallbackStep).length,
    // "Diubah manusia" = keputusan ini sudah pernah ditolak lalu diusulkan ulang.
    humanChanged: Number.isFinite(iteration) && iteration > 1,
    agents,
    deliveredAgents,
  };
}

export type QualityMetrics = {
  runs: number;
  totalSteps: number | null;
  avgSteps: number | null;
  agree: number;
  disagree: number;
  unavailable: number;
  /** Persen kesepakatan dari run YANG DINILAI verifikator (bukan dari semua run). */
  agreementRate: number | null;
  judged: number;
  totalFallbacks: number;
  fallbackRate: number | null;
  humanChanged: number;
  humanChangedRate: number | null;
  avgDurationMs: number | null;
  avgDurationLabel: string;
};

export function qualityMetrics(runs: QualityRun[]): QualityMetrics {
  const list = Array.isArray(runs) ? runs : [];
  const withSteps = list.filter((run) => run.steps !== null);
  const totalSteps = withSteps.length
    ? withSteps.reduce((total, run) => total + (run.steps ?? 0), 0)
    : null;
  const agree = list.filter((run) => run.verdict === "agree").length;
  const disagree = list.filter((run) => run.verdict === "disagree").length;
  const unavailable = list.filter((run) => run.verdict === "unavailable").length;
  const judged = agree + disagree;
  const durations = list
    .map((run) => run.durationMs)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const totalFallbacks = list.reduce((total, run) => total + run.fallbackSteps, 0);
  const humanChanged = list.filter((run) => run.humanChanged).length;
  const avgDurationMs = durations.length
    ? durations.reduce((total, value) => total + value, 0) / durations.length
    : null;
  return {
    runs: list.length,
    totalSteps,
    avgSteps: totalSteps === null || !withSteps.length ? null : totalSteps / withSteps.length,
    agree,
    disagree,
    unavailable,
    judged,
    agreementRate: judged ? (agree / judged) * 100 : null,
    totalFallbacks,
    fallbackRate: totalSteps ? (totalFallbacks / totalSteps) * 100 : null,
    humanChanged,
    humanChangedRate: list.length ? (humanChanged / list.length) * 100 : null,
    avgDurationMs,
    avgDurationLabel: durationLabel(avgDurationMs),
  };
}

export function percentLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return DASH;
  return `${value.toFixed(value < 10 ? 1 : 0)}%`;
}

export function averageLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return DASH;
  return value.toFixed(1);
}

// --- kualitas per agen -----------------------------------------------------

export type AgentVerdicts = { agree: number; disagree: number; unavailable: number };

export type AgentQualityRow = {
  key: string;
  label: string;
  role: "worker" | "supervisor" | "verifier";
  /** Jumlah run yang dinilai (sampel yang sama untuk semua baris). */
  runs: number;
  /** Run yang jejaknya memuat baris agen ini. */
  recorded: number;
  /** Run yang barisnya membawa keluaran nyata. */
  delivered: number;
  /** Run tanpa baris agen ini (runs - recorded). */
  missing: number;
  /** Rincian putusan verifier; null untuk agen lain. */
  verdicts: AgentVerdicts | null;
  verdictNote: string;
};

/**
 * Kualitas per agen dari jejak NYATA — sembilan baris, urutan pipeline.
 *
 * Tidak ada persen karangan: `catatan` hanya berisi hitungan run. Rincian
 * putusan verifier diambil dari approval-summary (`run.verdict`), bukan dari
 * jejak, karena verdict memang tidak ditulis di `agent_traces`.
 * Tanpa run sama sekali → daftar kosong (halaman menulis "belum ada run"),
 * bukan sembilan baris berisi 0.
 */
export function agentQuality(runs: QualityRun[]): AgentQualityRow[] {
  const list = Array.isArray(runs) ? runs : [];
  if (list.length === 0) return [];
  const verdicts: AgentVerdicts = { agree: 0, disagree: 0, unavailable: 0 };
  for (const run of list) {
    verdicts[run.verdict] += 1;
  }
  return SWARM_AGENTS.map((agent) => {
    const recorded = list.filter((run) => (run.agents ?? []).includes(agent.key)).length;
    const delivered = list.filter((run) =>
      (run.deliveredAgents ?? []).includes(agent.key)
    ).length;
    const isVerifier = agent.key === "verifier";
    return {
      key: agent.key,
      label: agent.label,
      role: agent.key === "supervisor" ? "supervisor" : isVerifier ? "verifier" : "worker",
      runs: list.length,
      recorded,
      delivered,
      missing: list.length - recorded,
      verdicts: isVerifier ? verdicts : null,
      verdictNote: isVerifier
        ? `${VERDICT_LABEL.agree} ${verdicts.agree} · ${VERDICT_LABEL.disagree} ${verdicts.disagree} · ${VERDICT_LABEL.unavailable} ${verdicts.unavailable}`
        : DASH,
    };
  });
}
