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
  // 29 Okt 2026 (tahap 7): keamanan & pemasok jadi tujuan nav tersendiri —
  // bagian itu kini blok sendiri (tahap 4), bukan lagi potongan kartu bukti.
  keamanan: "keamanan",
  jejak: "jejak",
} as const;

/**
 * Bagian Decision & Evidence — urutannya urutan baca halaman, bukan urutan
 * "yang penting dulu". Semuanya dirender bersamaan dengan keputusan terpilih,
 * jadi tidak ada tujuan yang bisa hilang.
 *
 * 29 Okt 2026 (tahap 7): label disamakan dengan judul bagian yang benar-benar
 * tercetak ("Keputusan" → "Persetujuan", "Bukti" → "Bukti biaya", tambah
 * "Keamanan & pemasok"). id jangkar TIDAK berubah supaya tautan lama
 * (`#zona-keputusan`, `#bukti`) tetap mendarat di tempat yang sama.
 *
 * "Identitas & batch" sengaja TIDAK jadi tujuan kelima→keenam: aturan
 * docs/design.md §24 membatasi lima tujuan, dan bagian itu pendek (dua tabel)
 * yang langsung disusul "Jejak & integritas" — tautan ke jejak melewatinya.
 */
export function evidenceSections(): JumpItem[] {
  return [
    { id: EVIDENCE_SECTION_IDS.ringkasan, label: "Ringkasan" },
    { id: EVIDENCE_SECTION_IDS.keputusan, label: "Persetujuan" },
    { id: EVIDENCE_SECTION_IDS.bukti, label: "Bukti biaya" },
    { id: EVIDENCE_SECTION_IDS.keamanan, label: "Keamanan & pemasok" },
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
 * "Batch perlu perhatian" sudah memuat sisa masa layak sehingga
 * tidak perlu jatah nav; "Menunggu persetujuan" dan "Pasokan masuk" punya
 * jangkar sendiri (`persetujuan`, `kiriman`).
 */
export function safetySections({
  ownLocation,
  hasDecisions,
  hasPending = false,
}: {
  /** Halaman menampilkan kartu "Penerimaan barang" — yaitu peran punya SPPG
   *  sendiri DAN ada barang baru yang menunggu diuji. Sejak 30 Okt 2026 kartu
   *  kosong "tidak ada barang baru" dihapus, jadi nilai ini BUKAN sekadar
   *  "punya lokasi sendiri": tanpa barang baru, tidak ada tujuan penerimaan
   *  dan tidak ada jangkar `safety-terima` (nav tidak boleh menunjuk ruang
   *  kosong). */
  ownLocation: boolean;
  hasDecisions: boolean;
  /** Ada catatan penerimaan yang menunggu persetujuan (aksi tulis hari ini). */
  hasPending?: boolean;
}): JumpItem[] {
  const items: JumpItem[] = [];
  // Aksi yang menahan stok didahulukan: pertanyaan pertama pembaca adalah
  // "ada yang harus saya putuskan sekarang?". Jatah lima tujuan tetap dipegang
  // `slice` di bawah, jadi menambah tujuan ini tidak menambah keruwetan nav.
  if (hasPending) items.push({ id: SAFETY_SECTION_IDS.persetujuan, label: "Menunggu keputusan" });
  items.push({ id: SAFETY_SECTION_IDS.ringkasan, label: "Ringkasan" });
  // Kartu "Batch perlu perhatian" (bukti suhu + sisa layak + kesegaran dalam
  // satu tabel) selalu dirender, jadi jangkarnya tetap di navigasi.
  items.push({ id: SAFETY_SECTION_IDS.bukti, label: "Perlu perhatian" });
  if (ownLocation) items.push({ id: SAFETY_SECTION_IDS.terima, label: "Penerimaan" });
  items.push({ id: SAFETY_SECTION_IDS.batch, label: "Status per batch" });
  if (hasDecisions) items.push({ id: SAFETY_SECTION_IDS.keputusan, label: "Keputusan" });
  return items.slice(0, 5);
}

/* ── Tiga halaman yang 29 Okt 2026 baru diberi navigasi bagian ─────────────
 *
 * Sebelumnya hanya Decision & Evidence, Overview, dan Food Safety yang punya
 * navigasi ini; Suppliers, Agent Activity Log, dan Location Network tidak —
 * padahal ketiganya sama panjangnya. Selisih itu bukan pilihan desain, hanya
 * akibat halaman ditambah satu per satu. Daftar di bawah mengikuti aturan
 * docs/design.md §24: ≥3 bagian tetap, maksimum lima tujuan, dan SETIAP id di
 * sini harus benar-benar dipasang di halamannya — tautan mati lebih buruk
 * daripada tidak ada nav (lihat tes `tests/navigation-shell.test.ts`).
 */

/** Jangkar halaman Suppliers (dipasang di `components/SupplierBoard.tsx`). */
export const SUPPLIER_SECTION_IDS = {
  ringkasan: "supplier-ringkasan",
  kiriman: "supplier-kiriman",
  daftar: "supplier-daftar",
  register: "supplier-register",
  usul: "supplier-usul",
} as const;

/**
 * Bagian Suppliers — LIMA tujuan (29 Okt 2026: dua jangkar pertama ditambah).
 *
 * Sebelumnya hanya tiga (daftar, register, usul) padahal halaman punya dua blok
 * besar di ATAS daftar: strip Ringkasan dan Papan kiriman. Akibatnya petugas
 * harus menggulir sendiri untuk sampai ke angka yang justru dibaca lebih dulu.
 * Ringkasan dan kiriman selalu dirender (termasuk saat datanya belum dimuat),
 * jadi keduanya layak jadi tujuan tetap. Lima = batas docs/design.md §24.
 */
export function supplierSections(): JumpItem[] {
  return [
    { id: SUPPLIER_SECTION_IDS.ringkasan, label: "Ringkasan" },
    { id: SUPPLIER_SECTION_IDS.kiriman, label: "Kiriman" },
    { id: SUPPLIER_SECTION_IDS.daftar, label: "Daftar pemasok" },
    { id: SUPPLIER_SECTION_IDS.register, label: "Register eksklusi" },
    { id: SUPPLIER_SECTION_IDS.usul, label: "Usul eksklusi" },
  ];
}

/** Jangkar halaman Agent Activity Log (dipasang di `app/page.tsx`). */
export const AGENT_LOG_SECTION_IDS = {
  pilih: "log-pilih",
  langkah: "log-langkah",
  integritas: "log-integritas",
} as const;

/**
 * Bagian Agent Activity Log, mengikuti urutan baca `06-agent-log.md` §4.3:
 * pilih keputusan → langkah rinci & model → integritas. Tiga tujuan; filter,
 * tabel, dan strip tahap sengaja digabung ke satu tujuan karena pembaca memakai
 * ketiganya sekaligus saat memilih keputusan.
 */
export function agentLogSections(): JumpItem[] {
  return [
    { id: AGENT_LOG_SECTION_IDS.pilih, label: "Pilih keputusan" },
    { id: AGENT_LOG_SECTION_IDS.langkah, label: "Langkah & model" },
    { id: AGENT_LOG_SECTION_IDS.integritas, label: "Integritas" },
  ];
}

/** Jangkar halaman Performance & Audit (tab `kpi-kualitas`).
 *  Dipasang di `components/KpiQualityBoard.tsx`, 29 Okt 2026 — tahap 1 redesign:
 *  halaman ini sebelumnya satu-satunya tab panjang tanpa navigasi bagian. */
export const PERF_AUDIT_SECTION_IDS = {
  hasil: "pa-hasil",
  audit: "pa-audit",
  mutu: "pa-mutu",
} as const;

/**
 * Bagian Performance & Audit, urutan baca: hasil (KPI) → audit perhitungan →
 * mutu agen. Tiga tujuan, sesuai docs/design.md §24 (maksimum lima).
 */
export function perfAuditSections(): JumpItem[] {
  return [
    { id: PERF_AUDIT_SECTION_IDS.hasil, label: "Hasil KPI" },
    { id: PERF_AUDIT_SECTION_IDS.audit, label: "Audit perhitungan" },
    { id: PERF_AUDIT_SECTION_IDS.mutu, label: "Mutu agen" },
  ];
}

/** Jangkar halaman Location Network (dipasang di `components/LocationNetworkBoard.tsx`). */
export const NETWORK_SECTION_IDS = {
  keadaan: "network-keadaan",
  lokasi: "network-lokasi",
  alih: "network-alih",
  limbah: "network-limbah",
} as const;

/**
 * Bagian Location Network: keadaan jaringan → lokasi → rencana alih → limbah.
 * "Rencana alih" hanya muncul bila ada rekomendasi alih; kalau tidak ada, tujuan
 * itu tidak dipasang supaya nav tidak menunjuk kartu yang tidak dirender.
 */
export function networkSections({
  hasRows,
  hasTransfer,
}: {
  /** Tabel lokasi hanya dirender bila ada baris (kosong = kartu tidak ada). */
  hasRows: boolean;
  /** Kartu "Rencana alih" dirender selama data tidak gagal dimuat. */
  hasTransfer: boolean;
}): JumpItem[] {
  const items: JumpItem[] = [{ id: NETWORK_SECTION_IDS.keadaan, label: "Keadaan jaringan" }];
  if (hasRows) items.push({ id: NETWORK_SECTION_IDS.lokasi, label: "Lokasi" });
  if (hasTransfer) items.push({ id: NETWORK_SECTION_IDS.alih, label: "Rencana alih" });
  items.push({ id: NETWORK_SECTION_IDS.limbah, label: "Limbah" });
  return items;
}
