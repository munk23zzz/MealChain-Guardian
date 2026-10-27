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
  rute: "rute",
  keputusan: "zona-keputusan",
  bukti: "bukti",
  jejak: "jejak",
} as const;

/**
 * Bagian Decision & Evidence. Kelimanya selalu dirender bersamaan dengan
 * keputusan terpilih, jadi daftarnya tetap — tidak ada tujuan yang bisa hilang.
 */
export function evidenceSections(): JumpItem[] {
  return [
    { id: EVIDENCE_SECTION_IDS.ringkasan, label: "Ringkasan" },
    { id: EVIDENCE_SECTION_IDS.rute, label: "Jalur persetujuan" },
    { id: EVIDENCE_SECTION_IDS.keputusan, label: "Keputusan" },
    { id: EVIDENCE_SECTION_IDS.bukti, label: "Bukti" },
    { id: EVIDENCE_SECTION_IDS.jejak, label: "Jejak & integritas" },
  ];
}

/** Jangkar halaman Overview (dipasang di `app/page.tsx`). */
export const OVERVIEW_SECTION_IDS = {
  ringkas: "ov-ringkas",
  peta: "overview-map",
  kiriman: "ov-kiriman",
  kecukupan: "ov-kecukupan",
  telemetri: "ov-telemetri",
} as const;

/** Jangkar halaman Keamanan Pangan (dipasang di `components/FoodSafetyBoard.tsx`). */
export const SAFETY_SECTION_IDS = {
  ringkasan: "safety-ringkasan",
  // Fase 3 MG butir 5: panel bukti suhu bisa dijangkau lewat navigasi bagian.
  bukti: "safety-bukti-suhu",
  segera: "safety-segera",
  terima: "safety-terima",
  batch: "safety-batch",
  keputusan: "safety-keputusan",
} as const;

/**
 * Bagian Overview. Peran SPPG/gizi melihat grafik kecukupan empat komoditas;
 * BGN Monitor melihat grafik pasokan lintas lokasi. Jangkar sama, judulnya
 * mengikuti apa yang benar-benar tampil.
 *
 * `hasShipments` ikut: kartu kiriman tidak merender apa pun saat tidak ada
 * kiriman aktif (kartu kosong lebih buruk daripada tidak ada kartu), jadi
 * tujuannya hanya dipasang kalau kartunya benar-benar ada.
 */
export function overviewSections({
  isApprover,
  hasShipments,
}: {
  isApprover: boolean;
  hasShipments: boolean;
}): JumpItem[] {
  const items: JumpItem[] = [
    { id: OVERVIEW_SECTION_IDS.ringkas, label: "Ringkasan" },
    { id: OVERVIEW_SECTION_IDS.peta, label: "Peta & antrean" },
  ];
  // Urutan HARUS sama dengan urutan render di `app/page.tsx`: Kecukupan
  // dirender SEBELUM Kiriman. Sebelumnya nav menaruh Kiriman di atas Kecukupan,
  // sehingga mengeklik "Kiriman" menggulir MELEWATI Kecukupan (terasa "ke-skip")
  // dan penanda posisi melompat tidak sesuai urutan mata. Diuji oleh
  // tests/overview-section-order.test.ts yang membaca urutan id di halaman.
  items.push({
    id: OVERVIEW_SECTION_IDS.kecukupan,
    label: isApprover ? "Kecukupan" : "Pasokan per lokasi",
  });
  if (hasShipments) items.push({ id: OVERVIEW_SECTION_IDS.kiriman, label: "Kiriman" });
  items.push({ id: OVERVIEW_SECTION_IDS.telemetri, label: "Telemetri" });
  return items;
}

/**
 * Bagian Keamanan Pangan. "Penerimaan barang" hanya dirender bila pengguna
 * punya lokasi sendiri; panel "Keputusan keamanan lokasi ini" hanya bila daftar
 * keputusan tersedia. Karena itu keduanya opsional di sini juga.
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
    { id: SAFETY_SECTION_IDS.segera, label: "Segera dipakai" },
  ];
  if (ownLocation) items.push({ id: SAFETY_SECTION_IDS.terima, label: "Penerimaan" });
  items.push({ id: SAFETY_SECTION_IDS.batch, label: "Status per batch" });
  if (hasDecisions) items.push({ id: SAFETY_SECTION_IDS.keputusan, label: "Keputusan" });
  return items;
}
