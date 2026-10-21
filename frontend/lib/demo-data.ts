/**
 * "Data & rentang waktu" (Fase 5, 2026-10-15) — logika MURNI, tanpa React/DOM.
 *
 * Semua kalimat yang dilihat operator dihitung di sini supaya bisa diuji tanpa
 * merender komponen, dan supaya panel tidak pernah mengarang angka: setiap
 * baris berasal dari payload backend (`/demo/preview`, `/demo/timeseries`,
 * `/demo/data-status`).
 *
 * Yang dijaga modul ini:
 * - **Rentang divalidasi SEBELUM dikirim** (pesan manusia, bukan `HTTP 422`),
 *   tetapi backend tetap penentu akhir — ini hanya menghindari perjalanan sia-sia.
 * - **Tanggal `YYYY-MM-DD` dari `<input type="date">` wajib diberi offset zona
 *   waktu** (`toIsoDateTime`). Backend menolak waktu tanpa offset (422) karena
 *   "hari ini" harus tunggal artinya.
 * - **Peringatan jujur**, bukan basa-basi: apa yang dihapus, apa yang tidak
 *   tersentuh, dan apa yang TIDAK dijanjikan (masa depan hanya rencana).
 */

/** Rentang default panel — sama dengan rencana Fase 4/5. */
export const DEFAULT_RANGE = { start: "2026-09-01", end: "2026-11-05" } as const;

/** Batas yang didukung backend (app/seed/timeseries.py: GENERATION_FLOOR/CEILING). */
export const RANGE_MIN = "2026-01-01";
export const RANGE_MAX = "2027-01-01";

/** Selang default generator (jam) — 12 jam menghasilkan 2 baris/hari. */
export const INTERVAL_HOURS = 12;

const NAMA_BULAN = [
  "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
  "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
];

/** `2026-09-01` → `1 Sep 2026` (deterministik, tanpa Intl). */
export function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const cocok = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!cocok) return iso;
  const [, tahun, bulan, hari] = cocok;
  const nama = NAMA_BULAN[Number(bulan) - 1] ?? bulan;
  return `${Number(hari)} ${nama} ${tahun}`;
}

/** `2.190` — pemisah ribuan gaya Indonesia. */
export function formatCount(value: number | null | undefined): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return "0";
  return n.toLocaleString("id-ID");
}

/** `<input type="date">` → waktu ISO dengan offset (kontrak backend). */
export function toIsoDateTime(date: string): string {
  return `${date}T00:00:00+00:00`;
}

/** Jumlah hari dalam rentang (inklusif kedua ujung). */
export function spanDays(start: string, end: string): number | null {
  const a = Date.parse(`${start}T00:00:00Z`);
  const b = Date.parse(`${end}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return null;
  return Math.round((b - a) / 86_400_000) + 1;
}

/**
 * Validasi rentang di sisi klien. `null` = boleh dikirim.
 * Pesannya sengaja sama artinya dengan galat backend (start < end, batas tahun).
 */
export function rangeError(start: string, end: string): string | null {
  const pola = /^\d{4}-\d{2}-\d{2}$/;
  if (!pola.test(start) || !pola.test(end)) {
    return "Isi tanggal mulai dan tanggal selesai (format YYYY-MM-DD).";
  }
  if (start >= end) return "Tanggal selesai harus setelah tanggal mulai.";
  if (start < RANGE_MIN || end > RANGE_MAX) {
    return `Rentang yang didukung ${RANGE_MIN} sampai ${RANGE_MAX}.`;
  }
  return null;
}

/** Kalimat pratinjau dari `GET /demo/preview` (tanpa menulis apa pun). */
export function previewLine(preview: any): string {
  if (!preview?.counts) return "Pratinjau tidak tersedia.";
  const supply = preview.counts.supply?.planned ?? 0;
  const prices = preview.counts.prices?.planned ?? 0;
  const menu = preview.counts.menu_plans?.planned ?? 0;
  const hari = spanDays(preview.range?.start?.slice(0, 10), preview.range?.end?.slice(0, 10));
  const potongan = [
    `${formatCount(supply)} baris pasokan`,
    `${formatCount(prices)} harga`,
    `${formatCount(menu)} rencana menu`,
  ].join(" · ");
  const rentang = hari ? ` untuk ${hari} hari` : "";
  const batasAktual = preview.range?.actual_end
    ? ` Baris aktual berhenti ${formatShortDate(preview.range.actual_end)} ${jamFrom(preview.range.actual_end)} UTC`
    : "";
  return `Akan menambah${rentang}: ${potongan}.${batasAktual} — jendela KPI tidak disentuh.`;
}

function jamFrom(iso: string): string {
  const cocok = /T(\d{2}):(\d{2})/.exec(iso);
  return cocok ? `${cocok[1]}.${cocok[2]}` : "";
}

/** Kalimat hasil dari `POST /demo/timeseries`. */
export function buildLine(result: any): string {
  if (!result?.counts) return "Selesai, tetapi ringkasan tidak dikenali.";
  const supply = result.counts.supply ?? {};
  const prices = result.counts.prices ?? {};
  const menu = result.counts.menu_plans ?? {};
  const dihapus = result.purged?.total ? `Dihapus dulu ${formatCount(result.purged.total)} baris demo. ` : "";
  const tetap = result.skipped?.menu_plans_kept
    ? ` ${formatCount(result.skipped.menu_plans_kept)} rencana menu yang sudah ada (baris kanonik) tidak ditimpa.`
    : "";
  return (
    `${dihapus}Ditambahkan ${formatCount(supply.added)} pasokan · ${formatCount(prices.added)} harga · ` +
    `${formatCount(menu.added)} rencana menu. Isi tabel sekarang: ${formatCount(supply.in_db)} · ` +
    `${formatCount(prices.in_db)} · ${formatCount(menu.in_db)}.${tetap}`
  );
}

/**
 * true bila status benar-benar memuat baris (demo atau kanonik).
 *
 * Badge kartu sempat menulis "data siap" hanya karena `status` tidak null —
 * setelah sesi demo berakhir (semua tabel 0) badge itu berbohong tepat di
 * kartu yang menyuruh menyiapkan data.
 */
export function adaBaris(status: any): boolean {
  const t = status?.tables;
  if (!t) return false;
  return [t.supply_records, t.price_signals, t.menu_plans].some(
    (x) => (x?.seed ?? 0) + (x?.demo ?? 0) > 0
  );
}

/** Baris status dari `GET /demo/data-status` — keadaan DB, bukan ingatan klien. */
export function statusLine(status: any): string {
  const tabel = status?.tables;
  if (!tabel) return "Status data belum bisa dibaca.";
  const demo = [tabel.supply_records, tabel.price_signals, tabel.menu_plans];
  const seed = demo.map((t) => t?.seed ?? 0);
  const demoCount = demo.map((t) => t?.demo ?? 0);
  const total = demoCount.reduce((a, b) => a + b, 0);
  if (total === 0) {
    return "Belum ada deret waktu demo — tombol “Buat/perbarui data” mengisinya.";
  }
  const rentang = `(${formatShortDate(tabel.supply_records?.demo_from)} – ${formatShortDate(
    tabel.menu_plans?.demo_to
  )})`;
  const dibuat = tabel.supply_records?.generated_at;
  const terakhir = dibuat
    ? ` Terakhir dibuat ${formatShortDate(dibuat)} ${jamFrom(dibuat)} UTC.`
    : "";
  return (
    `Deret waktu demo: ${formatCount(total)} baris ${rentang} — ` +
    `${formatCount(demoCount[0])} pasokan · ${formatCount(demoCount[1])} harga · ${formatCount(demoCount[2])} rencana menu. ` +
    `Snapshot kanonik: ${formatCount(seed.reduce((a, b) => a + b, 0))} baris (per ${formatShortDate(
      status.canonical_ref
    )} ${jamFrom(status.canonical_ref ?? "")} UTC) tidak disentuh.${terakhir}`
  );
}

/** Peringatan yang tampil SEBELUM tombol bersihkan dijalankan. */
export function purgeWarning(): string {
  return (
    "Menghapus SEMUA baris deret waktu demo (pasokan, harga, rencana menu). " +
    "Snapshot kanonik tidak tersentuh — Overview kembali ke angka kanonik " +
    "(4.900 kg, 3 surplus : 7 shortage). Kasus skrip punya tombolnya sendiri, " +
    "jadi ia tetap ada."
  );
}

/** Kalimat hasil dari `POST /demo/timeseries/purge`. */
export function purgeLine(result: any): string {
  const total = result?.total ?? 0;
  const deleted = result?.deleted ?? {};
  const rincian = [
    `${formatCount(deleted.supply_records ?? deleted.supply)} pasokan`,
    `${formatCount(deleted.price_signals ?? deleted.prices)} harga`,
    `${formatCount(deleted.menu_plans)} rencana menu`,
  ].join(" · ");
  if (!total) {
    return "Tidak ada baris deret waktu demo untuk dihapus — data sudah bersih seperti kanonik.";
  }
  return `Dihapus ${formatCount(total)} baris demo (${rincian}). Snapshot kanonik tidak tersentuh.`;
}

/**
 * Peringatan yang WAJIB tampil bersama tombol "Segarkan ke hari ini".
 *
 * Ini bukan basa-basi: seeder relatif `now` memang menggeser TANGGAL snapshot
 * kanonik, dan itu punya konsekuensi nyata (tes backend yang memaku 8 Okt 12.00
 * tidak lagi cocok). Nilai jangkar sendiri tidak berubah karena berasal dari
 * berkas seed yang sama.
 */
export function refreshWarning(): string {
  return (
    "Seeder relatif menjalankan ulang snapshot kanonik pada tanggal HARI INI dan " +
    "memuat ulang 4 kasus skrip dengan batas waktu baru. Nilai jangkar (4.900 kg, " +
    "3 surplus : 7 shortage, Cianjur 1.400 kg) tidak berubah — yang bergeser adalah " +
    "TANGGALNYA, sehingga tes backend yang memaku 8 Okt 12.00 tidak lagi cocok sampai " +
    "snapshot dikembalikan. Akun demo tidak direset dan baris deret waktu demo tidak dihapus."
  );
}

/** Kalimat hasil dari `POST /demo/refresh` — memakai pesan backend apa adanya. */
export function refreshLine(result: any): string {
  if (!result) return "Penyegaran belum dijalankan.";
  const kapan = `${formatShortDate(result.reference_time)} ${jamFrom(result.reference_time ?? "")}`.trim();
  const kasus = result.cases?.cases;
  const keputusan = result.cases?.decisions;
  const rincian =
    typeof kasus === "number"
      ? ` ${formatCount(kasus)} kasus skrip dimuat ulang` +
        (typeof keputusan === "number" ? ` (${formatCount(keputusan)} keputusan siap).` : ".")
      : "";
  return `Snapshot kanonik disegarkan ke ${kapan} UTC.${rincian}`;
}

/** Catatan tetap di bawah panel: apa yang boleh dan tidak boleh dijanjikan. */
export function honestNote(): string {
  return (
    "Baris masa depan hanya dibuat untuk tabel yang memang merencanakan (rencana menu sampai 5 Nov). " +
    "Aktual tidak pernah dikarang di masa depan, dan empat kasus skrip selalu di-anchor ke waktu sekarang."
  );
}

/** Apakah tombol aksi boleh ditekan (rentang sah + tidak sedang sibuk). */
export function canSubmit(start: string, end: string, busy: boolean): boolean {
  return !busy && rangeError(start, end) === null;
}

/** Bentuk ringkasan yang dikembalikan `POST /demo/template/rebuild`. */
export type RebuildSummary = {
  ok?: boolean;
  durasi_detik?: number;
  hitung?: {
    batches?: number;
    decisions?: number;
    receipts?: number;
    eksklusi?: number;
    ledger?: number;
    traces?: number;
    po?: number;
    users?: number;
  };
};

/**
 * Satu kalimat hasil bangun ulang — angka diambil dari `hitung` (dibaca ulang
 * server dari database sesudah commit), bukan dari parameter permintaan.
 */
export function rebuildLine(hasil: RebuildSummary | null | undefined): string {
  if (!hasil) return "Bangun ulang belum dijalankan.";
  const h = hasil.hitung ?? {};
  const bagian = [
    typeof h.batches === "number" ? `${formatCount(h.batches)} batch` : null,
    typeof h.decisions === "number" ? `${formatCount(h.decisions)} keputusan` : null,
    typeof h.po === "number" ? `${formatCount(h.po)} pesanan SAP` : null,
    typeof h.ledger === "number" ? `${formatCount(h.ledger)} blok ledger` : null,
  ].filter(Boolean);
  const durasi =
    typeof hasil.durasi_detik === "number" ? ` dalam ${hasil.durasi_detik.toFixed(1)} detik` : "";
  const isi = bagian.length ? `: ${bagian.join(", ")}` : "";
  return `Data demo dibangun ulang${durasi}${isi}.`;
}

/** Peringatan yang menyertai tombol — menyebut yang hilang DAN yang tidak. */
export function rebuildWarning(): string {
  return (
    "Baris operasional (batch, keputusan, pesanan, bukti, ledger) diganti dari template, " +
    "jadi angka kembali ke keadaan awal. Jendela sesi, akun demo, lokasi, dan pemasok tidak " +
    "disentuh. Proses ini butuh ±70 detik karena mengambil ulang rute jalan."
  );
}
