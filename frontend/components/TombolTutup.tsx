"use client";

// Tombol tutup SERAGAM — X bulat ber-label.
//
// Permintaan pemilik 29 Okt 2026: "untuk semua tombol keluar buat menjadi X
// bulat". Sebelumnya penutup muncul dalam tiga bentuk: tombol teks "Tutup" di
// kaki dialog, tombol teks di kepala kartu, dan X di kepala popup. Satu ikon
// yang sama di semua tempat membuat pembaca tidak perlu mencari kata.
//
// Aturan yang dipegang:
//   * bentuk & ukuran dari `.tombol-x` (globals.css) — 32 px, lingkaran penuh,
//     44 px di layar sentuh; jangan menyalin angka di komponen;
//   * label tetap ada untuk pembaca layar (`aria-label`) dan tooltip (`title`),
//     karena ikon saja tidak terbaca;
//   * Esc tetap ditangani induk (Popup), tombol ini hanya jalur klik.

export default function TombolTutup({
  onClick,
  label = "Tutup",
  title,
  className = "",
  size = 16,
  disabled = false,
}: {
  onClick?: () => void;
  /** Kalimat untuk pembaca layar; sebut APA yang ditutup. */
  label?: string;
  /** Tooltip; bawaannya sama dengan `label`. */
  title?: string;
  className?: string;
  size?: number;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={`tombol-x ${className}`.trim()}
      onClick={onClick}
      aria-label={label}
      title={title ?? label}
      disabled={disabled}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 16 16"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M3.5 3.5l9 9M12.5 3.5l-9 9"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    </button>
  );
}
