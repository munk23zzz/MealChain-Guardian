// @vitest-environment jsdom
// Popup penerimaan barang (Dok 05 §2–§5) — diuji dengan popup BENAR-BENAR dibuka.
//
// Kenapa bukan renderToStaticMarkup seperti tes halaman lain: popup hidup di
// dalam portal dan hanya dirender saat terbuka, jadi markup halaman tertutup
// tidak memuat satu pun isinya. Menguji string komponen secara terpisah akan
// lolos walau tombolnya tidak pernah membuka apa pun.
//
// Yang diperiksa di sini adalah tiga hal yang diminta pemilik (29 Okt 2026):
//   1. popup di TENGAH (bukan drawer kanan) dengan tujuh butir berbobot,
//   2. tiap butir dijawab dengan TIGA opsi — bukan kotak centang boolean,
//   3. berat timbangan divalidasi dan skor kelayakan ditampilkan dari server.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-11T06:00:00Z");

const BATCH = {
  id: "b-jkt-1",
  location: "Jakarta",
  commodity: "telur",
  quantity_kg: 180,
  safety_status: "pending",
  freshness_score: 0.9,
  usable_until: "2026-11-07T12:00:00Z",
  evidence: {
    temperature_observation: "missing",
    evidence_state: "insufficient",
    source: "seed",
    source_label: "log simulasi",
    observed_at: null,
    sample_count: 0,
    evidence_sufficient: false,
  },
};

/** Ceklis seperti yang dikirim `GET /receipts/checklist?commodity=telur`. */
const CEKLIS = {
  version: "2026-10-29",
  komoditas: "telur",
  total_bobot: 100,
  ambang: {
    fail_max_score: 64,
    ambiguous_max_score: 85,
    accepted_ratio_min: 0.95,
    berat_lebih_maks_persen: 110,
  },
  butir: [
    {
      kunci: "suhu",
      label: "Suhu saat tiba",
      bobot: 25,
      dari_timbangan: false,
      petunjuk: "Rentang aman 2–8 °C untuk telur.",
      opsi: [
        { kunci: "sesuai", label: "Sesuai rentang", faktor: 100, kritis: false, perlu_cek: false },
        { kunci: "sedikit", label: "Sedikit di atas batas", faktor: 55, kritis: false, perlu_cek: true },
        { kunci: "jauh", label: "Jauh di atas batas", faktor: 0, kritis: true, perlu_cek: false },
      ],
    },
    {
      kunci: "kebersihan",
      label: "Kebersihan & bau",
      bobot: 25,
      dari_timbangan: false,
      petunjuk: null,
      opsi: [
        { kunci: "bersih", label: "Bersih, tanpa bau", faktor: 100, kritis: false, perlu_cek: false },
        { kunci: "sedikit", label: "Sedikit kotor", faktor: 60, kritis: false, perlu_cek: true },
        { kunci: "kotor", label: "Kotor / berbau", faktor: 0, kritis: true, perlu_cek: false },
      ],
    },
    {
      kunci: "kemasan",
      label: "Kemasan utuh",
      bobot: 15,
      dari_timbangan: false,
      petunjuk: null,
      opsi: [
        { kunci: "utuh", label: "Utuh", faktor: 100, kritis: false, perlu_cek: false },
        { kunci: "sedikit", label: "Sedikit rusak", faktor: 55, kritis: false, perlu_cek: true },
        { kunci: "bocor", label: "Bocor / tumpah", faktor: 0, kritis: true, perlu_cek: false },
      ],
    },
    {
      kunci: "label",
      label: "Label & tanggal kedaluwarsa",
      bobot: 15,
      dari_timbangan: false,
      petunjuk: null,
      opsi: [
        { kunci: "lengkap", label: "Lengkap & jelas", faktor: 100, kritis: false, perlu_cek: false },
        { kunci: "sebagian", label: "Sebagian tidak terbaca", faktor: 55, kritis: false, perlu_cek: true },
        { kunci: "tidak", label: "Tidak ada", faktor: 0, kritis: false, perlu_cek: false },
      ],
    },
    {
      kunci: "jumlah",
      label: "Kesesuaian jumlah",
      bobot: 8,
      dari_timbangan: true,
      petunjuk: null,
      opsi: [
        { kunci: "sesuai", label: "Sesuai pesanan", faktor: 100, kritis: false, perlu_cek: false },
        { kunci: "kurang", label: "Kurang ≤ 5%", faktor: 50, kritis: false, perlu_cek: true },
        { kunci: "jauh", label: "Kurang > 5%", faktor: 0, kritis: false, perlu_cek: true },
      ],
    },
    {
      kunci: "kendaraan",
      label: "Kendaraan & kebersihan bak",
      bobot: 7,
      dari_timbangan: false,
      petunjuk: null,
      opsi: [
        { kunci: "bersih", label: "Bersih & tertutup", faktor: 100, kritis: false, perlu_cek: false },
        { kunci: "terbuka", label: "Terbuka sebagian", faktor: 55, kritis: false, perlu_cek: false },
        { kunci: "kotor", label: "Kotor / bercampur", faktor: 0, kritis: true, perlu_cek: false },
      ],
    },
    {
      kunci: "dokumen",
      label: "Surat jalan & sertifikat",
      bobot: 5,
      dari_timbangan: false,
      petunjuk: null,
      opsi: [
        { kunci: "lengkap", label: "Lengkap", faktor: 100, kritis: false, perlu_cek: false },
        { kunci: "menyusul", label: "Menyusul", faktor: 55, kritis: false, perlu_cek: true },
        { kunci: "tidak", label: "Tidak ada", faktor: 0, kritis: false, perlu_cek: false },
      ],
    },
  ],
  nama_putusan: {
    pass: "Layak diterima",
    needs_verification: "Perlu verifikasi",
    fail: "Tidak layak diterima",
  },
};

/** Balasan `POST /receipts` — server yang menghitung, bukan layar. */
const BALASAN = {
  id: "r-1",
  batch_id: "b-jkt-1",
  status: "menunggu",
  checked_count: 7,
  note: "karung lapis kedua basah",
  recorded_by_name: "Kepala Bandung",
  recorded_at: "2026-10-11T06:05:00Z",
  score: 97,
  verdict: "needs_verification",
  verdict_label: "Perlu verifikasi",
  advice: "Berat diterima 168 kg dari 180 kg (93%) — kurang dari 95%, periksa timbangan.",
  ordered_kg: 180,
  accepted_kg: 168,
  points: [
    { kunci: "suhu", label: "Suhu saat tiba", opsi_label: "Sesuai rentang", poin: 25, max_points: 25, kritis: false },
    { kunci: "kebersihan", label: "Kebersihan & bau", opsi_label: "Bersih, tanpa bau", poin: 25, max_points: 25, kritis: false },
    { kunci: "kemasan", label: "Kemasan utuh", opsi_label: "Utuh", poin: 15, max_points: 15, kritis: false },
    { kunci: "label", label: "Label & tanggal kedaluwarsa", opsi_label: "Lengkap & jelas", poin: 15, max_points: 15, kritis: false },
    { kunci: "jumlah", label: "Kesesuaian jumlah", opsi_label: "Kurang ≤ 5%", poin: 4, max_points: 8, kritis: false },
    { kunci: "kendaraan", label: "Kendaraan & kebersihan bak", opsi_label: "Bersih & tertutup", poin: 7, max_points: 7, kritis: false },
    { kunci: "dokumen", label: "Surat jalan & sertifikat", opsi_label: "Lengkap", poin: 5, max_points: 5, kritis: false },
  ],
  nilai_diterima_idr: 1932000,
  unit_price_idr: 11500,
  po_number: "MC-8C0B2C6031BC",
  price_source: "purchase_orders",
};

const ROW_TERSIMPAN = {
  ...BALASAN,
  batch_quantity_kg: 180,
  estimated_value_idr: 2070000,
  accepted_value_idr: null,
};

let host: HTMLDivElement;
let root: Root;

const tick = async (fn: () => void) => {
  await act(async () => {
    fn();
    await Promise.resolve();
  });
};

const diam = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
};

async function buka(props: Record<string, unknown> = {}) {
  const onRecordReceipt = vi.fn(async () => BALASAN);
  const loadReceipts = vi.fn(async () => ({ items: [ROW_TERSIMPAN], total: 1 }));
  const loadChecklist = vi.fn(async () => CEKLIS);
  await act(async () => {
    root.render(
      <FoodSafetyBoard
        batches={[BATCH]}
        now={NOW}
        ownLocation="Jakarta"
        canMutate
        canApprove
        onRecheck={async () => ({
          safety: { safety_status: "pass", reasons: ["Tidak ada penyimpangan suhu"], excursion_minutes: 0 },
          freshness: { freshness_score: 0.9, status: "ok", usable_until: "2026-11-07T12:00:00Z" },
        })}
        onRecordReceipt={onRecordReceipt}
        loadReceipts={loadReceipts}
        loadChecklist={loadChecklist}
        loadPendingReceipts={async () => ({ items: [], total: 0 })}
        onApproveReceipt={async () => ({ stock_kg: 168 })}
        onRejectReceipt={async () => ({})}
        {...props}
      />
    );
  });
  const pemicu = Array.from(host.ownerDocument.querySelectorAll("button")).find((b) =>
    (b.textContent ?? "").includes("Periksa & catat kiriman")
  );
  expect(pemicu).toBeTruthy();
  await tick(() => (pemicu as HTMLButtonElement).click());
  await diam();
  return { doc: host.ownerDocument, onRecordReceipt, loadReceipts, loadChecklist };
}

function tombol(doc: Document, teks: string): HTMLButtonElement | null {
  const ketemu = Array.from(doc.querySelectorAll("button")).find((b) =>
    (b.textContent ?? "").trim().startsWith(teks)
  );
  return (ketemu as HTMLButtonElement | undefined) ?? null;
}

/** Jawab semua butir yang dipilih petugas dengan opsi pertama. */
async function jawabSemua(doc: Document) {
  const grup = Array.from(doc.querySelectorAll('.popup-receipt [role="radiogroup"]'));
  for (const g of grup) {
    const radio = g.querySelector<HTMLInputElement>('input[type="radio"]');
    if (radio) await tick(() => radio.click());
  }
  return grup.length;
}

/** Aksi tulis sejak tahap 4 (30 Okt 2026) dijaga gerbang konfirmasi: klik
 *  pertama hanya membuka ringkasan, klik kedua baru mengirim ke server. */
async function catat(doc: Document) {
  await tick(() => (tombol(doc, "Lanjut: konfirmasi") as HTMLButtonElement).click());
  await tick(() => (tombol(doc, "Catat & hitung nilai") as HTMLButtonElement).click());
  await diam();
}

async function isiBerat(doc: Document, nilai: string) {
  const kolom = doc.querySelector<HTMLInputElement>("#berat-diterima");
  expect(kolom).toBeTruthy();
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value"
    )?.set as (v: string) => void;
    setter.call(kolom, nilai);
    kolom!.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  document.body.innerHTML = "";
});

describe("popup penerimaan barang — Dok 05 §2–§5", () => {
  it("popup di tengah berisi langkah 1 dengan tujuh butir dan TIGA opsi per butir", async () => {
    const { doc, loadChecklist } = await buka();
    const panel = doc.querySelector(".popup-receipt");
    expect(panel).toBeTruthy();
    // Dialog tengah: kelas yang sama dengan dialog lain, tanpa kelas drawer kanan.
    expect(panel?.className).not.toContain("popup-drawer");
    expect(loadChecklist).toHaveBeenCalledWith("telur");

    const teks = panel?.textContent ?? "";
    expect(teks).toContain("1. Periksa kondisi barang");
    expect(teks).toContain("2. Nilai dan putusan batch");
    expect(teks).toContain("3. Tandai barang");

    // Tujuh butir, bobotnya ditulis apa adanya dari server.
    const butir = doc.querySelectorAll('.popup-receipt li[data-testid^="butir-"]');
    expect(butir.length).toBe(7);
    expect(teks).toContain("25 poin");
    expect(teks).toContain("5 poin");

    // Enam butir dipilih (tiga opsi = tiga radio), satu butir dari timbangan.
    const grup = doc.querySelectorAll('.popup-receipt [role="radiogroup"]');
    expect(grup.length).toBe(6);
    for (const g of Array.from(grup)) {
      expect(g.querySelectorAll('input[type="radio"]').length).toBe(3);
    }
    expect(doc.querySelectorAll('.popup-receipt input[type="checkbox"]').length).toBe(0);
    expect(doc.querySelector('[data-testid="butir-jumlah"]')).toBeTruthy();
  });

  it("tombol simpan MATI sampai tujuh butir dijawab DAN berat diterima diisi", async () => {
    const { doc } = await buka();
    const simpan = () => tombol(doc, "Lanjut: konfirmasi");
    expect(simpan()).toBeTruthy();
    expect(simpan()?.disabled).toBe(true);
    expect(doc.querySelector('[data-testid="receipt-kemajuan"]')?.textContent).toContain(
      "0 dari 7 butir sudah dijawab"
    );

    const grup = await jawabSemua(doc);
    expect(grup).toBe(6);
    // Semua butir dijawab, berat masih kosong → tombol tetap mati.
    expect(simpan()?.disabled).toBe(true);
    expect(doc.querySelector('[data-testid="receipt-kemajuan"]')?.textContent).toContain(
      "6 dari 7 butir"
    );

    await isiBerat(doc, "168");
    expect(simpan()?.disabled).toBe(false);
  });

  it("berat di atas 110% pesanan ditolak di layar sebelum dikirim (Dok 05 §5.2)", async () => {
    const { doc, onRecordReceipt } = await buka();
    await jawabSemua(doc);
    await isiBerat(doc, "250");

    const galat = doc.querySelector("#berat-diterima-bantuan")?.textContent ?? "";
    expect(galat).toContain("melebihi 110% pesanan");
    expect(tombol(doc, "Lanjut: konfirmasi")?.disabled).toBe(true);
    expect(onRecordReceipt).not.toHaveBeenCalled();
  });

  // Tahap 4 redesign (30 Okt 2026): aksi tulis tidak boleh terjadi pada klik
  // pertama. Yang diuji di sini adalah janji itu sendiri — bukan tampilan.
  it("gerbang konfirmasi: klik pertama tidak menulis apa pun ke server", async () => {
    const { doc, onRecordReceipt } = await buka();
    await jawabSemua(doc);
    await isiBerat(doc, "168");

    await tick(() => (tombol(doc, "Lanjut: konfirmasi") as HTMLButtonElement).click());

    expect(onRecordReceipt).not.toHaveBeenCalled();
    const panel = doc.querySelector('[data-testid="receipt-konfirmasi"]');
    expect(panel).toBeTruthy();
    const teks = panel?.textContent ?? "";
    expect(teks).toContain("Konfirmasi sebelum dicatat");
    expect(teks).toContain("tidak bisa dibatalkan");
    expect(teks).toContain("168");
    // Jumlah butir terjawab ditampilkan sebagai "N dari 7"; angka tepatnya
    // sudah dikunci oleh uji kemajuan di atas.
    expect(teks).toMatch(/\d+ dari 7/);

    // "Kembali perbaiki" menutup ringkasan tanpa menulis apa pun.
    await tick(() => (tombol(doc, "Kembali perbaiki") as HTMLButtonElement).click());
    expect(doc.querySelector('[data-testid="receipt-konfirmasi"]')).toBeNull();
    expect(onRecordReceipt).not.toHaveBeenCalled();

    // Baru klik kedua (di dalam layar konfirmasi) yang menyimpan.
    await catat(doc);
    expect(onRecordReceipt).toHaveBeenCalledTimes(1);
  });

  it("sesudah dinilai: skor, putusan, saran, dan rincian poin tampil dari server", async () => {
    const { doc, onRecordReceipt, loadReceipts } = await buka();
    await jawabSemua(doc);
    await isiBerat(doc, "168");
    await catat(doc);

    // Yang dikirim: jawaban tujuh butir + berat timbangan sebagai angka.
    expect(onRecordReceipt).toHaveBeenCalledTimes(1);
    const arg = onRecordReceipt.mock.calls[0] as unknown as [
      string,
      Record<string, boolean>,
      string,
      { answers: Record<string, string>; acceptedKg: number },
    ];
    expect(arg[0]).toBe("b-jkt-1");
    expect(arg[3].acceptedKg).toBe(168);
    expect(Object.keys(arg[3].answers).length).toBe(6);

    const skor = doc.querySelector('[data-testid="receipt-score"]');
    expect(skor?.textContent).toContain("97");
    expect(skor?.textContent).toContain("Perlu verifikasi");
    expect(doc.querySelector('[data-testid="receipt-advice"]')?.textContent).toContain(
      "kurang dari 95%"
    );

    // Rincian poin: tujuh baris, butir jumlah hanya 4 dari 8.
    const baris = doc.querySelectorAll('[data-testid="receipt-points"] tbody tr');
    expect(baris.length).toBe(7);
    expect(baris[4].textContent).toContain("4 / 8");

    // Angka rupiah dibaca ulang dari server dan memakai kg DITERIMA.
    expect(loadReceipts).toHaveBeenCalled();
    expect(doc.querySelector('[data-testid="receipt-figures"]')?.textContent).toContain("168 kg");
    expect(doc.querySelector('[data-testid="receipt-value"]')?.textContent).toContain("1.932.000");
    expect(doc.querySelector('[data-testid="receipt-value-origin"]')?.textContent).toContain(
      "Rp 11.500"
    );
    expect(doc.body.textContent).toContain("Setujui & masukkan stok");
  });

  it("putusan fail menutup tombol setuju, bukan sekadar memperingatkan (Dok 05 §4)", async () => {
    const gagal = vi.fn(async () => ({
      ...BALASAN,
      score: 25,
      verdict: "fail",
      verdict_label: "Tidak layak diterima",
      advice: "Suhu jauh di atas batas — barang tidak boleh diterima.",
    }));
    const { doc } = await buka({ onRecordReceipt: gagal });
    await jawabSemua(doc);
    await isiBerat(doc, "168");
    await catat(doc);

    expect(doc.querySelector('[data-testid="receipt-blocked"]')).toBeTruthy();
    expect(tombol(doc, "Setujui & masukkan stok")).toBeNull();
    expect(doc.body.textContent).toContain("Tolak penerimaan");
  });

  it("bukti suhu kiriman disebut di langkah 1, termasuk saat bukti belum cukup", async () => {
    const { doc } = await buka();
    const baris = doc.querySelector('[data-role="bukti-terima"]');
    expect(baris).toBeTruthy();
    expect(baris?.textContent).toContain("log simulasi");
    expect(baris?.textContent).toContain("periksa dulu sebelum dipakai");
  });

  it("peran tanpa izin tulis: semua opsi mati dan tidak ada tombol simpan", async () => {
    const { doc } = await buka({ canMutate: false });
    const radio = Array.from(
      doc.querySelectorAll<HTMLInputElement>('.popup-receipt input[type="radio"]')
    );
    expect(radio.length).toBe(18);
    expect(radio.every((r) => r.disabled)).toBe(true);
    expect(tombol(doc, "Lanjut: konfirmasi")).toBeNull();
    expect(tombol(doc, "Catat & hitung nilai")).toBeNull();
    expect(doc.body.textContent).toContain("Hanya kepala SPPG dan ahli gizi");
  });
});
