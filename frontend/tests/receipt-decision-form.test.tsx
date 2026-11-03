// @vitest-environment jsdom
// Ceklis penerimaan DI KARTU KEPUTUSAN (30 Okt 2026).
//
// Keluhan pemilik: "human approval harus ngecek apa aja yang dicentang dan
// inputan tambahan — ini ga ada". Sebelum perubahan ini langkah 1 di popup
// penerimaan hanya MEMBACA titik periksa yang dicatat petugas di papan Keamanan
// Pangan: tidak ada satu pun kontrol untuk mengisi, tidak ada isian timbangan,
// sehingga tombol "Tandai diterima" praktis menunggu orang lain.
//
// Tes ini mengunci janji barunya: butir bisa dijawab di sini, berat ditimbang
// wajib diisi, dan tombol simpan baru hidup setelah isian lengkap.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GoodsReceiptSheet } from "../components/GoodsReceiptDrawer";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

const CEKLIS = {
  version: "2026-10-29",
  komoditas: "telur",
  total_bobot: 100,
  ambang: {
    fail_max_score: 64,
    ambiguous_max_score: 84,
    accepted_ratio_min: 0.9,
    berat_lebih_maks_persen: 110,
  },
  butir: [
    {
      kunci: "suhu",
      label: "Suhu wadah dalam rentang aman",
      bobot: 30,
      dari_timbangan: false,
      petunjuk: "telur 15–30 °C",
      opsi: [
        { kunci: "sesuai", label: "Sesuai", faktor: 1, kritis: false, perlu_cek: false },
        { kunci: "ragu", label: "Ragu", faktor: 0.6, kritis: false, perlu_cek: true },
        { kunci: "tidak", label: "Tidak sesuai", faktor: 0, kritis: true, perlu_cek: false },
      ],
    },
    {
      kunci: "jumlah",
      label: "Jumlah sesuai surat jalan",
      bobot: 30,
      dari_timbangan: true,
      petunjuk: null,
      opsi: [],
    },
    {
      kunci: "kemasan",
      label: "Kemasan utuh",
      bobot: 40,
      dari_timbangan: false,
      petunjuk: null,
      opsi: [
        { kunci: "ya", label: "Ya", faktor: 1, kritis: false, perlu_cek: false },
        { kunci: "tidak", label: "Tidak", faktor: 0, kritis: true, perlu_cek: false },
      ],
    },
  ],
  nama_putusan: { pass: "Layak diterima" },
};

const BARIS = {
  batchId: "b-1",
  status: "usable",
  statusLabel: "Layak masuk stok",
  canReceive: true,
  canQuarantine: false,
  reasons: [],
  nextStep: null,
};

const CATATAN = {
  id: "r-1",
  status: "menunggu",
  checked: {},
  checked_count: 0,
  other_note: null,
  accepted_kg: null,
  answers: null,
};

function Harness({ onSimpan }: { onSimpan: () => void }) {
  const [jawaban, setJawaban] = useState<Record<string, string>>({});
  const [berat, setBerat] = useState("");
  const [catatanIsi, setCatatanIsi] = useState("");
  return (
    <GoodsReceiptSheet
      baris={BARIS}
      catatan={CATATAN}
      bolehPutuskan
      bolehIsi
      checklist={CEKLIS as never}
      jawaban={jawaban}
      onJawab={(kunci, opsi) => setJawaban((lama) => ({ ...lama, [kunci]: opsi }))}
      berat={berat}
      onBerat={setBerat}
      catatanIsi={catatanIsi}
      onCatatanIsi={setCatatanIsi}
      menyimpan={false}
      onSimpan={onSimpan}
      busy={false}
      galat={null}
      pesan={null}
    />
  );
}

let wadah: HTMLDivElement;
let root: Root;

beforeEach(() => {
  wadah = document.createElement("div");
  document.body.appendChild(wadah);
  root = createRoot(wadah);
});

afterEach(() => {
  act(() => root.unmount());
  wadah.remove();
});

function tombolSimpan(): HTMLButtonElement {
  const el = wadah.querySelector<HTMLButtonElement>('[data-testid="receipt-save-checklist"]');
  if (!el) throw new Error("tombol simpan tidak dirender");
  return el;
}

describe("Ceklis penerimaan di kartu keputusan", () => {
  it("menyediakan pilihan jawaban, isian timbangan, dan catatan", () => {
    const onSimpan = vi.fn();
    act(() => root.render(<Harness onSimpan={onSimpan} />));

    // Tiap butir berbobot punya pilihan; butir timbangan tidak minta dipilih.
    expect(wadah.querySelectorAll('input[type="radio"]').length).toBe(5);
    expect(wadah.querySelector('[data-testid="butir-jumlah"]')?.textContent).toContain(
      "dihitung dari timbangan"
    );
    expect(wadah.querySelector('[data-testid="receipt-weight"]')).not.toBeNull();
    expect(wadah.querySelector('[data-testid="receipt-other-input"]')).not.toBeNull();
  });

  it("tombol simpan baru hidup setelah semua butir dijawab dan berat diisi", () => {
    act(() => root.render(<Harness onSimpan={vi.fn()} />));
    expect(tombolSimpan().disabled).toBe(true);

    act(() => {
      const suhu = wadah.querySelector<HTMLInputElement>('[data-testid="opsi-suhu-sesuai"]')!;
      suhu.click();
    });
    act(() => {
      const kemasan = wadah.querySelector<HTMLInputElement>('[data-testid="opsi-kemasan-ya"]')!;
      kemasan.click();
    });
    act(() => {
      const berat = wadah.querySelector<HTMLInputElement>('[data-testid="receipt-weight"]')!;
      const setter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value"
      )?.set;
      setter?.call(berat, "176,5");
      berat.dispatchEvent(new Event("input", { bubbles: true }));
    });

    expect(tombolSimpan().disabled).toBe(false);
    expect(wadah.querySelector('[data-testid="receipt-answer-progress"]')?.textContent).toContain(
      "2 dari 2 butir dijawab"
    );
  });

  it("menekan simpan memanggil jalur simpan, bukan menandai diterima", () => {
    const onSimpan = vi.fn();
    act(() => root.render(<Harness onSimpan={onSimpan} />));
    act(() => {
      tombolSimpan().click();
    });
    // Tombol disabled: klik tidak boleh menyimpan setengah isian.
    expect(onSimpan).not.toHaveBeenCalled();
  });

  it("peran tanpa izin mengisi tidak melihat formulir", () => {
    act(() =>
      root.render(
        <GoodsReceiptSheet
          baris={BARIS}
          catatan={CATATAN}
          bolehPutuskan={false}
          bolehIsi={false}
          checklist={CEKLIS as never}
          jawaban={{}}
          busy={false}
          galat={null}
          pesan={null}
        />
      )
    );
    expect(wadah.querySelector('[data-testid="receipt-check-form"]')).toBeNull();
    expect(wadah.querySelector('[data-testid="receipt-save-checklist"]')).toBeNull();
  });
});
