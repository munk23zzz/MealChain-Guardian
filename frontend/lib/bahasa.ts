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
