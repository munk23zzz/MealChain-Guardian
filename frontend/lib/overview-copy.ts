/**
 * Kop peta Overview (Ruling 2026-10-14).
 *
 * Sebelum cakupan lokasi ditegakkan, peta selalu berisi 10 lokasi sehingga
 * kalimat "Peta 10 lokasi SPPG" selalu masuk akal. Untuk kepala SPPG peta kini
 * berisi SATU titik — kalimat itu jadi janggal ("Peta 1 lokasi SPPG") dan bisa
 * terbaca seolah aplikasinya rusak. Karena itu kalimatnya dipisah ke fungsi
 * murni ini supaya bisa diuji, bukan ditebak di dalam JSX.
 */

export function mapHeaderSubtitle(locationCount: number): string {
  if (locationCount <= 0) return "Tidak ada lokasi pada cakupan ini.";
  if (locationCount === 1) {
    return "Peta SPPG Anda. Warna menunjukkan pasokan lebih, kurang, atau cukup.";
  }
  return `Peta ${locationCount} lokasi SPPG. Warna menunjukkan pasokan lebih, kurang, atau cukup.`;
}
