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
 * Label untuk baris TERISI yang dilipat karena kartu terlalu panjang.
 * Bedanya dengan `hiddenFactsLabel`: ini bukan data kosong, hanya sekunder —
 * karena itu kalimatnya netral ("rincian lainnya"), bukan "belum ada datanya".
 */
export function hiddenRowsLabel(jumlah: number): string {
  if (!Number.isFinite(jumlah) || jumlah <= 0) return "";
  return jumlah === 1 ? "1 rincian lainnya" : `${jumlah} rincian lainnya`;
}

/**
 * Peran yang boleh menyetujui/menolak/mengeksekusi — CERMINAN dari
 * `visibleActions()` di `components/DecisionActions.tsx` (satu-satunya pemanggil
 * API-nya). Kesamaan keduanya dijaga tes paritas di
 * `tests/evidence-summary.test.ts`; jangan menambah peran di sini tanpa
 * menambahnya di sana.
 */
const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);




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
  // "Alihkan" terbaca seperti mengalihkan perhatian/alamat, bukan memindahkan
  // pasokan. "Seimbangkan" menyebut tujuan tindakannya dan tidak mengklaim
  // sumbernya (bisa pemasok, bisa surplus SPPG lain — lihat baris pengirim).
  regional_balance: "Seimbangkan",
  safety_disruption: "Ganti pasokan",
  price_anomaly: "Sesuaikan harga",
  surplus_redistribution: "Redistribusikan",
  supplier_exclusion: "Keluarkan pemasok",
  // Judul pengadaan dibaca dua baris (permintaan pemilik 24 Okt 2026):
  //   Pengadaan 780 kg telur
  //   UD Sumber Rejeki Telur → Jakarta
  // Kata "pemasok" tidak perlu diulang karena baris kedua sudah nama pemasok.
  supplier_procurement: "Pengadaan",
  // Restorasi = usul MEMBUKA lagi eksklusi pemasok, bukan pengiriman barang.
  // Kuncinya WAJIB nama tipe yang benar-benar bisa disimpan backend —
  // `supplier_exclusion_restoration` (CheckConstraint `decisions_decision_type_check`
  // di backend/app/models/decisions.py, dan `/supplier-exclusions/{id}/restore`).
  // Nama karangan seperti "supplier_restoration" tidak pernah cocok, sehingga
  // judul jatuh ke slug mentah "supplier exclusion restoration" (terukur di UI
  // 28 Okt 2026). Frasa "status" mengikuti label Jenis yang sudah dipakai
  // ApprovalModal/RecommendationCard ("Pemulihan status pemasok").
  supplier_exclusion_restoration: "Pulihkan status pemasok",
};

/**
 * Jenis keputusan yang TIDAK menggerakkan barang: penyesuaian harga, pemasok
 * dikeluarkan, pemasok dipulihkan. Dipakai dua kali — menyembunyikan tanda "→"
 * (yang terbaca seperti truk berangkat) dan memilih cara menyebut pihaknya.
 */
const JENIS_ADMINISTRATIF = new Set([
  "price_anomaly",
  "supplier_exclusion",
  "supplier_exclusion_restoration",
]);

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
  // Asal barang: PEMASOK bila keputusan menyebut pemasok (kolom
  // source_location pada kasus itu hanya kota gudang), kota SPPG lain bila
  // ini pemindahan antar-SPPG. Tanpa pemasok dan tanpa kota asal, tidak ada
  // baris rute sama sekali — lebih baik diam daripada mengarang asal.
  const pemasok = supplierNameOf(s) ?? supplierNameOf(d);
  const kotaAsal = text(s.source_location) ?? text(d.source_location);
  // Keputusan yang barangnya DIBELI dari pemasok (pengadaan, ganti pasokan)
  // menyebut nama perusahaan; pemindahan antar-SPPG menyebut kota asal.
  const dariPemasok = type === "supplier_procurement" || type === "safety_disruption";
  const asal = dariPemasok ? pemasok ?? kotaAsal : kotaAsal ?? pemasok;
  const tujuan = text(s.target_location) ?? text(d.target_location);
  // Jenis administratif BUKAN pengiriman barang: harga disesuaikan, pemasok
  // dikeluarkan, pemasok dipulihkan. Menampilkan "Cianjur → Jakarta" di
  // judulnya membuat pembaca mengira ada truk berangkat, padahal tidak ada
  // barang bergerak — jadi pihak yang diubah (pemasok) dan lingkupnya disebut
  // dengan "di", bukan panah.
  const administratif = type ? JENIS_ADMINISTRATIF.has(type) : false;
  if (administratif) {
    // Hanya nama pemasok + kota tujuan: `source_location` pada kasus ini kota
    // gudang/cakupan, bukan kota asal kiriman, sehingga tidak boleh dicetak
    // sebagai sisi asal ("Cianjur di Jakarta" bukan kalimat).
    const lingkup = pemasok && tujuan ? `${pemasok} di ${tujuan}` : pemasok ?? "";
    if (lingkup) return `${bagian.join(" ")}: ${lingkup}`;
    return tujuan ? `${bagian.join(" ")} di ${tujuan}` : bagian.join(" ");
  }
  const bedaKota = Boolean(asal && tujuan && asal !== tujuan);
  // Barang dari pemasok dibaca dua baris: baris 1 "apa", baris 2 "dari siapa
  // ke mana". Pemindahan antar-SPPG tetap satu baris karena asalnya kota.
  if (dariPemasok && pemasok && bedaKota) {
    return `${bagian.join(" ")}\n${pemasok} → ${tujuan}`;
  }
  const rute = bedaKota ? `: ${asal} → ${tujuan}` : "";
  return `${bagian.join(" ")}${rute}`;
}

/**
 * Angka dari payload, atau `null` bila nilainya memang tidak diketahui.
 *
 * Dipakai supaya "tidak ada data" tidak berubah menjadi angka: `Number(null)`
 * dan `Number("")` sama-sama bernilai 0, sehingga nilai kosong sempat tercetak
 * "Rp0" — angka yang tidak pernah terukur. Angka 0 yang SUNGGUH tersimpan tetap
 * dikembalikan sebagai 0 (0 terukur sah ditampilkan).
 */
function angkaAtauNull(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string" && value.trim() === "") return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

/** 2–4 angka kunci untuk dibaca dalam tiga detik. Yang tidak ada tidak dipaksa. */
export function decisionMetrics(decision: unknown, summary: unknown, now?: Date | null): MetricItem[] {
  const d = objectOf(decision) ?? {};
  const s = objectOf(summary) ?? {};
  const rows: MetricItem[] = [];
  const jumlah = kg(d.quantity_kg ?? s.quantity_kg);
  if (jumlah) rows.push({ label: "Kuantitas", value: jumlah });
  // Biaya aman terkirim: `null` dari backend berarti kolom DB kosong, BUKAN nol
  // (`app/api/decisions.py` dan `services/approval_summary.py` memetakan NULL
  // apa adanya). Terukur 28 Okt 2026 pada keputusan `supplier_exclusion_restoration`
  // — tipe administratif tanpa PO dan tanpa pengiriman barang: kartu feed menulis
  // "SDC —" sementara strip ini menulis "Rp0" karena `Number(null) === 0`.
  // Sekarang keduanya memakai aturan yang sama: kosong → "—".
  const biaya = angkaAtauNull(s.safe_delivered_cost ?? d.safe_delivered_cost);
  if (biaya !== null) {
    rows.push({ label: "Biaya aman terkirim", value: idr(biaya) });
  } else if ("safe_delivered_cost" in s || "safe_delivered_cost" in d) {
    // Medan DIKIRIM tetapi kosong: keputusan ini memang tidak punya biaya.
    // Baris tetap disebut dengan "—" (pembaca perlu tahu biayanya tidak ada),
    // sama seperti kartu feed. Medan yang tidak dikirim sama sekali tidak dikarang.
    rows.push({ label: "Biaya aman terkirim", value: DASH });
  }
  // Selisih hanya bisa dihitung kalau biaya dan harga beli dua-duanya diketahui.
  const beli = angkaAtauNull(objectOf(s.cost_breakdown)?.purchase);
  if (biaya !== null && beli !== null && beli > 0) {
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

/**
 * Nama pemasok dari payload keputusan. Dua bentuk nyata di lapangan:
 * `/decisions/{id}` mengirim objek `{id, name}`, `/approval-summary` juga
 * mengirim objek, sedangkan beberapa panel lama mengirim string. `null` tetap
 * `null` — nama pemasok tidak pernah ditebak dari lokasi atau quote.
 */
export function supplierNameOf(payload: unknown): string | null {
  const p = (payload ?? {}) as Record<string, unknown>;
  const supplier = p.supplier ?? p.supplier_name ?? null;
  if (supplier && typeof supplier === "object") {
    return text((supplier as Record<string, unknown>).name);
  }
  return text(supplier);
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
  const type = text(merged.decision_type);
  const pemasok = supplierNameOf(merged);
  const pengadaan = type === "supplier_procurement";
  const iteration = Number(merged.iteration);
  // Pengadaan menampilkan asalnya PEMASOK. Sebelum ini barisnya berbunyi
  // "Rute —" karena source_location_id NULL — terbaca seperti data rusak,
  // padahal asal yang benar memang pemasoknya.
  const barisRute: FactRow = pengadaan
    ? {
        label: "Pemasok → SPPG",
        value: pemasok && target ? `${pemasok} → ${target}` : DASH,
      }
    : {
        label: "Rute",
        value: source && target ? `${source} → ${target}` : DASH,
      };
  return [
    barisRute,
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

/** Biaya: rincian enam komponen Safe Delivered Cost + total. */
export function costFacts(decision: unknown): FactRow[] {
  const payload = (decision ?? {}) as Record<string, unknown>;
  const summary = (payload.summary ?? null) as Record<string, unknown> | null;
  // Sebagian baris lama menyimpan SELURUH payload rekomendasi di kolom ini
  // (`{"cost_breakdown": {...}, "candidate_score": ...}`). Buka bungkusnya
  // supaya komponennya terbaca, bukan tampil "—" semua.
  const mentah = (summary?.cost_breakdown ?? payload.cost_breakdown ?? {}) as Record<string, unknown>;
  const breakdown = (
    mentah.cost_breakdown && typeof mentah.cost_breakdown === "object"
      ? (mentah.cost_breakdown as Record<string, unknown>)
      : mentah
  ) as Record<string, unknown>;
  const total = summary?.safe_delivered_cost ?? payload.safe_delivered_cost;
  const ada = (k: string) => breakdown[k] !== undefined && breakdown[k] !== null;

  // Enam komponen kontrak SDC (core/safe_delivered_cost.py). Baris yang tidak
  // dikirim backend TETAP muncul dengan "—" dan alasannya — kalau disembunyikan,
  // pembaca mengira total hanya terdiri dari dua komponen.
  const komponen: Array<[string, string, string]> = [
    ["purchase", "Harga beli", "harga/kg × jumlah"],
    ["transport", "Logistik", "linehaul antar SPPG + angkut pemasok"],
    ["handling", "Penanganan", "biaya bongkar-muat tetap"],
    [
      "expected_loss",
      "Potensi susut",
      // Konsep Performance & Audit (29 Okt 2026): susut = fungsi WAKTU, bukan
      // kesegaran. Kesegaran hanya menambah risiko, bukan susut gudang.
      "purchase × laju susut × (hari simpan ÷ umur simpan)",
    ],
    ["freshness_risk", "Risiko kesegaran", "penalti bila kesegaran < 0,60"],
    ["safety_penalty", "Penalti keamanan", "penalti bila status belum terverifikasi"],
  ];
  // `logistics` adalah alias lama untuk komponen angkut — dibaca sebagai
  // fallback supaya keputusan sebelum Fase 7d tetap punya nilainya.
  const nilai = (key: string): unknown =>
    key === "transport" && !ada("transport") ? breakdown.logistics : breakdown[key];
  const rows: FactRow[] = komponen.map(([key, label, alasan]) => ({
    label,
    value: nilai(key) === undefined || nilai(key) === null ? DASH : idr(nilai(key)),
    hint: nilai(key) === undefined || nilai(key) === null
      ? `tidak ada di data keputusan ini (${alasan})`
      : null,
  }));

  // Pecahan angkut (pemasok → SPPG, antar SPPG) tidak lagi dirender sebagai
  // baris tersendiri (permintaan pemilik 29 Okt 2026): dua baris itu memecah
  // "Logistik" menjadi potongan yang tidak dipakai saat membaca bukti. Nilai
  // `logistics` tetap satu baris, dan `supplierLegHint` tetap tersedia untuk
  // pemakai lain.

  // Total hanya sah bila rincian yang ada menjumlah ke sana. Kalau tidak
  // (baris lama tanpa komponen), total ditandai — bukan ditampilkan seolah
  // rekonsiliasi berhasil.
  const enam = komponen.map(([key]) => nilai(key)).filter((v) => v !== undefined && v !== null);
  const jumlah = enam.reduce((acc: number, v) => acc + Number(v ?? 0), 0);
  const totalNum = Number(total);
  const lengkap = enam.length === komponen.length;
  const cocok = lengkap && Number.isFinite(totalNum) && Math.abs(jumlah - totalNum) < 0.01;
  // Total sengaja TIDAK diulang di kartu (angka yang sama sudah ada di strip
  // metrik). Yang ditampilkan hanya ketidakcocokan — itulah yang harus terlihat.
  if (!lengkap || !cocok) {
    rows.push({
      label: "Rekonsiliasi rincian",
      value: DASH,
      // Total kosong juga tidak dicetak "Rp0": `idr(null)` bernilai Rp0 karena
      // `Number(null) === 0`. Yang belum tercatat disebut apa adanya.
      hint: lengkap
        ? Number.isFinite(totalNum)
          ? `enam komponen berjumlah ${idr(jumlah)}, total tercatat ${idr(total)} — jangan dikutip sampai dihitung ulang`
          : `enam komponen berjumlah ${idr(jumlah)}, total (biaya aman terkirim) belum tercatat — jangan dikutip sampai dihitung ulang`
        : `${komponen.length - enam.length} dari ${komponen.length} komponen belum ada — rincian tidak bisa direkonsiliasi`,
      tone: "danger",
    });
  }

  // Dasar hitung: menggantikan catatan tulisan tangan lama.
  const basis = text(breakdown.basis) ?? text(breakdown.note);
  if (basis) rows.push({ label: "Dasar hitung", value: basis });
  return rows;
}

/** Keamanan pangan & jejak eksekusi dari /approval-summary. */
export function safetyFacts(summary: unknown, opts: { countInBadge?: boolean } = {}): FactRow[] {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const safety = (payload?.safety ?? null) as Record<string, unknown> | null;
  const verifier = (payload?.verifier ?? null) as Record<string, unknown> | null;
  const worst = text(safety?.worst_status)?.toUpperCase() ?? null;
  const checked = Number(safety?.batches_checked);
  const blocked = typeof safety?.blocked === "boolean" ? safety.blocked : null;
  const verdict = text(verifier?.verdict);
  const verifiedBy = text(verifier?.verified_by);
  const rows: FactRow[] = [
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
  // Jumlah batch yang sudah naik ke lencana putusan (lihat `safetyBadge`) tidak
  // dicetak dua kali di kartu yang sama — satu angka, satu tempat di layar.
  if (opts.countInBadge && safetyBadge(summary)?.detail) {
    return rows.filter((row) => row.label !== "Batch diperiksa");
  }
  return rows;
}

export type SafetyBadge = {
  /** Nada lencana: memakai kelas `.board-badge-*` yang sudah ada. */
  tone: "ok" | "warn" | "danger" | "muted";
  /** Putusan dalam kata manusia ("Gagal", "Lolos", "Perlu verifikasi"). */
  label: string;
  /**
   * Provenance "N batch diperiksa" — `null` bila server tidak mengirim jumlah
   * yang bermakna. Backend mengirim `batches_checked: 0` juga saat status tidak
   * terdefinisi, jadi 0 TIDAK dinaikkan menjadi kalimat (itu akan terbaca
   * seolah nol batch sudah diperiksa dan dianggap aman).
   */
  detail: string | null;
  /** Teks lencana siap cetak: "Gagal · 3 batch diperiksa". */
  text: string;
};

/**
 * Putusan safety satu keputusan sebagai SATU lencana (dokumen
 * `07-safety-evidence.md` §4.2 butir 2): status + jumlah batch yang diperiksa.
 *
 * Semua nilainya dari `GET /decisions/{id}/approval-summary`; tidak ada angka
 * yang dihitung ulang di klien dan tidak ada status yang diubah nadanya.
 */
export function safetyBadge(summary: unknown): SafetyBadge | null {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const safety = (payload?.safety ?? null) as Record<string, unknown> | null;
  const worst = text(safety?.worst_status)?.toUpperCase() ?? null;
  if (!worst) return null;
  const label = safetyLabel(worst) ?? worst;
  const checked = Number(safety?.batches_checked);
  const detail = Number.isFinite(checked) && checked > 0 ? `${checked} batch diperiksa` : null;
  const tone: SafetyBadge["tone"] =
    worst === "PASS" ? "ok" : worst === "FAIL" ? "danger" : SAFETY_TONE[worst] === "warn" ? "warn" : "muted";
  return { tone, label, detail, text: detail ? `${label} · ${detail}` : label };
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
