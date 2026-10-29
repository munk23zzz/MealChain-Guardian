/**
 * Jejak agen untuk UI (Fase 4 redesign, 2026-10-16).
 *
 * Agent Log perlu terasa hidup — tetapi tabel `agent_traces` TIDAK punya kolom
 * status: setiap baris ditulis setelah langkahnya selesai. Karena itu:
 *
 * - "sedang berjalan" HANYA muncul kalau data sendiri mengatakannya
 *   (`output_summary.status` di RUNNING_STATUSES). Tidak ada inferensi
 *   "kayaknya masih jalan" — di demo, klaim seperti itu tidak bisa dibuktikan
 *   juri dan itu justru yang paling mahal.
 * - Yang selalu bisa dihitung adalah WAKTU: umur langkah dari `step_at`
 *   ("baru masuk 12 dtk lalu"). Itu fakta, dan dipakai apa adanya — termasuk
 *   saat jam klien mundur (waktu di masa depan → tidak diklaim baru).
 *
 * Jalur halaman Agent Log memakainya untuk: chip umur di kepala konsol,
 * penanda langkah baru, dan durasi per langkah (duration_ms yang selama ini
 * tidak pernah ditampilkan padahal sudah dikirim backend).
 */

/** Status yang berarti langkah BELUM selesai (dari output_summary backend). */
export const RUNNING_STATUSES = ["running", "in_progress", "started", "pending"] as const;

/** Jendela "langkah baru masuk" — 2 menit, dengan polling jejak tiap 5 detik. */
export const NEW_STEP_MS = 120_000;

function parseAt(value: unknown): Date | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Umur dalam ms; null bila waktunya tak terbaca, tanpa jam klien, atau di
 *  masa depan (jam klien mundur — jangan klaim "baru"). */
function ageMs(value: unknown, now: Date | null): number | null {
  const at = parseAt(value);
  if (!at || !(now instanceof Date) || Number.isNaN(now.getTime())) return null;
  const diff = now.getTime() - at.getTime();
  return diff < 0 ? null : diff;
}

export function stepAgeLabel(stepAt: unknown, now: Date | null): string | null {
  const ms = ageMs(stepAt, now);
  if (ms === null) return null;
  const detik = Math.floor(ms / 1000);
  if (detik < 60) return `baru masuk ${detik} dtk lalu`;
  const menit = Math.floor(detik / 60);
  if (menit < 60) return `baru masuk ${menit} mnt lalu`;
  const jam = Math.floor(menit / 60);
  if (jam < 24) return `${jam} jam lalu`;
  return `${Math.floor(jam / 24)} hari lalu`;
}

export function isRunningStep(step: any): boolean {
  const status = step?.output_summary?.status;
  return (
    typeof status === "string" &&
    (RUNNING_STATUSES as readonly string[]).includes(status.trim().toLowerCase())
  );
}

export function isNewStep(
  stepAt: unknown,
  now: Date | null,
  windowMs: number = NEW_STEP_MS
): boolean {
  const ms = ageMs(stepAt, now);
  return ms !== null && ms <= windowMs;
}

export function stepDurationLabel(step: any): string | null {
  const raw = step?.duration_ms;
  if (typeof raw !== "number" || !Number.isFinite(raw) || raw < 0) return null;
  if (raw < 1000) return `${Math.round(raw)} ms`;
  return `${(raw / 1000).toLocaleString("id-ID", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} dtk`;
}

/**
 * Berapa langkah jejak yang tercatat SEBELUM keputusannya dibuat.
 *
 * Kenapa perlu: 39 dari 48 keputusan di data demo punya seluruh langkah
 * bertanggal lebih awal daripada `created_at` keputusannya. Itu cacat data,
 * bukan urutan kejadian nyata. Selama cacatnya ada, halaman harus mengatakannya
 * terang-terangan — menyembunyikannya dengan jam tanpa tanggal adalah cara
 * paling mudah membuat pembaca menyimpulkan hal yang salah.
 */
export function jejakSebelumKeputusan(
  createdAt: string | null | undefined,
  steps: ReadonlyArray<{ step_at?: unknown }> | null | undefined
): { jumlah: number; pertama: string | null } {
  if (!createdAt) return { jumlah: 0, pertama: null };
  const lahir = new Date(createdAt).getTime();
  if (Number.isNaN(lahir)) return { jumlah: 0, pertama: null };
  let jumlah = 0;
  let pertama: string | null = null;
  let pertamaMs = Number.POSITIVE_INFINITY;
  for (const s of steps ?? []) {
    const iso = typeof s?.step_at === "string" ? s.step_at : null;
    if (!iso) continue;
    const ms = new Date(iso).getTime();
    if (Number.isNaN(ms) || ms >= lahir) continue;
    jumlah += 1;
    if (ms < pertamaMs) {
      pertamaMs = ms;
      pertama = iso;
    }
  }
  return { jumlah, pertama };
}

/**
 * Catatan bila jejak tidak dimulai dari DETECT.
 *
 * Di data demo ada 9 keputusan yang jejaknya mulai dari LEARN / PREDICT /
 * OPTIMIZE. Tanpa kalimat, pembaca menyimpulkan agent melewatkan pendeteksian;
 * yang benar: tahap awalnya tidak tercatat pada data ini.
 */
export function catatanAwalJejak(
  steps: ReadonlyArray<{ step_name?: unknown }> | null | undefined
): string | null {
  const pertama = steps?.[0]?.step_name;
  if (typeof pertama !== "string" || !pertama) return null;
  if (pertama === "DETECT") return null;
  return `Jejak ini dimulai dari ${pertama}, bukan DETECT — tahap awal tidak tercatat pada data demo.`;
}
