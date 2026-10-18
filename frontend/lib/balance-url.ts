/**
 * Path `GET /balance/{lokasi}/{komoditas}` (+ `as_of` opsional).
 *
 * `as_of` dipakai agar panel detail memakai snapshot yang SAMA dengan peta
 * (`GET /balance/map` mengembalikan `as_of`-nya). Tanpa ini, membuka detail
 * beberapa detik kemudian menampilkan angka dari instant lain — selisih kecil
 * yang terbaca sebagai "angka tidak konsisten antar tampilan".
 */
export function balancePath(
  location: string,
  commodity: string,
  asOf?: string | null,
): string {
  const base = `/balance/${encodeURIComponent(location)}/${encodeURIComponent(commodity)}`;
  const batas = asOf?.trim();
  if (!batas) return base;
  return `${base}?as_of=${encodeURIComponent(batas)}`;
}
