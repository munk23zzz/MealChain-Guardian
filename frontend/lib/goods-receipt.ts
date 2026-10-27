// Fase 9 MG butir 2 & 4 — tampilan status penerimaan, sepenuhnya mengikuti SERVER.
//
// Aturan modul ini:
//   1. TIDAK ada keputusan boleh/tidak di sini. `can_receive`, `can_quarantine`,
//      `status`, dan `next_step` dibaca dari `receipt_gate` pada
//      `GET /decisions/{id}/approval-summary` (dihitung `app/services/receipt_gate.py`).
//      Klien yang menghitung sendiri akan menyimpang dari pagar endpoint.
//   2. Kode alasan diterjemahkan ke kalimat; kode mentah tidak boleh sampai ke layar
//      (`safety_pending` bukan bahasa petugas dapur). Kode yang tidak dikenal
//      dikembalikan apa adanya — tidak dikarang.
//   3. `on_hold` dan `quarantined` BUKAN kegagalan aplikasi: keduanya keadaan sah
//      yang punya langkah berikutnya sendiri.

export type ReceiptGateRow = {
  batchId: string;
  status: string;
  statusLabel: string;
  canReceive: boolean;
  canQuarantine: boolean;
  reasons: string[];
  nextStep: string | null;
};

export type ReceiptGateView = {
  present: boolean;
  locationId: string | null;
  canReceive: boolean;
  canQuarantine: boolean;
  rows: ReceiptGateRow[];
  /** Ringkasan satu kalimat kenapa penerimaan tertahan (kosong bila bisa). */
  blockedSentence: string | null;
};

/** Label status kelayakan batch — kata yang dipakai papan Keamanan Pangan juga. */
const STATUS_LABEL: Record<string, string> = {
  usable: "Layak masuk stok",
  on_hold: "Tertahan — belum terbukti aman",
  rejected: "Ditolak — tidak boleh masuk stok",
  quarantined: "Karantina — ditahan dari alokasi",
};

/**
 * Kode → kalimat. Dua keluarga kode:
 *  - kode gerbang penerimaan/karantina (milik `app/services/receipt_gate.py`),
 *  - kode evaluator batch (`app/core/batch_eligibility.py`) yang dibawa apa adanya.
 */
const CODE_SENTENCE: Record<string, string> = {
  // gerbang penerimaan & karantina
  role_not_head: "hanya Kepala SPPG yang boleh menyetujui penerimaan",
  role_not_sppg: "hanya SPPG pemilik lokasi batch yang boleh menahan barang",
  out_of_scope: "barang ini di luar cakupan lokasi akun Anda",
  receipt_missing: "catat hasil terima petugas lebih dulu",
  receipt_already_decided: "catatan penerimaan ini sudah diputuskan",
  safety_fail_not_quarantinable:
    "barang sudah dinyatakan gagal, karantina tidak diperlukan lagi",
  safety_status_unknown: "status keamanan barang belum diketahui",
  quarantine_transition_invalid: "barang sudah berada dalam karantina",
  viewer_unknown: "peran pembaca tidak diketahui",
  no_batch: "belum ada barang di dapur penerima",
  // kode evaluator batch
  safety_pending: "belum diuji keamanan pangannya",
  safety_needs_verification: "menunggu verifikasi keamanan pangan",
  safety_fail: "gagal uji keamanan pangan",
  quarantined: "masih berstatus karantina",
  freshness_fail: "kesegaran di bawah ambang verifikasi",
  temperature_evidence_incomplete: "bukti suhu belum lengkap",
  evidence_missing: "bukti barang belum lengkap",
  batch_expired: "sudah lewat masa layak",
  expiry_unknown: "masa layak tidak tercatat",
  expired_before_arrival: "kedaluwarsa sebelum jadwal tiba",
  delivery_window_exceeded: "jadwal kirim sudah terlampaui",
};

/**
 * Peran yang boleh MEMUTUSKAN catatan penerimaan — cermin `require_roles("sppg_head")`
 * pada `POST /receipts/{id}/approve` dan `/reject`. Bukan aturan baru: server tetap
 * penentu, ini hanya supaya tombol tidak ditawarkan kepada peran yang pasti 403.
 */
export const RECEIPT_DECIDER_ROLE = "sppg_head";

export const RECEIPT_APPROVE_LABEL = "Tandai diterima";
export const RECEIPT_REJECT_LABEL = "Tolak penerimaan";
export const QUARANTINE_HOLD_LABEL = "Tahan (karantina)";

export function canDecideReceipt(role: unknown): boolean {
  return String(role ?? "") === RECEIPT_DECIDER_ROLE;
}

export function receiptReason(code: unknown): string {
  const kode = String(code ?? "").trim();
  if (!kode) return "";
  return CODE_SENTENCE[kode] ?? kode;
}

export function receiptStatusLabel(status: unknown): string {
  const kunci = String(status ?? "").trim();
  if (!kunci) return "Status tidak tercatat";
  return STATUS_LABEL[kunci] ?? kunci;
}

function daftar(nilai: unknown): string[] {
  return Array.isArray(nilai) ? nilai.map((v) => receiptReason(v)).filter(Boolean) : [];
}

/**
 * Bentuk `receipt_gate` server → tampilan. Tanpa nilai server, `present: false`
 * (UI menyebut "tidak tercatat", bukan menebak "tidak boleh").
 */
export function receiptGateView(summary: unknown): ReceiptGateView {
  const payload = (summary ?? null) as Record<string, any> | null;
  const gate = (payload?.receipt_gate ?? null) as Record<string, any> | null;
  if (!gate || !Array.isArray(gate.batches)) {
    return {
      present: false,
      locationId: null,
      canReceive: false,
      canQuarantine: false,
      rows: [],
      blockedSentence: null,
    };
  }
  const rows: ReceiptGateRow[] = gate.batches.map((b: Record<string, any>) => ({
    batchId: String(b?.batch_id ?? ""),
    status: String(b?.status ?? ""),
    statusLabel: receiptStatusLabel(b?.status),
    canReceive: b?.can_receive === true,
    canQuarantine: b?.can_quarantine === true,
    reasons: daftar(b?.receive_reasons),
    // Langkah PER BATCH bila server mengirimnya; agregat hanya cadangan.
    nextStep: (b?.next_step ?? gate.next_step ?? null) as string | null,
  }));
  const alasan = daftar(gate.receive_reasons);
  const canReceive = gate.can_receive === true;
  const canQuarantine = gate.can_quarantine === true;
  return {
    present: true,
    locationId: gate.location_id ? String(gate.location_id) : null,
    canReceive,
    canQuarantine,
    rows,
    blockedSentence: canReceive || alasan.length === 0 ? null : `Penerimaan tertahan: ${alasan.join("; ")}.`,
  };
}

/** Catatan penerimaan yang belum diputuskan (menunggu) untuk satu batch. */
export function pendingReceipt(
  items: Array<Record<string, any>> | undefined
): Record<string, any> | null {
  if (!Array.isArray(items)) return null;
  return items.find((row) => String(row?.status ?? "") === "menunggu") ?? null;
}

/**
 * Pesan galat dari server untuk ditampilkan apa adanya (butir 4: 409 wajib
 * memperlihatkan `detail` supaya alasannya bisa diperbaiki pengguna).
 */
export function serverDetail(err: unknown): string {
  const e = (err ?? null) as Record<string, any> | null;
  const detail = e?.detail ?? e?.payload?.detail ?? null;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (detail && typeof detail === "object") {
    const pesan = (detail as Record<string, any>).message;
    if (typeof pesan === "string" && pesan.trim()) return pesan.trim();
  }
  const message = e?.message;
  return typeof message === "string" ? message : "";
}
