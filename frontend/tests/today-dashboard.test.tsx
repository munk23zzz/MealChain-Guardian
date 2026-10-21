// Kontrak markup halaman "Hari Ini" (Langkah 3). Yang dipin di sini:
// - lima kartu ada (menunggu tindakan, batch, shortage, KPI, rantai audit);
// - angka datang dari data, nilai yang tidak diketahui ditulis "—";
// - jam sisa memakai `now` yang diberikan pemanggil (bukan jam perangkat);
// - tidak ada angka palsu 0 saat data kosong.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import TodayDashboard from "../components/TodayDashboard";

const NOW = new Date("2026-10-11T04:00:00Z");
const iso = (ms: number) => new Date(NOW.getTime() + ms).toISOString();
const H = 3600000;

const DECISIONS = [
  {
    decision_id: "d-lewat",
    decision_type: "safety_disruption",
    status: "pending_approval",
    quantity_kg: 600,
    expires_at: iso(-2 * H),
  },
  {
    decision_id: "d-dekat",
    decision_type: "regional_balance",
    status: "verifier_flagged",
    quantity_kg: 780,
    expires_at: iso(45 * 60 * 1000),
  },
  { decision_id: "d-ditolak", decision_type: "price_anomaly", status: "rejected", quantity_kg: 600 },
];

const BATCHES = [
  {
    id: "b-expired",
    location: "Bandung",
    commodity: "telur",
    quantity_kg: 400,
    freshness_score: 0.69,
    safety_status: "pass",
    usable_until: iso(-3 * H),
  },
  {
    id: "b-soon",
    location: "Bogor",
    commodity: "telur",
    quantity_kg: 250,
    freshness_score: 0.81,
    safety_status: "pass",
    usable_until: iso(10 * H),
  },
];

const LOCATIONS = [
  { location: "Jakarta", region: "DKI Jakarta", status: "shortage", shortage_kg: 780 },
  { location: "Medan", region: "Sumatera Utara", status: "shortage", shortage_kg: 6 },
  { location: "Bandung", region: "Jawa Barat", status: "surplus", shortage_kg: null },
];

const KPI = {
  metrics: [
    { name: "Regional Imbalance Resolution Rate", unit: "percent", value: "0.00", state: "available" },
    { name: "Meal Continuity Rate", unit: "percent", value: null, state: "no_data", reason: "belum ada menu plan" },
    { name: "Safe Delivered Cost", unit: "IDR", value: "16206000", state: "available" },
  ],
  period: { start: iso(-24 * H), end: iso(0) },
};

const LEDGER = { valid: true, blocks: 758, head: "0fb6bff271d50349f1d56722b4f9f078a48a776da143c7c23c6cf85e14abef12" };

function render(over: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <TodayDashboard
      decisions={DECISIONS as any}
      batches={BATCHES as any}
      locations={LOCATIONS as any}
      commodity="telur"
      kpi={KPI as any}
      ledger={LEDGER}
      now={NOW}
      {...over}
    />
  );
}

describe("halaman Hari Ini — struktur", () => {
  it("judul halaman + lima kartu rekap", () => {
    const html = render();
    expect(html).toContain("Hari Ini");
    expect(html).toContain("Menunggu tindakan");
    expect(html).toContain("Batch mendekati kedaluwarsa");
    expect(html).toContain("Lokasi shortage");
    expect(html).toContain("KPI 24 jam");
    expect(html).toContain("Rantai audit");
  });

  it("menyebut komoditas aktif di kepala halaman", () => {
    expect(render()).toContain("Komoditas telur");
  });
});

describe("kebersihan copy halaman Hari Ini", () => {
  it("deskripsi berbicara manfaat, bukan sumber API", () => {
    const html = render();
    expect(html).toContain("Apa yang perlu ditindak hari ini");
    expect(html).not.toContain("semua dari API");
  });

  it("tidak menampilkan path endpoint agenda", () => {
    const html = render({
      agenda: { days: [] },
      agendaDate: "2026-10-20",
      agendaMonth: { year: 2026, month: 10 },
      agendaPicker: {
        open: false,
        month: { year: 2026, month: 10 },
        years: [2026],
        agenda: null,
        loading: false,
        error: null,
        today: "2026-10-20",
        selected: "2026-10-20",
        onOpen: () => {},
        onClose: () => {},
        onShiftMonth: () => {},
        onSetMonth: () => {},
        onSelect: () => {},
        onToday: () => {},
        onRetry: () => {},
      },
    });
    expect(html).toContain("Rencana menu, pasokan, limbah, dan keputusan pada hari terpilih.");
    expect(html).not.toContain("GET /agenda");
  });

  it("rantai audit memakai istilah pengguna dan hash penuh hanya di tooltip", () => {
    const html = render();
    expect(html).toContain("Kode verifikasi");
    expect(html).not.toContain("Head hash");
    expect(html).toContain('title="0fb6bff271d50349f1d56722b4f9f078a48a776da143c7c23c6cf85e14abef12"');
  });

  it("jenis keputusan restoration diterjemahkan, bukan slug mentah", () => {
    const html = render({
      decisions: [
        {
          decision_id: "d-restorasi",
          decision_type: "supplier_exclusion_restoration",
          status: "pending_approval",
          quantity_kg: 120,
          expires_at: iso(2 * H),
        },
      ],
    });
    expect(html).toContain("Pemulihan status pemasok");
    expect(html).not.toContain("supplier exclusion restoration");
  });

  it("jumlah yang tidak tercatat diberi alasan, bukan '—' tanpa konteks", () => {
    const html = render({
      decisions: [
        {
          decision_id: "d-tanpa-jumlah",
          decision_type: "regional_balance",
          status: "pending_approval",
          quantity_kg: null,
          expires_at: iso(2 * H),
        },
      ],
    });
    expect(html).toContain("Jumlah tidak tercatat");
  });

  it("label KPI memakai bahasa Indonesia; nama asli tetap tersedia di tooltip", () => {
    const html = render();
    expect(html).toContain("Keberlanjutan menu");
    expect(html).toContain('title="Meal Continuity Rate"');
    expect(html).not.toContain(">Meal Continuity Rate<");
  });

  it("status 'tersedia' tidak diulang di setiap baris KPI", () => {
    const html = render();
    expect(html).not.toContain(">tersedia<");
    expect(html).toContain("belum ada data");
  });

  it("tombol membuka keputusan diberi kata kerja yang jelas", () => {
    const html = render({ onOpenDecision: () => {} });
    expect(html).toContain(">Tinjau</button>");
    expect(html).not.toContain(">Buka</button>");
  });
});

describe("kartu keputusan menunggu tindakan", () => {
  it("hanya menghitung yang actionable (rejected tidak ikut)", () => {
    const html = render();
    expect(html).toContain('<span class="today-count">2</span>');
    expect(html).not.toContain("d-ditolak");
  });

  it("menampilkan sisa waktu dari `now` yang diberikan", () => {
    const html = render();
    expect(html).toContain("Lewat 2 jam");
    expect(html).toContain("45 menit lagi");
  });

  it("baris batch menampilkan status keamanan yang dikirim server", () => {
    // /batches mengirim `safety_status`. Dulu komponen membaca
    // `food_safety_status` (tidak ada di backend) sehingga label ini selalu
    // hilang tanpa error apa pun.
    const html = render();
    expect(html).toContain("lolos uji");
  });

  it("menyebut agenda terdekat dan jumlah yang lewat tenggat", () => {
    const html = render();
    expect(html).toContain("Agenda terdekat 45 menit lagi · 1 sudah lewat tenggat");
  });

  it("tanpa agenda baru, dikatakan apa adanya (bukan '—')", () => {
    const html = render({
      decisions: [
        { decision_id: "d-lewat", decision_type: "regional_balance", status: "pending_approval", quantity_kg: 600, expires_at: iso(-3 * H) },
      ],
    });
    expect(html).toContain("Tidak ada agenda yang belum lewat tenggat");
  });

  it("daftar dipotong 6 baris, sisanya DINYATAKAN (bukan hilang diam-diam)", () => {
    const many = Array.from({ length: 9 }, (_, i) => ({
      decision_id: `d${i}`,
      decision_type: "regional_balance",
      status: "pending_approval",
      quantity_kg: 500,
      expires_at: iso((i + 1) * H),
    }));
    const html = render({ decisions: many, onOpenAllDecisions: () => {} });
    expect(html).toContain('<span class="today-count">9</span>');
    expect(html).toContain("+3 keputusan lain menunggu tindakan");
    expect(html).toContain("Lihat semua");
  });

  it("tanpa keputusan: nol tertulis apa adanya, bukan karangan", () => {
    const html = render({ decisions: [] });
    expect(html).toContain("Tidak ada keputusan yang menunggu tindakan manusia.");
    expect(html).toContain('<span class="today-count">0</span>');
  });
});

describe("kartu batch", () => {
  it("memisahkan kedaluwarsa dan segera, dengan kg dan kesegaran", () => {
    const html = render();
    expect(html).toContain("Kedaluwarsa 1 batch (400 kg)");
    expect(html).toContain("segera 1 batch (250 kg)");
    expect(html).toContain("kesegaran 69%");
    expect(html).toContain("kesegaran 81%");
    expect(html).toContain("lolos uji");
  });

  it("kelompok kosong tidak ditulis sebagai '0 batch (—)'", () => {
    const html = render({
      batches: [BATCHES[0]],
    });
    expect(html).toContain("Kedaluwarsa 1 batch (400 kg)");
    expect(html).not.toContain("segera 0 batch");
  });

  it("meta batch tidak menempelkan '—' saat kesegaran/uji tidak diketahui", () => {
    const html = render({
      batches: [
        { id: "b-null", location: "Bandung", commodity: "telur", quantity_kg: 400, freshness_score: null, safety_status: null, usable_until: iso(-2 * H) },
      ],
    });
    expect(html).toContain("400 kg");
    expect(html).not.toContain("kesegaran —");
    expect(html).not.toContain("· —");
  });

  it("lebih dari enam batch: sisanya DINYATAKAN, bukan hilang diam-diam", () => {
    const banyak = Array.from({ length: 9 }, (_, i) => ({
      id: `b${i}`,
      location: "Bandung",
      commodity: "telur",
      quantity_kg: 100,
      freshness_score: 0.9,
      safety_status: "pass",
      usable_until: iso(-(i + 1) * H),
    }));
    const html = render({ batches: banyak, onOpenBatches: () => {} });
    expect(html).toContain("<span class=\"today-count\">9</span>");
    expect(html).toContain("+3 batch lain mendekati kedaluwarsa");
    expect(html).toContain(">Lihat semua</button>");
  });

  it("data batch belum ada: '—' dan tidak diklaim kosong", () => {
    const html = render({ batches: null, batchesLoading: true });
    expect(html).toContain("Memuat data batch…");
    expect(html).toContain('<span class="today-count">—</span>');
  });

  it("gagal memuat: pesan galat + tombol coba lagi", () => {
    const html = render({ batchesError: "HTTP 500", onRetry: () => {} });
    expect(html).toContain("Gagal memuat batch: HTTP 500");
    expect(html).toContain("Coba lagi");
  });
});

describe("kartu lokasi shortage", () => {
  it("hanya shortage, urut dari terbesar, total dijumlahkan", () => {
    const html = render();
    expect(html).toContain('<span class="today-count">2</span>');
    expect(html).toContain("Total kekurangan 786 kg");
    expect(html).toContain("kurang 780 kg");
    expect(html.indexOf("JKT")).toBeLessThan(html.indexOf("MDN"));
  });

  it("lebih dari 6 lokasi: sisanya dinyatakan, bukan disembunyikan", () => {
    const rows = Array.from({ length: 8 }, (_, i) => ({
      location: `Lokasi ${i + 1}`,
      region: "Jawa",
      status: "shortage",
      shortage_kg: 100 - i,
    }));
    const html = render({ locations: rows });
    expect(html).toContain('<span class="today-count">8</span>');
    expect(html).toContain("+2 lokasi lain kekurangan");
  });

  it("tanpa shortage: pesan jelas, bukan angka 0 palsu", () => {
    const html = render({ locations: [LOCATIONS[2]] });
    expect(html).toContain("Tidak ada lokasi kekurangan untuk komoditas ini.");
    expect(html).toContain('<span class="today-count">0</span>');
  });
});

describe("kartu KPI", () => {
  it("nilai tersedia diformat, yang belum ada ditulis '—'", () => {
    const html = render();
    expect(html).toContain("2/3");
    expect(html).toContain("0,00 persen");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("belum ada data");
    expect(html).toContain("today-value-none");
  });

  it("semua metrik terisi: dikatakan utuh, bukan peringatan generik", () => {
    const html = render({
      kpi: {
        metrics: [
          { name: "Meal Continuity Rate", unit: "percent", value: "100", state: "available" },
          { name: "Safe Delivered Cost", unit: "IDR", value: "16206000", state: "available" },
        ],
      },
    });
    expect(html).toContain("Semua metrik tersedia untuk periode ini.");
    expect(html).not.toContain("Sebagian metrik belum tersedia");
  });

  it("belum ada jawaban KPI: diakui, bukan dianggap nol", () => {
    const html = render({ kpi: null });
    expect(html).toContain("Belum ada data KPI untuk periode ini.");
    expect(html).not.toContain("/kpi");
  });
});

describe("kartu rantai audit", () => {
  it("rantai utuh: status, jumlah blok, head disingkat", () => {
    const html = render();
    expect(html).toContain("Rantai utuh");
    expect(html).toContain("758 blok");
    expect(html).toContain("0fb6bff271");
  });

  it("belum ada jawaban: semua '—'", () => {
    const html = render({ ledger: null });
    expect(html).toContain("today-badge-unknown");
    expect(html).toContain("—");
  });
});

describe("sapaan header + nada sisa waktu (Fase 6)", () => {
  it("sapaan memakai jam klien + nama peran; tanpa jam, tidak menyapa (tidak menebak waktu)", () => {
    const html = render({ greetingName: "SPPG Operations Lead" });
    expect(html).toContain("page-header-eyebrow");
    expect(html).toMatch(/Selamat (pagi|siang|sore|malam), SPPG Operations Lead/);
    const tanpaJam = render({ greetingName: "SPPG Operations Lead", now: null });
    expect(tanpaJam).not.toContain("Selamat ");
    expect(tanpaJam).not.toContain("page-header-eyebrow");
  });

  it("tanpa nama peran: sapaan tetap jujur (tanpa koma menggantung)", () => {
    const html = render();
    expect(html).toMatch(/Selamat (pagi|siang|sore|malam)</);
    expect(html).not.toContain("Selamat pagi, <");
  });

  it("chip sisa waktu: lewat = merah, ≤48 jam = amber, jauh = netral", () => {
    const html = render();
    // d-lewat (2 jam lewat) dan batch kedaluwarsa → over; d-dekat (45 menit) dan
    // batch 10 jam lagi → soon (ambang 48 jam yang sudah dipakai halaman ini).
    expect(html).toContain("today-due-over");
    expect(html).toContain("today-due-soon");

    const jauh = render({
      decisions: [
        { decision_id: "d-jauh", decision_type: "regional_balance", status: "pending_approval", quantity_kg: 100, expires_at: iso(72 * H) },
      ],
      batches: [],
      locations: [],
    });
    expect(jauh).toContain("today-due");
    expect(jauh).not.toContain("today-due-soon");
    expect(jauh).not.toContain("today-due-over");
  });

  it("jam belum siap → tanpa amber/merah (keadaan tidak diklaim)", () => {
    const html = render({ now: null });
    expect(html).not.toContain("today-due-soon");
    expect(html).not.toContain("today-due-over");
  });
});

describe("jam klien belum siap", () => {
  it("label waktu ditulis '—' supaya tidak ada selisih server/klien", () => {
    const html = render({ now: null });
    expect(html).toContain("today-due");
    expect(html).not.toContain("Lewat 2 jam");
  });
});

const PICKER = {
  open: false,
  month: { year: 2026, month: 10 },
  years: [2026, 2027],
  agenda: null,
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

const denganAgenda = { agendaDate: "2026-10-20", agendaMonth: { year: 2026, month: 10 }, agendaPicker: PICKER };

describe("susunan halaman setelah desain ulang (2026-10-17)", () => {
  it("tiap kartu punya id tetap — id inilah sasaran lompatan strip ringkasan", () => {
    const html = render(denganAgenda);
    for (const id of ["today-action", "today-agenda", "today-batches", "today-shortage", "today-kpi", "today-ledger"]) {
      expect(html).toContain(`id="${id}"`);
    }
  });

  it("strip ringkasan berdiri paling atas, sebelum kartu pertama", () => {
    // Referensi: status dulu dalam satu detik pandang, baru rincian.
    const html = render(denganAgenda);
    expect(html).toContain("today-summary");
    expect(html.indexOf("today-summary")).toBeLessThan(html.indexOf('id="today-action"'));
  });

  it("daftar pengecualian lebih dulu, agenda harian menyusul", () => {
    // Referensi (shieldthemes.com, Jul 2025): daftar pengecualian adalah bagian
    // yang paling sering dipakai, jadi ia tidak boleh tenggelam di bawah.
    const html = render(denganAgenda);
    expect(html.indexOf('id="today-action"')).toBeLessThan(html.indexOf('id="today-agenda"'));
  });

  it("empat kartu rincian duduk dalam satu bento dua kolom di bawah", () => {
    const html = render(denganAgenda);
    expect(html).toContain("today-detail-grid");
    const mulai = html.indexOf("today-detail-grid");
    expect(mulai).toBeGreaterThan(html.indexOf('id="today-agenda"'));
    for (const id of ["today-batches", "today-shortage", "today-kpi", "today-ledger"]) {
      expect(html.indexOf(`id="${id}"`)).toBeGreaterThan(mulai);
    }
  });

  it("kartu tinggi berpasangan dan kartu pendek berpasangan (tanpa sel menganga)", () => {
    // Dulu urutannya batches-shortage-kpi-ledger: baris pertama setinggi 436 px
    // sedangkan kartu shortage cuma 148 px, baris kedua 479 px vs ledger 133 px
    // — sekitar 630 px ruang kosong di dalam grid. Sekarang kartu tinggi
    // (batches, kpi) berbagi baris pertama dan kartu pendek (shortage, ledger)
    // baris kedua, sehingga sisa kosong tiap sel tinggal beberapa puluh px.
    const html = render(denganAgenda);
    const posisi = ["today-batches", "today-kpi", "today-shortage", "today-ledger"].map((id) =>
      html.indexOf(`id="${id}"`)
    );
    expect(posisi.every((n) => n > 0)).toBe(true);
    expect([...posisi].sort((a, b) => a - b)).toEqual(posisi);
  });

  it("agenda harian hanya dirender bila halaman mengirim state kalender", () => {
    expect(render()).not.toContain("Agenda harian");
    expect(render(denganAgenda)).toContain("Agenda harian");
  });

  it("kepala halaman menyebut kapan data diperbarui (memakai jam WIB)", () => {
    const html = render(denganAgenda);
    expect(html).toContain("Diperbarui 11.00 WIB");
    // Jam belum siap → tidak menulis label dengan angka karangan.
    expect(render({ ...denganAgenda, now: null })).not.toContain("Diperbarui");
  });
});
