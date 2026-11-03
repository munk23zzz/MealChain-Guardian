import type { DirectoryMetrics } from "./suppliers-board";

// Angka Ringkasan halaman Pemasok — satu baris KPI, hanya dibaca.
//
// Bentuk ini dipilih pemilik 29 Okt 2026 setelah dua percobaan sebelumnya
// (daftar fakta datar, lalu papan sorotan dengan tile/chip) dinilai sulit
// dipahami. Keputusannya: kartu Ringkasan TIDAK menyaring apa pun dan tidak
// punya tombol. Penyaring tetap satu — tombol "Hanya dalam jangkauan" di atas
// kolom cari, yang memang sudah ada dan dekat dengan tabelnya.
//
// S2 (29 Okt 2026) — EMPAT angka, satu di antaranya dipromosikan:
//   1. [dipromosikan] pemasok dalam jangkauan (atau pemasok terdaftar bila
//      peran tidak punya ambang jangkauan)
//   2. rata-rata keandalan
//   3. pemasok dengan keandalan di bawah 60%
//   4. pemasok tanpa stok layak hari ini
//
// Kenapa "jumlah pemasok" dan "di luar jangkauan" tidak lagi berdiri sendiri:
//   - jumlah pemasok sudah jadi pil di kepala halaman (S1) — mengulanginya di
//     strip membuat satu angka tampil di dua tempat;
//   - "di luar jangkauan" sudah tertulis sebagai kalimat di baris penyaring
//     jangkauan ("30 dari 60 pemasok berjarak di atas 120 km"), tepat di atas
//     tabel yang ia saring.
// Jadi strip hanya memuat angka yang tidak ada di tempat lain: berapa pemasok
// yang bisa dipakai hari ini, dan seberapa bagus mutunya.
//
// Angka 0 tetap ditampilkan (bukan disembunyikan): pada strip KPI, "0" adalah
// jawaban yang sah dan tidak lagi terbaca seperti data yang gagal dimuat.

export type Kpi = {
  label: string;
  value: string;
  /** `warn`/`danger` memberi warna pada angka yang perlu dilihat. */
  tone: "plain" | "warn" | "danger";
  /** Angka yang dipromosikan — satu per strip, dibaca lebih dulu. */
  lead?: boolean;
};

function angka(n: number): string {
  return Number.isFinite(n) ? n.toLocaleString("id-ID") : "—";
}

export function kpiRingkasan(
  metrics: DirectoryMetrics,
  reachKm?: number | null
): Kpi[] {
  const tanpaStok = Math.max(0, metrics.suppliers - metrics.shipping);
  const punyaJangkauan =
    reachKm !== null && reachKm !== undefined && Number.isFinite(reachKm);
  const dalamJangkauan = Math.max(0, metrics.suppliers - metrics.outOfReach);
  const utama: Kpi = punyaJangkauan
    ? {
        label: `Pemasok dalam jangkauan ${reachKm} km`,
        value: angka(dalamJangkauan),
        tone: "plain",
        lead: true,
      }
    : {
        label: "Pemasok terdaftar",
        value: angka(metrics.suppliers),
        tone: "plain",
        lead: true,
      };
  return [
    utama,
    {
      label: "Rata-rata keandalan",
      value: metrics.avgReliabilityLabel,
      tone: "plain",
    },
    {
      label: "Keandalan di bawah 60%",
      value: angka(metrics.lowReliability),
      tone: metrics.lowReliability > 0 ? "warn" : "plain",
    },
    {
      label: "Tanpa stok layak hari ini",
      value: angka(tanpaStok),
      tone: tanpaStok > 0 ? "warn" : "plain",
    },
  ];
}
