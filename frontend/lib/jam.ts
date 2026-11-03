// Jam header konsol — waktu Indonesia dengan detik + label zona.
//
// Dipisah dari komponen supaya bisa diuji murni (tanpa DOM/timer): komponen
// hanya memanggil formatJam() tiap detik.
//
// Zona: data demo seluruhnya Indonesia. Label singkatan (WIB/WITA/WIT) tidak
// bisa diturunkan otomatis dari Intl dengan andal di semua runtime, jadi
// pemetaannya eksplisit di sini.

/** Zona default konsol (SPPG demo ada di Jakarta). */
export const ZONA_DEFAULT = "Asia/Jakarta";

/** IANA → singkatan resmi zona waktu Indonesia. */
const ZONA_INDONESIA: Record<string, string> = {
  "Asia/Jakarta": "WIB",
  "Asia/Pontianak": "WIB",
  "Asia/Makassar": "WITA",
  "Asia/Ujung_Pandang": "WITA",
  "Asia/Jayapura": "WIT",
};

export type JamTeks = {
  /** Jam:menit:detik gaya Indonesia, mis. "15.42.30". */
  jam: string;
  /** Singkatan zona, mis. "WIB". */
  zona: string;
  /** Teks tampil lengkap, mis. "15.42.30 WIB". */
  teks: string;
  /** Nama aksesibel untuk aria-label. */
  aria: string;
};

/** Singkatan zona Indonesia; tak dikenal → WIB (default konsol). */
export function zonaLabel(timeZone: string = ZONA_DEFAULT): string {
  return ZONA_INDONESIA[timeZone] ?? "WIB";
}

/**
 * Format jam Indonesia (dengan DETIK) pada zona waktu tertentu.
 * Selalu memakai WIB/WITA/WIT sesuai zona, bukan zona mesin pemakai.
 */
export function formatJam(date: Date, timeZone: string = ZONA_DEFAULT): JamTeks {
  const jam = new Intl.DateTimeFormat("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone,
  }).format(date);
  const zona = zonaLabel(timeZone);
  return {
    jam,
    zona,
    teks: `${jam} ${zona}`,
    aria: `Waktu saat ini: ${jam} ${zona} (${timeZone})`,
  };
}
