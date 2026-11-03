/**
 * Padanan teks untuk isi peta (K3, riset 7b-3 — 17 Okt 2026).
 *
 * Masalah yang dijawab: penanda peta tidak masuk urutan Tab, daftar teks lokasi
 * dimatikan di Overview (`showStatusList={false}`), dan nama kiriman hanya
 * muncul di pil pemilih/popup. Tanpa padanan teks, isi peta tidak terbaca sama
 * sekali oleh pembaca layar.
 *
 * Batas yang dijaga: keluaran ini BUKAN tabel. Tabel "Rincian Pasokan per
 * Lokasi" sengaja dihapus atas permintaan pemilik; di sini hanya satu baris
 * ringkas (nama + selisih) dan daftar sr-only dari data yang sama.
 *
 * Fungsi murni: seluruh keputusan ada di `penandaPeta`, sehingga bisa diuji
 * tanpa merender peta.
 */
import {
  formatBalanceGap,
  formatBalanceStatus,
  type BalanceMapLocation,
} from "./overview-format";

export type PenandaPeta = {
  /** Nama lokasi seperti yang dipakai server. */
  nama: string;
  /** Status mentah (`shortage` / `surplus` / `balanced` / lain). */
  status: string;
  /** Ringkasan untuk layar: "kurang 765,8 kg". */
  ringkas: string;
  /** Satu kalimat lengkap untuk pembaca layar (status disebut, bukan warna). */
  aria: string;
  /** Besar selisih untuk pengurutan; 0 bila tidak ada. */
  selisih: number;
};

/** Urutan kepentingan: kekurangan dulu, lalu kelebihan, seimbang terakhir. */
const PERINGKAT: Record<string, number> = {
  shortage: 0,
  surplus: 1,
  balanced: 2,
};

function angka(nilai: unknown): number {
  const n = Number(nilai);
  return Number.isFinite(n) ? Math.abs(n) : 0;
}

export function penandaPeta(
  locations: readonly BalanceMapLocation[] | null | undefined
): PenandaPeta[] {
  const daftar = (locations ?? []).filter(
    (l): l is BalanceMapLocation =>
      Boolean(l) && typeof l.location === "string" && l.location.trim().length > 0
  );

  return daftar
    .map((lokasi) => {
      const ringkas = formatBalanceGap(lokasi);
      return {
        nama: lokasi.location.trim(),
        status: lokasi.status,
        ringkas,
        aria: `${lokasi.location.trim()} — ${formatBalanceStatus(lokasi.status)}, ${ringkas}`,
        selisih:
          lokasi.status === "shortage"
            ? angka(lokasi.shortage_kg)
            : lokasi.status === "surplus"
              ? angka(lokasi.surplus_kg)
              : 0,
      };
    })
    .sort((a, b) => {
      const peringkat = (PERINGKAT[a.status] ?? 3) - (PERINGKAT[b.status] ?? 3);
      if (peringkat !== 0) return peringkat;
      if (b.selisih !== a.selisih) return b.selisih - a.selisih;
      return a.nama.localeCompare(b.nama, "id");
    });
}

/**
 * Satu baris untuk layar: N penanda terpenting + sisaannya.
 * `maks` kecil (3) supaya baris ini tidak pernah mendorong peta ke bawah.
 */
export function ringkasPenanda(items: PenandaPeta[], maks = 3): string {
  if (items.length === 0) return "";
  const tampil = items.slice(0, Math.max(1, maks));
  const sisa = items.length - tampil.length;
  const teks = tampil.map((p) => `${p.nama} ${p.ringkas}`).join(" · ");
  return sisa > 0 ? `${teks} · +${sisa} lokasi lain` : teks;
}
