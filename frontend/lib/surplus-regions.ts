// Panel "Surplus wilayah lain" (28 Okt 2026) — modul MURNI.
//
// Kenapa modul sendiri: grafik kecukupan menjawab "lokasi saya cukup atau tidak".
// Pertanyaan berikutnya, "surplusnya ada di mana?", TIDAK bisa dihitung klien
// dari `GET /balance/map` — peta akun SPPG dibatasi cakupan (Ruling 2026-10-14)
// sehingga hanya berisi satu lokasi. Agregat wilayah datang dari server
// (`GET /surplus/regions`); berkas ini hanya mem-parse dan memformatnya, tanpa
// menambah, menaksir, atau membulatkan ulang angka server.
//
// Aturan kejujuran yang dipaku di sini (dan di tests/surplus-regions.test.ts):
// - angka yang tidak ada = null → dirender "—", bukan 0 kg;
// - baris tanpa nama wilayah atau dengan kg tidak valid dibuang (tidak ada NaN
//   di lebar batang);
// - urutan wilayah menurun, mengikuti besaran surplus.
import { formatKg } from "./overview-format";

/**
 * Angka kg tanpa satuan, untuk chip yang satuannya sudah disebut sekali di
 * labelnya ("Dari komoditas (kg)"). Mengulang "kg" di setiap chip memakan
 * ~17 px per chip, dan empat chip jadi tidak muat satu baris di kartu 434 px —
 * akibatnya satu pil terbuang sendirian ke baris kedua.
 */
export function formatKgTanpaSatuan(value: number | string | null | undefined): string {
  return formatKg(value).replace(/\s*kg$/, "");
}

export type SurplusKomoditas = { commodity: string; surplusKg: number };

export type SurplusSumber = {
  location: string;
  surplusKg: number;
  byCommodity: SurplusKomoditas[];
};

export type SurplusWilayah = {
  region: string;
  surplusKg: number;
  /** Bagian surplus dari lokasi ≥ ambang (layak dialihkan). */
  layakKg: number | null;
  locations: number;
  byCommodity: SurplusKomoditas[];
  sources: SurplusSumber[];
};

export type RegionSurplusView = {
  tersedia: boolean;
  regions: SurplusWilayah[];
  totalKg: number | null;
  layakKg: number | null;
  sourceLocations: number | null;
  /** Lokasi pengguna yang dilewati server (null = server tidak memfilter). */
  excludedLocation: string | null;
  /**
   * Wilayah yang punya setidaknya satu sumber ≥ ambang — inilah yang layak
   * direncanakan pengirimannya. `kecil` = sisanya (surplusnya nyata tetapi tiap
   * lokasi di bawah ambang), dikumpulkan satu baris supaya panel tidak penuh
   * baris 0,5 kg yang batangnya tak terlihat.
   */
  layak: SurplusWilayah[];
  kecil: SurplusWilayah[];
  kecilKg: number | null;
  /** Surplus lokasi pengguna sendiri — TIDAK dihitung di `totalKg`. */
  excludedKg: number | null;
  /** Lokasi bersurplus yang permintaannya belum tercatat (tidak dihitung). */
  unmeasured: number;
  komoditas: string[];
  minKg: number | null;
  reason: string | null;
  kosong: boolean;
};

const DASH = "—";
const TONE_COUNT = 4;

function angka(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function daftarKomoditas(value: unknown): SurplusKomoditas[] {
  if (!Array.isArray(value)) return [];
  const out: SurplusKomoditas[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as { commodity?: unknown; surplus_kg?: unknown };
    const nama = String(row.commodity ?? "").trim();
    const kg = angka(row.surplus_kg);
    if (!nama || kg === null || kg <= 0) continue;
    out.push({ commodity: nama, surplusKg: kg });
  }
  return out.sort((a, b) => b.surplusKg - a.surplusKg);
}

function daftarSumber(value: unknown): SurplusSumber[] {
  if (!Array.isArray(value)) return [];
  const out: SurplusSumber[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as { location?: unknown; surplus_kg?: unknown; by_commodity?: unknown };
    const nama = String(row.location ?? "").trim();
    const kg = angka(row.surplus_kg);
    if (!nama || kg === null) continue;
    out.push({
      location: nama,
      surplusKg: kg,
      byCommodity: daftarKomoditas(row.by_commodity),
    });
  }
  return out.sort((a, b) => b.surplusKg - a.surplusKg);
}

/**
 * Parse `GET /surplus/regions`. Tidak pernah melempar: payload rusak menjadi
 * tampilan kosong dengan alasan, bukan layar putih.
 */
export function regionSurplus(payload: unknown): RegionSurplusView {
  const data = (payload ?? {}) as Record<string, unknown>;
  const totals = (data.totals ?? {}) as Record<string, unknown>;
  const tersedia = Boolean(data.available);

  const mentah = Array.isArray(data.regions) ? data.regions : [];
  const regions: SurplusWilayah[] = [];
  for (const item of mentah) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const nama = String(row.region ?? "").trim();
    const kg = angka(row.surplus_kg);
    if (!nama || kg === null || kg <= 0) continue;
    const sources = daftarSumber(row.sources);
    regions.push({
      region: nama,
      surplusKg: kg,
      layakKg: angka(row.layak_kg),
      // Jumlah lokasi: pakai angka server bila ada; kalau tidak, hitung dari
      // sumber yang benar-benar dilaporkan. Tidak pernah "0 lokasi" untuk
      // wilayah yang punya kg.
      locations: angka(row.locations) ?? sources.length,
      byCommodity: daftarKomoditas(row.by_commodity),
      sources,
    });
  }
  regions.sort((a, b) => b.surplusKg - a.surplusKg);

  const total = angka(totals.surplus_kg);
  const layak = angka(totals.layak_kg);
  const sumber = angka(totals.source_locations);
  // Wilayah "layak" = punya minimal satu sumber ≥ ambang. Tanpa server ambang
  // (minKg null), semua wilayah dianggap layak: memilah tanpa kriteria berarti
  // menyembunyikan baris tanpa alasan.
  const ambang = angka(data.min_surplus_kg);
  const layakWilayah =
    ambang === null ? regions : regions.filter((r) => (r.layakKg ?? 0) > 0);
  const kecilWilayah = ambang === null ? [] : regions.filter((r) => (r.layakKg ?? 0) <= 0);

  return {
    tersedia,
    regions,
    layak: layakWilayah,
    kecil: kecilWilayah,
    kecilKg: kecilWilayah.length
      ? kecilWilayah.reduce((jumlah, r) => jumlah + r.surplusKg, 0)
      : null,
    // Tanpa baris tersedia, angka 0 dari server berarti "belum ada catatan",
    // bukan "nol surplus" — jadi dirender "—".
    totalKg: tersedia ? (total ?? sumRegions(regions)) : null,
    layakKg: tersedia ? (layak ?? null) : null,
    sourceLocations: tersedia ? (sumber ?? null) : null,
    excludedLocation: data.excluded_location ? String(data.excluded_location) : null,
    excludedKg: angka(totals.excluded_surplus_kg),
    unmeasured: angka(totals.surplus_unmeasured_locations) ?? 0,
    komoditas: Array.isArray(data.commodities)
      ? data.commodities.map((k) => String(k)).filter(Boolean)
      : [],
    minKg: angka(data.min_surplus_kg),
    reason: typeof data.reason === "string" ? data.reason : null,
    kosong: regions.length === 0,
  };
}

function sumRegions(regions: readonly SurplusWilayah[]): number | null {
  if (!regions.length) return null;
  return regions.reduce((total, r) => total + r.surplusKg, 0);
}

/** Lebar batang relatif terhadap wilayah terbesar (0–100, aman dari NaN). */
export function regionSharePct(kg: number, terbesar: number): number {
  const nilai = angka(kg) ?? 0;
  const skala = angka(terbesar) ?? 0;
  if (skala <= 0 || nilai <= 0) return 0;
  // Dibulatkan 2 desimal: lebar batang di DOM tidak perlu 14 digit pecahan.
  return Math.round(Math.min(100, (nilai / skala) * 100) * 100) / 100;
}

/**
 * Satu kolom BAR VERTIKAL untuk panel surplus (30 Okt 2026).
 *
 * Kenapa bentuknya kolom, bukan baris: kartu ini duduk bersebelahan dengan
 * "Kecukupan pasokan" yang juga berupa kolom. Dua kartu satu baris wajib
 * memakai SATU bahasa grafik, kalau tidak pembaca harus menafsirkan dua
 * geometri berbeda untuk pertanyaan yang sama ("berapa, dibanding apa").
 *
 * Kenapa SEMUA wilayah digambar (termasuk yang di bawah ambang): batang baris
 * lama menyembunyikan wilayah kecil ke satu kalimat karena batang 0,5 kg tidak
 * terlihat. Di kolom, wilayah kecil tetap kecil — dan justru itu informasinya.
 * Ambang kirim tetap terbaca lewat nada pucat + catatan "di bawah ambang",
 * jadi tidak ada wilayah yang hilang diam-diam.
 */
export type SurplusColumn = {
  key: string;
  label: string;
  /** kg surplus wilayah — angka server, tanpa pembulatan ulang. */
  surplusKg: number;
  /** Tinggi batang 0–100 terhadap wilayah terbesar (skalanya satu untuk kartu). */
  fillPct: number;
  /** Nilai yang dicetak di atas batang. */
  value: string;
  /** Nilai yang sama tanpa satuan "kg" — untuk angka di tengah cincin. */
  valueTanpaSatuan: string;
  /** Baris kecil di bawah nama wilayah. */
  note: string;
  /** Seluruh surplus wilayah ini di bawah ambang kirim. */
  belowThreshold: boolean;
  /** Lencana "terbesar" — hanya berguna bila ada pembanding. */
  badge: string | null;
  /** Kalimat lengkap untuk pembaca layar & tooltip. */
  aria: string;
};

/**
 * Irisan donat "komposisi komoditas" untuk panel surplus (31 Okt 2026).
 *
 * Kenapa per KOMODITAS, bukan per wilayah: pemilik meminta satu diagram dengan
 * warna berbeda per komoditas. Warna komoditas sudah punya arti tetap di seluruh
 * aplikasi (titik pil di peta, legenda, chip), jadi memakainya di donat membuat
 * satu warna = satu komoditas di mana pun pembaca melihatnya.
 *
 * Angka tetap milik server: kg dijumlahkan dari `by_commodity` per wilayah,
 * tanpa pembulatan ulang. Bila komoditas lebih banyak dari `batas`, sisanya
 * digabung menjadi satu irisan "Lainnya" supaya donat tidak jadi cakram tipis.
 */
export type SurplusSlice = {
  key: string;
  label: string;
  kg: number;
  /** Warna identitas komoditas (kelas .sr-komod-*). */
  toneClass: string;
  /** Pangsa terhadap total kartu, 0–100, 2 desimal. */
  sharePct: number;
  /** true untuk irisan gabungan "Lainnya". */
  gabungan: boolean;
};

export function surplusCommoditySlices(
  view: RegionSurplusView,
  batas = 5
): SurplusSlice[] {
  const jumlah = new Map<string, number>();
  for (const wilayah of view.regions) {
    for (const komoditas of wilayah.byCommodity) {
      const nama = String(komoditas.commodity ?? "").trim();
      const kg = angka(komoditas.surplusKg);
      if (!nama || kg === null || kg <= 0) continue;
      jumlah.set(nama, (jumlah.get(nama) ?? 0) + kg);
    }
  }

  const total = [...jumlah.values()].reduce((a, b) => a + b, 0);
  if (total <= 0) return [];

  const urut = [...jumlah.entries()].sort((a, b) => b[1] - a[1]);
  const utama = urut.slice(0, Math.max(1, batas));
  const sisa = urut.slice(Math.max(1, batas));

  const irisan: SurplusSlice[] = utama.map(([nama, kg], index) => ({
    key: nama,
    label: nama,
    kg,
    toneClass: komoditasToneClass(nama, index),
    sharePct: Math.round((kg / total) * 10_000) / 100,
    gabungan: false,
  }));

  if (sisa.length) {
    const kg = sisa.reduce((a, b) => a + b[1], 0);
    irisan.push({
      key: "__lainnya",
      label: `Lainnya (${sisa.length})`,
      kg,
      toneClass: "sr-komod-netral",
      sharePct: Math.round((kg / total) * 10_000) / 100,
      gabungan: true,
    });
  }

  return irisan;
}

export function surplusColumns(view: RegionSurplusView): SurplusColumn[] {
  const terbesar = view.regions[0]?.surplusKg ?? 0;
  return view.regions.map((wilayah, index) => {
    const belowThreshold = view.minKg !== null && (wilayah.layakKg ?? 0) <= 0;
    const komoditas = wilayah.byCommodity
      .map((c) => `${c.commodity} ${formatKg(c.surplusKg)}`)
      .join(", ");
    const layak =
      wilayah.layakKg !== null && wilayah.layakKg > 0 && wilayah.layakKg !== wilayah.surplusKg
        ? `${formatKg(wilayah.layakKg)} layak dialihkan`
        : null;
    return {
      key: wilayah.region,
      label: wilayah.region,
      surplusKg: wilayah.surplusKg,
      fillPct: regionSharePct(wilayah.surplusKg, terbesar),
      value: formatKg(wilayah.surplusKg),
      // Nilai yang sama tanpa " kg" — dipakai di tengah cincin, dengan satuan
      // dicetak sekali di bawahnya. Angka tetap milik server (tanpa pembulatan).
      valueTanpaSatuan: formatKg(wilayah.surplusKg).replace(/\s*kg$/, ""),
      note: belowThreshold
        ? `${wilayah.locations} lokasi · di bawah ambang`
        : `${wilayah.locations} lokasi`,
      belowThreshold,
      badge: index === 0 && view.regions.length > 1 ? "terbesar" : null,
      aria: [
        `${wilayah.region}: surplus ${formatKg(wilayah.surplusKg)}${layak ? `, ${layak}` : ""}`,
        `${wilayah.locations} lokasi sumber (${sumberRingkas(wilayah, 3)})`,
        belowThreshold && view.minKg !== null
          ? `seluruh surplusnya di bawah ambang ${formatKg(view.minKg)}`
          : null,
        komoditas ? `rincian komoditas ${komoditas}` : "rincian komoditas belum tersedia",
      ]
        .filter(Boolean)
        .join(". "),
    };
  });
}

/** Indeks warna komoditas — stabil per daftar, berputar untuk nama asing. */
export function komoditasTone(daftar: readonly string[], nama: string): number {
  const index = daftar.indexOf(nama);
  if (index >= 0) return index % TONE_COUNT;
  if (!daftar.length) return 0;
  let hash = 0;
  for (let i = 0; i < nama.length; i += 1) {
    hash = (hash * 31 + nama.charCodeAt(i)) % 100_000;
  }
  return hash % TONE_COUNT;
}

/**
 * Keluarga warna IDENTITAS per komoditas kanonik (docs/design.md: telur amber,
 * ayam rose, beras biru, wortel violet — sama dengan titik pada pil komoditas
 * di peta). Dipakai supaya satu komoditas berwarna SAMA di peta, legenda, dan
 * panel surplus; `komoditasTone` hanya cadangan untuk nama di luar empat itu.
 * Mengembalikan null bila nama tidak dikenal (pemanggil memakai indeks).
 */
const KELUARGA_KOMODITAS: Record<string, string> = {
  telur: "amber",
  ayam: "rose",
  beras: "blue",
  wortel: "violet",
};

export function komoditasKeluarga(nama: string): string | null {
  const kunci = String(nama).trim().toLowerCase();
  return KELUARGA_KOMODITAS[kunci] ?? null;
}

/**
 * Kelas warna IDENTITAS untuk satu komoditas (memakai `--sr-komod`).
 * Empat komoditas kanonik dapat warnanya sendiri (docs/design.md: telur amber,
 * ayam rose, beras biru, wortel violet); nama asing memakai indeks urutan daftar
 * supaya tetap berbeda warna tanpa mengarang arti baru.
 */
export function komoditasToneClass(nama: string, index = 0): string {
  const keluarga = komoditasKeluarga(nama);
  return `sr-komod-${keluarga ?? index % 4}`;
}

/** "Cianjur, Bogor +1" — sumber teratas, sisanya disebut sebagai jumlah. */
export function sumberRingkas(wilayah: SurplusWilayah, batas = 2): string {
  const nama = wilayah.sources.map((s) => s.location).filter(Boolean);
  if (!nama.length) return "tanpa nama sumber";
  const tampil = nama.slice(0, batas).join(", ");
  const sisa = nama.length - batas;
  return sisa > 0 ? `${tampil} +${sisa}` : tampil;
}

/** Sebab panel kosong, dalam bahasa aplikasi (bukan kode server). */
export function regionSurplusReason(reason?: string | null): string {
  switch (reason) {
    case "surplus_hanya_di_lokasi_ini":
      return "Seluruh surplus komoditas ini ada di lokasi Anda sendiri — tidak ada daerah lain yang bisa memasok.";
    case "surplus_tanpa_permintaan_tercatat":
      return "Ada pasokan berlebih, tetapi permintaannya belum tercatat — itu bukan surplus, jadi tidak dihitung.";
    case "tidak_ada_surplus_terukur":
      return "Belum ada lokasi mana pun yang surplusnya bisa diukur untuk komoditas ini.";
    default:
      return "Belum ada surplus terukur di daerah lain untuk komoditas ini.";
  }
}

export { DASH as SURPLUS_DASH };
