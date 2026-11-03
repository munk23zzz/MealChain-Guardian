/**
 * Kendali tampilan peta (langkah 7b-1; riset: `docs/research/peta-ui-industri.md` §5).
 *
 * Latar: peta tidak punya jalan kembali ke tampilan awal. Setelah pengguna
 * menggeser/zoom (atau mengikuti satu lokasi aktif), satu-satunya cara kembali
 * adalah menekan tombol zoom berulang kali. Literatur interaksi peta menyebut
 * ini eksplisit: "it's easy to get lost, so it's generally a good idea to
 * include some kind of reset button for reverting the map to its default
 * extent" (Axis Maps, Cartography Guide — Map interaction).
 *
 * Judul tombolnya adalah fungsi murni, bukan teks di JSX, karena judul itu
 * adalah JANJI: tombol memanggil `fitBounds()` ulang, jadi kalimatnya harus
 * persis menyebut apa yang akan tampil lagi — dan tidak boleh mengarang angka
 * saat datanya belum ada.
 */

/** Label pendek tombol (ikon di dalam grup kontrol peta). */
export const MAP_RESET_LABEL = "Tampilkan semua";

/**
 * Ikon tombol: empat sudut bingkai (arti "muat semua ke layar") — SVG inline,
 * bukan emoji dan bukan berkas gambar (docs/design.md §ikon). Warnanya mengikuti
 * `currentColor` supaya ikut warna teks tombol saat disorot/difokus.
 */
export const MAP_RESET_ICON =
  '<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M3 7V3h4M17 7V3h-4M3 13v4h4M17 13v4h-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

/**
 * Kalimat lengkap tombol — dipakai sebagai `title` + `aria-label` supaya
 * pembaca layar dan pengguna tetikus mendapat keterangan yang SAMA.
 *
 * `jumlahLokasi` yang tidak wajar (negatif, NaN, pecahan) tidak dipaksa jadi
 * angka: jumlah lokasi adalah bilangan bulat hasil hitung, dan menulis
 * "0 lokasi" saat data belum termuat akan salah (belum ada ≠ tidak ada).
 */
export function mapResetTitle(jumlahLokasi: number, adaJalur: boolean): string {
  const jumlah = Number.isFinite(jumlahLokasi) && jumlahLokasi >= 1 ? Math.floor(jumlahLokasi) : 0;
  const bagian = jumlah > 0 ? `semua ${jumlah} lokasi` : "semua lokasi";
  return adaJalur
    ? `Kembalikan tampilan ke ${bagian} dan jalur kiriman`
    : `Kembalikan tampilan ke ${bagian}`;
}

/* --- Gestur kooperatif (celah C9, langkah 7b-2) -----------------------------
   Di ponsel, geser satu jari di atas peta "mencuri" gulir halaman: pengguna
   tidak bisa melewati peta untuk sampai ke kartu di bawahnya. MapLibre punya
   mode *cooperative gestures* untuk itu — sekali sentuh = gulir HALAMAN, dua
   jari = geser peta (persis seperti peta tersemat di aplikasi lain).
   Konsekuensinya mode ini juga mengubah desktop: roda tetikus butuh Ctrl.
   Karena itu ia hanya boleh menyala untuk perangkat sentuh UTAMA. */

/**
 * Kebijakan gestur kooperatif, diuji lewat penyuplai media query — bukan lewat
 * `window` — supaya bisa diperiksa tanpa peramban.
 *
 * Yang diperiksa HANYA jenis penunjuk (`pointer: coarse`), bukan lebar jendela:
 * mencabut zoom roda tetikus hanya karena jendela desktop disempitkan akan
 * mengejutkan, dan itu bukan keluhan yang sedang diperbaiki (riset §5 C9
 * menyebut keluhan gulir halaman di ponsel).
 */
export function mapCooperativeGestures(query: (q: string) => boolean): boolean {
  return query("(pointer: coarse)");
}

/** Kalimat pengganti pesan bawaan MapLibre (Inggris) untuk perangkat sentuh. */
export const MAP_GESTURE_HINT_MOBILE =
  "Satu jari menggulir halaman · dua jari menggeser peta";

/** Kalimat untuk perangkat yang butuh tombol pengubah (desktop). */
export const MAP_GESTURE_HINT_DESKTOP =
  "Tekan Ctrl sambil menggulir untuk memperbesar peta";

/**
 * Mengganti pesan layar gestur MapLibre dengan kalimat Indonesia.
 *
 * Peta ini seluruhnya berbahasa Indonesia; pesan bawaan MapLibre berbahasa
 * Inggris dan muncul TEPAT saat pengguna bingung ("kenapa petanya tidak
 * bergeser?"). Fungsi ini tidak melempar apa pun kalau elemennya tidak ada —
 * versi MapLibre lain bisa memberi nama kelas yang berbeda, dan peta tidak boleh
 * gagal jalan hanya karena kalimat bantuan tidak ditemukan.
 */
export function lokalkanPesanGesture(root: ParentNode): void {
  const layar = root.querySelector(".maplibregl-cooperative-gesture-screen");
  if (!layar) return;
  const mobile = layar.querySelector(".maplibregl-mobile-message");
  if (mobile) mobile.textContent = MAP_GESTURE_HINT_MOBILE;
  const desktop = layar.querySelector(".maplibregl-desktop-message");
  if (desktop) desktop.textContent = MAP_GESTURE_HINT_DESKTOP;
}
