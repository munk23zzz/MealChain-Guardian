"use client";

// Keadaan kosong Recommendation Feed (Tahap 5 redesign, 30 Okt 2026).
//
// Sebelumnya kotak ini `border: 1px dashed var(--status-warning)` — kuning
// peringatan untuk keadaan yang bukan peringatan — dan isinya bergantung pada
// cabang: dengan filter aktif hanya satu kalimat tanpa tindakan, tanpa filter
// satu kalimat + satu tombol. Aturan *Empty States* menuntut tiga hal: sebab,
// aksi utama, aksi sekunder. Karena itu blok ini dipisah dari `app/page.tsx`
// (2.500+ baris, komponen klien, butuh sesi) supaya bisa diuji sebagai render
// biasa — bukan hanya lewat grep sumber.
//
// Angka & label yang dicetak di sini DILEWATKAN dari pemanggil (`totalInWindow`,
// `windowLabel`, `windowHint`); komponen ini tidak menghitung sendiri.

export default function FeedEmptyState({
  filterActive,
  windowKey,
  windowLabel,
  windowHint = null,
  totalInWindow,
  onResetFilter,
  onWidenWindow,
  onRetry,
}: {
  /** Ada kata kunci / chip status yang menyaring daftar. */
  filterActive: boolean;
  /** Jendela waktu yang sedang aktif ("7d" · "30d" · …). */
  windowKey: string;
  /** Label jendela apa adanya dari pemanggil ("7 hari terakhir"). */
  windowLabel: string;
  /** Kalimat tambahan yang membedakan jendela, bila ada. */
  windowHint?: string | null;
  /** Jumlah rekomendasi pada jendela INI (tanpa saringan). */
  totalInWindow: number;
  onResetFilter?: () => void;
  onWidenWindow?: () => void;
  onRetry?: () => void;
}) {
  const bisaMelebar = windowKey !== "30d";

  const utama = filterActive
    ? { label: "Kosongkan filter", onClick: onResetFilter }
    : bisaMelebar
      ? { label: "Lihat 1 bulan terakhir", onClick: onWidenWindow }
      : { label: "Muat ulang", onClick: onRetry };

  const sekunder =
    filterActive && bisaMelebar
      ? { label: "Lihat 1 bulan terakhir", onClick: onWidenWindow }
      : utama.label === "Muat ulang"
        ? null
        : { label: "Muat ulang", onClick: onRetry };

  return (
    <div className="feed-empty" data-empty-state="feed" role="status">
      <p className="feed-empty-sebab">
        {filterActive ? (
          <>
            Tidak ada rekomendasi yang cocok dengan filter atau kata kunci ini.
            Coba kata lain, atau kosongkan filter untuk melihat seluruh{" "}
            {totalInWindow} rekomendasi pada periode {windowLabel.toLowerCase()}.
          </>
        ) : (
          <>
            Tidak ada rekomendasi pada periode <strong>{windowLabel.toLowerCase()}</strong>
            {windowHint ? ` (${windowHint})` : ""}.
          </>
        )}
      </p>
      <div className="feed-empty-aksi">
        <button
          type="button"
          className="button"
          data-aksi="utama"
          onClick={utama.onClick}
          disabled={!utama.onClick}
        >
          {utama.label}
        </button>
        {sekunder ? (
          <button
            type="button"
            className="button button-secondary"
            data-aksi="sekunder"
            onClick={sekunder.onClick}
            disabled={!sekunder.onClick}
          >
            {sekunder.label}
          </button>
        ) : null}
      </div>
    </div>
  );
}
