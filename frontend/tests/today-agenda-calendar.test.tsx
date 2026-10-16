// Kalender agenda harian di tab "Hari Ini" (permintaan pemilik 2026-10-16).
//
// Kontrak tampilan yang dikunci:
// - grid bulan 42 sel (mulai Senin) + sel bulan pipi ditandai;
// - TEPAT SATU sel bertanda `aria-current="true"` (hari terpilih) — pembaca
//   layar butuh itu, dan tanpa penanda tegas "hari terpilih" cuma warna;
// - tiap sel membawa `data-activity` (jumlah bagian berisi) sebagai titik
//   penanda — inilah gunanya kalender: melihat hari mana yang ADA datanya;
// - panel hari memakai `agendaRows`: bagian tanpa catatan menulis
//   "tidak ada catatan", TIDAK PERNAH "0 porsi"/"0 kg" (aturan repo).
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

function render(overrides: Record<string, unknown> = {}) {
  const props: any = {
    agenda: PAYLOAD,
    year: 2026,
    month: 10,
    selected: "2026-10-20",
    onSelect: () => {},
    onShiftMonth: () => {},
    onRetry: () => {},
    ...overrides,
  };
  return renderToStaticMarkup(<TodayAgendaCalendar {...props} />);
}

describe("kalender agenda — grid", () => {
  it("merender 42 sel tanggal dan satu header bulan bahasa Indonesia", () => {
    const html = render();
    expect((html.match(/data-date=/g) ?? []).length).toBe(42);
    expect(html).toContain("Oktober 2026");
    expect(html).toContain("agenda-calendar");
  });

  it("menandai TEPAT SATU hari terpilih dengan aria-current", () => {
    const html = render();
    expect((html.match(/aria-current="true"/g) ?? []).length).toBe(1);
    expect(html).toMatch(/data-date="2026-10-20"[^>]*aria-current="true"/);
  });

  it("membawa titik penanda dari `activity` dan nol untuk hari tanpa catatan", () => {
    const html = render();
    expect(html).toMatch(/data-date="2026-10-20"[^>]*data-activity="1"/);
    // 20 Okt ada di payload; hari lain tak punya data → activity 0, tanpa angka karangan.
    expect(html).toMatch(/data-date="2026-10-21"[^>]*data-activity="0"/);
  });

  it("menandai sel di luar bulan agar mata tahu batas bulan", () => {
    const html = render();
    expect(html).toContain("agenda-cell-outer");
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
