import type { EvidenceRow, SafetyRow, SafetyTone } from "./food-safety";

// Satu baris per batch yang perlu perhatian (29 Okt 2026).
//
// Kenapa modul ini ada: halaman Keamanan Pangan dulu menampilkan tiga kartu
// terpisah — "Bukti suhu", "Batch perlu segera dipakai", "Kesegaran terendah" —
// yang semuanya membaca array batch yang sama. Satu batch bisa muncul tiga kali
// dengan tiga bahasa berbeda (bukti kurang / sisa 20 jam / segar 42%), dan
// pembaca harus menggabungkannya sendiri. Sekarang ketiganya menjadi KOLOM di
// satu tabel: satu baris per batch, tiga putusan berdampingan.
//
// Semua teks berasal dari server (`evidence_state`, `evidence_reasons`,
// `hours_label`, `freshness`). Modul ini tidak menilai ulang kelengkapan bukti
// dan tidak mengarang angka: satu-satunya perhitungannya adalah memilih baris
// mana yang perlu perhatian, mengurutkannya, dan menyingkat alasan server.

/** Alasan yang lebih panjang dari ini dipotong; versi utuh tetap ada di `penuh`. */
const MAX_KENAPA = 64;

/** Ambang "segera dipakai" — sama dengan lencana kartu lama (≤ 48 jam). */
const AMBANG_SISA_JAM = 48;

/** Di bawah ini skor kesegaran dianggap perlu dilihat (skor 0..1). */
const AMBANG_SEGAR = 0.5;

export type PerhatianRow = {
  id: string | null;
  commodity: string;
  location: string;
  kg: number | null;
  /** Label bukti suhu dari server ("Bukti cukup" / "Bukti kurang" / …). */
  buktiLabel: string;
  buktiTone: SafetyTone;
  /** Sisa masa layak APA ADANYA dari server. */
  sisa: string;
  /** Skor kesegaran APA ADANYA dari server; "—" bila tidak dikirim. */
  segar: string;
  /** Alasan singkat untuk kolom "Kenapa"; null bila server tidak memberi alasan. */
  kenapa: string | null;
  /** Alasan utuh dari server (untuk tooltip — tidak ada informasi yang hilang). */
  penuh: string[];
  tone: SafetyTone;
  /** Skor urut internal (lebih besar = lebih perlu tindakan). */
  bobot: number;
};

/**
 * Durasi dalam menit → satuan yang bisa dibayangkan.
 * "29685 menit" tidak berarti apa-apa bagi pembaca; "20 hari" berarti.
 */
export function durasiManusia(menit: number | null | undefined): string {
  if (menit === null || menit === undefined || !Number.isFinite(menit) || menit < 0) {
    return "—";
  }
  const total = Math.round(menit);
  const hari = Math.floor(total / 1440);
  if (hari >= 1) return `${hari} hari`;
  const jam = Math.floor(total / 60);
  const sisaMenit = total % 60;
  if (jam >= 1) return sisaMenit ? `${jam} jam ${sisaMenit} menit` : `${jam} jam`;
  return `${total} menit`;
}

type Klausa = { kunci: string; teks: string };

/**
 * Alasan server → satu-dua klausa pendek, tanpa pengulangan.
 *
 * Contoh nyata yang diringkas di sini:
 *   "entri log rusak pada indeks 1; entri log rusak pada indeks 2;
 *    sampel sah kurang dari 2 (ada 1); 2 entri log tidak terbaca"
 * → "2 entri log rusak · 1 sampel sah dari minimum 2"
 */
export function alasanSingkat(reasons: readonly string[] | null | undefined): string | null {
  const daftar = Array.isArray(reasons) ? reasons.map((r) => String(r)) : [];
  if (!daftar.length) return null;

  const klausa: Klausa[] = [];
  const tambah = (kunci: string, teks: string) => {
    if (!teks) return;
    if (klausa.some((k) => k.kunci === kunci)) return;
    klausa.push({ kunci, teks });
  };

  // 1. Kedaluwarsa: "sampel terakhir 29685 menit lalu, lewat batas 360 menit".
  const basi = daftar.find((r) => /sampel terakhir\s+\d+\s+menit lalu/i.test(r));
  if (basi) {
    const lama = Number((basi.match(/sampel terakhir\s+(\d+)\s+menit lalu/i) ?? [])[1]);
    const batas = Number((basi.match(/lewat batas\s+(\d+)\s+menit/i) ?? [])[1]);
    const umur = durasiManusia(Number.isFinite(lama) ? lama : null);
    const ambang = durasiManusia(Number.isFinite(batas) ? batas : null);
    tambah(
      "basi",
      ambang === "—"
        ? `log kedaluwarsa: sampel terakhir ${umur} lalu`
        : `log kedaluwarsa: sampel terakhir ${umur} lalu (batas ${ambang})`
    );
  }

  // 2. Sampel sah kurang: "sampel sah kurang dari 2 (ada 1)" / "sampel sah 1 dari minimum 2".
  const sampel = daftar.find((r) => /sampel sah/i.test(r));
  if (sampel) {
    const ada = Number((sampel.match(/\(ada\s+(\d+)\)/i) ?? [])[1]);
    const min = Number(
      (sampel.match(/kurang dari\s+(\d+)/i) ?? sampel.match(/dari minimum\s+(\d+)/i) ?? [])[1]
    );
    if (Number.isFinite(ada) && Number.isFinite(min)) {
      tambah("sampel", `${ada} sampel sah dari minimum ${min}`);
    } else if (Number.isFinite(min)) {
      tambah("sampel", `sampel sah kurang dari ${min}`);
    } else {
      tambah("sampel", "sampel sah kurang");
    }
  }

  // 3. Entri log rusak/tidak terbaca: hitung entri, jangan sebut indeksnya.
  // Server kadang memberi ANGKA ("2 entri log tidak terbaca") sekaligus
  // menyebut tiap entri ("rusak pada indeks 1", "… indeks 2"). Angka eksplisit
  // yang dipakai; menghitung baris akan melebih-lebihkan (2 entri jadi 3).
  const rusak = daftar.filter((r) => /(entri log rusak|entri log tidak terbaca)/i.test(r));
  if (rusak.length) {
    const angkaEksplisit = rusak
      .map((r) => Number((r.match(/(\d+)\s+entri log tidak terbaca/i) ?? [])[1]))
      .filter((n) => Number.isFinite(n) && n > 0);
    const jumlah = angkaEksplisit.length ? Math.max(...angkaEksplisit) : rusak.length;
    tambah("rusak", `${jumlah} entri log rusak`);
  }

  // 4. Alasan lain yang belum dikenali: tulis apa adanya (terpotong).
  if (!klausa.length) {
    const mentah = daftar[0].replace(/\s+/g, " ").trim();
    tambah("lain", potong(mentah, MAX_KENAPA));
  }

  return klausa
    .slice(0, 2)
    .map((k) => k.teks)
    .join(" · ");
}

function potong(teks: string, maks: number): string {
  if (teks.length <= maks) return teks;
  const potongDi = teks.lastIndexOf(" ", maks);
  return `${teks.slice(0, potongDi > 20 ? potongDi : maks)}…`;
}

const TONE_URUT: Record<SafetyTone, number> = { ok: 0, warn: 1, danger: 2, muted: 3 };

/** Tingkat keparahan; `muted` (tidak diketahui) tidak boleh lebih ringan dari `warn`. */
function bobotBukti(row: EvidenceRow): number {
  if (row.sufficient) return 0;
  if (row.state === "ambiguous") return 3;
  if (row.state === "unknown") return 1;
  return 2; // insufficient
}

/**
 * Gabungkan baris keselamatan dengan bukti suhu menjadi daftar "perlu perhatian".
 *
 * Baris masuk daftar bila salah satu benar: bukti suhu belum cukup, sisa masa
 * layak ≤ 48 jam, atau skor kesegaran di bawah 0,5. Baris yang hanya "cukup"
 * pada ketiganya tidak ditampilkan — daftar ini alat pindai, bukan register;
 * register lengkapnya tetap tabel "Status keamanan per batch".
 */
export function batchPerhatian(
  safety: readonly SafetyRow[] | null | undefined,
  evidence: readonly EvidenceRow[] | null | undefined,
  opsi: { maks?: number } = {}
): PerhatianRow[] {
  // `Array.isArray` pada array `readonly` menyempit ke `any[]`, jadi tipenya
  // ditegaskan di sini — tanpa itu `row.tone` kehilangan tipenya.
  const daftarSafety: readonly SafetyRow[] = Array.isArray(safety) ? safety : [];
  const daftarBukti: readonly EvidenceRow[] = Array.isArray(evidence) ? evidence : [];
  const buktiPerId = new Map<string, EvidenceRow>();
  for (const row of daftarBukti) {
    if (row.id) buktiPerId.set(row.id, row);
  }

  const hasil: PerhatianRow[] = [];
  for (const row of daftarSafety) {
    const bukti = row.id ? buktiPerId.get(row.id) : undefined;
    const buktiBelumCukup = Boolean(bukti && !bukti.sufficient);
    const sisaMendesak =
      row.hoursLeft !== null && Number.isFinite(row.hoursLeft) && row.hoursLeft <= AMBANG_SISA_JAM;
    const segarRendah =
      row.freshnessScore !== null &&
      Number.isFinite(row.freshnessScore) &&
      row.freshnessScore < AMBANG_SEGAR;

    if (!buktiBelumCukup && !sisaMendesak && !segarRendah) continue;

    let bobot = 0;
    if (buktiBelumCukup) bobot += 4 + bobotBukti(bukti as EvidenceRow);
    if (row.hoursLeft !== null && row.hoursLeft <= 0) bobot += 3;
    else if (sisaMendesak) bobot += 2;
    if (segarRendah) bobot += 1;

    const alasan = bukti ? bukti.reasons : [];
    hasil.push({
      id: row.id,
      commodity: row.commodity,
      location: row.location,
      kg: row.kg,
      buktiLabel: bukti ? bukti.stateLabel : "Tidak dinilai",
      buktiTone: bukti ? bukti.tone : "muted",
      sisa: row.hoursLabel,
      segar: row.freshness,
      kenapa: alasanSingkat(alasan),
      penuh: Array.isArray(alasan) ? alasan.map((r) => String(r)) : [],
      tone: buktiBelumCukup
        ? bukti!.tone
        : TONE_URUT[row.tone] >= TONE_URUT.warn
          ? row.tone
          : segarRendah
            ? ("warn" as const)
            : row.tone,
      bobot,
    });
  }

  hasil.sort((a, b) => {
    if (b.bobot !== a.bobot) return b.bobot - a.bobot;
    const sisaA = a.sisa;
    const sisaB = b.sisa;
    return sisaA.localeCompare(sisaB, "id");
  });

  const maks = opsi.maks ?? hasil.length;
  return maks >= 0 ? hasil.slice(0, maks) : hasil;
}
