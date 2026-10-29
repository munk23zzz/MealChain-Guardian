import type { DirectoryMetrics } from "./suppliers-board";

// Angka Ringkasan halaman Pemasok — satu baris KPI, hanya dibaca.
//
// Bentuk ini dipilih pemilik 29 Okt 2026 setelah dua percobaan sebelumnya
// (daftar fakta datar, lalu papan sorotan dengan tile/chip) dinilai sulit
// dipahami. Keputusannya: kartu Ringkasan TIDAK menyaring apa pun dan tidak
// punya tombol. Penyaring tetap satu — tombol "Hanya dalam jangkauan" di atas
// kolom cari, yang memang sudah ada dan dekat dengan tabelnya.
//
// Isi strip, urut tetap:
//   1. jumlah pemasok
//   2. rata-rata keandalan
//   3. pemasok dengan keandalan di bawah 60%
//   4. pemasok tanpa stok layak hari ini
//   5. pemasok di luar jangkauan (hanya bila peran punya ambang jangkauan)
//
// Angka 0 tetap ditampilkan (bukan disembunyikan): pada strip KPI, "0" adalah
// jawaban yang sah dan tidak lagi terbaca seperti data yang gagal dimuat.

export type Kpi = {
  label: string;
  value: string;
  /** `warn`/`danger` memberi warna pada angka yang perlu dilihat. */
  tone: "plain" | "warn" | "danger";
};

function angka(n: number): string {
  return Number.isFinite(n) ? n.toLocaleString("id-ID") : "—";
}

export function kpiRingkasan(
  metrics: DirectoryMetrics,
  reachKm?: number | null
): Kpi[] {
  const tanpaStok = Math.max(0, metrics.suppliers - metrics.shipping);
  const items: Kpi[] = [
    { label: "Pemasok", value: angka(metrics.suppliers), tone: "plain" },
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
  if (reachKm !== null && reachKm !== undefined && Number.isFinite(reachKm)) {
    items.push({
      label: `Di luar jangkauan ${reachKm} km`,
      value: angka(metrics.outOfReach),
      tone: metrics.outOfReach > 0 ? "warn" : "plain",
    });
  }
  return items;
}
