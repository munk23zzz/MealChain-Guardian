import { dueLabel } from "./today";

// Putusan mesin aturan persetujuan (enum backend) → bahasa manusia; nilai tak
// dikenal tetap ditampilkan apa adanya (jujur, tanpa menebak).
const REQUIREMENT_VERDICT_ID: Record<string, string> = {
  ok: "terpenuhi",
  consistent: "konsisten",
  flagged: "terindikasi",
  unavailable: "tidak dapat dievaluasi",
};

// Keputusan yang dipakai saat halaman "Decision & Evidence" dibuka tanpa
// pilihan: utamakan yang BUTUH tindakan (menunggu persetujuan, ditandai
// verifikator, terverifikasi), lalu yang paling baru. Halaman tidak boleh
// terbuka kosong kalau datanya ada — itu yang membuat halaman terasa "tidak ada".
const NEEDS_ACTION = ["pending_approval", "verifier_flagged", "verified", "proposed"];

export function defaultEvidenceId(
  decisions: Array<{ decision_id?: string; status?: string; created_at?: string; expires_at?: string }> | null | undefined
): string | null {
  const list = (decisions ?? []).filter((d) => typeof d?.decision_id === "string" && d.decision_id);
  if (!list.length) return null;
  const time = (d: { expires_at?: string; created_at?: string }) => {
    const t = Date.parse(String(d?.expires_at ?? d?.created_at ?? ""));
    return Number.isFinite(t) ? t : 0;
  };
  for (const status of NEEDS_ACTION) {
    const kandidat = list.filter((d) => String(d.status) === status).sort((a, b) => time(a) - time(b));
    if (kandidat.length) return kandidat[0].decision_id!;
  }
  return [...list].sort((a, b) => time(b) - time(a))[0].decision_id!;
}

export type ComplianceStatus = "PASS" | "FAIL" | "NEEDS_VERIFICATION";

export type ComplianceEvidence = {
  id: string;
  evidence_type: string;
  payload?: Record<string, unknown> | null;
  is_consistent?: boolean | null;
  recorded_at?: string | null;
};

export type ComplianceDossier = {
  decision_id: string;
  content_address?: string;
  signature?: Record<string, unknown>;
  verify?: boolean | null;
  decision?: Record<string, unknown>;
  evidence?: ComplianceEvidence[];
  approvals?: unknown[];
  traces?: unknown[];
  [key: string]: unknown;
};

export type EvidenceRow = {
  id: string;
  evidenceType: string;
  status: ComplianceStatus;
  reading: unknown;
  unit: unknown;
  source: unknown;
  provenance: unknown;
  recordedAt: string | null;
  consistency: boolean | null;
  rule: unknown;
  payload: Record<string, unknown>;
};

const STATUS_KEYS = ["status", "safety_status", "outcome_status"] as const;
const READING_KEYS = ["reading", "value", "measurement", "measured_value"] as const;

function statusFrom(value: unknown): ComplianceStatus {
  if (typeof value === "string") {
    const upper = value.toUpperCase();
    if (upper === "PASS" || upper === "FAIL" || upper === "NEEDS_VERIFICATION") return upper;
  }
  // Missing persisted status/measurement is not evidence of safety.
  return "NEEDS_VERIFICATION";
}

export function evidenceRowsFromDossier(dossier: ComplianceDossier): EvidenceRow[] {
  return (dossier.evidence ?? []).map((item) => {
    const payload = item.payload ?? {};
    const statusValue = STATUS_KEYS.map((key) => payload[key]).find((value) => value !== undefined);
    const reading = READING_KEYS.map((key) => payload[key]).find((value) => value !== undefined) ?? null;
    return {
      id: item.id,
      evidenceType: item.evidence_type,
      status: statusFrom(statusValue),
      reading,
      unit: payload.unit ?? null,
      source: payload.source ?? payload.provenance ?? null,
      provenance: payload.provenance ?? payload.source ?? null,
      recordedAt: item.recorded_at ?? null,
      consistency: item.is_consistent ?? null,
      rule: payload.rule ?? null,
      payload,
    };
  });
}

// ---------------------------------------------------------------------------
// Langkah 4 (permintaan Roy 2026-10-11): ringkasan untuk halaman tersendiri
// "Decision & Evidence". Semuanya murni (tanpa DOM) supaya bisa diuji dan
// supaya komponen tidak menghitung apa pun sendiri.
//
// Aturan yang dipegang: nilai yang tidak ada ditulis "—", tidak dikarang dan
// tidak diganti 0. "Boleh disetujui" hanya ditulis "Belum" kalau backend
// MENYATAKAN false — kalau belum ada jawaban, ditulis "—".
// ---------------------------------------------------------------------------

/** Nada warna untuk satu baris fakta (dipetakan ke kelas CSS oleh komponen). */
export type FactTone = "ok" | "warn" | "danger" | "muted";

export type FactRow = {
  label: string;
  value: string;
  hint?: string | null;
  tone?: FactTone;
};

const DASH = "—";

function text(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const str = String(value).trim();
  return str === "" ? null : str;
}

function idr(value: unknown): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return DASH;
  return `Rp${num.toLocaleString("id-ID", { maximumFractionDigits: 0 })}`;
}

function shortId(value: unknown): string {
  const str = text(value);
  if (!str) return DASH;
  return str.length > 8 ? str.slice(0, 8) : str;
}

function boolLabel(value: unknown): string {
  if (value === true) return "Ya";
  if (value === false) return "Belum";
  return DASH;
}

/** Hitungan status bukti dari daftar EvidenceRow. */
export function evidenceTally(rows: EvidenceRow[]) {
  const list = Array.isArray(rows) ? rows : [];
  return {
    pass: list.filter((row) => row.status === "PASS").length,
    fail: list.filter((row) => row.status === "FAIL").length,
    needsVerification: list.filter((row) => row.status === "NEEDS_VERIFICATION").length,
    total: list.length,
  };
}

const SAFETY_TONE: Record<string, FactTone> = {
  PASS: "ok",
  FAIL: "danger",
  TIGHT: "warn",
  NEEDS_VERIFICATION: "warn",
};

/** Alamat konten, tanda tangan ECDSA, dan hasil verifikasi dossier. */
export function dossierMeta(dossier: unknown) {
  const payload = (dossier ?? null) as {
    content_address?: unknown;
    signature?: { state?: unknown; algorithm?: unknown; reason?: unknown } | null;
    verify?: unknown;
  } | null;
  if (!payload || typeof payload !== "object") {
    return {
      contentAddress: DASH,
      signatureLabel: DASH,
      signatureReason: null,
      verifyLabel: DASH,
      verifyOk: null,
      hasDossier: false,
    };
  }
  const state = text(payload.signature?.state)?.toLowerCase() ?? null;
  const algorithm = text(payload.signature?.algorithm);
  const signatureLabel =
    state === "signed"
      ? algorithm
        ? `Tertanda (${algorithm})`
        : "Tertanda"
      : state === "unsigned"
        ? "Belum ditandatangani"
        : DASH;
  const verifyOk = typeof payload.verify === "boolean" ? payload.verify : null;
  return {
    contentAddress: text(payload.content_address) ?? DASH,
    signatureLabel,
    signatureReason: text(payload.signature?.reason),
    verifyLabel: verifyOk === true ? "Terverifikasi" : verifyOk === false ? "Tidak terverifikasi" : DASH,
    verifyOk,
    hasDossier: true,
  };
}

/** Identitas keputusan: rute, komoditas, jumlah, iterasi, tenggat, asal-usul. */
export function decisionFacts(decision: unknown, now: Date): FactRow[] {
  const decisionPayload = (decision ?? {}) as Record<string, unknown>;
  // Summary kanonik (/approval-summary) memberi nama lokasi; payload keputusan
  // hanya memberi id — jangan tebak namanya kalau tidak ada.
  const summary = (decisionPayload.summary ?? null) as Record<string, unknown> | null;
  const merged: Record<string, unknown> = summary ? { ...decisionPayload, ...summary } : decisionPayload;
  const source = text(merged.source_location);
  const target = text(merged.target_location);
  const kg = Number(merged.quantity_kg);
  const iteration = Number(merged.iteration);
  // Tenggat bisa ada di root (payload keputusan) atau di `expiry` (summary).
  const expiry = (merged.expiry ?? null) as Record<string, unknown> | null;
  const expiresAt = merged.expires_at ?? expiry?.expires_at ?? null;
  const seconds = Number(merged.seconds_remaining ?? expiry?.seconds_remaining);
  return [
    {
      label: "Rute",
      value: source && target ? `${source} → ${target}` : DASH,
    },
    { label: "Komoditas", value: text(merged.commodity) ?? DASH },
    {
      label: "Jumlah",
      value: Number.isFinite(kg) ? `${kg.toLocaleString("id-ID")} kg` : DASH,
    },
    {
      label: "Iterasi",
      value: Number.isFinite(iteration) ? String(iteration) : DASH,
    },
    { label: "Menggantikan", value: shortId(merged.supersedes_id) },
    { label: "Diusulkan oleh", value: text(merged.proposed_by) ?? DASH },
    {
      label: "Tenggat",
      value: dueLabel(expiresAt, now),
      hint: Number.isFinite(seconds) && seconds > 0 ? `${Math.round(seconds / 60)} mnt sisa di server` : null,
    },
  ];
}

/** Biaya: rincian + total biaya aman terkirim. */
export function costFacts(decision: unknown): FactRow[] {
  const payload = (decision ?? {}) as Record<string, unknown>;
  const summary = (payload.summary ?? null) as Record<string, unknown> | null;
  const breakdown = (summary?.cost_breakdown ?? payload.cost_breakdown ?? {}) as Record<string, unknown>;
  const total = summary?.safe_delivered_cost ?? payload.safe_delivered_cost;
  return [
    { label: "Harga beli", value: breakdown.purchase === undefined ? DASH : idr(breakdown.purchase) },
    { label: "Logistik", value: breakdown.logistics === undefined ? DASH : idr(breakdown.logistics) },
    { label: "Biaya aman terkirim", value: total === undefined || total === null ? DASH : idr(total) },
    { label: "Catatan", value: text(breakdown.note) ?? DASH },
  ];
}

/** Keamanan pangan & jejak eksekusi dari /approval-summary. */
export function safetyFacts(summary: unknown): FactRow[] {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const safety = (payload?.safety ?? null) as Record<string, unknown> | null;
  const verifier = (payload?.verifier ?? null) as Record<string, unknown> | null;
  const worst = text(safety?.worst_status)?.toUpperCase() ?? null;
  const checked = Number(safety?.batches_checked);
  const blocked = typeof safety?.blocked === "boolean" ? safety.blocked : null;
  const verdict = text(verifier?.verdict);
  const verifiedBy = text(verifier?.verified_by);
  return [
    {
      label: "Status keamanan terburuk",
      value: worst ?? DASH,
      tone: worst ? (SAFETY_TONE[worst] ?? "muted") : "muted",
    },
    { label: "Batch diperiksa", value: Number.isFinite(checked) ? String(checked) : DASH },
    {
      label: "Diblokir keamanan",
      value: blocked === null ? DASH : blocked ? "Ya" : "Tidak",
      tone: blocked === null ? "muted" : blocked ? "danger" : "ok",
    },
    {
      label: "Verifikator",
      value: verdict || verifiedBy ? [verdict, verifiedBy].filter(Boolean).join(" · ") : DASH,
    },
    { label: "Nomor material", value: text(payload?.material_number) ?? DASH },
    { label: "Target eksekusi", value: text(payload?.execution_target) ?? DASH },
  ];
}

/** Pemasok + skor keandalan (persen kalau ada). */
export function supplierFact(summary: unknown): FactRow {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const supplier = (payload?.supplier ?? null) as Record<string, unknown> | null;
  const name = text(supplier?.name);
  const score = Number(supplier?.reliability_score);
  return {
    label: "Pemasok",
    value: name ?? DASH,
    hint: name && Number.isFinite(score) ? `keandalan ${Math.round(score * 100)}%` : null,
  };
}

/** Governance: jumlah persetujuan, syarat, izin, alasan tertahan, peran. */
export function approvalFacts(summary: unknown): FactRow[] {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const approvals = Array.isArray(payload?.approvals) ? (payload!.approvals as unknown[]) : null;
  const requirement = (payload?.approval_requirement ?? null) as Record<string, unknown> | null;
  const minApprovals = Number(requirement?.min_approvals);
  const requirementText = text(requirement?.requirement);
  const requirementVerdict = text(requirement?.verdict);
  // Kalau backend tidak memberi kalimat syarat, tuliskan ambangnya apa adanya
  // ("minimal 2 persetujuan"); verdict tetap muncul sebagai petunjuk karena
  // itulah yang menjelaskan kenapa tombol approve masih tertahan.
  const requirementValue =
    requirementText ??
    (Number.isFinite(minApprovals) ? `minimal ${minApprovals} persetujuan` : DASH);
  const blocking = Array.isArray(payload?.blocking_reasons)
    ? (payload!.blocking_reasons as unknown[]).map((reason) => text(reason)).filter(Boolean)
    : [];
  const roles = Array.isArray(payload?.approver_roles)
    ? (payload!.approver_roles as unknown[]).map((role) => text(role)).filter(Boolean)
    : [];
  return [
    {
      label: "Persetujuan",
      value: approvals ? `${approvals.length} dari ${Number.isFinite(minApprovals) ? minApprovals : DASH}` : DASH,
    },
    {
      label: "Syarat persetujuan",
      value: requirementValue,
      hint: requirementVerdict && requirementVerdict !== "ok"
        ? `putusan aturan: ${REQUIREMENT_VERDICT_ID[requirementVerdict.toLowerCase()] ?? requirementVerdict}`
        : null,
    },
    { label: "Boleh disetujui", value: boolLabel(payload?.can_approve) },
    { label: "Boleh dieksekusi", value: boolLabel(payload?.can_execute) },
    { label: "Alasan tertahan", value: blocking.length ? blocking.join(" · ") : DASH },
    { label: "Peran penyetuju", value: roles.length ? roles.join(" · ") : DASH },
  ];
}
