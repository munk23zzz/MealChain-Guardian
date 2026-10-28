// Fase 4 MG, poin 7 (`MG/phase-04-safety-gates.md`): satu tempat untuk
// menerjemahkan KODE ALASAN STABIL dari evaluator batch
// (`backend/app/core/batch_eligibility.py`) menjadi kalimat Indonesia dan
// LANGKAH VERIFIKASI BERIKUTNYA.
//
// Kenapa modul sendiri:
//  - kode seperti `safety_pending` dan `temperature_evidence_incomplete` adalah
//    bahasa API, bukan bahasa penyetuju. Sebelum ini popup menampilkan
//    `blocking_reasons[0]` apa adanya, sehingga layar bisa menulis
//    "safety_pending" tanpa menjelaskan apa yang harus dilakukan;
//  - tiga permukaan UI (popup governance, ringkasan approval, papan Keamanan
//    Pangan) harus menyebut sebab yang SAMA untuk batch yang sama. Peta yang
//    bercabang dua adalah sumber kalimat yang saling bertentangan;
//  - UI TIDAK menghitung ulang aturan: `can_execute`, `blocking_reasons`, dan
//    `safety` tetap milik server. Modul ini hanya menamai hasilnya.
//
// ATURAN: tidak mengarang. Kode/frasa yang tidak dikenal dikembalikan apa
// adanya (itu bukti, bukan hiasan) — tetapi tetap dinormalkan spasinya.

/** Kode evaluator → kalimat + langkah berikutnya. */
const KODE: Record<string, { teks: string; langkah: string }> = {
  safety_fail: {
    teks: "batch sumber gagal uji keamanan pangan",
    langkah: "Karantina batch atau ajukan keputusan penanganan",
  },
  safety_pending: {
    teks: "batch sumber belum diuji keamanan pangan",
    langkah: "Uji keamanan pangan batch ini, lalu catat verifikasi",
  },
  safety_needs_verification: {
    teks: "batch sumber menunggu keputusan verifikasi keamanan pangan",
    langkah: "Selesaikan verifikasi verifier sebelum barang bergerak",
  },
  safety_status_unknown: {
    teks: "status keamanan batch sumber tidak dikenal",
    langkah: "Uji ulang keamanan batch supaya statusnya tercatat",
  },
  evidence_missing: {
    teks: "bukti batch tidak lengkap",
    langkah: "Lengkapi bukti batch (log suhu & catatan panen), lalu uji ulang",
  },
  temperature_evidence_incomplete: {
    teks: "Bukti suhu batch belum lengkap",
    langkah: "Lengkapi Log suhu batch, lalu jalankan uji ulang keamanan",
  },
  freshness_fail: {
    teks: "batch sumber tidak lagi segar",
    langkah: "Catat hasil terima baru atau tolak batch ini",
  },
  batch_expired: {
    teks: "batch sumber sudah kedaluwarsa",
    langkah: "Ganti batch — masa layaknya sudah lewat",
  },
  expiry_unknown: {
    teks: "masa layak batch sumber tidak tercatat",
    langkah: "Catat tanggal layak pakai batch lebih dulu",
  },
  expired_before_arrival: {
    teks: "batch sumber kedaluwarsa sebelum tiba",
    langkah: "Pilih batch yang masih layak saat barang tiba",
  },
  delivery_window_exceeded: {
    teks: "jadwal kirim tidak lagi terpenuhi",
    langkah: "Ajukan jadwal kirim baru untuk batch ini",
  },
  quarantined: {
    teks: "batch sumber sedang dikarantina",
    langkah: "Lepas karantina atau nyatakan gagal",
  },
};

/**
 * Frasa kalimat yang dikirim jalur LAMA (`supplier_eligibility.PESAN_BLOKIR`,
 * `approval_summary`) → kode di atas. Diperlukan karena 409 dan
 * `blocking_reasons` masih membawa kalimat, bukan kode.
 */
const FRASA_KE_KODE: Record<string, string> = {
  "safety revalidation gagal: batch sumber kini fail": "safety_fail",
  "batch sumber fail": "safety_fail",
  "batch sumber kini fail (temperature excursion)": "safety_fail",
  "safety revalidation gagal: batch sumber dikarantina/gagal": "quarantined",
  "batch sumber dikarantina/gagal": "quarantined",
  "batch sumber belum diuji (safety pending) — perlu verifikasi": "safety_pending",
  "batch sumber menunggu verifikasi keamanan pangan": "safety_needs_verification",
  "safety revalidation gagal: tidak ada batch sumber": "evidence_missing",
};

function teks(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const bersih = value.trim().replace(/\s+/g, " ");
  return bersih.length ? bersih : null;
}

/** Kode stabil yang dikenali (hanya kecocokan PERSIS, tanpa frasa lama). */
export function reasonCodeExact(raw: unknown): string | null {
  const asli = teks(raw);
  if (!asli) return null;
  const kunci = asli.toLowerCase();
  return KODE[kunci] ? kunci : null;
}

/** Kalimat/frasa mentah → kode stabil, atau null bila tak dikenal. */
export function reasonCode(raw: unknown): string | null {
  const asli = teks(raw);
  if (!asli) return null;
  const kunci = asli.toLowerCase();
  if (KODE[kunci]) return kunci;
  if (FRASA_KE_KODE[kunci]) return FRASA_KE_KODE[kunci];
  // Frasa yang dibungkus pesan lain ("Gagal mengeksekusi: batch sumber FAIL").
  let hasil: string | null = null;
  for (const [frasa, kode] of Object.entries(FRASA_KE_KODE)) {
    if (kunci.includes(frasa)) hasil = kode;
  }
  return hasil;
}

/** Satu alasan mentah → kalimat siap tampil (kode mentah tidak lolos). */
export function reasonText(raw: unknown): string | null {
  const asli = teks(raw);
  if (!asli) return null;
  const kode = reasonCode(asli);
  if (kode) return KODE[kode].teks;
  return asli;
}

export type BatchGateKind = "siap" | "on_hold" | "quarantined" | "tertahan" | "selesai";

export type BatchGateView = {
  kind: BatchGateKind;
  /** Label chip: satu kata keadaan, bukan kode. */
  label: string;
  /** Kalimat sebab (terjemahan), sudah tanpa duplikat. */
  reasons: string[];
  /** Kode asli yang dikenali — untuk logika, BUKAN untuk ditampilkan. */
  codes: string[];
  /** Langkah verifikasi berikutnya (null bila tidak ada yang tertahan). */
  nextStep: string | null;
  /** true hanya bila server mengizinkan eksekusi. */
  canExecute: boolean;
};

const LABEL: Record<BatchGateKind, string> = {
  siap: "Siap dieksekusi",
  on_hold: "Ditahan — menunggu verifikasi",
  quarantined: "Karantina",
  tertahan: "Tertahan",
  selesai: "Sudah dieksekusi",
};

/** Kode yang berarti "tunggu verifikasi manusia" (bukan gagal permanen). */
const ON_HOLD_CODES = new Set([
  "safety_pending",
  "safety_needs_verification",
  "safety_status_unknown",
  "temperature_evidence_incomplete",
]);

function kumpulanAlasan(summary: unknown): unknown[] {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const daftar = Array.isArray(payload?.blocking_reasons)
    ? (payload!.blocking_reasons as unknown[])
    : [];
  const safety = (payload?.safety ?? null) as Record<string, unknown> | null;
  const sebabSafety = safety?.reason;
  return sebabSafety ? [...daftar, sebabSafety] : daftar;
}

/**
 * Read model `/decisions/{id}/approval-summary` → keadaan gerbang batch.
 *
 * `can_execute` dan `blocking_reasons` dipakai APA ADANYA dari server; fungsi
 * ini tidak menambah atau mengurangi syarat.
 */
export function batchGateView(summary: unknown): BatchGateView {
  const payload = (summary ?? null) as Record<string, unknown> | null;
  const mentah = kumpulanAlasan(summary);
  const codes: string[] = [];
  const reasons: string[] = [];
  for (const baris of mentah) {
    const kode = reasonCode(baris);
    if (kode && !codes.includes(kode)) codes.push(kode);
    const kalimat = reasonText(baris);
    if (kalimat && !reasons.includes(kalimat)) reasons.push(kalimat);
  }
  const canExecute = payload?.can_execute === true;

  let kind: BatchGateKind;
  if (payload?.status === "executed") kind = "selesai";
  else if (codes.includes("quarantined")) kind = "quarantined";
  else if (codes.some((kode) => ON_HOLD_CODES.has(kode))) kind = "on_hold";
  else if (canExecute) kind = "siap";
  else kind = "tertahan";

  // Langkah berikutnya: sebab PERTAMA yang punya langkah — urutan server
  // dipertahankan supaya sebab terparah (yang ditulis lebih dulu) menang.
  let nextStep: string | null = null;
  for (const kode of codes) {
    if (kode === "quarantined" || ON_HOLD_CODES.has(kode)) {
      nextStep = KODE[kode].langkah;
      break;
    }
  }
  if (!nextStep && kind !== "siap" && kind !== "selesai") {
    for (const kode of codes) {
      if (KODE[kode]) {
        nextStep = KODE[kode].langkah;
        break;
      }
    }
  }

  return {
    kind,
    label: LABEL[kind],
    reasons,
    codes,
    nextStep,
    canExecute,
  };
}

/**
 * Langkah berikutnya untuk SATU baris papan (bukan popup keputusan).
 *
 * Dua fakta bisa berlaku bersamaan dan tidak boleh saling menutupi: batch bisa
 * `needs_verification` SEKALIGUS dikarantina. Karena itu langkah uji keamanan
 * dan langkah karantina dikembalikan terpisah, keduanya dari peta kode yang
 * sama dengan popup governance.
 */
export function rowNextSteps(
  safetyStatus: string | null | undefined,
  quarantine: string | null | undefined
): { safety: string | null; karantina: string | null } {
  const safety = rowGate(safetyStatus, "none");
  const ditahan = rowGate(null, quarantine);
  return {
    safety: safety.nextStep,
    karantina: ditahan.kind === "quarantined" ? ditahan.nextStep : null,
  };
}

/**
 * Satu BARIS batch (`GET /batches`) → keadaan gerbang yang sama.
 *
 * Dipakai papan Keamanan Pangan: label karantina dan langkah verifikasi tidak
 * boleh lahir dari aturan kedua yang berbeda dari popup governance.
 */
export function rowGate(
  safetyStatus: string | null | undefined,
  quarantine: string | null | undefined
): BatchGateView {
  const karantina = String(quarantine ?? "").trim().toLowerCase();
  if (karantina === "quarantined" || karantina === "failed") {
    return {
      kind: "quarantined",
      label: LABEL.quarantined,
      reasons: [KODE.quarantined.teks],
      codes: ["quarantined"],
      nextStep: KODE.quarantined.langkah,
      canExecute: false,
    };
  }
  const status = String(safetyStatus ?? "").trim().toLowerCase();
  const kode =
    status === "pending"
      ? "safety_pending"
      : status === "needs_verification"
        ? "safety_needs_verification"
        : status === "fail"
          ? "safety_fail"
          : status === "pass"
            ? null
            : "safety_status_unknown";
  if (!kode) {
    return { kind: "siap", label: LABEL.siap, reasons: [], codes: [], nextStep: null, canExecute: true };
  }
  const masukTahan = ON_HOLD_CODES.has(kode);
  return {
    kind: masukTahan ? "on_hold" : "tertahan",
    label: masukTahan ? LABEL.on_hold : LABEL.tertahan,
    reasons: [KODE[kode].teks],
    codes: [kode],
    nextStep: KODE[kode].langkah,
    canExecute: false,
  };
}
