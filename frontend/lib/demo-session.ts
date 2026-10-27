/**
 * Sesi demo — logika MURNI (tanpa React/DOM).
 *
 * Aturan pemilik (20 Okt 2026): tampilan default KOSONG; tombol "Siapkan data
 * demo" mengaktifkan data selama satu jendela waktu; ada hitungan mundur; sesi
 * bisa diperpanjang tanpa mengubah data berjalan; data hanya bisa diubah
 * selama sesi; sesudah habis, data kembali kosong.
 *
 * Semua hitungan waktu di modul ini memakai `remaining_seconds` dari SERVER,
 * bukan jam browser: jam laptop yang melenceng 10 menit tidak boleh membuat
 * sesi tampak habis (atau masih hidup) padahal tidak.
 */

export type StatusSesiDemo = {
  active: boolean;
  enforced: boolean;
  session_id: string | null;
  status: string;
  /**
   * Fase 2 MG: mode dan jangkar adalah sifat SESI. `null` = baris lama/pra-Fase 2
   * (panel menampilkan "mode belum ditentukan", bukan menebak `replay`).
   */
  mode?: "replay" | "realtime" | null;
  evaluation_anchor?: string | null;
  dataset_version?: string | null;
  expires_at: string | null;
  anchor_now: string | null;
  server_now: string;
  remaining_seconds: number;
};

/** Mode sesi untuk ditampilkan; tidak pernah menebak dari data terbaru. */
export function modeSesi(
  sesi: StatusSesiDemo | null
): "replay" | "realtime" | null {
  const mode = sesi?.mode;
  return mode === "replay" || mode === "realtime" ? mode : null;
}

/**
 * Jangkar evaluasi yang ditampilkan: `8 Okt 2026 12:00 UTC`.
 *
 * Jangkar dikirim RFC3339 UTC; kalau tidak bisa diurai, kembalikan `null` supaya
 * panel menampilkan "—" alih-alih tanggal palsu.
 */
export function jangkarSesi(sesi: StatusSesiDemo | null): string | null {
  const iso = sesi?.evaluation_anchor;
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const bulan = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
  ][d.getUTCMonth()];
  const jam = String(d.getUTCHours()).padStart(2, "0");
  const menit = String(d.getUTCMinutes()).padStart(2, "0");
  return `${d.getUTCDate()} ${bulan} ${d.getUTCFullYear()} ${jam}:${menit} UTC`;
}

export type KeadaanSesi = "mati" | "kosong" | "berjalan" | "habis";

/** Ringkasan satu sesi untuk panel — dihitung di sini supaya panel tidak
 *  memformat sendiri (dua tempat = dua tanggal yang bisa berbeda). */
export type RingkasanSesi = {
  /** `replay`/`realtime`, atau `null` untuk sesi pra-Fase 2. */
  mode: "replay" | "realtime" | null;
  /** Jangkar evaluasi terformat, mis. `8 Okt 2026 12:00 UTC`. */
  anchor: string | null;
  datasetVersion: string | null;
  /** true hanya bila ada sesi demo aktif: suhu dataset demo SIMULASI. */
  simulasi: boolean;
  /** Satu kalimat siap tampil; `null` bila tidak ada sesi aktif. */
  baris: string | null;
};

/**
 * Ringkasan sesi aktif tanpa menebak apa pun: mode dan jangkar dibaca apa
 * adanya dari sesi, `simulasi` hanya menyala untuk sesi demo yang hidup.
 *
 * Yang TIDAK dilakukan: menyimpulkan mode dari "data terbaru" (dua sesi bisa
 * hidup berdampingan) atau mengarang jangkar saat kolomnya kosong.
 */
export function ringkasSesi(sesi: StatusSesiDemo | null): RingkasanSesi {
  const aktif = Boolean(sesi?.active);
  const mode = modeSesi(sesi);
  const anchor = jangkarSesi(sesi);
  if (!aktif) {
    return {
      mode,
      anchor,
      datasetVersion: null,
      simulasi: false,
      baris: null,
    };
  }
  const bagian = [
    `Dataset ${labelSesi(mode)}`,
    anchor ? `jangkar ${anchor}` : "jangkar tidak tercatat",
  ];
  if (sesi?.dataset_version) bagian.push(`versi ${sesi.dataset_version}`);
  bagian.push("suhu simulasi");
  return {
    mode,
    anchor,
    datasetVersion: sesi?.dataset_version ?? null,
    simulasi: true,
    baris: bagian.join(" · "),
  };
}

/** Label pendek mode untuk kalimat ringkasan. */
export function labelSesi(mode: "replay" | "realtime" | null): string {
  if (mode === "replay") return "replay";
  if (mode === "realtime") return "real-time";
  return "tanpa mode";
}

/** Sisa detik saat ini: nilai server dikurangi waktu yang berjalan di layar. */
export function sisaDetik(
  sesi: StatusSesiDemo | null,
  detikBerlalu: number
): number {
  if (!sesi || !sesi.active) return 0;
  return Math.max(0, Math.round(sesi.remaining_seconds - Math.max(0, detikBerlalu)));
}

/** "2 j 05 m" / "07 m 12 d" / "habis" — satuan Indonesia, tanpa Intl. */
export function formatSisa(detik: number): string {
  const total = Math.max(0, Math.floor(detik));
  if (total <= 0) return "habis";
  const jam = Math.floor(total / 3600);
  const menit = Math.floor((total % 3600) / 60);
  const sisaDetiknya = total % 60;
  if (jam > 0) return `${jam} j ${String(menit).padStart(2, "0")} m`;
  if (menit > 0) return `${menit} m ${String(sisaDetiknya).padStart(2, "0")} d`;
  return `${sisaDetiknya} d`;
}

/** Keadaan untuk tampilan: mode sesi mati, kosong, berjalan, atau habis. */
export function keadaanSesi(sesi: StatusSesiDemo | null): KeadaanSesi {
  if (!sesi || !sesi.enforced) return "mati";
  if (sesi.active) return "berjalan";
  if (sesi.status === "expired" || sesi.status === "ended") return "habis";
  return "kosong";
}

/** true bila data boleh diubah: mode sesi mati (dev) atau sesi berjalan. */
export function bolehUbahData(sesi: StatusSesiDemo | null): boolean {
  if (!sesi || !sesi.enforced) return true;
  return sesi.active;
}

/** Satu kalimat status untuk pembaca layar dan layar. */
export function pesanSesi(sesi: StatusSesiDemo | null, detikBerlalu = 0): string {
  const keadaan = keadaanSesi(sesi);
  if (keadaan === "mati") return "Mode sesi demo mati — data demo tidak dibatasi waktu.";
  if (keadaan === "berjalan") return `Sesi demo berjalan — sisa ${formatSisa(sisaDetik(sesi, detikBerlalu))}.`;
  // Audit 21 Okt 2026: baris template SENGAJA tidak berstempel, jadi "Akhiri sesi"
  // hanya membuang perubahan sesi — data contoh tetap tampil. Kalimat "dikosongkan
  // kembali" menjanjikan layar kosong yang tidak pernah terjadi.
  if (keadaan === "habis")
    return "Sesi demo sudah berakhir — perubahan selama sesi dibuang; data contoh bawaan tetap tampil.";
  return "Belum ada sesi demo — tekan Siapkan data demo untuk membangun data contoh selama satu jendela waktu.";
}

/** Peringatan yang layak muncul di layar saat sisa waktu menipis. */
export function peringatanWaktu(detik: number): string | null {
  if (detik <= 0) return "Waktu sesi habis — data demo akan dikosongkan.";
  if (detik <= 300) return `Sisa ${formatSisa(detik)} lagi — perpanjang bila demo masih berjalan.`;
  return null;
}
