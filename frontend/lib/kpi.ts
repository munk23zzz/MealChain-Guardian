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
  { key: "30d", label: "30 hari", hours: 24 * 30 },
];

/** Rentang ISO untuk satu jendela. Kunci tak dikenal → 24 jam (perilaku lama). */
export function kpiWindowRange(
  key: KpiWindowKey | string | null | undefined,
  now: Date = new Date()
): { start: string; end: string } {
  const found = KPI_WINDOWS.find((w) => w.key === key) ?? KPI_WINDOWS[0];
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
