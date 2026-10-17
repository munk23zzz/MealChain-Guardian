/**
 * Memotong garis jalur pada posisi yang sudah ditempuh (Arah C riset 16 Okt 2026).
 *
 * Riset §6 (pola Oracle): "segmen yang belum ditempuh digambar putus-putus".
 * Kita TIDAK punya posisi kendaraan; yang ada hanya `journey.progress` (0–1) dari
 * server. Jadi potongannya adalah perkiraan menurut jarak tempuh di sepanjang
 * GEOMETRI JALAN, bukan pin kendaraan — dan itu sebabnya di UI segmen putus-putus
 * diberi keterangan "belum ditempuh", bukan "posisi truk sekarang".
 *
 * Aturan:
 * 1. Tidak ada tebakan: `progress` null/NaN/tidak masuk akal → `null`, dan
 *    pemanggil menggambar garis apa adanya (jangan paksa 0% atau 100%).
 * 2. `progress <= 0` → seluruh garis "belum ditempuh"; `>= 1` → seluruhnya selesai.
 *    Keduanya dihitung dari ANGKA SERVER, bukan disimpulkan dari keadaan.
 * 3. Geometri < 2 titik tidak bisa dipotong → `null`.
 */
export type LngLat = [number, number];

export type LineSplit = {
  /** Bagian yang sudah ditempuh (selalu dimulai di titik asal). */
  done: LngLat[];
  /** Bagian yang belum ditempuh (selalu berakhir di tujuan). */
  todo: LngLat[];
  /** Nilai yang benar-benar dipakai setelah dijepit ke 0–1. */
  progress: number;
};

/**
 * Jarak dua titik dalam METER — presisi penuh, sengaja tidak dibulatkan seperti
 * `haversineKm` (pembulatan ke km cukup untuk menampilkan jarak, tetapi salah
 * untuk memotong garis: segmen 0,5 km akan jadi 0 atau 1).
 */
function jarakMeter(a: LngLat, b: LngLat): number {
  const rad = Math.PI / 180;
  const dLat = (b[1] - a[1]) * rad;
  const dLng = (b[0] - a[0]) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.min(1, Math.sqrt(h)));
}

function koordinatValid(coords: readonly LngLat[] | null | undefined): coords is LngLat[] {
  if (!coords || coords.length < 2) return false;
  return coords.every(
    (c) => Array.isArray(c) && c.length >= 2 && Number.isFinite(c[0]) && Number.isFinite(c[1])
  );
}

export function lineSplit(
  coords: readonly LngLat[] | null | undefined,
  progress: number | null | undefined
): LineSplit | null {
  if (!koordinatValid(coords)) return null;
  if (progress === null || progress === undefined || !Number.isFinite(progress)) return null;

  const p = Math.min(1, Math.max(0, progress));
  if (p <= 0) return { done: [], todo: [...coords], progress: 0 };
  if (p >= 1) return { done: [...coords], todo: [], progress: 1 };

  const panjang: number[] = [];
  let total = 0;
  for (let i = 1; i < coords.length; i += 1) {
    const seg = jarakMeter(coords[i - 1], coords[i]);
    panjang.push(seg);
    total += seg;
  }
  // Geometri dengan panjang nol (titik bertumpuk) tidak punya "di tengah":
  // gambarnya utuh, tetapi ANGKA server dibiarkan apa adanya — menaikkannya jadi 1
  // berarti mengklaim perjalanan selesai.
  if (total <= 0) return { done: [...coords], todo: [], progress: p };

  const target = total * p;
  let lewat = 0;
  for (let i = 0; i < panjang.length; i += 1) {
    const seg = panjang[i];
    if (lewat + seg >= target) {
      const rasio = seg === 0 ? 0 : (target - lewat) / seg;
      const a = coords[i];
      const b = coords[i + 1];
      const potong: LngLat = [a[0] + (b[0] - a[0]) * rasio, a[1] + (b[1] - a[1]) * rasio];
      return {
        done: [...coords.slice(0, i + 1), potong],
        todo: [potong, ...coords.slice(i + 1)],
        progress: p,
      };
    }
    lewat += seg;
  }
  // Tidak mungkin tercapai (target <= total), tapi jangan mengembalikan bentuk aneh.
  return { done: [...coords], todo: [], progress: p };
}
