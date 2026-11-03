// Acuan hitung untuk POPUP detail keputusan (dokumen `01-detail-keputusan.md`).
//
// Kenapa modul murni terpisah: popup hanya boleh MENGATAKAN apa yang bisa
// diturunkan dari payload, dan setiap turunan itu harus bisa diuji tanpa DOM.
// Modul ini tidak menyentuh React dan tidak memformat lewat i18n global, supaya
// angka yang sama bisa dipakai di tes dan di layar.
//
// Aturan yang mengikat (dokumen §3 & §4):
// - komponen biaya yang tidak ada bernilai `null`, BUKAN 0. "Tidak tercatat" dan
//   "nol rupiah" adalah dua keadaan berbeda dan tidak boleh tampil sama;
// - harga satuan PO = safe_delivered_cost / quantity_kg (= harga terkirim),
//   BUKAN harga beli. Karena itu popup menamainya "Harga terkirim per kg";
// - perbandingan harga hanya berarti bila harga acuan DAN harga terkirim ada;
// - keputusan administratif (tanpa barang yang dibeli) tidak punya biaya, harga,
//   maupun PO — jangan menampilkan nol.

/** Jenis keputusan yang membeli barang: punya biaya, harga, dan PO. */
const JENIS_PEMBELIAN = new Set([
  "regional_balance",
  "safety_disruption",
  "supplier_procurement",
]);

/** Jenis keputusan administratif: tidak ada barang berpindah, tidak ada PO. */
const JENIS_ADMINISTRATIF = new Set([
  "price_anomaly",
  "supplier_exclusion",
  "supplier_exclusion_restoration",
]);

export function jenisKeputusan(tipe: unknown): "pembelian" | "administratif" | "lain" {
  const t = typeof tipe === "string" ? tipe : "";
  if (JENIS_PEMBELIAN.has(t)) return "pembelian";
  if (JENIS_ADMINISTRATIF.has(t)) return "administratif";
  return "lain";
}

/** Angka dari payload: string angka, number, atau null. Selain itu = null. */
function angka(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function objek(value: unknown): Record<string, any> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, any>)
    : null;
}

/** Rupiah tanpa desimal: "Rp7.358.754". Null → null (bukan "Rp0"). */
export function rupiah(value: unknown): string | null {
  const n = angka(value);
  if (n === null) return null;
  return `Rp${Math.round(n).toLocaleString("id-ID")}`;
}

/** Angka kg tanpa nol berlebih: 780, 779.86 → "779,86". */
export function kg(value: unknown): string | null {
  const n = angka(value);
  if (n === null) return null;
  const bulat = Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, "");
  return bulat.replace(".", ",");
}

// ── 2. Strip alur ──────────────────────────────────────────────────────────

export type KeadaanTahap = "selesai" | "kini" | "menunggu" | "buntu";
export type TahapAlur = { label: string; state: KeadaanTahap };

/**
 * Empat langkah untuk keputusan pembelian, tiga untuk administratif
 * (dokumen §2 butir 2). Yang ditolak TIDAK dipetakan ke langkah mana pun: ia
 * muncul sebagai chip jalan buntu di ujung strip, karena "ditolak" bukan tahap
 * yang lebih maju daripada approval.
 */
export function alurKeputusan(
  decision: unknown,
  summary: unknown
): { steps: TahapAlur[]; buntu: string | null } {
  const d = objek(decision) ?? {};
  const s = objek(summary) ?? {};
  const tipe = d.decision_type ?? s.decision_type;
  const status = String(s.status ?? d.status ?? "");
  const jenis = jenisKeputusan(tipe);
  const label =
    jenis === "pembelian"
      ? ["Usulan", "Verifikasi", "Approval", "Dibeli"]
      : ["Usulan", "Persetujuan", "Diberlakukan"];

  if (status === "rejected") {
    // Semua tahap yang SUDAH terjadi tetap terbaca sebagai selesai sampai tahap
    // tempat ia berhenti; sisanya "menunggu" — dan chip buntu menjelaskan akhirnya.
    return {
      steps: label.map((l, i) => ({
        label: l,
        state: i === 0 ? "selesai" : "menunggu",
      })),
      buntu: "Ditolak",
    };
  }

  // Indeks tahap yang sedang berjalan, dihitung dari status yang benar-benar ada.
  const urutan: Record<string, number> = {
    draft: 0,
    pending_verification: 1,
    pending_approval: jenis === "pembelian" ? 2 : 1,
    approved: jenis === "pembelian" ? 3 : 2,
    // Selesai = TIDAK ada langkah yang "kini": seluruhnya selesai (indeks di luar
    // panjang strip). Kalau diisi `label.length - 1`, langkah terakhir akan
    // tampil "kini" pada keputusan yang sudah dieksekusi.
    executed: label.length,
    confirmed: label.length,
  };
  const kini = urutan[status] ?? 0;

  return {
    steps: label.map((l, i) => ({
      label: l,
      state: i < kini ? "selesai" : i === kini ? "kini" : "menunggu",
    })),
    buntu: null,
  };
}

// ── 3. Biaya: tiga lapis (dokumen §6.2) ────────────────────────────────────

export type BarisBiaya = { label: string; nilai: string | null; rumus: string | null };
export type LapisBiaya = {
  judul: string;
  nilai: string | null;
  rumus: string | null;
  baris: BarisBiaya[];
};

/**
 * Tiga lapis yang menjelaskan kenapa harga terkirim lebih tinggi dari harga beli:
 * (1) yang dibayar ke pemasok, (2) tambahan sampai barang tiba, (3) tambahan
 * karena risiko. Tabel datar enam baris tidak menjelaskan apa pun, jadi turunan
 * ini mengelompokkan komponen yang SAMA dengan rumus yang bisa dibaca.
 *
 * `null` di setiap tingkat berarti komponennya tidak tercatat — bukan nol.
 */
export function tigaLapisBiaya(
  commercial: unknown,
  quantityKg: unknown
): { lapis: LapisBiaya[]; total: BarisBiaya | null; adaData: boolean } {
  const c = objek(commercial);
  const qty = angka(quantityKg);
  if (!c) return { lapis: [], total: null, adaData: false };

  const beli = angka(c.purchase_total);
  const angkut = angka(c.transport_total);
  const tangani = angka(c.handling_total);
  const susut = angka(c.expected_loss);
  const segar = angka(c.freshness_risk);
  const aman = angka(c.safety_penalty);
  const sdc = angka(c.sdc_total);

  const jumlah = (...xs: (number | null)[]) =>
    xs.some((x) => x !== null)
      ? xs.reduce<number>((a, b) => a + (b ?? 0), 0)
      : null;

  // Rumus hanya dicetak bila pembaginya ada dan bukan nol: "dibagi 0 kg" bukan
  // penjelasan, itu kesalahan data yang harus terlihat sebagai ketiadaan.
  const perKg = (nilai: number | null) =>
    nilai !== null && qty !== null && qty > 0
      ? `${rupiah(nilai)} ÷ ${kg(qty)} kg`
      : null;

  const lapis: LapisBiaya[] = [
    {
      judul: "Dibayar ke pemasok",
      nilai: rupiah(beli),
      rumus: perKg(beli),
      baris: [
        { label: "Harga beli", nilai: rupiah(beli), rumus: null },
      ],
    },
    {
      judul: "Tambahan sampai barang tiba",
      nilai: rupiah(jumlah(angkut, tangani)),
      rumus: perKg(jumlah(angkut, tangani)),
      baris: [
        { label: "Logistik", nilai: rupiah(angkut), rumus: null },
        { label: "Penanganan", nilai: rupiah(tangani), rumus: null },
      ],
    },
    {
      // Susut BUKAN risiko (konsep Performance & Audit, 29 Okt 2026): ia biaya
      // yang tumbuh karena barang menunggu di gudang. Dipisah agar tidak
      // tercampur dengan penalti mutu/keamanan yang sifatnya lain.
      judul: "Susut selama disimpan",
      nilai: rupiah(susut),
      rumus: perKg(susut),
      baris: [
        {
          label: "Susut gudang",
          nilai: rupiah(susut),
          // Rumus waktu, bukan kesegaran.
          rumus: "harga beli × laju susut × (hari simpan ÷ umur simpan)",
        },
      ],
    },
    {
      judul: "Tambahan karena risiko",
      nilai: rupiah(jumlah(segar, aman)),
      rumus: perKg(jumlah(segar, aman)),
      baris: [
        { label: "Risiko kesegaran", nilai: rupiah(segar), rumus: null },
        { label: "Penalti keamanan", nilai: rupiah(aman), rumus: null },
      ],
    },
  ];

  return {
    lapis,
    total: {
      label: "Biaya terkirim",
      nilai: rupiah(sdc),
      rumus: perKg(sdc),
    },
    adaData: [beli, angkut, tangani, susut, segar, aman, sdc].some((x) => x !== null),
  };
}

// ── 4. Perbandingan harga (dokumen §3.3) ───────────────────────────────────

export type Perbandingan = {
  arah: "lebih murah" | "lebih mahal" | "sama";
  perKg: string;
  persen: string;
  acuanPerKg: string;
  kalimat: string;
};

/** `difference = acuan - terkirim`; positif = lebih murah dari kota tujuan. */
export function perbandinganHarga(
  market: unknown,
  commercial: unknown
): Perbandingan | null {
  const m = objek(market);
  const c = objek(commercial);
  const acuan = angka(m?.price_per_kg);
  const terkirim = angka(c?.sdc_unit_price);
  if (acuan === null || terkirim === null || acuan <= 0) return null;

  const selisih = acuan - terkirim;
  const persen = Math.abs((selisih / acuan) * 100);
  const arah = selisih > 0 ? "lebih murah" : selisih < 0 ? "lebih mahal" : "sama";
  const perKg = rupiah(Math.abs(selisih)) ?? "";
  const persenTeks = `${persen.toFixed(1).replace(".", ",")}%`;
  const kalimat =
    arah === "sama"
      ? "Sama dengan harga acuan setempat"
      : `${arah === "lebih murah" ? "Lebih murah" : "Lebih mahal"} ${perKg} per kg ` +
        `(${persenTeks}) daripada harga acuan di kota tujuan`;

  return {
    arah,
    perKg,
    persen: persenTeks,
    acuanPerKg: rupiah(acuan) ?? "",
    kalimat,
  };
}

// ── 5. Status PO sebagai langkah (dokumen §6.4) ────────────────────────────

export type TahapPo = { label: string; state: KeadaanTahap };

/**
 * Tiga keadaan nyata PO (dokumen §6.4) + keadaan "belum terbit". Status backend
 * `draft → submitted → confirmed` (lihat `app/services/po_document.py`).
 */
export function tahapPo(po: unknown): {
  steps: TahapPo[];
  terbit: boolean;
  nomor: string | null;
  statusLabel: string;
} {
  const p = objek(po);
  if (!p || !p.po_number) {
    return {
      steps: [
        { label: "Terbit", state: "menunggu" },
        { label: "Terkirim", state: "menunggu" },
        { label: "Diterima SAP", state: "menunggu" },
      ],
      terbit: false,
      nomor: null,
      statusLabel: "Belum terbit",
    };
  }
  const status = String(p.status ?? "");
  const indeks = status === "confirmed" ? 2 : status === "submitted" ? 1 : 0;
  const label = ["Terbit", "Terkirim", "Diterima SAP"];
  return {
    steps: label.map((l, i) => ({
      label: l,
      state: i < indeks ? "selesai" : i === indeks ? (status === "confirmed" ? "selesai" : "kini") : "menunggu",
    })),
    terbit: true,
    nomor: String(p.po_number),
    // Label berbahasa Indonesia: status mentah backend ("draft"/"submitted"/
    // "confirmed") tidak pernah dicetak ke layar.
    statusLabel:
      status === "confirmed"
        ? "Diterima SAP"
        : status === "submitted"
          ? "Terkirim ke SAP"
          : status === "draft"
            ? "Draf, menunggu review"
            : "Tidak diketahui",
  };
}
