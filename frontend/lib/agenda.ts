// Kalender agenda harian (langkah 2, permintaan pemilik 2026-10-16) — fungsi MURNI.
//
// Semua aritmetika kalender ada di sini, bukan di komponen, supaya bisa diuji
// tanpa DOM dan supaya tak ada dua tempat yang menghitung "hari" secara berbeda:
// - grid bulan selalu 42 sel mulai SENIN (pola kalender Indonesia);
// - rentangnya 42 hari, di bawah batas 62 hari kontrak `GET /agenda`;
// - hari dihitung menurut WIB (UTC+7) — layar konsol memakai WIB ("23.38 WIB"),
//   jadi memakai UTC akan menggeser hari antara pukul 00:00–07:00 WIB.

export const AGENDA_MONTH_LABELS: Record<number, string> = {
  1: "Januari",
  2: "Februari",
  3: "Maret",
  4: "April",
  5: "Mei",
  6: "Juni",
  7: "Juli",
  8: "Agustus",
  9: "September",
  10: "Oktober",
  11: "November",
  12: "Desember",
};

export const AGENDA_DAY_LABELS = [
  "Minggu",
  "Senin",
  "Selasa",
  "Rabu",
  "Kamis",
  "Jumat",
  "Sabtu",
];

export const AGENDA_WEEKDAY_HEADERS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

const WIB_OFFSET_MS = 7 * 60 * 60 * 1000;
const HARI_MS = 24 * 60 * 60 * 1000;

export type AgendaCell = {
  date: string;
  day: number;
  inMonth: boolean;
  weekday: number;
};

export type AgendaSection = { rows: number; available: boolean } & Record<string, unknown>;

export type AgendaDay = {
  date: string;
  menu: AgendaSection;
  delivery: AgendaSection;
  disposal: AgendaSection;
  supply: AgendaSection;
  price: AgendaSection;
  batches_expiring: AgendaSection;
  decisions: AgendaSection;
  activity: number;
};

export type AgendaPayload = {
  period?: { start?: string; end?: string; timezone?: string };
  scope?: { location_id?: string | null; national?: boolean };
  computed_at?: string;
  days?: AgendaDay[];
} | null;

export type AgendaRow = { label: string; value: string | null; available: boolean; hint?: string };

/** Tanggal hari ini menurut WIB sebagai `YYYY-MM-DD` (bukan tanggal UTC). */
export function wibToday(now: Date): string {
  return new Date(now.getTime() + WIB_OFFSET_MS).toISOString().slice(0, 10);
}

/** `{year, month}` dari tanggal ISO — untuk state awal halaman. */
export function monthOf(iso: string): { year: number; month: number } {
  const d = new Date(`${iso}T00:00:00Z`);
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1 };
}

/** Geser bulan, menyeberang tahun bila perlu. */
export function shiftMonth(
  year: number,
  month: number,
  delta: number,
): { year: number; month: number } {
  const total = year * 12 + (month - 1) + delta;
  return { year: Math.floor(total / 12), month: (total % 12 + 12) % 12 + 1 };
}

/** 42 sel mulai Senin: dua minggu pipi + minggu bulan itu. */
export function monthGrid(year: number, month: number): AgendaCell[] {
  const pertama = new Date(Date.UTC(year, month - 1, 1));
  const sejakSenin = (pertama.getUTCDay() + 6) % 7;
  const sel: AgendaCell[] = [];
  for (let i = 0; i < 42; i += 1) {
    const d = new Date(pertama.getTime() + (i - sejakSenin) * HARI_MS);
    sel.push({
      date: d.toISOString().slice(0, 10),
      day: d.getUTCDate(),
      inMonth: d.getUTCMonth() === month - 1,
      weekday: d.getUTCDay(),
    });
  }
  return sel;
}

/** Rentang yang dikirim ke `GET /agenda` = rentang grid yang terlihat. */
export function gridRange(cells: AgendaCell[]): { start: string; end: string } {
  return { start: cells[0].date, end: cells[cells.length - 1].date };
}

export function monthTitle(year: number, month: number): string {
  return `${AGENDA_MONTH_LABELS[month]} ${year}`;
}

/** Pilihan bulan untuk dropdown pemilih tanggal (Januari→Desember). */
export function monthChoices(): { value: number; label: string }[] {
  return Object.keys(AGENDA_MONTH_LABELS)
    .map(Number)
    .sort((a, b) => a - b)
    .map((value) => ({ value, label: AGENDA_MONTH_LABELS[value] }));
}

/**
 * Tahun yang bisa dipilih di pemilih tanggal: setiap tahun yang dicakup rentang
 * data (`fromIso`..`toIso`), DITAMBAH tahun yang sedang tampil bila di luar
 * rentang itu — tanpa itu `<select>` bisa menampilkan nilai yang tidak ada di
 * daftarnya sendiri (kontrol tampak kosong padahal bulan itu sedang dibuka).
 * Tahunnya berasal dari rentang data yang didukung backend, bukan angka karangan.
 */
export function pickerYears(fromIso: string, toIso: string, keep?: number): number[] {
  const dari = Number(fromIso.slice(0, 4));
  const sampai = Number(toIso.slice(0, 4));
  const tahun: number[] = [];
  for (let y = Math.min(dari, sampai); y <= Math.max(dari, sampai); y += 1) tahun.push(y);
  if (keep !== undefined && !tahun.includes(keep)) tahun.push(keep);
  return tahun.sort((a, b) => a - b);
}

/** "Selasa, 20 Oktober 2026" — tanpa Intl, supaya stabil di server & klien. */
export function formatDayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return `${AGENDA_DAY_LABELS[d.getUTCDay()]}, ${d.getUTCDate()} ${
    AGENDA_MONTH_LABELS[d.getUTCMonth() + 1]
  } ${d.getUTCFullYear()}`;
}

export function dayOf(agenda: AgendaPayload, iso: string): AgendaDay | null {
  const days = agenda?.days ?? [];
  return days.find((d) => d.date === iso) ?? null;
}

/** Jumlah bagian berisi untuk sebuah tanggal (0 = tak ada catatan sama sekali). */
export function activityOf(agenda: AgendaPayload, iso: string): number {
  const hari = dayOf(agenda, iso);
  return hari ? hari.activity : 0;
}

const ANGKA = new Intl.NumberFormat("id-ID");

function angka(n: unknown): string {
  return ANGKA.format(Number(n) || 0);
}

function kg(n: unknown): string {
  const nilai = Number(n) || 0;
  return Number.isInteger(nilai) ? angka(nilai) : nilai.toFixed(1).replace(".", ",");
}

const STATUS_LABELS: Record<string, string> = {
  proposed: "diusulkan",
  pending_approval: "menunggu persetujuan",
  needs_verification: "menunggu verifikasi",
  verifier_flagged: "ditandai verifikator",
  verified: "terverifikasi",
  approved: "disetujui",
  executed: "dieksekusi",
  rejected: "ditolak",
  review_only: "tinjauan (review-only)",
  expired: "kedaluwarsa",
};

/**
 * Baris ringkasan satu hari. Bagian tanpa catatan → `value: null`
 * (`available: false`), BUKAN "0 porsi"/"0 kg": aturan repo melarang angka yang
 * tampak terukur padahal tidak ada datanya.
 */
export function agendaRows(hari: AgendaDay): AgendaRow[] {
  const bagian = (nama: keyof AgendaDay): AgendaSection | null => {
    const nilai = hari[nama] as AgendaSection | undefined;
    return nilai && nilai.available ? nilai : null;
  };

  const menu = bagian("menu");
  const kiriman = bagian("delivery");
  const limbah = bagian("disposal");
  const pasokan = bagian("supply");
  const harga = bagian("price");
  const batch = bagian("batches_expiring");
  const keputusan = bagian("decisions");

  const rincianStatus = Object.entries((keputusan?.by_status ?? {}) as Record<string, number>)
    .sort((a, b) => b[1] - a[1])
    .map(([status, jumlah]) => `${jumlah} ${STATUS_LABELS[status] ?? status}`);

  return [
    {
      label: "Rencana menu",
      value: menu ? `${angka(menu.planned_portions)} porsi` : null,
      available: Boolean(menu),
      hint: menu ? `${angka(menu.rows)} lokasi merencanakan` : undefined,
    },
    {
      label: "Kiriman tiba",
      value: kiriman ? `${angka(kiriman.delivered_portions)} porsi` : null,
      available: Boolean(kiriman),
      hint: kiriman ? `${angka(kiriman.rows)} kiriman tercatat` : undefined,
    },
    {
      label: "Limbah dibuang",
      value: limbah ? `${kg(limbah.quantity_kg)} kg` : null,
      available: Boolean(limbah),
      hint: limbah ? `${angka(limbah.rows)} peristiwa` : undefined,
    },
    {
      label: "Pasokan tercatat",
      value: pasokan ? `${angka(pasokan.rows)} baris` : null,
      available: Boolean(pasokan),
    },
    {
      label: "Harga tercatat",
      value: harga ? `${angka(harga.rows)} baris` : null,
      available: Boolean(harga),
    },
    {
      label: "Batch kedaluwarsa",
      value: batch ? `${angka(batch.rows)} batch` : null,
      available: Boolean(batch),
    },
    {
      label: "Keputusan agen",
      value: keputusan
        ? `${angka(keputusan.rows)}${rincianStatus.length ? ` (${rincianStatus.join(", ")})` : ""}`
        : null,
      available: Boolean(keputusan),
    },
  ];
}

export const AGENDA_NO_DATA = "tidak ada catatan";

/**
 * Geser tanggal sebanyak `delta` HARI (boleh negatif), menyeberang bulan/tahun.
 * Dipakai kepala kartu agenda harian setelah grid bulan dihapus: ‹ › berarti
 * "hari sebelumnya/berikutnya", bukan bulan.
 */
export function shiftDay(iso: string, delta: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return new Date(d.getTime() + delta * HARI_MS).toISOString().slice(0, 10);
}

/**
 * Hasil langkah hari yang DIBATASI rentang data (`min`..`max`).
 * `null` = tombol ‹ › harus mati: melangkah ke luar rentang hanya akan
 * menampilkan hari kosong yang tampak seperti "tidak ada operasi hari itu",
 * padahal datanya memang tidak diminta ke server.
 */
export function clampDayStep(
  iso: string,
  delta: number,
  min: string,
  max: string,
): string | null {
  const tujuan = shiftDay(iso, delta);
  return tujuan < min || tujuan > max ? null : tujuan;
}

export type AgendaGroup = { title: string; rows: AgendaRow[] };

/**
 * Kelompok bertema untuk info harian. Dulu ketujuh baris ditumpuk rata sehingga
 * mata harus memindai semuanya; kelompok membuat "rencana/pasokan", "limbah",
 * dan "keputusan" bisa ditemukan sendiri-sendiri.
 */
const AGENDA_GROUPS: { title: string; labels: string[] }[] = [
  {
    title: "Rencana & pasokan",
    labels: ["Rencana menu", "Kiriman tiba", "Pasokan tercatat", "Harga tercatat"],
  },
  { title: "Limbah & kedaluwarsa", labels: ["Limbah dibuang", "Batch kedaluwarsa"] },
  { title: "Keputusan agen", labels: ["Keputusan agen"] },
];

export function agendaGroups(hari: AgendaDay): AgendaGroup[] {
  const semua = agendaRows(hari);
  const terpakai = new Set<string>();
  const groups: AgendaGroup[] = AGENDA_GROUPS.map((grup) => ({
    title: grup.title,
    rows: grup.labels.flatMap((label) => {
      const row = semua.find((baris) => baris.label === label);
      if (!row) return [];
      terpakai.add(label);
      return [row];
    }),
  }));
  // Jaring pengaman: baris baru di `agendaRows` tidak boleh hilang diam-diam
  // hanya karena daftar kelompok di atas belum diperbarui.
  const sisa = semua.filter((baris) => !terpakai.has(baris.label));
  if (sisa.length) groups.push({ title: "Catatan lain", rows: sisa });
  return groups;
}
