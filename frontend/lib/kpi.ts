/** Gerbang muat KPI (GET /kpi) per tab.

KPI dipakai DUA bagian aplikasi:
- tab **Hari Ini** (kartu KPI 24 jam di rekap operasional), dan
- tab **KPI & Kualitas Agen** (halaman gabungan, keputusan pemilik 2026-10-15).

Sebelum 2026-10-15 `useKpi` TIDAK punya gerbang: potret KPI diambil di setiap tab
walau hanya dua tab yang memakainya. Gerbang ini mempertahankan kedua pemakai itu
secara eksplisit — kalau salah satu dilupakan, angkanya hilang tanpa error, jadi
daftarnya sengaja ditulis sebagai konstanta yang diuji.
 */

export const KPI_TABS: readonly string[] = ["today", "kpi-kualitas"];

/* ---------------------------------------------------------------------------
   Jendela periode KPI (permintaan pemilik 2026-10-16)

   Sebelum ini jendela dipaku 24 jam di dalam hook. Dataset demo berhenti di
   sekitar 8 Okt (snapshot kanonik), sedangkan "hari ini" 16 Okt — jadi tiga
   kartu menjawab "belum ada data" walau datanya ADA di database, hanya di luar
   24 jam. Daftar jendela ditulis di sini (bukan angka ajaib di hook) supaya
   label di layar, jamnya, dan rentang yang dikirim ke API tidak bisa menyimpang.
   TIDAK ada ambang/target yang dikarang: jendela hanya menentukan rentang.
   --------------------------------------------------------------------------- */

export type KpiWindowKey = "24h" | "7d" | "30d";

export const KPI_WINDOWS: readonly { key: KpiWindowKey; label: string; hours: number }[] = [
  { key: "24h", label: "24 jam", hours: 24 },
  { key: "7d", label: "7 hari", hours: 24 * 7 },
  { key: "30d", label: "1 bulan", hours: 24 * 30 },
];

/** Rentang ISO untuk satu jendela. Kunci tak dikenal → 24 jam (perilaku lama). */
export function kpiWindowRange(
  key: KpiWindowKey | string | null | undefined,
  now: Date = new Date()
): { start: string; end: string } {
  const found = KPI_WINDOWS.find((w) => w.key === key) ?? KPI_WINDOWS[0];
  if (found.key === "30d") {
    // "1 bulan" = bulan berjalan menurut WIB, bukan 30 hari bergulir.
    // Alasannya tampilan: label periode menulis bulan ("Oktober 2026"), jadi
    // jendelanya harus satu bulan — bukan 20 Sep–20 Okt yang terbaca dua bulan.
    const WIB = 7 * 60 * 60 * 1000;
    const wib = new Date(now.getTime() + WIB);
    const awal = Date.UTC(wib.getUTCFullYear(), wib.getUTCMonth(), 1) - WIB;
    return { start: new Date(awal).toISOString(), end: now.toISOString() };
  }
  return {
    start: new Date(now.getTime() - found.hours * 60 * 60 * 1000).toISOString(),
    end: now.toISOString(),
  };
}

/** True bila tab ini benar-benar menampilkan angka KPI. */
export function shouldLoadKpi(tab: string | null | undefined): boolean {
  return KPI_TABS.includes((tab ?? "").trim());
}

/* ---------------------------------------------------------------------------
   Bullet bar KPI (Fase 4 redesign, 2026-10-16)

   Rencana redesign meminta "bullet chart: rentang kualitatif bad/ok/good +
   penanda target". Yang TIDAK boleh dilakukan: mengarang ambangnya. Envelope
   GET /kpi (backend kpi_service.py) tidak membawa target/threshold sama sekali —
   jadi ambang "baik/buruk" di UI hanya bisa datang dari angka karangan, dan itu
   bertentangan dengan aturan repo ini (null ditulis "—", bukan diganti angka).

   Yang dikerjakan, dan semuanya berasal dari data:
   - skala metrik itu sendiri (persen → 0–100) untuk menggambar bar,
   - arah perbaikan yang sudah tertulis di definisi metrik (Meal Continuity =
     porsi tersaji/rencana → tinggi lebih baik; Avoidable Food Loss, Price
     Deviation, Decision Time → rendah lebih baik; Evidence & Imbalance → tinggi),
   - nilai aslinya tetap dicetak apa adanya; bar hanya dibatasi lebarnya bila
     nilai melewati skala (overMax), angka di kartu tidak dipotong.
   --------------------------------------------------------------------------- */

export type KpiDirection = "higher" | "lower" | "none";

/** Arah perbaikan per metrik — satu sumber untuk kartu KPI. */
export const KPI_DIRECTION: Record<string, KpiDirection> = {
  "Meal Continuity Rate": "higher",
  "Avoidable Food Loss": "lower",
  "Regional Imbalance Resolution Rate": "higher",
  "Safe Delivered Cost": "lower",
  "Procurement Price Deviation": "lower",
  "Decision Time": "lower",
  "Evidence Completeness": "higher",
};

const DIRECTION_LABEL: Record<"higher" | "lower", string> = {
  higher: "makin tinggi makin baik",
  lower: "makin rendah makin baik",
};

/**
 * Nama metrik untuk LAYAR. Kunci tetap nama kanonik dari server; yang
 * diterjemahkan hanya tampilannya. Nama tak dikenal dikembalikan apa adanya —
 * jangan mengarang label untuk metrik yang belum pernah dilihat.
 */
export const KPI_LABELS: Record<string, string> = {
  "Meal Continuity Rate": "Keberlanjutan menu",
  "Avoidable Food Loss": "Susut pangan",
  "Regional Imbalance Resolution Rate": "Penyelesaian ketimpangan",
  "Safe Delivered Cost": "Biaya kirim aman",
  "Procurement Price Deviation": "Simpangan harga",
  "Decision Time": "Waktu keputusan",
  "Evidence Completeness": "Kelengkapan bukti",
};

export function metricLabel(name: unknown): string {
  const key = String(name ?? "").trim();
  if (!key) return "—";
  return KPI_LABELS[key] ?? key;
}

export function directionLabel(direction: KpiDirection): string | null {
  return direction === "none" ? null : DIRECTION_LABEL[direction];
}

/** Satuan yang punya batas atas alami. Satuan lain (IDR, menit, kg) tidak
 *  punya skala tetap → kartunya TIDAK digambar bar, karena bar tanpa skala
 *  hanyalah hiasan yang menyesatkan. */
const SCALE_MAX: Record<string, number> = {
  percent: 100,
  percentage: 100,
  pct: 100,
};

export type KpiBullet = {
  /** Nilai numerik yang sah, apa adanya (tidak dibatasi skala). */
  value: number | null;
  /** Batas atas skala metrik; null bila metriknya tidak berskala. */
  max: number | null;
  /** Lebar bar 0–100; null = tidak ada bar. */
  pct: number | null;
  hasScale: boolean;
  /** Nilai melewati skala (mis. > 100%) — bar penuh, angkanya tetap asli. */
  overMax: boolean;
  direction: KpiDirection;
};

export function bulletOf(metric: any): KpiBullet | null {
  if (!metric || typeof metric !== "object") return null;
  const direction = KPI_DIRECTION[String(metric.name ?? "")] ?? "none";
  const max = SCALE_MAX[String(metric.unit ?? "").trim().toLowerCase()] ?? null;
  const raw = metric.value;
  // "" → Number("") = 0, angka palsu: kosong harus ditolak lebih dulu.
  const num =
    raw === null || raw === undefined || raw === "" ? Number.NaN : Number(raw);
  const valid = Number.isFinite(num) && num >= 0 && metric.state === "available";
  if (max === null) {
    return {
      value: valid ? num : null,
      max: null,
      pct: null,
      hasScale: false,
      overMax: false,
      direction,
    };
  }
  if (!valid) {
    return { value: null, max, pct: null, hasScale: true, overMax: false, direction };
  }
  return {
    value: num,
    max,
    pct: Math.min(100, (num / max) * 100),
    hasScale: true,
    overMax: num > max,
    direction,
  };
}

/**
 * Label periode sebagai BULAN saja: "September – Oktober 2026".
 *
 * Pemilik meminta tanggal persis ("20 Sep 2026 – 20 Okt 2026") diganti nama
 * bulan: pada kartu KPI rentang tanggal penuh terbaca sebagai detail teknis,
 * sementara pertanyaannya "periode mana", bukan "tanggal berapa".
 *
 * Tahun ditulis sekali bila sama ("September – Oktober 2026") dan dua kali bila
 * berbeda ("Desember 2026 – Januari 2027"). Waktu diformat di zona Asia/Jakarta:
 * batas periode datang sebagai ISO UTC, dan 31 Okt 20.00 UTC adalah 1 Nov WIB —
 * memakai UTC akan memberi nama bulan yang berbeda dari yang dibaca operator.
 */
export function periodeBulan(
  mulaiIso?: string | null,
  selesaiIso?: string | null
): string {
  const bagian = (
    iso?: string | null
  ): { bulan: string; tahun: string } | null => {
    if (!iso) return null;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    const f = new Intl.DateTimeFormat("id-ID", {
      month: "long",
      year: "numeric",
      timeZone: "Asia/Jakarta",
    });
    const potongan = f.formatToParts(d);
    const ambil = (jenis: string) =>
      potongan.find((p) => p.type === jenis)?.value ?? "";
    return { bulan: ambil("month"), tahun: ambil("year") };
  };

  const awal = bagian(mulaiIso);
  const akhir = bagian(selesaiIso) ?? awal;
  if (!awal || !akhir) return "—";
  if (awal.bulan === akhir.bulan && awal.tahun === akhir.tahun) {
    return `${akhir.bulan} ${akhir.tahun}`;
  }
  if (awal.tahun === akhir.tahun) {
    return `${awal.bulan} – ${akhir.bulan} ${akhir.tahun}`;
  }
  return `${awal.bulan} ${awal.tahun} – ${akhir.bulan} ${akhir.tahun}`;
}
