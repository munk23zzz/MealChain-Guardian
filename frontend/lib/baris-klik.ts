// Aturan "klik baris tabel" (permintaan pemilik, 29 Okt 2026).
//
// Pemilik: *"tabel yang ada tombol tidak perlu menekan tombol — menekan baris
// tabelnya juga bisa ke-trigger"*.
//
// Kenapa aturannya ditaruh di satu fungsi murni: tiga tabel memakai pola yang
// sama, dan kesalahan yang paling mudah terjadi bukan "tidak berfungsi" tapi
// **dua kali jalan** — klik pada tombol di dalam baris memicu aksi tombol DAN
// aksi baris, sehingga satu klik membuka dua kali (atau, untuk aksi tulis,
// mengirim dua permintaan).
//
// Yang dianggap klik baris:
// - klik di sel biasa (teks, angka, lencana),
// - target bukan elemen (mis. `document`).
//
// Yang BUKAN klik baris:
// - klik pada kontrol di dalam baris (`button`, `a`, `input`, `select`,
//   `textarea`, `label`, `summary`, apa pun ber-`role="button"`/`role="link"`,
//   atau elemen bertanda `data-tanpa-klik-baris`) — kontrol itu punya aksinya
//   sendiri dan tetap menjadi jalur papan ketik,
// - saat ada teks yang sedang disorot: menyalin isi tabel tidak boleh diartikan
//   sebagai perintah membuka baris.

const KONTROL_DALAM_BARIS = [
  "button",
  "a",
  "input",
  "select",
  "textarea",
  "label",
  "summary",
  '[role="button"]',
  '[role="link"]',
  "[data-tanpa-klik-baris]",
].join(", ");

/** True bila klik ini boleh dianggap "klik baris". */
export function bolehKlikBaris(
  target: EventTarget | null,
  teksTersorot: string | null | undefined = "",
): boolean {
  if (teksTersorot && teksTersorot.trim()) return false;
  if (!(target instanceof Element)) return true;
  return target.closest(KONTROL_DALAM_BARIS) === null;
}

/** Pembungkus untuk `onClick` baris: menjalankan `aksi` hanya bila kliknya sah.
 *
 *  Dipakai sebagai `onClick={(e) => klikBaris(e, () => onSelect(...))}` supaya
 *  tiap tabel tidak perlu mengulang pemeriksaan yang sama.
 */
export function klikBaris(event: { target: EventTarget | null }, aksi: () => void): void {
  const sorotan =
    typeof window !== "undefined" && window.getSelection
      ? window.getSelection()?.toString() ?? ""
      : "";
  if (!bolehKlikBaris(event.target, sorotan)) return;
  aksi();
}
