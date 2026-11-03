/**
 * Titik yang berjalan di sepanjang geometri jalur — dipakai penanda "kiriman
 * sedang berjalan" di peta (permintaan pemilik 20 Okt 2026).
 *
 * Kenapa bukan animasi dash: MapLibre tidak punya `line-dash-offset`, dan
 * mengubah `line-dasharray` tiap frame memaksa re-tilasi garis. Titik yang
 * dipindahkan di atas garis jauh lebih murah: satu source kecil berisi
 * 2–6 titik, `setData` saja.
 *
 * Panjang dihitung pada bidang datar dengan koreksi cos(lat) (equirectangular).
 * Untuk jalur 100–700 km di Jawa galatnya di bawah 0,3% — cukup untuk hias,
 * tanpa biaya haversine per frame.
 */

export type JalurSiap = {
  koordinat: [number, number][];
  /** Panjang kumulatif (derajat bidang) sampai titik ke-i. */
  kumulatif: number[];
  total: number;
};

export type OpsiAlir = {
  /** Lama satu putaran penuh jalur. */
  durasiMs: number;
  /** Jumlah titik yang tampak sekaligus. */
  jumlah: number;
};

const RAD = Math.PI / 180;

function panjangSegmen(a: [number, number], b: [number, number]): number {
  const lat = ((a[1] + b[1]) / 2) * RAD;
  const dx = (b[0] - a[0]) * Math.cos(lat);
  const dy = b[1] - a[1];
  return Math.hypot(dx, dy);
}

/** Siapkan jalur sekali per data; `null` bila jalur tak bisa ditempuh. */
export function siapkanJalur(koordinat: [number, number][]): JalurSiap | null {
  if (!Array.isArray(koordinat) || koordinat.length < 2) return null;
  const kumulatif: number[] = [0];
  for (let i = 1; i < koordinat.length; i += 1) {
    kumulatif.push(kumulatif[i - 1] + panjangSegmen(koordinat[i - 1], koordinat[i]));
  }
  const total = kumulatif[kumulatif.length - 1];
  if (!Number.isFinite(total) || total <= 0) return null;
  return { koordinat, kumulatif, total };
}

/** Titik pada fraksi 0..1 sepanjang jalur (di luar rentang dijepit). */
export function titikPada(jalur: JalurSiap, frac: number): [number, number] {
  const f = Math.min(1, Math.max(0, frac));
  if (f === 0) return jalur.koordinat[0];
  if (f === 1) return jalur.koordinat[jalur.koordinat.length - 1];
  const target = f * jalur.total;
  let i = 1;
  while (i < jalur.kumulatif.length - 1 && jalur.kumulatif[i] < target) i += 1;
  const sebelum = jalur.kumulatif[i - 1];
  const panjang = jalur.kumulatif[i] - sebelum;
  const t = panjang === 0 ? 0 : (target - sebelum) / panjang;
  const a = jalur.koordinat[i - 1];
  const b = jalur.koordinat[i];
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

/**
 * Posisi `jumlah` titik pada waktu `waktuMs`. Titik disebar merata dan bergerak
 * dari awal ke ujung, lalu mengulang.
 */
export function titikMengalir(
  jalur: JalurSiap,
  waktuMs: number,
  { durasiMs, jumlah }: OpsiAlir
): [number, number][] {
  const n = Math.max(1, Math.floor(jumlah));
  const durasi = durasiMs > 0 ? durasiMs : 6000;
  const dasar = ((waktuMs % durasi) + durasi) % durasi / durasi;
  const hasil: [number, number][] = [];
  for (let i = 0; i < n; i += 1) {
    hasil.push(titikPada(jalur, (dasar + i / n) % 1));
  }
  return hasil;
}

/**
 * Posisi + arah (bearing) pada fraksi jalur — dipakai ikon mobil kiriman supaya
 * menghadap arah perjalanan, bukan selalu tegak.
 *
 * Bearing: 0 = utara, 90 = timur (searah jarum jam), sama dengan konvensi
 * `rotate` CSS pada glyph yang sudah menghadap utara.
 */
export function posisiDanArah(
  jalur: JalurSiap,
  frac: number
): { posisi: [number, number]; arah: number } {
  const f = Math.min(1, Math.max(0, frac));
  const posisi = titikPada(jalur, f);
  // Arah diambil dari segmen di sekitar posisi; pada ujung jalur pakai segmen
  // terakhir yang masih punya panjang, supaya ikon tidak berputar liar.
  const target = f * jalur.total;
  let i = 1;
  while (i < jalur.kumulatif.length - 1 && jalur.kumulatif[i] < target) i += 1;
  const a = jalur.koordinat[i - 1];
  const b = jalur.koordinat[i];
  const lat = ((a[1] + b[1]) / 2) * RAD;
  const dx = (b[0] - a[0]) * Math.cos(lat);
  const dy = b[1] - a[1];
  const arah = (Math.atan2(dx, dy) * 180) / Math.PI;
  return { posisi, arah: (arah + 360) % 360 };
}

/**
 * Ekor (wake) di belakang kendaraan: potongan jalur yang BARU SAJA dilewati,
 * dari `frac - span` sampai `frac`.
 *
 * Kenapa ada: posisi truk bergerak tiap 5 detik (Live Sync) dan lompatannya bisa
 * beberapa kilometer. Ekor memberi arah gerak yang bisa dibaca mata — bukan
 * sekadar titik yang tiba-tiba pindah. Panjangnya dibatasi `span` (fraksi 0..1)
 * supaya tidak berubah menjadi garis penuh kalau truk sudah jauh di depan.
 *
 * Mengembalikan `[]` bila panjangnya nol (mis. frac 0), supaya pemanggil tidak
 * menggambar garis kosong.
 */
export function wakeLine(
  jalur: JalurSiap,
  frac: number,
  span = 0.05,
  langkah = 6
): [number, number][] {
  const akhir = Math.min(1, Math.max(0, frac));
  const awal = Math.max(0, akhir - span);
  if (akhir <= awal) return [];
  const titik: [number, number][] = [];
  for (let i = 0; i <= langkah; i += 1) {
    titik.push(titikPada(jalur, awal + ((akhir - awal) * i) / langkah));
  }
  return titik;
}
