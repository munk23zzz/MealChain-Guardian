/**
 * Copy kartu "Rekomendasi menunggu" di Overview.
 *
 * Satu tempat untuk angka + kalimat, supaya tidak ada lagi keadaan "3 menunggu"
 * dengan kalimat "semua sudah ditindaklanjuti". `rest` (sisa di luar batas
 * tampil) BUKAN jumlah pekerjaan; keputusan selesai hanya saat total = 0.
 */
import { formatKg } from "./overview-format";

export type PendingKpiInput = {
  total: number;
  monitored: number;
  limit?: number;
  loading?: boolean;
  expired?: number;
};

export type PendingKpiCopy = {
  value: string;
  foot: string;
  mini: string;
};

function angka(value: number | undefined): number {
  return Number.isFinite(value) ? Math.max(0, Math.trunc(value as number)) : 0;
}

export function pendingKpiCopy({
  total,
  monitored,
  limit = 4,
  loading = false,
  expired = 0,
}: PendingKpiInput): PendingKpiCopy {
  const jumlah = angka(total);
  const dipantau = angka(monitored);
  const lewat = angka(expired);
  const batas = Math.max(1, angka(limit));

  if (loading) {
    return {
      value: "—",
      foot: "memuat daftar keputusan",
      mini: "menunggu data",
    };
  }

  if (jumlah > 0) {
    const sisa = Math.max(0, jumlah - batas);
    const tambahan = [
      sisa > 0 ? `+${sisa} lain menunggu tindakan` : null,
      lewat > 0 ? `${lewat} lewat tenggat` : null,
    ].filter(Boolean);
    return {
      value: String(jumlah),
      foot: `${jumlah} menunggu tindakan · ${dipantau} total dipantau`,
      mini:
        tambahan.length > 0
          ? tambahan.join(" · ")
          : "semua rekomendasi tampil di antrean",
    };
  }

  if (lewat > 0) {
    return {
      value: "0",
      foot: `${lewat} lewat tenggat — tidak bisa ditindak lagi`,
      mini: "tidak ada yang bisa ditindak",
    };
  }

  if (dipantau > 0) {
    return {
      value: "0",
      foot: `${dipantau} keputusan dipantau`,
      mini: "tidak ada yang menunggu",
    };
  }

  return {
    value: "—",
    foot: "belum ada data keputusan",
    mini: "siapkan data demo atau tunggu sinkronisasi",
  };
}

/**
 * Jumlah pada baris antrean. `formatKg` menulis "—" untuk nilai yang tidak
 * terbaca; di sini tanda itu harus menjelaskan alasannya, bukan terbaca nol.
 */
export function queueQuantityLabel(value: unknown): string {
  const label = formatKg(value as number | string | null | undefined);
  return label === "—" ? "jumlah tidak tercatat" : label;
}
