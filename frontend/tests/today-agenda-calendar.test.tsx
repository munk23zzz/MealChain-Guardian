// Agenda harian (desain ulang "Hari Ini", 2026-10-17). Grid bulan besar
// DIHAPUS dari kartu atas permintaan pemilik — "hapus untuk kalender agenda yang
// bukan pop up, namun untuk informasinya tetap di pakai". Jadi kontrak kartu ini
// sekarang:
// - TIDAK ada grid 42 sel di kartu (`role="grid"`/`data-date` hanya hidup di
//   dalam popup pemilih tanggal) — kartu tidak lagi meminta rentang bulan penuh
//   hanya untuk menggambar sel;
// - kepala kartu menyisakan: ikon kecil pemilih tanggal (popup), tombol ‹ › yang
//   memindahkan SATU HARI, dan "Hari ini";
// - tombol langkah hari MATI di tepi rentang data (bukan membawa pengguna ke
//   hari kosong tanpa penjelasan);
// - panel hari memakai `agendaRows` yang dikelompokkan: bagian tanpa catatan
//   menulis "tidak ada catatan", TIDAK PERNAH "0 porsi"/"0 kg".
//
// Komponen ini TIDAK memanggil API: data datang lewat props dari halaman
// (pola React Query repo — lihat tests/agenda-wiring.test.tsx).

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import TodayAgendaCalendar from "../components/TodayAgendaCalendar";

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
  scope: { location_id: "23e6e766-524c-445e-abda-6175d56878b0", national: false },
  computed_at: "2026-10-16T17:00:00+00:00",
  days: [HARI],
};

const PICKER = {
  open: false,
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
};

function render(overrides: Record<string, unknown> = {}) {
  const props: any = {
    agenda: PAYLOAD,
    selected: "2026-10-20",
    today: "2026-10-17",
    onSelect: () => {},
    onShiftDay: () => {},
    prevDisabled: false,
    nextDisabled: false,
    onRetry: () => {},
    picker: PICKER,
    ...overrides,
  };
  return renderToStaticMarkup(<TodayAgendaCalendar {...props} />);
}

describe("agenda harian — grid bulan sudah TIDAK ada di kartu", () => {
  it("tidak merender satu sel pun dan tidak memakai peran grid", () => {
    const html = render();
    expect((html.match(/data-date=/g) ?? []).length).toBe(0);
    expect(html).not.toContain('role="grid"');
    expect(html).not.toContain("agenda-cell");
    expect(html).not.toContain("agenda-weekday");
  });

  it("kartu menyebut dirinya agenda harian, bukan kalender bulan", () => {
    const html = render();
    expect(html).toContain("Agenda harian");
    expect(html).not.toContain("Kalender agenda");
  });

  it("bulan yang sedang dibuka tetap terbaca di kepala (tanpa perlu membuka popup)", () => {
    expect(render()).toContain("Oktober 2026");
  });
});

describe("kepala kartu — pemilih tanggal + langkah hari", () => {
  it("ikon kecil pemilih tanggal membuka popup, bukan teks mati", () => {
    const html = render();
    expect(html).toContain("agenda-month-btn");
    expect(html).toMatch(/aria-haspopup="dialog"/);
    expect(html).toMatch(/aria-expanded="false"/);
    expect(html).toMatch(/<svg[^>]*aria-hidden="true"/);
  });

  it("tombol ‹ › memindahkan SATU HARI, bukan satu bulan", () => {
    const html = render();
    expect(html).toContain('aria-label="Hari sebelumnya"');
    expect(html).toContain('aria-label="Hari berikutnya"');
    expect(html).not.toContain('aria-label="Bulan sebelumnya"');
    expect(html).not.toContain('aria-label="Bulan berikutnya"');
  });

  it("kedua tombol langkah hari terlihat, dengan bulan tetap jadi konteks pilihan", () => {
    const html = render();
    const posisiTanda = html.indexOf("Hari sebelumnya");
    const posisiPemicu = html.indexOf("agenda-month-btn");
    const posisiTandaBerikut = html.indexOf("Hari berikutnya");
    expect(posisiTanda).toBeLessThan(posisiPemicu);
    expect(posisiPemicu).toBeLessThan(posisiTandaBerikut);
  });

  it("di tepi rentang data, tombolnya MATI (bukan membawa ke hari kosong)", () => {
    const kiri = render({ prevDisabled: true });
    expect(kiri).toMatch(/aria-label="Hari sebelumnya"[^>]*disabled/);
    const kanan = render({ nextDisabled: true });
    expect(kanan).toMatch(/aria-label="Hari berikutnya"[^>]*disabled/);
  });

  it("tombol 'Hari ini' tetap ada untuk kembali ke hari berjalan", () => {
    const html = render();
    expect(html).toContain("Hari ini");
  });
});

describe("kalender agenda — panel hari terpilih", () => {
  it("menulis nilai yang ada dan 'tidak ada catatan' untuk yang kosong", () => {
    const html = render();
    expect(html).toContain("Rencana menu");
    expect(html).toContain("1.200 porsi");
    expect(html).toContain("tidak ada catatan");
    // Aturan anti-angka-palsu: tak boleh ada nol yang tampak terukur. Batas kata
    // dipakai karena "1.200 porsi" MENGANDUNG teks "0 porsi".
    expect(html).not.toMatch(/(?:^|>|\s)0 porsi/);
    expect(html).not.toMatch(/(?:^|>|\s)0 kg/);
  });

  it("menyebut hari terpilih dalam bahasa Indonesia", () => {
    const html = render();
    expect(html).toContain("Selasa, 20 Oktober 2026");
  });

  it("info hari itu dikelompokkan supaya bisa dipindai, bukan tujuh baris pipih", () => {
    const html = render();
    expect(html).toContain("Rencana &amp; pasokan");
    expect(html).toContain("Limbah &amp; kedaluwarsa");
    expect(html).toContain("Keputusan agen");
  });

  it("tanpa data sama sekali tetap jujur (bukan daftar nol)", () => {
    const html = render({
      agenda: { ...PAYLOAD, days: [] },
    });
    expect(html).toContain("tidak ada catatan");
    expect(html).not.toMatch(/(?:^|>|\s)0 porsi/);
  });

  it("galat ditampilkan apa adanya + tombol coba lagi", () => {
    const html = render({ agenda: null, error: "gagal memuat agenda" });
    expect(html).toContain("gagal memuat agenda");
    expect(html).toContain("Coba lagi");
  });
});
