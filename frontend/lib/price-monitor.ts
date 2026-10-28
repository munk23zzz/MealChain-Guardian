// Monitor harga pasar — logika MURNI (tanpa React, tanpa DOM).
//
// Sumber: snapshot PIHPS Bank Indonesia lewat `GET /price/monitor`. Semua angka
// dihitung dari baris yang benar-benar dikirim server. Aturan repo yang dijaga
// di sini: nilai yang tidak ada ditulis `null` → tampil "—", BUKAN 0. Hari
// tanpa publikasi (Sabtu/Minggu) memang tidak ada barisnya, jadi grafik harus
// memperlihatkan JARAK, bukan harga turun ke nol.

export type MonitorBaris = {
  commodity_code: string;
  commodity_label: string;
  region_name: string;
  region_level: "nasional" | "provinsi" | "kota" | string;
  observed_on: string; // YYYY-MM-DD
  price_per_kg: number;
};

export type MonitorKomoditas = {
  code: string;
  label: string;
  /** Nama komoditas MealChain ('telur' dst.) atau null untuk seri non-proyek. */
  project_key: string | null;
};

export type MonitorPayload = {
  status: "ok" | "kosong";
  alasan: string | null;
  source: string | null;
  source_url: string | null;
  market: string | null;
  unit: string | null;
  fetched_at: string | null;
  window: { start: string; end: string } | null;
  days: number;
  commodities: MonitorKomoditas[];
  /** Pergerakan harga terbesar antar wilayah — dihitung SERVER dari seluruh
   *  snapshot (jendela satu wilayah tidak cukup untuk membandingkan). */
  movers: { region_name: string; awal: number; akhir: number; delta_pct: number }[];
  regions: { level: string; name: string }[];
  coverage: {
    tanggal_terisi: number;
    tanggal_pertama: string | null;
    tanggal_terakhir: string | null;
  };
  rows: MonitorBaris[];
};

/**
 * Nama wilayah PIHPS untuk tiap lokasi MealChain.
 *
 * PIHPS memakai nama resmi ("Kota Jakarta Pusat"), sedangkan peta memakai nama
 * pendek ("Jakarta"). `fallback` dipakai bila baris kota tidak diterbitkan
 * (Cianjur memang tidak disampel PIHPS) — panel menyebut cadangan itu apa
 * adanya, tidak menyamarkannya sebagai harga Cianjur.
 */
export const PETA_WILAYAH: Record<
  string,
  { pihps: string | null; fallback: string; level: "kota" | "provinsi" }
> = {
  Jakarta: { pihps: "Kota Jakarta Pusat", fallback: "DKI Jakarta", level: "kota" },
  Bogor: { pihps: "Kota Bogor", fallback: "Jawa Barat", level: "kota" },
  Cianjur: { pihps: null, fallback: "Jawa Barat", level: "provinsi" },
  Bandung: { pihps: "Kota Bandung", fallback: "Jawa Barat", level: "kota" },
  Semarang: { pihps: "Kota Semarang", fallback: "Jawa Tengah", level: "kota" },
  Yogyakarta: { pihps: "Kota Yogyakarta", fallback: "DI Yogyakarta", level: "kota" },
  Surabaya: { pihps: "Kota Surabaya", fallback: "Jawa Timur", level: "kota" },
  Makassar: { pihps: "Kota Makassar", fallback: "Sulawesi Selatan", level: "kota" },
  Palembang: { pihps: "Kota Palembang", fallback: "Sumatera Selatan", level: "kota" },
  Medan: { pihps: "Kota Medan", fallback: "Sumatera Utara", level: "kota" },
};

/** Komoditas MealChain yang punya seri PIHPS, urut seperti chip di panel. */
export const KOMODITAS_PANEL: { kode: string; nama: string }[] = [
  { kode: "com_3", nama: "Beras" },
  { kode: "com_10", nama: "Telur" },
  { kode: "com_7", nama: "Ayam" },
];

export type WilayahAktif = {
  /** Nama wilayah yang dikirim ke server, atau null bila tak ada yang cocok. */
  nama: string | null;
  /** true = memakai cadangan provinsi karena baris kota tidak terbit. */
  cadangan: boolean;
  /** Kalimat jujur untuk ditampilkan di kepala panel. */
  catatan: string | null;
};

/**
 * Calon wilayah PIHPS untuk satu lokasi, URUT prioritas.
 *
 * Dipakai panel: coba kandidat pertama, dan bila server menjawab kosong
 * (baris kota tidak diterbitkan) jatuh ke kandidat berikutnya. Cadangan selalu
 * membawa `catatan` supaya layar menyebut sumber angkanya, bukan diam-diam
 * menampilkan harga provinsi seolah harga kota.
 */
export function kandidatWilayah(lokasi: string | null): WilayahAktif[] {
  if (!lokasi) {
    return [
      {
        nama: "Semua Provinsi",
        cadangan: true,
        catatan: "Cakupan nasional (belum ada lokasi dipilih di bar atas).",
      },
    ];
  }
  const peta = PETA_WILAYAH[lokasi];
  if (!peta) return [];
  const hasil: WilayahAktif[] = [];
  if (peta.pihps) {
    hasil.push({ nama: peta.pihps, cadangan: false, catatan: null });
  }
  hasil.push({
    nama: peta.fallback,
    cadangan: true,
    catatan: `PIHPS tidak menerbitkan baris kota untuk ${lokasi}; yang ditampilkan harga ${peta.fallback}.`,
  });
  return hasil;
}

/**
 * Lokasi peta → nama wilayah PIHPS yang tersedia di payload.
 *
 * Tanpa lokasi aktif (cakupan "Semua lokasi"), panel memakai baris nasional
 * supaya angka yang dibaca tetap satu cerita dengan peta.
 */
export function wilayahUntuk(
  lokasi: string | null,
  tersedia: readonly { level: string; name: string }[],
): WilayahAktif {
  const nama = new Set(tersedia.map((w) => w.name));
  const kandidat = kandidatWilayah(lokasi);
  if (!lokasi) {
    return nama.has("Semua Provinsi")
      ? kandidat[0]
      : {
          nama: null,
          cadangan: true,
          catatan: "Cakupan nasional (belum ada lokasi dipilih di bar atas).",
        };
  }
  const cocok = kandidat.find((k) => k.nama !== null && nama.has(k.nama));
  if (cocok) return cocok;
  if (kandidat.length === 0) {
    return {
      nama: null,
      cadangan: false,
      catatan: `Wilayah "${lokasi}" belum dipetakan ke data PIHPS.`,
    };
  }
  return { nama: null, cadangan: false, catatan: `Tidak ada baris PIHPS untuk ${lokasi}.` };
}

/** Kode yang punya baris pada payload (dipakai untuk mematikan chip kosong). */
export function kodeTersedia(payload: MonitorPayload | null | undefined): Set<string> {
  const set = new Set<string>();
  for (const baris of payload?.rows ?? []) set.add(baris.commodity_code);
  return set;
}

export type TitikSeri = { tanggal: string; label: string } & Record<string, number | string | null>;

/**
 * Susun deret untuk recharts: satu baris per tanggal publikasi, satu kolom per
 * komoditas. Tanggal tanpa nilai dibiarkan `null` → `connectNulls={false}`
 * menggambar jarak, bukan garis turun ke nol.
 */
export function susunSeri(
  rows: readonly MonitorBaris[],
  kodeTerpilih: readonly string[],
): { data: TitikSeri[]; tanggal: string[]; basis: Record<string, number> } {
  const perTanggal = new Map<string, TitikSeri>();
  for (const baris of rows) {
    if (!kodeTerpilih.includes(baris.commodity_code)) continue;
    if (typeof baris.price_per_kg !== "number" || baris.price_per_kg <= 0) continue;
    const tanggal = baris.observed_on;
    if (!perTanggal.has(tanggal)) {
      perTanggal.set(tanggal, { tanggal, label: labelTanggalPendek(tanggal) });
    }
    perTanggal.get(tanggal)![baris.commodity_code] = baris.price_per_kg;
  }
  const tanggal = Array.from(perTanggal.keys()).sort();
  const data = tanggal.map((t) => {
    const titik = perTanggal.get(t)!;
    for (const kode of kodeTerpilih) {
      if (titik[kode] === undefined) titik[kode] = null;
    }
    return titik;
  });
  // Kolom indeks (basis 100 di titik pertama tiap komoditas). Tanpa ini grafik
  // tiga komoditas dengan level berbeda (beras ~Rp17rb, ayam ~Rp39rb) tampak
  // sebagai tiga garis datar: perubahan 3% hilang pada sumbu 15rb–45rb.
  const basis: Record<string, number> = {};
  for (const kode of kodeTerpilih) {
    const pertama = data.find(
      (titik) => typeof titik[kode] === "number" && (titik[kode] as number) > 0
    );
    if (pertama) basis[kode] = pertama[kode] as number;
  }
  for (const titik of data) {
    for (const kode of kodeTerpilih) {
      const nilai = titik[kode];
      const dasar = basis[kode];
      titik[`idx_${kode}`] =
        typeof nilai === "number" && dasar > 0 ? (nilai / dasar) * 100 : null;
    }
  }
  return { data, tanggal, basis };
}

export type RingkasanKomoditas = {
  kode: string;
  terakhir: number | null;
  tanggalTerakhir: string | null;
  deltaHarian: number | null;
  deltaTujuh: number | null;
  /** Tanggal pembanding untuk `deltaTujuh` (7 publikasi sebelumnya). */
  tanggalPembanding: string | null;
  tertinggi: { nilai: number; tanggal: string } | null;
  terendah: { nilai: number; tanggal: string } | null;
  jumlahTitik: number;
};

/** Ringkasan satu komoditas. `deltaTujuh` = selisih terhadap 7 PUBLIKASI sebelumnya. */
export function ringkasKomoditas(
  rows: readonly MonitorBaris[],
  kode: string,
  kodeHasil: readonly string[] = [kode],
): RingkasanKomoditas {
  const seri = rows
    .filter(
      (b) =>
        b.commodity_code === kode &&
        typeof b.price_per_kg === "number" &&
        b.price_per_kg > 0 &&
        kodeHasil.includes(b.commodity_code),
    )
    .sort((a, b) => a.observed_on.localeCompare(b.observed_on));

  const kosong: RingkasanKomoditas = {
    kode,
    terakhir: null,
    tanggalTerakhir: null,
    deltaHarian: null,
    deltaTujuh: null,
    tanggalPembanding: null,
    tertinggi: null,
    terendah: null,
    jumlahTitik: 0,
  };
  if (seri.length === 0) return kosong;

  const akhir = seri[seri.length - 1];
  const sebelum = seri.length >= 2 ? seri[seri.length - 2] : null;
  const tujuh = seri.length >= 8 ? seri[seri.length - 8] : seri[0];
  let tinggi = seri[0];
  let rendah = seri[0];
  for (const titik of seri) {
    if (titik.price_per_kg > tinggi.price_per_kg) tinggi = titik;
    if (titik.price_per_kg < rendah.price_per_kg) rendah = titik;
  }

  return {
    kode,
    terakhir: akhir.price_per_kg,
    tanggalTerakhir: akhir.observed_on,
    deltaHarian: sebelum ? persenPerubahan(sebelum.price_per_kg, akhir.price_per_kg) : null,
    deltaTujuh:
      seri.length >= 2 ? persenPerubahan(tujuh.price_per_kg, akhir.price_per_kg) : null,
    tanggalPembanding: seri.length >= 2 ? tujuh.observed_on : null,
    tertinggi: { nilai: tinggi.price_per_kg, tanggal: tinggi.observed_on },
    terendah: { nilai: rendah.price_per_kg, tanggal: rendah.observed_on },
    jumlahTitik: seri.length,
  };
}

/** Persen perubahan `akhir` terhadap `awal`; null bila `awal` tidak masuk akal. */
export function persenPerubahan(awal: number, akhir: number): number | null {
  if (!Number.isFinite(awal) || !Number.isFinite(akhir) || awal <= 0) return null;
  return ((akhir - awal) / awal) * 100;
}

/** "+2,4%" / "−3,1%" / "—". Tanda selalu ada supaya arah tidak bergantung warna. */
export function formatPersen(nilai: number | null | undefined, desimal = 1): string {
  if (nilai === null || nilai === undefined || !Number.isFinite(nilai)) return "—";
  const tanda = nilai > 0 ? "+" : nilai < 0 ? "−" : "";
  return `${tanda}${Math.abs(nilai).toLocaleString("id-ID", {
    minimumFractionDigits: desimal,
    maximumFractionDigits: desimal,
  })}%`;
}

/** "Rp25.700" — tanpa desimal, pemisah ribuan Indonesia. */
export function formatRp(nilai: number | null | undefined): string {
  if (nilai === null || nilai === undefined || !Number.isFinite(nilai)) return "—";
  return `Rp${Math.round(nilai).toLocaleString("id-ID")}`;
}

const NAMA_BULAN = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "Mei",
  "Jun",
  "Jul",
  "Agu",
  "Sep",
  "Okt",
  "Nov",
  "Des",
];

/** "2026-10-28" → "28 Okt" (label sumbu X). */
export function labelTanggalPendek(iso: string | null | undefined): string {
  const bagian = (iso ?? "").split("-");
  if (bagian.length !== 3) return "—";
  const bulan = Number(bagian[1]);
  const hari = Number(bagian[2]);
  if (!Number.isInteger(bulan) || bulan < 1 || bulan > 12 || !Number.isInteger(hari)) return "—";
  return `${hari} ${NAMA_BULAN[bulan - 1]}`;
}

/** "2026-10-28" → "28 Okt 2026". */
export function labelTanggalPanjang(iso: string | null | undefined): string {
  const bagian = (iso ?? "").split("-");
  if (bagian.length !== 3) return "—";
  const bulan = Number(bagian[1]);
  if (!Number.isInteger(bulan) || bulan < 1 || bulan > 12) return "—";
  return `${Number(bagian[2])} ${NAMA_BULAN[bulan - 1]} ${bagian[0]}`;
}

/**
 * Waktu tarik dalam WIB: "28 Okt 2026 · 16.54 WIB".
 *
 * Waktu disimpan UTC; panel menampilkannya di zona Indonesia Barat karena itu
 * zona pembaca dan zona penerbitan PIHPS.
 */
/**
 * Jam tarik saja ("16.54 WIB").
 *
 * Dipakai baris sumber panel, yang sudah menyebut TANGGAL data terakhir di
 * sebelahnya. `labelWaktuTarik` menulis tanggal+jam; memakainya di situ membuat
 * tanggal yang sama tercetak dua kali dalam satu kalimat.
 */
export function labelJamTarik(iso: string | null | undefined): string {
  if (!iso) return "—";
  const waktu = new Date(iso);
  if (Number.isNaN(waktu.getTime())) return "—";
  return `${new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Jakarta",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(waktu)
    .replace(":", ".")} WIB`;
}

export function labelWaktuTarik(iso: string | null | undefined): string {
  if (!iso) return "—";
  const waktu = new Date(iso);
  if (Number.isNaN(waktu.getTime())) return "—";
  const bagian = new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Jakarta",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(waktu);
  const jam = new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Jakarta",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .format(waktu)
    .replace(":", ".");
  return `${bagian} · ${jam} WIB`;
}

/** Kalimat ringkas untuk pembaca layar (pengganti grafik). */
export function ringkasanTeks(ringkasan: readonly RingkasanKomoditas[], nama: (kode: string) => string): string {
  const bagian = ringkasan
    .filter((r) => r.terakhir !== null)
    .map((r) => {
      const arah =
        r.deltaTujuh === null
          ? "belum ada pembanding"
          : r.deltaTujuh > 0
            ? `naik ${formatPersen(r.deltaTujuh)}`
            : r.deltaTujuh < 0
              ? `turun ${formatPersen(r.deltaTujuh)}`
              : "tetap";
      return `${nama(r.kode)} ${formatRp(r.terakhir)} per kg, ${arah} dalam tujuh publikasi terakhir`;
    });
  if (bagian.length === 0) return "Belum ada angka harga untuk ditampilkan.";
  return `Grafik harga pasar. ${bagian.join("; ")}.`;
}
