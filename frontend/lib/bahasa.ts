// "Bahasa" — satu tempat untuk menerjemahkan enum & kalimat teknis backend ke
// bahasa yang dibaca penyetuju.
//
// Kenapa modul sendiri: halaman Decision & Evidence sempat menampilkan
//   "putusan aturan: approval belum memenuhi requirement (missing/rejected)",
//   "Peran penyetuju: sppg_head", "Verifikator: consistent · verifier_agent",
//   "Target eksekusi: MOCK"
// — yaitu log server, bukan penjelasan untuk manusia. Semua pemetaan tinggal di
// sini supaya peta label tidak bercabang dua (sumber bug kepercayaan).
//
// ATURAN: tidak ada tebakan. String yang tidak dikenal dikembalikan apa adanya;
// hanya padanan yang benar-benar diketahui yang diterjemahkan.

import { roleLabel } from "./settings";
import { statusWord } from "./decision-picker";

function teks(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const bersih = value.trim();
  return bersih.length ? bersih : null;
}

// Kalimat yang benar-benar dikirim `services/approval_summary.py` +
// `api/actions.py`. Sisi kiri PERSIS seperti di server.
const BLOCKER_ID: Record<string, string> = {
  "decision expired": "jendela berlaku keputusan sudah lewat",
  "decision belum terverifikasi": "keputusan belum diverifikasi",
  "decision ditolak": "keputusan sudah ditolak",
  "decision sudah dieksekusi": "keputusan sudah dieksekusi",
  "approval belum memenuhi requirement (missing/rejected)":
    "persetujuan belum lengkap — masih ada kelompok peran yang belum menyetujui",
  "safety revalidation gagal": "pemeriksaan ulang keamanan gagal",
  "batch sumber FAIL": "batch sumber gagal pemeriksaan keamanan",
  // 409 /actions/execute dari `supplier_eligibility.resolve_binding`. Dulu
  // kalimat ini muncul MENTAH di popup aksi ("binding batch/supplier berubah")
  // tanpa menyebut batch mana atau apa yang harus dilakukan penyetuju.
  "binding batch/supplier berubah":
    "batch/pemasok yang terikat tidak lagi cocok dengan keputusan — ajukan keputusan baru",
  "binding ambigu; ajukan keputusan baru":
    "bukti alokasi ganda (lebih dari satu binding) — keputusan perlu diajukan ulang",
  "binding tidak valid": "bukti alokasi tidak dapat dibaca — ajukan keputusan baru",
  "supplier excluded pada SPPG penerima": "pemasok sedang dikecualikan untuk SPPG penerima",
  "commodity decision tidak valid": "komoditas keputusan tidak valid",
  "quantity decision tidak valid": "kuantitas keputusan tidak valid",
  "unit price decision tidak valid": "harga satuan keputusan tidak valid",
  "supplier untuk lokasi target tidak ditemukan": "pemasok untuk lokasi tujuan tidak ditemukan",
  "decision tinjauan (review-only) — tidak untuk dieksekusi":
    "ini temuan tinjauan, bukan perintah eksekusi",
  "tidak ada verdict hasil audit": "belum ada hasil audit verifier",
  // 409 /supplier-eligibility mengirim kode ini di awal kalimat; di kartu
  // "Lanjutkan" (Decision & Evidence) kode mentah tidak boleh tampil.
  supplier_unknown: "pemasok tidak dikenal",
  // Fase 6: kode alasan gerbang hierarki (`core/batch_eligibility`). Sebelum
  // ini kode mentah seperti `temperature_evidence_incomplete` bisa muncul di
  // UI kandidat tertahan.
  temperature_evidence_incomplete: "bukti suhu belum lengkap",
  evidence_missing: "bukti yang disyaratkan tidak tercatat",
  safety_fail: "batch gagal uji keamanan pangan",
  safety_pending: "batch belum diuji keamanannya",
  safety_needs_verification: "batch menunggu verifikasi",
  safety_status_unknown: "status keamanan batch tidak diketahui",
  freshness_fail: "kesegaran batch di bawah syarat",
  batch_expired: "masa layak batch sudah lewat",
  expiry_unknown: "masa layak batch tidak tercatat",
  expired_before_arrival: "batch kedaluwarsa sebelum tiba",
  delivery_window_exceeded: "waktu tiba melewati tenggat kebutuhan",
  quarantined: "batch masih dikarantina",
  // Kode gerbang keamanan yang dulu lolos mentah ke tabel evaluasi batch
  // ("safety_status_bukan_pass" tercetak apa adanya). Semua kode di
  // `core/safety_gate` + beberapa varian Indonesia di `core/batch_eligibility`
  // diberi kalimat, bukan dibiarkan tampil sebagai kunci.
  safety_status_bukan_pass: "status keamanan batch sumber belum lolos",
  safety_status_fail_sumber: "batch sumber gagal uji keamanan",
  tidak_ada_batch_sumber: "keputusan tidak menunjuk batch sumber",
  bukti_suhu_tidak_lengkap: "bukti suhu penerimaan belum lengkap",
  // CATATAN: kunci satu kata berbahasa Indonesia ("kedaluwarsa", "dikarantina")
  // TIDAK boleh ditambahkan di sini. Penerjemah mencocokkan potongan kalimat,
  // jadi kata biasa akan merusak kalimat yang sudah benar ("batch kedaluwarsa"
  // → "batch batch sudah kedaluwarsa"). Yang aman: kunci bergaya kode.
};

// Urutan penting: frasa terpanjang dulu supaya tidak terpotong oleh yang pendek.
const FRASA: Array<[string, string]> = Object.entries(BLOCKER_ID).sort(
  (a, b) => b[0].length - a[0].length
);

/**
 * Sebab tertahan → bahasa penyetuju. Menerima kalimat utuh ("decision expired")
 * maupun kalimat yang dibungkus pesan error ("Gagal menyetujui: decision expired"),
 * karena dialog aksi menampilkan `message` dari server apa adanya.
 */
export function humanizeBlocker(reason: unknown): string | null {
  const asli = teks(reason);
  if (!asli) return null;
  const langsung = BLOCKER_ID[asli];
  if (langsung) return langsung;

  let hasil = asli;
  for (const [dari, ke] of FRASA) {
    if (hasil.includes(dari)) hasil = hasil.split(dari).join(ke);
  }
  // "status verifier_flagged tidak dapat dieksekusi" — status dinamis memakai
  // kosakata yang sama dengan lencana status di halaman ini.
  hasil = hasil.replace(/status\s+([a-z_]+)\s+tidak dapat dieksekusi/gi, (utuh, kode: string) => {
    const kata = statusWord(kode);
    return `status ${kata} tidak dapat dieksekusi`;
  });
  // Dua gerbang eksekusi (dokumen 02-approval-action.md §6): kalimat server
  // "purchase order MC-… menunggu review Kepala SPPG" membawa nomor PO, jadi
  // tidak bisa jadi kunci peta statis. Yang diterjemahkan hanya istilahnya.
  hasil = hasil.replace(
    /purchase order\s+(\S+)\s+menunggu review Kepala SPPG/gi,
    "PO $1 menunggu review Kepala SPPG"
  );
  return hasil;
}

/** `blocking_reasons` dari /approval-summary → daftar siap tampil. */
export function blockingReasons(summary: unknown): string[] {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const daftar = Array.isArray(payload?.blocking_reasons)
    ? (payload!.blocking_reasons as unknown[])
    : [];
  const hasil: string[] = [];
  for (const baris of daftar) {
    const kata = humanizeBlocker(baris);
    if (kata) hasil.push(kata);
  }
  return hasil;
}

const SAFETY_ID: Record<string, string> = {
  pass: "Lolos",
  fail: "Gagal",
  needs_verification: "Perlu verifikasi",
  pending: "Belum diuji",
  unavailable: "Tidak dapat dievaluasi",
};

/** PASS/FAIL/NEEDS_VERIFICATION → kata; tak dikenal dikembalikan apa adanya. */
export function safetyLabel(status: unknown): string | null {
  const asli = teks(status);
  if (!asli) return null;
  return SAFETY_ID[asli.toLowerCase()] ?? asli;
}

// Lencana status (components/StatusBadge) dulu menampilkan enum mentah berbahasa
// Inggris: "PENDING APPROVAL" 23x di feed Recommendation, "NEEDS VERIFICATION",
// "PROPOSED" di Demo Control (temuan QA 17 Okt 2026). Pemetaan tinggal di sini
// supaya satu status tidak punya dua nama di dua halaman.
const STATUS_ID: Record<string, string> = {
  PASS: "Lolos",
  FAIL: "Gagal",
  NEEDS_VERIFICATION: "Perlu verifikasi",
  PROPOSED: "Diusulkan",
  VERIFIER_FLAGGED: "Ditandai verifikator",
  PENDING_APPROVAL: "Menunggu persetujuan",
  APPROVED: "Disetujui",
  REJECTED: "Ditolak",
  EXECUTED: "Dieksekusi",
  // 29 Okt 2026: status ini tidak ada di peta, sehingga lencana kartu feed
  // mencetak enum Inggris utuh "REVIEW ONLY" di tengah UI berbahasa Indonesia.
  REVIEW_ONLY: "Temuan tinjauan",
  SURPLUS: "Surplus",
  SHORTAGE: "Shortage",
  TIGHT: "Ketat",
};

/**
 * Status enum → kata di layar. Nilai yang belum pernah dilihat TIDAK dikarang:
 * hanya garis bawahnya dibuang supaya tetap terbaca ("CUSTOM_STATE" → "CUSTOM STATE").
 */
export function statusLabel(status: unknown): string | null {
  const asli = teks(status);
  if (!asli) return null;
  const kunci = asli.toUpperCase().replace(/\s+/g, "_");
  return STATUS_ID[kunci] ?? kunci.replace(/_/g, " ");
}

// Nama alat internal agen (kolom "alat" di kartu kualitas agen). Yang dikenal
// diberi sebutan manusia; sisanya tampil apa adanya — itu bukti, bukan hiasan.
const TOOL_ID: Record<string, string> = {
  "supply_balance.propose": "Neraca pasokan · usulkan",
  "rejection_loop.repropose": "Usulan ulang setelah penolakan",
  "demand.snapshot": "Potret permintaan",
  "price.signal": "Sinyal harga",
  "evidence.crosscheck": "Pemeriksaan silang bukti",
  "forecast.daily": "Perkiraan harian",
  "forecast.provider": "Penyedia perkiraan",
  "logistics.reroute": "Alih rute kiriman",
  "logistics.status": "Status kiriman",
  "supply.get+demand.get": "Ambil pasokan & permintaan",
  "verifier.rest": "Layanan verifikator",
  "balance.recommend": "Saran neraca pasokan",
  "post /decisions": "Buat keputusan",
  evaluate_safety: "Periksa keamanan",
  build_recommendations: "Susun rekomendasi",
  evaluate_balance: "Periksa neraca",
  build_evidence: "Susun bukti",
};

/** Nama alat → sebutan; alat lain dikembalikan apa adanya. */
export function toolLabel(tool: unknown): string | null {
  const asli = teks(tool);
  if (!asli) return null;
  return TOOL_ID[asli.toLowerCase()] ?? asli;
}

const AGENT_ID: Record<string, string> = {
  supervisor_agent: "Agen supervisor",
  verifier_agent: "Agen verifikator",
};

/** Nama agen teknis → sebutan manusia; agen lain dibiarkan apa adanya. */
export function agentLabel(agent: unknown): string | null {
  const asli = teks(agent);
  if (!asli) return null;
  return AGENT_ID[asli.toLowerCase()] ?? asli;
}

// Target eksekusi dari approval_summary.py: "MOCK" (lokasi tujuan ada) dan
// "LOCAL" (tata kelola pemasok — tindakan administratif lokal, tanpa PO).
const TARGET_ID: Record<string, string> = {
  mock: "Simulasi",
  local: "Lokal (tanpa PO)",
};

/** Target eksekusi → bahasa pembaca; nilai lain dikembalikan apa adanya. */
export function executionTargetLabel(target: unknown): string | null {
  const asli = teks(target);
  if (!asli) return null;
  return TARGET_ID[asli.toLowerCase()] ?? asli;
}

/** Daftar peran mentah ("sppg_head") → label manusia, dipisah " · ". */
export function roleList(roles: unknown): string[] {
  if (!Array.isArray(roles)) return [];
  const hasil: string[] = [];
  for (const peran of roles) {
    const asli = teks(peran);
    if (asli) hasil.push(roleLabel(asli));
  }
  return hasil;
}
