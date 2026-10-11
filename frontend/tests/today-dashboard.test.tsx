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

describe("kartu keputusan menunggu tindakan", () => {
  it("hanya menghitung yang actionable (rejected tidak ikut)", () => {
    const html = render();
    expect(html).toContain('<span class="today-count">2</span>');
    expect(html).not.toContain("d-ditolak");
  });

  it("menampilkan sisa waktu dari `now` yang diberikan", () => {
    const html = render();
    expect(html).toContain("Lewat 2 jam");
    expect(html).toContain("45 mnt lagi");
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
    expect(html).toContain("Agenda terdekat 45 mnt lagi · 1 sudah lewat tenggat");
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
    expect(html.indexOf("Jakarta")).toBeLessThan(html.indexOf("Medan"));
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
    expect(html).toContain("0,00 percent");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("belum ada data");
    expect(html).toContain("today-value-none");
  });

  it("belum ada jawaban /kpi: diakui, bukan dianggap nol", () => {
    const html = render({ kpi: null });
    expect(html).toContain("Belum ada jawaban /kpi untuk periode ini.");
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

describe("jam klien belum siap", () => {
  it("label waktu ditulis '—' supaya tidak ada selisih server/klien", () => {
    const html = render({ now: null });
    expect(html).toContain("today-due");
    expect(html).not.toContain("Lewat 2 jam");
  });
});
