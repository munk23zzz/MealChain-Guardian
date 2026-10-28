// Daftar bagian halaman untuk navigasi "lompat ke bagian" (20 Okt 2026).
//
// Satu tempat untuk dua hal yang gampang berselisih:
//   1. id jangkar yang DIPASANG di halaman, dan
//   2. label yang dibaca pengguna di nav.
//
// Daftarnya dibangun dari kondisi render yang SAMA dengan bagiannya. Halaman
// yang bagiannya bergantung pada data (mis. "Penerimaan barang" hanya muncul
// untuk peran yang punya SPPG sendiri) tidak boleh menampilkan tautan yang
// tidak ada sasarannya — itu tautan mati, dan tautan mati membuat nav lebih
// buruk daripada tidak ada nav.
//
// Aturan pemakaian (lihat docs/design.md §24): nav hanya dipasang di halaman
// yang benar-benar panjang (≥ ±2,5 layar) dan punya ≥ 3 bagian tetap; maksimum
// lima tujuan.

export type JumpItem = {
  /** id elemen tujuan di halaman (tanpa '#'). */
  id: string;
  /** Label pendek yang dibaca pengguna. */
  label: string;
};

/** Jangkar halaman Decision & Evidence (dipasang di `components/DecisionEvidence.tsx`). */
export const EVIDENCE_SECTION_IDS = {
  ringkasan: "ringkasan",
  // 29 Okt 2026: "rute" dilepas bersama kartu "Jalur persetujuan" — urutan
  // langkah sudah dibaca di dalam blok Governance, jadi satu kartu terpisah
  // untuk kronologi yang sama hanya menambah tinggi + satu tujuan nav.
  keputusan: "zona-keputusan",
  bukti: "bukti",
  jejak: "jejak",
} as const;

/**
 * Bagian Decision & Evidence. Keempatnya selalu dirender bersamaan dengan
 * keputusan terpilih, jadi daftarnya tetap — tidak ada tujuan yang bisa hilang.
 */
export function evidenceSections(): JumpItem[] {
  return [
    { id: EVIDENCE_SECTION_IDS.ringkasan, label: "Ringkasan" },
    { id: EVIDENCE_SECTION_IDS.keputusan, label: "Keputusan" },
    { id: EVIDENCE_SECTION_IDS.bukti, label: "Bukti" },
    { id: EVIDENCE_SECTION_IDS.jejak, label: "Jejak & integritas" },
  ];
}

/** Jangkar halaman Overview (dipasang di `app/page.tsx`). */
export const OVERVIEW_SECTION_IDS = {
  ringkas: "ov-ringkas",
  peta: "overview-map",
  kecukupan: "ov-kecukupan",
  // 28 Okt 2026: "kiriman" dan "telemetri" dilepas dari Overview; panel harga
  // pasar menggantikan keduanya. Komponen aslinya tetap ada di repo.
  harga: "ov-harga",
} as const;

/** Jangkar halaman Keamanan Pangan (dipasang di `components/FoodSafetyBoard.tsx`). */
export const SAFETY_SECTION_IDS = {
  ringkasan: "safety-ringkasan",
  // Fase 3 MG butir 5: panel bukti suhu bisa dijangkau lewat navigasi bagian.
  bukti: "safety-bukti-suhu",
  segera: "safety-segera",
  terima: "safety-terima",
  // Jangkar "Menunggu persetujuan" dan "Pasokan masuk": tidak masuk nav (jatah
  // lima tujuan penuh) tetapi tetap punya id supaya bisa ditautkan langsung.
  persetujuan: "safety-persetujuan",
  batch: "safety-batch",
  kiriman: "safety-pasokan",
  keputusan: "safety-keputusan",
} as const;

/**
 * Bagian Overview.
 *
 * Peran SPPG/gizi melihat grafik kecukupan empat komoditas; BGN Monitor melihat
 * grafik pasokan lintas lokasi. Jangkar sama, judulnya mengikuti apa yang
 * benar-benar tampil.
 *
 * Sejak 28 Okt 2026 daftar ini TETAP empat tujuan: Ringkasan, Peta & antrean,
 * Kecukupan, Harga pasar. Dulu ada tujuan "Kiriman" yang muncul hanya bila ada
 * kiriman aktif; kartunya dilepas dari Overview sehingga tujuan itu tidak
 * dipasang lagi (nav tidak boleh menunjuk tempat yang tidak ada).
 */
export function overviewSections({ isApprover }: { isApprover: boolean }): JumpItem[] {
  return [
    { id: OVERVIEW_SECTION_IDS.ringkas, label: "Ringkasan" },
    { id: OVERVIEW_SECTION_IDS.peta, label: "Peta & antrean" },
    {
      id: OVERVIEW_SECTION_IDS.kecukupan,
      label: isApprover ? "Kecukupan" : "Pasokan per lokasi",
    },
    { id: OVERVIEW_SECTION_IDS.harga, label: "Harga pasar" },
  ];
}

/**
 * Bagian Keamanan Pangan.
 *
 * URUTAN daftar ini harus sama dengan urutan render di `FoodSafetyBoard.tsx`:
 * keadaan → bukti → tindakan tulis → rujukan panjang → konteks → jejak audit.
 * Nav yang urutannya berbeda membuat klik "Status per batch" menggulir MELEWATI
 * bagian lain, dan penanda posisi melompat tidak sesuai urutan mata.
 *
 * Jatah maksimum lima tujuan (docs/design.md §24). Halaman ini punya tujuh
 * bagian, jadi yang masuk nav adalah yang paling sering dituju: keadaan, bukti,
 * tindakan tulis (penerimaan), rujukan panjang (status batch), dan jejak audit.
 * "Batch perlu segera dipakai" hanya satu kartu di bawah panel bukti sehingga
 * tidak perlu jatah nav; "Menunggu persetujuan" dan "Pasokan masuk" punya
 * jangkar sendiri (`persetujuan`, `kiriman`).
 */
export function safetySections({
  ownLocation,
  hasDecisions,
}: {
  ownLocation: boolean;
  hasDecisions: boolean;
}): JumpItem[] {
  const items: JumpItem[] = [
    { id: SAFETY_SECTION_IDS.ringkasan, label: "Ringkasan" },
    // Panel bukti suhu selalu dirender (Fase 3 butir 5), jadi jangkarnya tetap.
    { id: SAFETY_SECTION_IDS.bukti, label: "Bukti suhu" },
  ];
  if (ownLocation) items.push({ id: SAFETY_SECTION_IDS.terima, label: "Penerimaan" });
  items.push({ id: SAFETY_SECTION_IDS.batch, label: "Status per batch" });
  if (hasDecisions) items.push({ id: SAFETY_SECTION_IDS.keputusan, label: "Keputusan" });
  return items;
}
