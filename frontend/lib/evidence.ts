import { dueLabel } from "./today";
import { formatDateTime } from "./datetime";
import { roleLabel } from "./settings";
import { statusWord } from "./decision-picker";
import { isPendingAction } from "./topbar";
import {
  agentLabel,
  blockingReasons,
  executionTargetLabel,
  roleList,
  safetyLabel,
} from "./bahasa";

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
  decisions: Array<{
    decision_id?: string;
    status?: string;
    created_at?: string;
    expires_at?: string;
    valid?: boolean | null;
  }> | null | undefined,
  now?: Date | null
): string | null {
  const list = (decisions ?? []).filter((d) => typeof d?.decision_id === "string" && d.decision_id);
  if (!list.length) return null;
  const time = (d: { expires_at?: string; created_at?: string }) => {
    const t = Date.parse(String(d?.expires_at ?? d?.created_at ?? ""));
    return Number.isFinite(t) ? t : 0;
  };
  // 1) Menunggu tindakan DAN jendelanya masih terbuka — jatuh tempo terdekat
  //    dulu. Sebelum ini yang dipilih justru keputusan pending paling lama
  //    kedaluwarsa, sehingga halaman terbuka pada keputusan tanpa tombol
  //    Eksekusi (laporan owner 17 Okt).
  const hidup = list
    .filter((d) => isPendingAction(d as { status?: string; valid?: boolean | null; expires_at?: string }, now))
    .sort((a, b) => time(a) - time(b));
  if (hidup.length) return hidup[0].decision_id!;
  // 2) Semua sudah lewat: perilaku lama — status yang butuh tindakan lebih dulu.
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
// "plain" = tanpa penekanan warna (kelas .fact-plain sudah ada di globals.css);
// diketik eksplisit supaya halaman baru tidak perlu menulis `tone: undefined`.
export type FactTone = "plain" | "ok" | "warn" | "danger" | "muted";

export type FactRow = {
  label: string;
  value: string;
  hint?: string | null;
  tone?: FactTone;
};

const DASH = "—";

/**
 * Apakah baris ini benar-benar punya isi? HANYA "—" yang dianggap kosong.
 * "0", "Rp0", dan "Tidak" adalah jawaban nyata — menyembunyikannya akan
 * mengubah arti (laporan bisa "bersih" karena sesuatu memang nol/tidak).
 */
export function hasValue(row: FactRow): boolean {
  return String(row?.value ?? "").trim() !== DASH;
}

/**
 * Pisahkan baris berisi dari baris yang belum ada datanya. Urutan asli TIDAK
 * diubah — hanya dikelompokkan. Dipakai kartu fakta supaya tidak terbaca
 * seperti dump database (dulu 4 dari 8 baris hanya "—"), tanpa menyembunyikan
 * apa pun: baris kosong tetap tersedia di balik satu klik.
 */
export function splitFacts(rows: FactRow[]): { filled: FactRow[]; empty: FactRow[] } {
  const filled: FactRow[] = [];
  const empty: FactRow[] = [];
  for (const row of rows ?? []) (hasValue(row) ? filled : empty).push(row);
  return { filled, empty };
}

/** Label tombol rincian yang disembunyikan ("" = tidak ada yang disembunyikan). */
export function hiddenFactsLabel(jumlah: number): string {
  if (!Number.isFinite(jumlah) || jumlah <= 0) return "";
  return jumlah === 1 ? "1 rincian belum ada datanya" : `${jumlah} rincian belum ada datanya`;
}

/**
 * Peran yang boleh menyetujui/menolak/mengeksekusi — CERMINAN dari
 * `visibleActions()` di `components/DecisionActions.tsx` (satu-satunya pemanggil
 * API-nya). Kesamaan keduanya dijaga tes paritas di
 * `tests/evidence-summary.test.ts`; jangan menambah peran di sini tanpa
 * menambahnya di sana.
 */
const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

/**
 * Satu kalimat yang menjawab "apa yang harus saya lakukan sekarang?" untuk
 * keputusan yang sedang dibuka. Halaman Decision & Evidence dulu hanya
 * menumpahkan fakta, sehingga pengguna harus menyimpulkan sendiri tindakannya
 * dari belasan baris label/nilai. Kalimat ini HANYA memakai data yang sudah
 * ada di payload (status, approvals, approval_requirement, blocking_reasons,
 * expiry, can_execute) — tidak ada kesimpulan yang dikarang.
 */
export function nextStep(input: {
  role: string;
  status: string;
  summary: unknown;
}): { text: string; tone: FactTone } {
  const role = String(input?.role ?? "");
  const status = String(input?.status ?? "");
  const payload = (input?.summary ?? null) as Record<string, unknown> | null;

  if (!APPROVER_ROLES.has(role)) {
    return {
      text: "Peran ini bersifat pengawasan: buktinya bisa dibaca, tetapi keputusan hanya bisa ditindaklanjuti oleh Kepala SPPG atau Ahli Gizi.",
      tone: "muted",
    };
  }

  const approvals = Array.isArray(payload?.approvals)
    ? (payload!.approvals as unknown[]).length
    : null;
  const requirement = (payload?.approval_requirement ?? null) as Record<string, unknown> | null;
  const minApprovals = Number(requirement?.min_approvals);
  const blocking = blockingReasons(payload);
  const expiry = (payload?.expiry ?? null) as Record<string, unknown> | null;
  const lewat = expiry ? expiry.valid === false : false;
  // Daftar penahan dipangkas: tiga alasan sekaligus membuat kalimatnya
  // berubah jadi dinding teks dan justru tidak terbaca.
  const penahanDaftar =
    blocking.length > 2
      ? `${blocking.slice(0, 2).join(" · ")} (+${blocking.length - 2} lain)`
      : blocking.join(" · ");
  const penahan = penahanDaftar ? ` — yang menahan: ${penahanDaftar}` : "";

  if (status === "rejected") {
    return {
      text: "Keputusan sudah ditolak — agent dapat mengajukan iterasi baru dari keputusan ini.",
      tone: "danger",
    };
  }
  if (status === "executed") {
    return {
      text: "Keputusan sudah dieksekusi — tidak ada tindakan tersisa selain membaca buktinya.",
      tone: "ok",
    };
  }
  if (payload?.can_execute === true) {
    return { text: "Semua syarat terpenuhi — keputusan siap dieksekusi.", tone: "ok" };
  }
  if (status === "review_only") {
    // Audit M6: temuan (mis. anomali harga) berhenti sebagai bukti; jendela
    // berlakunya tidak relevan karena tidak ada barang yang akan bergerak.
    return {
      text: "Temuan tinjauan — dicatat sebagai bukti. Tidak ada transfer yang dieksekusi dari keputusan ini.",
      tone: "plain",
    };
  }
  if (lewat) {
    return {
      text: `Jendela berlaku keputusan sudah lewat${penahan}. Mintakan keputusan baru atau ajukan iterasi ulang sebelum barang bergerak.`,
      tone: "warn",
    };
  }
  if (status === "verifier_flagged") {
    return {
      text: `Verifikator menandai keputusan ini${penahan}. Selesaikan verifikasi ulang sebelum minta persetujuan.`,
      tone: "warn",
    };
  }
  if (status === "pending_approval") {
    const hitung =
      approvals === null
        ? ""
        : ` (${approvals} dari ${Number.isFinite(minApprovals) ? minApprovals : "?"})`;
    return { text: `Menunggu persetujuan${hitung}${penahan}.`, tone: "warn" };
  }
  if (status === "proposed") {
    return {
      text: `Keputusan belum diajukan — ajukan untuk persetujuan supaya Ahli Gizi dan Kepala SPPG bisa menilai${penahan}.`,
      tone: "warn",
    };
  }
  return { text: "Tidak ada tindakan mendesak untuk keputusan ini.", tone: "plain" };
}

// ─────────────────────────────────────────────────────────────────────────────
// DESAIN BARU HALAMAN BUKTI (17 Okt 2026) — struktur "catatan keputusan".
//
// Riset pola (rujukan lengkap di _qa/rencana-decision-evidence-v2.md):
//   • Approval workflow (UX Patterns Guide): catatan permintaan yang dirutekan —
//     ringkasan, penyetuju, status rute, tenggat, kontrol keputusan, riwayat.
//   • Aturan 3 detik (AgentInterface): aksi = huruf terbesar, lalu skala, lalu
//     konsekuensi; "kuning bukan merah" — merah hanya untuk yang merusak.
//   • Triage lewat FLAG (Code and Proof): daftar panjang bisa ditinjau kalau
//     yang menyimpang ditandai, dan konsekuensinya dirender dari data
//     terstruktur — bukan dari kalimat yang dikarang.
//
// Semua fungsi di bawah HANYA membaca field yang sudah dikirim backend:
//   /decisions/{id} → decision_type, status, quantity_kg, created_at,
//     proposed_by, iteration, rejection_reason, verified_by
//   /decisions/{id}/approval-summary → source/target_location, commodity,
//     safe_delivered_cost, cost_breakdown, supplier, verifier, safety, expiry,
//     approval_requirement, approval_state, approvals, can_execute,
//     blocking_reasons, execution_target
// Tidak ada angka, ambang, atau sebab yang dikarang di sini.
// ─────────────────────────────────────────────────────────────────────────────

/** Aksi dalam bahasa manusia untuk judul kepala halaman (bukan label jenis). */
const HEADLINE_VERBS: Record<string, string> = {
  regional_balance: "Alihkan",
  safety_disruption: "Ganti pasokan",
  price_anomaly: "Sesuaikan harga",
  surplus_redistribution: "Redistribusikan",
  supplier_exclusion: "Keluarkan pemasok",
  supplier_restoration: "Pulihkan pemasok",
};

export type MetricItem = { label: string; value: string };
export type FlagItem = { id: string; label: string; text: string; tone: FactTone };
export type RouteStep = {
  id: "proposed" | "verify" | "approve" | "execute";
  label: string;
  state: "done" | "current" | "waiting" | "blocked";
  detail: string;
};

const objectOf = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

const listOf = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const kg = (value: unknown): string | null => {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) return null;
  return `${num.toLocaleString("id-ID", { maximumFractionDigits: 3 })} kg`;
};

/** Angka rupiah bertanda untuk selisih (mis. "+Rp486.000"). */
function selisih(value: number): string {
  if (!Number.isFinite(value) || value === 0) return idr(value);
  return `${value > 0 ? "+" : "−"}${idr(Math.abs(value))}`;
}

/**
 * Judul satu baris: aksi + jumlah + komoditas + rute yang BENAR-BENAR diketahui.
 * Bagian yang datanya tidak ada dihilangkan (bukan ditulis "—"): judul dengan
 * tanda pisah justru terbaca seperti data rusak.
 */
export function decisionHeadline(decision: unknown, summary: unknown): string {
  const d = objectOf(decision) ?? {};
  const s = objectOf(summary) ?? {};
  const type = text(d.decision_type) ?? text(s.decision_type);
  const verb = type ? HEADLINE_VERBS[type] : null;
  const kepala = verb ?? (type ? type.replace(/_/g, " ") : "Keputusan");
  const bagian = [kepala];
  const jumlah = kg(d.quantity_kg ?? s.quantity_kg);
  if (jumlah) bagian.push(jumlah);
  const komoditas = text(s.commodity) ?? text(d.commodity);
  if (komoditas) bagian.push(komoditas);
  const asal = text(s.source_location) ?? text(d.source_location);
  const tujuan = text(s.target_location) ?? text(d.target_location);
  const rute = asal && tujuan ? `: ${asal} → ${tujuan}` : "";
  return `${bagian.join(" ")}${rute}`;
}

/** 2–4 angka kunci untuk dibaca dalam tiga detik. Yang tidak ada tidak dipaksa. */
export function decisionMetrics(decision: unknown, summary: unknown, now?: Date | null): MetricItem[] {
  const d = objectOf(decision) ?? {};
  const s = objectOf(summary) ?? {};
  const rows: MetricItem[] = [];
  const jumlah = kg(d.quantity_kg ?? s.quantity_kg);
  if (jumlah) rows.push({ label: "Kuantitas", value: jumlah });
  const biaya = Number(s.safe_delivered_cost ?? d.safe_delivered_cost);
  if (Number.isFinite(biaya)) rows.push({ label: "Biaya aman terkirim", value: idr(biaya) });
  const beli = Number(objectOf(s.cost_breakdown)?.purchase);
  if (Number.isFinite(biaya) && Number.isFinite(beli) && beli > 0) {
    rows.push({ label: "Selisih dari harga beli", value: selisih(biaya - beli) });
  }
  // "Tujuan" keluar dari strip: ia sudah ada di judul keputusan ("…: Bogor → Jakarta").
  // Slot keempat dipakai TENGGAT, yang sebelumnya diulang di kartu Identitas —
  // jadi satu angka pindah tempat, bukan informasi yang hilang.
  const expiresAt =
    text(s.expires_at) ??
    text(d.expires_at) ??
    text((objectOf(s.expiry) ?? {}).expires_at) ??
    text((objectOf(d.expiry) ?? {}).expires_at);
  if (expiresAt) {
    // Tanpa jam acuan kita tetap menyebut barisnya dengan "—": pembaca perlu
    // tahu keputusan INI punya tenggat, hanya jamnya belum bisa dihitung.
    rows.push({ label: "Tenggat", value: now ? dueLabel(expiresAt, now) : DASH });
  }
  return rows;
}

/**
 * "Perlu diperhatikan": TRIASE, bukan alarm. Hanya keadaan yang benar-benar
 * dinyatakan data yang masuk — keputusan sehat menghasilkan daftar kosong.
 */
export function attentionFlags(input: { decision: unknown; summary: unknown }): FlagItem[] {
  const d = objectOf(input?.decision) ?? {};
  const s = objectOf(input?.summary) ?? {};
  const status = (text(d.status) ?? text(s.status) ?? "").toLowerCase();
  const flags: FlagItem[] = [];

  const verifier = objectOf(s.verifier);
  if (status !== "rejected" && !text(verifier?.verified_by)) {
    flags.push({
      id: "verifier",
      label: "Belum diverifikasi",
      text: "Belum ada verdict verifier untuk keputusan ini — eksekusi ditolak sampai diverifikasi.",
      tone: "warn",
    });
  }

  const expiry = objectOf(s.expiry);
  if (expiry && expiry.valid === false) {
    const habis = formatDateTime(String(expiry.expires_at ?? ""));
    flags.push({
      id: "expiry",
      label: "Jendela berlaku lewat",
      text:
        habis === DASH
          ? "Jendela berlaku sudah habis; eksekusi ditolak sampai ada keputusan baru."
          : `Jendela berlaku habis ${habis}; eksekusi ditolak sampai ada keputusan baru.`,
      tone: "warn",
    });
  }

  const safety = objectOf(s.safety);
  if (safety?.blocked === true) {
    flags.push({
      id: "safety",
      label: "Keamanan batch sumber",
      text: text(safety.reason) ?? "Batch sumber tidak lolos pemeriksaan keamanan.",
      tone: "danger",
    });
  }

  if (status === "rejected") {
    const alasan = text(d.rejection_reason);
    flags.push({
      id: "rejected",
      label: "Keputusan ditolak",
      text: alasan
        ? `Alasan: ${alasan}`
        : "Permintaan ini berhenti; agent dapat mengajukan iterasi baru dengan perbaikan.",
      tone: "danger",
    });
  }

  return flags;
}

/** Kata manusia untuk verdict verifier (peta sudah ada; jangan diduplikasi). */
function verdictWord(verdict: unknown): string | null {
  const key = text(verdict)?.toLowerCase();
  if (!key) return null;
  return REQUIREMENT_VERDICT_ID[key] ?? key.replace(/_/g, " ");
}

/**
 * Jalur persetujuan sebagai empat langkah tetap (diajukan → verifikasi →
 * persetujuan → eksekusi). Sama untuk semua peran; hanya kontrolnya yang
 * berbeda. Rincian langkah menyebut SIAPA memegang dan SIAPA berikutnya.
 */
export function approvalRoute(input: {
  decision: unknown;
  summary: unknown;
  now: Date | null;
}): RouteStep[] {
  const d = objectOf(input?.decision) ?? {};
  const s = objectOf(input?.summary) ?? {};
  const status = (text(d.status) ?? text(s.status) ?? "").toLowerCase();

  const created = formatDateTime(String(d.created_at ?? ""));
  const steps: RouteStep[] = [
    {
      id: "proposed",
      label: "Diajukan",
      state: "done",
      detail: [agentLabel(d.proposed_by) ?? "agent", created === DASH ? null : created]
        .filter(Boolean)
        .join(" · "),
    },
  ];

  const verifier = objectOf(s.verifier);
  const verifiedBy = text(verifier?.verified_by) ?? text(d.verified_by);
  steps.push({
    id: "verify",
    label: "Verifikasi agent",
    state: verifiedBy ? "done" : "waiting",
    detail: verifiedBy
      ? [verdictWord(verifier?.verdict), agentLabel(verifiedBy)].filter(Boolean).join(" · ")
      : "belum ada verdict",
  });

  const state = objectOf(s.approval_state);
  const req = objectOf(s.approval_requirement);
  const approvals = listOf(s.approvals).map((row) => objectOf(row) ?? {});
  const disetujui = approvals.filter((row) => row.approved === true);
  const peran = new Set(
    listOf(state?.approved_roles)
      .map((role) => String(role))
      .concat(disetujui.map((row) => String(row.role ?? "")))
  );
  const grup = listOf(req?.required_roles);
  const kurang = grup.filter(
    (group) => !listOf(group).some((role) => peran.has(String(role)))
  );
  const min = Number(req?.min_approvals);
  // Hitungan memakai PERAN unik yang sudah menyetujui (requirement berbicara
  // grup peran, bukan jumlah klik): dua approval dari peran sama tetap "1 dari 2".
  const disetujuiPeran = Array.from(peran).filter((role) => role !== "").length;
  const jumlah = Number.isFinite(min)
    ? `${disetujuiPeran} dari ${min}`
    : `${disetujuiPeran} disetujui`;
  const berikutnya = kurang
    .map((group) => listOf(group).map((role) => roleLabel(String(role))).join(" atau "))
    .filter(Boolean);
  const ditolak = state?.rejected === true || status === "rejected";
  const puas =
    !ditolak &&
    (state?.satisfied === true || (kurang.length === 0 && grup.length > 0));
  steps.push({
    id: "approve",
    label: "Persetujuan",
    state: ditolak ? "blocked" : puas ? "done" : "current",
    detail: [
      jumlah,
      berikutnya.length ? `berikutnya: ${berikutnya.join(" · ")}` : null,
    ]
      .filter(Boolean)
      .join(" · "),
  });

  const executed = status === "executed";
  const target = text(s.execution_target);
  steps.push({
    id: "execute",
    label: "Eksekusi",
    state: executed ? "done" : s.can_execute === true ? "current" : "waiting",
    detail: executed
      ? target
        ? `sudah dijalankan (${target})`
        : "sudah dijalankan"
      : target
        ? `target ${executionTargetLabel(target) ?? target}`
        : "belum dijalankan",
  });

  return steps;
}

/**
 * Akibat tiap pilihan — jawaban untuk "kalau saya pilih ini, lalu apa?".
 * Hanya bersumber data: target eksekusi, penghalang, status, nomor iterasi.
 */
export function consequences(input: { decision: unknown; summary: unknown }): {
  approve: string;
  reject: string;
} {
  const d = objectOf(input?.decision) ?? {};
  const s = objectOf(input?.summary) ?? {};
  const target = text(s.execution_target);
  const penghalang = blockingReasons(s);

  let approve: string;
  if (s.can_execute === true) {
    approve =
      target === "MOCK"
        ? "Eksekusi dijalankan di simulasi (mock) — tidak ada pesanan nyata yang dibuat."
        : target
          ? `Eksekusi dijalankan di target ${executionTargetLabel(target) ?? target}.`
          : "Eksekusi dijalankan.";
  } else if (penghalang.length) {
    const dipangkas = penghalang.slice(0, 2).join(" · ");
    const sisa = penghalang.length > 2 ? ` (+${penghalang.length - 2} lain)` : "";
    approve = `Belum bisa dieksekusi: ${dipangkas}${sisa}.`;
  } else {
    approve = "Belum bisa dieksekusi — masih ada syarat yang belum terpenuhi.";
  }

  const status = (text(d.status) ?? text(s.status) ?? "").toLowerCase();
  const iterasi = Number(d.iteration ?? s.iteration);
  const reject =
    status === "rejected"
      ? "Keputusan sudah ditolak; agent dapat mengajukan iterasi baru dengan perbaikan."
      : `Permintaan ini berhenti. Agent dapat mengajukan iterasi ${
          Number.isFinite(iterasi) ? `v${iterasi + 1}` : "baru"
        } dengan perbaikan.`;

  return { approve, reject };
}

// ── Langkah 2 (17 Okt 2026): lini masa audit + umur jendela ──────────────────

/** Catatan verifier yang hanya mengulang verdict mentah → jangan diulang. */
function catatanUnik(verdict: unknown, note: unknown): string | null {
  const isi = text(note);
  if (!isi) return null;
  const putusan = text(verdict);
  return putusan && isi.trim().toLowerCase() === putusan.trim().toLowerCase() ? null : isi;
}

export type AuditEvent = {
  id: string;
  /** ISO waktu kejadian, atau null kalau memang tidak ada — jangan dikarang. */
  at: string | null;
  title: string;
  /** Siapa pelakunya (peran manusia bila yang tersedia hanya peran backend). */
  actor: string | null;
  detail: string | null;
  tone: FactTone;
};

/** Waktu → milidetik; tak terbaca = Infinity supaya tetap di urutan terakhir. */
function waktu(value: unknown): number {
  if (value === null || value === undefined || value === "") return Infinity;
  const ms = Date.parse(String(value));
  return Number.isFinite(ms) ? ms : Infinity;
}

/**
 * Lini masa audit satu keluarga keputusan: iterasi lama → pengajuan iterasi kini
 * → verifikasi → tiap keputusan orang. Urutannya BERCERITA (bukan diurut ulang
 * menurut jam), karena verifikasi tidak punya kolom waktunya sendiri di DB —
 * mengurutkannya secara kronologis akan menaruh verifikasi di akhir, salah.
 *
 * Hanya memakai: `/decisions/{id}` (created_at, proposed_by, verifier_note,
 * iteration, rejection_reason), `/approval-summary` (verifier, approvals[]),
 * dan `/decisions/{id}/chain` (iterasi keluarga).
 */
export function auditTimeline(input: {
  decision: unknown;
  summary: unknown;
  chain: unknown;
}): AuditEvent[] {
  const d = objectOf(input?.decision) ?? {};
  const s = objectOf(input?.summary) ?? {};
  const idKini = text(d.decision_id);
  const events: AuditEvent[] = [];

  const riwayat = listOf(input?.chain)
    .map((row) => objectOf(row))
    .filter((row): row is Record<string, unknown> => row !== null);
  for (const item of riwayat) {
    // Iterasi yang sedang dibuka dirender dari payload keputusan di bawah.
    if (idKini && text(item.decision_id) === idKini) continue;
    const nomor = Number(item.iteration);
    const status = (text(item.status) ?? "").toLowerCase();
    const alasan = text(item.rejection_reason);
    events.push({
      id: `iterasi-${text(item.decision_id) ?? events.length}`,
      at: text(item.created_at),
      title: `v${Number.isFinite(nomor) ? nomor : "?"} diajukan`,
      actor: null,
      detail:
        [status ? statusWord(status) : null, alasan ? `alasan: ${alasan}` : null]
          .filter(Boolean)
          .join(" · ") || null,
      tone: status === "rejected" ? "danger" : "plain",
    });
  }

  const nomorKini = Number(d.iteration ?? s.iteration);
  events.push({
    id: "diajukan",
    at: text(d.created_at),
    title: `v${Number.isFinite(nomorKini) ? nomorKini : "?"} diajukan`,
    actor: agentLabel(d.proposed_by),
    detail: null,
    tone: "plain",
  });

  const verifier = objectOf(s.verifier);
  const verifiedBy = text(verifier?.verified_by) ?? text(d.verified_by);
  if (verifiedBy) {
    events.push({
      id: "verifikasi",
      // Model Decision tidak menyimpan waktu verifikasi — null, bukan jam karangan.
      at: null,
      title: "Diverifikasi",
      actor: agentLabel(verifiedBy),
      // Kalau catatan verifier cuma mengulang putusannya ("consistent" →
      // "konsisten · consistent"), jangan dibordukan — sekali saja.
      detail:
        [verdictWord(verifier?.verdict), catatanUnik(verifier?.verdict, d.verifier_note)]
          .filter(Boolean)
          .join(" · ") || null,
      tone: "ok",
    });
  }

  const approvals = listOf(s.approvals).map((row) => objectOf(row) ?? {});
  const berurut = approvals
    .map((row, index) => ({ row, index, ms: waktu(row.approved_at) }))
    .sort((a, b) => (a.ms === b.ms ? a.index - b.index : a.ms - b.ms))
    .map((entry) => entry.row);
  for (let index = 0; index < berurut.length; index += 1) {
    const row = berurut[index];
    // Baris tanpa keputusan biner (true/false) BUKAN penolakan: mengklaim
    // "Ditolak" dari field yang tidak ada = melaporkan sesuatu yang tak terjadi.
    if (row.approved !== true && row.approved !== false) continue;
    const setuju = row.approved === true;
    const peran = text(row.role);
    events.push({
      id: `keputusan-${index}`,
      at: text(row.approved_at),
      title: setuju ? "Disetujui" : "Ditolak",
      // Nama orangnya tidak dikirim API — peran manusia adalah yang paling jujur.
      actor: peran ? roleLabel(peran) : null,
      detail: text(row.comment),
      tone: setuju ? "ok" : "danger",
    });
  }

  const status = (text(d.status) ?? text(s.status) ?? "").toLowerCase();
  if (status === "rejected" && !approvals.some((row) => row.approved === false)) {
    events.push({
      id: "ditolak",
      at: null,
      title: "Ditolak",
      actor: null,
      detail: text(d.rejection_reason),
      tone: "danger",
    });
  }

  return events;
}

/**
 * Umur jendela berlaku dalam persen. SENGAJA tidak memakai ember
 * "fresh/aging/breached" ala Skopx: target waktu-ke-keputusan per jenis
 * permintaan tidak ada di data repo ini, dan mengarang ambangnya = mengarang
 * kebijakan. Yang ditampilkan hanya dua fakta: persen terpakai & lewat/tidak.
 */
export function windowUsage(input: {
  created_at: unknown;
  expires_at: unknown;
  now: Date | null;
}): { state: "aman" | "lewat" | "tidak diketahui"; persen: number | null; label: string } {
  const tidakTahu = {
    state: "tidak diketahui" as const,
    persen: null,
    label: "Umur jendela tidak dapat dihitung",
  };
  const now = input?.now instanceof Date && Number.isFinite(input.now.getTime()) ? input.now : null;
  const mulai = waktu(input?.created_at);
  const selesai = waktu(input?.expires_at);
  if (!now || !Number.isFinite(mulai) || !Number.isFinite(selesai)) return tidakTahu;
  const total = selesai - mulai;
  if (!(total > 0)) return tidakTahu;
  if (now.getTime() >= selesai) return { state: "lewat", persen: 100, label: "Jendela lewat" };
  const persen = Math.min(99, Math.max(0, Math.round(((now.getTime() - mulai) / total) * 100)));
  return { state: "aman", persen, label: `Jendela terpakai ${persen}%` };
}

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

/** Identitas keputusan: rute, komoditas, iterasi, asal-usul. */
export function decisionFacts(decision: unknown, _now?: Date | null): FactRow[] {
  const decisionPayload = (decision ?? {}) as Record<string, unknown>;
  // Summary kanonik (/approval-summary) memberi nama lokasi; payload keputusan
  // hanya memberi id — jangan tebak namanya kalau tidak ada.
  const summary = (decisionPayload.summary ?? null) as Record<string, unknown> | null;
  const merged: Record<string, unknown> = summary ? { ...decisionPayload, ...summary } : decisionPayload;
  const source = text(merged.source_location);
  const target = text(merged.target_location);
  const iteration = Number(merged.iteration);
  return [
    {
      label: "Rute",
      value: source && target ? `${source} → ${target}` : DASH,
    },
    { label: "Komoditas", value: text(merged.commodity) ?? DASH },
    {
      label: "Iterasi",
      value: Number.isFinite(iteration) ? String(iteration) : DASH,
    },
    { label: "Menggantikan", value: shortId(merged.supersedes_id) },
    { label: "Diusulkan oleh", value: agentLabel(merged.proposed_by) ?? DASH },
    // "Jumlah" dan "Tenggat" sengaja TIDAK di sini: keduanya sudah tampil di strip
    // metrik kepala halaman (F1 redesign, _qa/rencana-decision-evidence-v3.md).
  ];
}

/** Label jujur untuk baris angkut kaki pertama (Fase 7d). */
const LEG_REFERENCE_HINT: Record<string, string> = {
  supplier_coordinates: "koordinat pemasok",
  supplier_coordinates_missing: "jarak tidak diketahui — koordinat pemasok kosong",
  no_supplier: "tanpa identitas pemasok",
};

/**
 * Hint baris angkut pemasok → SPPG: km bila benar-benar diketahui, atau
 * ALASANnya bila tidak. Angka 0 km tidak pernah ditampilkan sebagai jarak —
 * nol berarti "pemasok menempel di dinding SPPG", klaim yang tidak punya dasar.
 */
export function supplierLegHint(breakdown: unknown): string | null {
  const bd = (breakdown ?? {}) as Record<string, unknown>;
  const reference = text(bd.supplier_leg_reference);
  const km = Number(bd.supplier_leg_km);
  if (reference === "supplier_coordinates" && Number.isFinite(km)) {
    return `${km.toLocaleString("id-ID", { maximumFractionDigits: 3 })} km dari pemasok`;
  }
  if (reference) return LEG_REFERENCE_HINT[reference] ?? "jarak tidak diketahui";
  return null;
}

/** Biaya: rincian + total biaya aman terkirim. */
export function costFacts(decision: unknown): FactRow[] {
  const payload = (decision ?? {}) as Record<string, unknown>;
  const summary = (payload.summary ?? null) as Record<string, unknown> | null;
  const breakdown = (summary?.cost_breakdown ?? payload.cost_breakdown ?? {}) as Record<string, unknown>;
  const rows: FactRow[] = [
    { label: "Harga beli", value: breakdown.purchase === undefined ? DASH : idr(breakdown.purchase) },
    { label: "Logistik", value: breakdown.logistics === undefined ? DASH : idr(breakdown.logistics) },
    { label: "Catatan", value: text(breakdown.note) ?? DASH },
  ];
  // Fase 7d: biaya angkut dipecah jadi kaki pertama (pemasok → SPPG sumber) dan
  // linehaul (SPPG → SPPG). Baris hanya muncul bila backend memang mengirim
  // pecahannya — keputusan lama tidak diberi baris "—" palsu.
  const leg = breakdown.transport_supplier_leg;
  const linehaul = breakdown.transport_linehaul;
  if (leg !== undefined || linehaul !== undefined) {
    rows.splice(
      2,
      0,
      {
        label: "Angkut pemasok → SPPG",
        value: leg === undefined ? DASH : idr(leg),
        hint: supplierLegHint(breakdown),
      },
      {
        label: "Angkut antar SPPG",
        value: linehaul === undefined ? DASH : idr(linehaul),
      }
    );
  }
  return rows;
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
      // Nada tetap dari enum mentah; yang dibaca manusia adalah katanya.
      value: safetyLabel(worst) ?? DASH,
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
      // "consistent · verifier_agent" → "konsisten · Agen verifikator".
      value:
        [verdictWord(verdict), agentLabel(verifiedBy)].filter(Boolean).join(" · ") || DASH,
    },
    { label: "Nomor material", value: text(payload?.material_number) ?? DASH },
    { label: "Target eksekusi", value: executionTargetLabel(payload?.execution_target) ?? DASH },
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

/** Governance: syarat, izin, alasan tertahan, peran. Hitungan persetujuan ada di stepper. */
export function approvalFacts(summary: unknown): FactRow[] {
  const payload = (summary ?? null) as Record<string, unknown> | null;
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
  const blocking = blockingReasons(payload);
  const roles = roleList(payload?.approver_roles);
  return [
    {
      label: "Syarat persetujuan",
      value: requirementValue,
      hint: requirementVerdict && requirementVerdict !== "ok"
        ? `aturan persetujuan: ${REQUIREMENT_VERDICT_ID[requirementVerdict.toLowerCase()] ?? requirementVerdict}`
        : null,
    },
    { label: "Boleh disetujui", value: boolLabel(payload?.can_approve) },
    { label: "Boleh dieksekusi", value: boolLabel(payload?.can_execute) },
    { label: "Alasan tertahan", value: blocking.length ? blocking.join(" · ") : DASH },
    { label: "Peran penyetuju", value: roles.length ? roles.join(" · ") : DASH },
  ];
}
