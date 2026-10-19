/**
 * Baris legenda ringkas di bawah kanvas peta (celah C2, langkah 7b-2; riset:
 * `docs/research/peta-ui-industri.md` §5).
 *
 * Latar: legenda peta sebelumnya HANYA ada di balik tombol "Info map" — supaya
 * kotaknya tidak menutupi kanvas (keputusan pemilik 2026-10-16: panel yang
 * mengapung pernah menutup 39% kanvas, tepat di atas Jawa Barat). Akibatnya
 * makna titik/garis baru terbaca SESUDAH satu klik. Literatur legenda menuntut
 * sebaliknya: "The legend should always be visible" (Esri, Tips for legend
 * design) — dan solusi yang tidak melanggar aturan pemilik adalah menaruhnya
 * DI BAWAH kanvas, tempat ia tidak bisa menutupi apa pun.
 *
 * Isi baris ini adalah ATURAN, bukan tata letak:
 * 1. status lokasi SELALU tampil (pin SPPG tidak punya sakelar — kalau warna
 *    pinnya ada di peta, artinya wajib ada di legenda);
 * 2. keterangan sebuah lapisan hanya muncul kalau lapisan itu memang hidup —
 *    warna tanpa lapisan adalah informasi palsu;
 * 3. urutan tetap: status lokasi → jalur kiriman → pemasok.
 *
 * Kelas tandanya sengaja SAMA dengan kotak Info map (`legendMarkClass`), supaya
 * tidak lahir gaya ganda untuk arti yang sama.
 */

/** Tiga status lokasi (sama dengan badge daftar lokasi & warna pin). */
export const STATUS_LEGEND: readonly { tone: string; label: string }[] = [
  { tone: "surplus", label: "Surplus" },
  { tone: "balanced", label: "Seimbang" },
  { tone: "shortage", label: "Shortage" },
] as const;

export type LegendJenis = "titik" | "garis" | "bentuk";

export type LegendItem = {
  /** Id stabil, menyebut asalnya (`status:surplus`) — dipakai React key. */
  id: string;
  jenis: LegendJenis;
  nada: string;
  label: string;
  /** Hanya untuk garis: `padat` = sudah ditempuh, `putus` = sisa/perkiraan (K1). */
  gaya?: "padat" | "putus";
};

export type CompactLegendInput = {
  /** Nada jalur kiriman, atau `null`/`[]` kalau lapisannya mati/tidak ada. */
  jalur: readonly { tone: string; label: string; gaya?: "padat" | "putus" }[] | null;
  /** Nada pin pemasok, atau `null`/`[]` kalau lapisannya mati/tidak ada. */
  pemasok: readonly { tone: string; label: string }[] | null;
};

/** Label kosong/berisi spasi dibuang: pil legenda tanpa teks tidak berguna. */
function rapi(label: string): string | null {
  const bersih = label.trim();
  return bersih.length > 0 ? bersih : null;
}

function butir(
  asal: string,
  jenis: LegendJenis,
  entri: readonly { tone: string; label: string; gaya?: "padat" | "putus" }[]
): LegendItem[] {
  const hasil: LegendItem[] = [];
  for (const { tone, label, gaya } of entri) {
    const teks = rapi(label);
    if (teks === null) continue;
    // Gaya ikut masuk id: dua butir bernada sama (padat/putus) tidak boleh
    // bertabrakan sebagai React key.
    const id = gaya ? `${asal}:${tone}:${gaya}` : `${asal}:${tone}`;
    hasil.push({ id, jenis, nada: tone, label: teks, ...(gaya ? { gaya } : {}) });
  }
  return hasil;
}

/**
 * Isi baris legenda ringkas, sudah dalam urutan tampil.
 *
 * `jalur`/`pemasok` bernilai `null` atau `[]` diperlakukan sama: tidak ada
 * butirnya. Pemisahan "tidak ada lapisan" vs "tidak ada nada" sengaja TIDAK
 * dilakukan di sini — keputusan itu milik pemanggil (`showRoutes`/`showSuppliers`
 * di komponen), dan baris legenda hanya perlu tahu apa yang sedang tampil.
 */
export function compactLegendItems(input: CompactLegendInput): LegendItem[] {
  return [
    ...butir("status", "titik", STATUS_LEGEND),
    ...butir("jalur", "garis", input.jalur ?? []),
    ...butir("pemasok", "bentuk", input.pemasok ?? []),
  ];
}

/**
 * Indeks butir yang HARUS mulai di baris baru (permintaan pemilik 2026-10-19).
 *
 * Baris legenda ringkas adalah satu `flex-wrap`, jadi patahannya ditentukan
 * lebar layar — bukan makna. Terukur di 925 px dengan lapisan pemasok hidup:
 * "Pemasok · Keandalan rendah · Dikecualikan" menempel di ujung baris 1,
 * sedangkan "Di luar jangkauan · Sedang mengirim" menggantung di baris 2.
 * Kelompok pemasok (5 butir) harus utuh di baris 2; baris 1 tetap milik status
 * lokasi + jalur kiriman. Pemenggalan hanya di depan butir pemasok pertama —
 * kelompok lain tidak dipenggal supaya tidak lahir baris ketiga.
 */
export function legendBreakIndexes(items: readonly LegendItem[]): number[] {
  const penggal: number[] = [];
  let asalSebelumnya: string | null = null;
  items.forEach((item, urutan) => {
    // Id selalu `asal:nada[:gaya]` (lihat `butir()`), jadi asalnya terbaca tanpa
    // menambah field baru ke kontrak `LegendItem`.
    const asal = item.id.split(":")[0];
    if (asal === "pemasok" && asalSebelumnya !== "pemasok") penggal.push(urutan);
    asalSebelumnya = asal;
  });
  return penggal;
}

/** Kelas tanda (dot/garis/bentuk) — memakai kelas kotak Info map yang sama. */
export function legendMarkClass(item: LegendItem): [string, string] | [string, string, string] {
  switch (item.jenis) {
    case "garis":
      // Gaya (padat/putus) adalah KELAS KETIGA: nada tetap menentukan warna,
      // gaya menentukan bentuk garis — sama seperti di peta.
      if (item.gaya) {
        return ["map-legend-line", `map-legend-line-${item.nada}`, `map-legend-line-${item.gaya}`];
      }
      return ["map-legend-line", `map-legend-line-${item.nada}`];
    case "bentuk":
      return ["map-legend-box-shape", `map-legend-box-shape-${item.nada}`];
    default:
      return ["map-legend-box-dot", `map-legend-box-dot-${item.nada}`];
  }
}
