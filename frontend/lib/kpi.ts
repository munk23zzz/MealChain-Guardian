/** Gerbang muat KPI (GET /kpi) per tab.

KPI dipakai DUA bagian aplikasi:
- tab **Hari Ini** (kartu KPI hari ini di rekap operasional), dan
- tab **KPI & Kualitas Agen** (halaman gabungan, keputusan pemilik 2026-10-15).

Sebelum 2026-10-15 `useKpi` TIDAK punya gerbang: potret KPI diambil di setiap tab
walau hanya dua tab yang memakainya. Gerbang ini mempertahankan kedua pemakai itu
secara eksplisit — kalau salah satu dilupakan, angkanya hilang tanpa error, jadi
daftarnya sengaja ditulis sebagai konstanta yang diuji.
 */

import { KPI_POLL_MS } from "./query";

export const KPI_TABS: readonly string[] = ["today", "kpi-kualitas"];

/* ---------------------------------------------------------------------------
   Jendela periode KPI (permintaan pemilik 2026-10-16)

   Sebelum ini jendela dipaku 24 jam di dalam hook. Dataset demo berhenti di
   sekitar 8 Okt (snapshot kanonik), sedangkan "hari ini" 16 Okt — jadi tiga
   kartu menjawab "belum ada data" walau datanya ADA di database, hanya di luar
   24 jam. Daftar jendela ditulis di sini (bukan angka ajaib di hook) supaya
   label di layar tidak bisa menyimpang dari kunci yang dikirim ke API. RENTANG
   tidak dihitung di sini: backend menghitungnya dalam hari kalender Asia/Jakarta
   (`GET /kpi?periode=today|7d|1bulan`), sehingga "Hari ini" di layar berarti
   hari kalender yang sama untuk semua kartu.
   TIDAK ada ambang/target yang dikarang: jendela hanya menentukan rentang.
   --------------------------------------------------------------------------- */

export type KpiWindowKey = "today" | "7d" | "1bulan";

export const KPI_WINDOWS: readonly { key: KpiWindowKey; label: string }[] = [
  { key: "today", label: "Hari ini" },
  { key: "7d", label: "7 hari" },
  { key: "1bulan", label: "1 bulan" },
];

/** Kunci bawaan saat halaman dibuka: hari kalender berjalan (WIB). */
export const KPI_DEFAULT_WINDOW: KpiWindowKey = "today";

/** True bila tab ini benar-benar menampilkan angka KPI. */
export function shouldLoadKpi(tab: string | null | undefined): boolean {
  return KPI_TABS.includes((tab ?? "").trim());
}

/**
 * Kebijakan muat KPI: kapan dimuat, seberapa segar, dan seberapa sering dipoll.
 *
 * Kenapa ditulis sebagai fungsi murni: `refetchInterval` di hook dulu `false`
 * ("KPI adalah potret"), sehingga saat demo angka kartu baru terlihat setelah
 * tab ditinggalkan. Sekarang KPI diperlakukan sebagai panel live: selalu
 * dianggap basi saat dibuka (`staleTime: 0`) dan dipoll tiap `KPI_POLL_MS`
 * hanya di tab yang memamerkannya. Kebijakan ini diuji tanpa DOM supaya
 * kembalinya `refetchInterval: false` tidak lolos diam-diam.
 */
export type KpiQueryPolicy = {
  enabled: boolean;
  staleTime: number;
  refetchInterval: number | false;
};

export function kpiQueryPolicy(tab: string | null | undefined): KpiQueryPolicy {
  const aktif = shouldLoadKpi(tab);
  return {
    enabled: aktif,
    staleTime: 0,
    refetchInterval: aktif ? KPI_POLL_MS : false,
  };
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

/** Satu baris arti metrik (English) — dipakai kartu KPI sebagai subjudul.
 *  Sumber istilah: glosarium metrik deck (28 Okt 2026). Metrik yang belum
 *  punya arti tidak diberi subjudul — lebih baik kosong daripada dikarang. */
export const KPI_DESCRIPTIONS: Record<string, string> = {
  "Meal Continuity Rate": "Fulfilled demand vs requirement",
  "Avoidable Food Loss": "kg and monetary value",
  "Regional Imbalance Resolution Rate": "Resolved shortage and surpluses",
  "Safe Delivered Cost": "Total cost until goods are received",
  "Procurement Price Deviation": "Deviation from valid reference prices",
  "Decision Time": "Time to generate recommendation",
  "Evidence Completeness": "Availability of supporting data and logs",
};

export function metricDescription(name: unknown): string | null {
  const key = String(name ?? "").trim();
  return KPI_DESCRIPTIONS[key] ?? null;
}

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

/**
 * Label pil periode di kepala kartu KPI — mengikuti JENDELA yang diminta,
 * bukan nama bulan dari rentangnya (audit 26 Okt 2026).
 *
 * Sebelumnya pil selalu memakai `periodeBulan(start, end)`. Untuk jendela
 * "Hari ini" (26 Okt 00.00 → sekarang WIB) hasilnya "Periode Oktober 2026":
 * angka harian terbaca sebagai angka sebulan. Sekarang:
 *   today  → "Hari ini · 26 Okt 2026"
 *   7d     → "7 hari · 20–26 Okt 2026"
 *   1bulan → "1 bulan · Oktober 2026"
 */
export function periodePil(
  windowKey: KpiWindowKey | string | null | undefined,
  mulaiIso?: string | null,
  selesaiIso?: string | null
): string {
  const label = KPI_WINDOWS.find((w) => w.key === windowKey)?.label ?? "Periode";
  if (windowKey === "1bulan") {
    return `${label} · ${periodeBulan(mulaiIso, selesaiIso)}`;
  }
  const hari = (iso?: string | null): Date | null => {
    if (!iso) return null;
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  };
  const tanggal = (d: Date) =>
    d.toLocaleDateString("id-ID", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "Asia/Jakarta",
    });
  const angkaHari = (d: Date) =>
    d.toLocaleDateString("id-ID", { day: "numeric", timeZone: "Asia/Jakarta" });
  const awal = hari(mulaiIso);
  const akhir = hari(selesaiIso);
  if (!awal) return label;
  if (windowKey === "today" || !akhir) return `${label} · ${tanggal(awal)}`;
  return `${label} · ${angkaHari(awal)}–${tanggal(akhir)}`;
}

/**
 * Cakupan (coverage) dari payload KPI → persen.
 *
 * Payload mengirim RASIO ("1.00", "0.50"), tetapi kartu mencetaknya apa adanya
 * sehingga terbaca "coverage 1" — pembaca menyimpulkan 1%, padahal 100%
 * (audit 26 Okt 2026). Nilai > 1 dianggap sudah persen supaya baris baru yang
 * mengirim "100" tidak berubah arti.
 */
export function fmtCoverage(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const pct = n <= 1 ? n * 100 : n;
  return `${pct.toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
}
