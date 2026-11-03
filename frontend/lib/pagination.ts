/**
 * Paginasi daftar — logika murni, tanpa React.
 *
 * Dipakai "Daftar pemasok" dan "Papan kiriman" di halaman Pemasok (permintaan
 * pemilik 19 Okt 2026: tampilkan 10 baris per halaman, sisanya di halaman
 * berikutnya). Dua bagian itu berbagi satu aturan supaya nomor halaman, rentang
 * "1–10 dari 60", dan perilaku di batas data tidak berbeda antar panel.
 *
 * Semua masukan dijepit, bukan dilempar: data bisa menyusut setelah penyaring
 * atau penyegaran, dan halaman kosong karena nomor halaman basi lebih buruk
 * daripada halaman terakhir yang terisi sebagian.
 */

export type Page<T> = {
  /** Halaman yang benar-benar dipakai (sudah dijepit ke 1..pageCount). */
  page: number;
  pageCount: number;
  /** Jumlah baris keseluruhan, bukan jumlah di halaman ini. */
  total: number;
  items: T[];
  /** Nomor baris pertama & terakhir yang tampil (1-based); 0 saat kosong. */
  start: number;
  end: number;
  hasPrev: boolean;
  hasNext: boolean;
};

/** Potong `items` menjadi satu halaman. `size` tidak sah diperlakukan sebagai 1. */
export function paginate<T>(
  items: readonly T[],
  page: number,
  size: number
): Page<T> {
  const ukuran = Math.max(1, Math.floor(size) || 1);
  const total = items.length;
  const pageCount = Math.max(1, Math.ceil(total / ukuran));
  const aktif = Math.min(Math.max(1, Math.floor(page) || 1), pageCount);
  const mulai = (aktif - 1) * ukuran;
  const potong = items.slice(mulai, mulai + ukuran);
  return {
    page: aktif,
    pageCount,
    total,
    items: potong,
    start: potong.length > 0 ? mulai + 1 : 0,
    end: potong.length > 0 ? mulai + potong.length : 0,
    hasPrev: aktif > 1,
    hasNext: aktif < pageCount,
  };
}

/**
 * Nomor halaman yang ditampilkan tombol pager, dengan `"…"` untuk lompatan.
 * Halaman pertama & terakhir selalu ada; halaman aktif selalu ada.
 */
export function pageSlots(
  page: number,
  pageCount: number,
  slots = 7
): (number | "…")[] {
  const maks = Math.max(5, Math.floor(slots) || 7);
  const total = Math.max(1, Math.floor(pageCount) || 1);
  const aktif = Math.min(Math.max(1, Math.floor(page) || 1), total);

  if (total <= maks) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const sisi = Math.max(0, Math.floor((maks - 4) / 2));
  const blokAwal = Array.from({ length: maks - 2 }, (_, i) => i + 1);
  const blokAkhir = Array.from(
    { length: maks - 2 },
    (_, i) => total - (maks - 3) + i
  );

  if (aktif - sisi <= 2) return [...blokAwal, "…", total];
  if (aktif + sisi >= total - 1) return [1, "…", ...blokAkhir];

  const tengah: number[] = [];
  for (let n = aktif - sisi; n <= aktif + sisi; n += 1) tengah.push(n);
  return [1, "…", ...tengah, "…", total];
}

/** Rentang yang dibaca pembaca layar: "1–10 dari 60". */
export function rangeLabel(page: Page<unknown>): string {
  if (page.total === 0) return "Tidak ada baris";
  const angka = (n: number) => n.toLocaleString("id-ID");
  return `${angka(page.start)}–${angka(page.end)} dari ${angka(page.total)}`;
}
