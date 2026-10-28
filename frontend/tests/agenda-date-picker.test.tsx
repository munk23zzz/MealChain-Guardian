// @vitest-environment jsdom
// Popup pemilih tanggal (permintaan pemilik 2026-10-17) — kalender lama hanya
// punya tombol ‹ › dan judul bulan yang mati, jadi dari Okt 2026 ke Okt 2025
// butuh 12 klik. Kontrak yang dikunci:
// - pemicunya tombol di header kartu (ikon + "Oktober 2026"), bukan teks mati;
// - popup = `role="dialog"` berisi dropdown Bulan (12 bulan Indonesia) dan
//   Tahun (daftar dari rentang data), plus grid hari yang BISA DIKLIK;
// - memilih tanggal hanya memberi tahu halaman (`onSelect`) — popup mana yang
//   menutup adalah urusan halaman, karena bulan & hari terpilih milik halaman;
// - saat bulan draft sedang dimuat, popup menulis status memuat, BUKAN grid
//   kosong yang terbaca sebagai "bulan ini tidak punya catatan";
// - fokus kembali ke pemicu saat popup ditutup (bukan ke awal dokumen).

import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";

import AgendaDatePicker, { type AgendaPickerProps } from "../components/AgendaDatePicker";

const HARI = {
  date: "2026-10-20",
  menu: { rows: 1, planned_portions: 1200, available: true },
  delivery: { rows: 0, delivered_portions: 0, available: false },
  disposal: { rows: 0, quantity_kg: 0, available: false },
  supply: { rows: 0, available: false },
  price: { rows: 0, available: false },
  batches_expiring: { rows: 0, available: false },
  decisions: { rows: 0, by_status: {}, available: false },
  activity: 1,
};

const PAYLOAD = {
  period: { start: "2026-09-28", end: "2026-11-08", timezone: "Asia/Jakarta" },
  computed_at: "2026-10-16T17:00:00+00:00",
  days: [HARI],
};

let root: Root;
let host: HTMLDivElement;

function mount(overrides: Partial<AgendaPickerProps> = {}) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  const props: AgendaPickerProps = {
    open: true,
    month: { year: 2026, month: 10 },
    years: [2026, 2027],
    agenda: PAYLOAD,
    loading: false,
    error: null,
    today: "2026-10-17",
    selected: "2026-10-20",
    onOpen: () => {},
    onClose: () => {},
    onShiftMonth: () => {},
    onSetMonth: () => {},
    onSelect: () => {},
    onToday: () => {},
    onRetry: () => {},
    ...overrides,
  };
  act(() => root.render(<AgendaDatePicker {...props} />));
  return props;
}

function rerender(props: AgendaPickerProps) {
  act(() => root.render(<AgendaDatePicker {...props} />));
}

const dialog = () => document.querySelector<HTMLElement>('[role="dialog"]');
const cells = () => document.querySelectorAll<HTMLElement>("[data-date]");
const select = (label: string) =>
  document.querySelector<HTMLSelectElement>(`select[aria-label="${label}"]`);
const buttonByText = (text: string) =>
  Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(
    (b) => b.textContent?.trim() === text
  );

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  vi.unstubAllGlobals();
});

describe("popup pemilih tanggal — tertutup vs terbuka", () => {
  it("tertutup → tidak merender dialog maupun sel tanggal", () => {
    mount({ open: false });
    expect(dialog()).toBeNull();
    expect(cells()).toHaveLength(0);
  });

  it("terbuka → dialog modal berjudul 'Pilih tanggal'", () => {
    mount();
    expect(dialog()).not.toBeNull();
    expect(dialog()?.getAttribute("aria-modal")).toBe("true");
    expect(dialog()?.textContent).toContain("Pilih tanggal");
  });
});

describe("popup pemilih tanggal — pilih bulan & tahun", () => {
  it("dropdown Bulan berisi 12 bulan Indonesia dengan bulan aktif terpilih", () => {
    mount();
    const bulan = select("Bulan");
    expect(bulan).not.toBeNull();
    expect(Array.from(bulan!.options).map((o) => o.textContent)).toEqual([
      "Januari", "Februari", "Maret", "April", "Mei", "Juni",
      "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]);
    expect(bulan!.value).toBe("10");
  });

  it("dropdown Tahun memakai daftar dari halaman, tahun aktif terpilih", () => {
    mount();
    const tahun = select("Tahun");
    expect(Array.from(tahun!.options).map((o) => o.value)).toEqual(["2026", "2027"]);
    expect(tahun!.value).toBe("2026");
  });

  it("mengganti bulan → onSetMonth dengan tahun yang sama", () => {
    const onSetMonth = vi.fn();
    mount({ onSetMonth });
    act(() => {
      const bulan = select("Bulan")!;
      bulan.value = "9";
      bulan.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(onSetMonth).toHaveBeenCalledWith({ year: 2026, month: 9 });
  });

  it("mengganti tahun → onSetMonth dengan bulan yang sama", () => {
    const onSetMonth = vi.fn();
    mount({ onSetMonth });
    act(() => {
      const tahun = select("Tahun")!;
      tahun.value = "2027";
      tahun.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(onSetMonth).toHaveBeenCalledWith({ year: 2027, month: 10 });
  });

  it("tombol ‹ › menggeser bulan satu langkah", () => {
    const onShiftMonth = vi.fn();
    mount({ onShiftMonth });
    act(() => {
      document.querySelector<HTMLButtonElement>('[aria-label="Bulan sebelumnya"]')!.click();
      document.querySelector<HTMLButtonElement>('[aria-label="Bulan berikutnya"]')!.click();
    });
    expect(onShiftMonth).toHaveBeenNthCalledWith(1, -1);
    expect(onShiftMonth).toHaveBeenNthCalledWith(2, 1);
  });
});

describe("popup pemilih tanggal — grid hari", () => {
  it("42 sel, satu hari terpilih, titik penanda dari `activity`", () => {
    mount();
    expect(cells()).toHaveLength(42);
    expect(document.querySelectorAll('[aria-current="true"]')).toHaveLength(1);
    expect(
      document.querySelector('[data-date="2026-10-20"]')?.getAttribute("aria-current")
    ).toBe("true");
    expect(
      document.querySelector('[data-date="2026-10-20"]')?.getAttribute("data-activity")
    ).toBe("1");
    // Hari tanpa catatan: nol titik, bukan angka karangan.
    expect(
      document.querySelector('[data-date="2026-10-21"]')?.getAttribute("data-activity")
    ).toBe("0");
  });

  it("tiap sel punya nama aksesibel bertanggal lengkap", () => {
    mount();
    expect(
      document.querySelector('[data-date="2026-10-20"]')?.getAttribute("aria-label")
    ).toContain("Selasa, 20 Oktober 2026");
  });

  it("klik tanggal → onSelect dengan tanggal itu saja", () => {
    const onSelect = vi.fn();
    mount({ onSelect });
    act(() => {
      document.querySelector<HTMLButtonElement>('[data-date="2026-10-20"]')!.click();
    });
    expect(onSelect).toHaveBeenCalledWith("2026-10-20");
  });
});

describe("popup pemilih tanggal — keadaan memuat & galat", () => {
  it("bulan draft sedang dimuat → status memuat, bukan grid kosong", () => {
    mount({ agenda: null, loading: true });
    expect(cells()).toHaveLength(0);
    expect(dialog()?.textContent).toContain("Memuat agenda");
    // Tidak boleh ada klaim "tidak ada catatan" untuk bulan yang belum termuat.
    expect(dialog()?.textContent).not.toContain("tidak ada catatan");
  });

  it("galat dimuat apa adanya + tombol coba lagi", () => {
    const onRetry = vi.fn();
    mount({ agenda: null, loading: false, error: "gagal memuat agenda", onRetry });
    expect(dialog()?.textContent).toContain("gagal memuat agenda");
    act(() => buttonByText("Coba lagi")!.click());
    expect(onRetry).toHaveBeenCalled();
  });
});

describe("popup pemilih tanggal — aksi", () => {
  it("tombol 'Hari ini' memberi tahu halaman tanpa menutup sendiri", () => {
    const onToday = vi.fn();
    mount({ onToday });
    act(() => buttonByText("Hari ini")!.click());
    expect(onToday).toHaveBeenCalled();
  });

  it("X di kepala popup menutup popup — kaki tidak lagi punya 'Tutup' kedua", () => {
    // 29 Okt 2026: semua penutup jadi X bulat. Tombol teks "Tutup" di kaki
    // dialog dibuang karena popup ini sudah punya X di kepalanya; dua kontrol
    // untuk satu hal di satu layar hanya membuat orang memilih.
    const onClose = vi.fn();
    mount({ onClose });
    expect(buttonByText("Tutup")).toBeUndefined();
    const x = document.querySelector<HTMLButtonElement>('[aria-label="Tutup jendela"]');
    expect(x).toBeTruthy();
    act(() => x!.click());
    expect(onClose).toHaveBeenCalled();
  });

  it("fokus dikembalikan ke pemicu saat popup ditutup", () => {
    // Pemicunya tombol di header kartu, di LUAR dialog — tanpa ini, pengguna
    // keyboard yang menutup popup kembali ke awal dokumen.
    const trigger = document.createElement("button");
    trigger.textContent = "Oktober 2026";
    document.body.append(trigger);
    const ref = { current: trigger } as { current: HTMLButtonElement | null };
    const props = mount({ returnFocusRef: ref as never });
    rerender({ ...props, open: false });
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
