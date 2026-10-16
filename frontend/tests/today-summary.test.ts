// Strip ringkasan "Hari Ini" (desain ulang 2026-10-17) — fungsi MURNI.
//
// Alasan strip ini ada (riset, lihat docs/verification/hari-ini-desain-ulang.md):
// halaman lama menaruh lima kartu berbobot SAMA, sehingga tidak ada yang bisa
// dilihat "dalam satu detik". Referensi operasional (shieldthemes.com, Jul 2025,
// "Designing operational dashboards people actually use") menetapkan hierarki:
// status dulu (3–5 indikator), lalu daftar pengecualian, lalu rincian.
//
// Kontrak yang dikunci di sini:
// - TEPAT lima tile, urutannya tetap (mata memakai urutan sebagai peta);
// - tiap tile tahu ke kartu mana ia melompat (`target`), jadi strip bukan hiasan;
// - nilai yang belum diketahui ditulis "—" dan nadanya "none" — tidak pernah
//   diklaim 0 (aturan repo: angka yang tampak terukur padahal tak ada data).
import { describe, expect, it } from "vitest";

import { batchExpiry, kpiPeriodLabel, ledgerSummary, pendingDecisions, shortageSummary, summaryTiles, updatedLabel } from "../lib/today";
import { ZONA_DEFAULT, zonaLabel } from "../lib/jam";

const NOW = new Date("2026-10-17T04:00:00Z");
const H = 3600000;
const iso = (ms: number) => new Date(NOW.getTime() + ms).toISOString();

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
];

const BATCHES = [
  { id: "b1", location: "Bandung", commodity: "telur", quantity_kg: 400, usable_until: iso(-3 * H) },
  { id: "b2", location: "Bogor", commodity: "telur", quantity_kg: 250, usable_until: iso(10 * H) },
];

const LOCATIONS = [
  { location: "Jakarta", region: "DKI Jakarta", status: "shortage", shortage_kg: 780 },
  { location: "Medan", region: "Sumatera Utara", status: "shortage", shortage_kg: 6 },
];

const LEDGER = { valid: true, blocks: 3301, head: "ae43179af0" };

function tiles(over: Record<string, unknown> = {}) {
  const decisions = over.decisions ?? DECISIONS;
  const batches = "batches" in over ? over.batches : BATCHES;
  const locations = over.locations ?? LOCATIONS;
  const metrics = "metrics" in over ? over.metrics : [
    { name: "A", unit: "percent", value: "1", state: "available" },
    { name: "B", unit: "percent", value: "2", state: "available" },
  ];
  const ledger = "ledger" in over ? over.ledger : LEDGER;
  return summaryTiles({
    pending: pendingDecisions(decisions, NOW),
    batch: batchExpiry(batches ?? [], NOW),
    batchLoaded: batches !== null,
    shortage: shortageSummary(locations),
    metrics: metrics as { value?: string | null }[] | null,
    ledger: ledgerSummary(ledger),
  });
}

describe("strip ringkasan — lima tile dengan urutan tetap", () => {
  it("mengembalikan lima tile: tindakan, batch, shortage, KPI, rantai audit", () => {
    const hasil = tiles();
    expect(hasil.map((t) => t.key)).toEqual(["action", "batches", "shortage", "kpi", "ledger"]);
    expect(hasil).toHaveLength(5);
  });

  it("tiap tile tahu ke kartu mana ia melompat (bukan hiasan)", () => {
    const hasil = tiles();
    expect(hasil.map((t) => t.target)).toEqual([
      "today-action",
      "today-batches",
      "today-shortage",
      "today-kpi",
      "today-ledger",
    ]);
  });

  it("label tile memakai istilah halaman, bukan singkatan baru", () => {
    expect(tiles().map((t) => t.label)).toEqual([
      "Menunggu tindakan",
      "Batch <48 jam",
      "Lokasi shortage",
      "KPI terisi",
      "Rantai audit",
    ]);
  });
});

describe("strip ringkasan — nada dari data, bukan dari harapan", () => {
  it("keputusan yang sudah lewat tenggat → nada bahaya, dan jumlahnya disebut", () => {
    const [action] = tiles();
    expect(action.value).toBe("2");
    expect(action.note).toContain("1 sudah lewat tenggat");
    expect(action.tone).toBe("danger");
  });

  it("tidak ada keputusan menunggu → nada aman, bukan bahaya", () => {
    const [action] = tiles({ decisions: [] });
    expect(action.value).toBe("0");
    expect(action.tone).toBe("ok");
  });

  it("batch: kedaluwarsa → bahaya; hanya mendekati → waspada; kosong → aman", () => {
    expect(tiles()[1].tone).toBe("danger");
    const hanyaSoon = tiles({ batches: [BATCHES[1]] });
    expect(hanyaSoon[1].tone).toBe("warn");
    expect(hanyaSoon[1].note).toContain("segera");
    const kosong = tiles({ batches: [] });
    expect(kosong[1].value).toBe("0");
    expect(kosong[1].tone).toBe("ok");
  });

  it("batch belum termuat: nilai '—' dan nada 'none' (tidak diklaim nol)", () => {
    const [tindakan, batchTile, ...sisa] = tiles({ batches: null });
    expect(tindakan.value).toBe("2");
    expect(batchTile.value).toBe("—");
    expect(batchTile.tone).toBe("none");
    expect(sisa).toHaveLength(3);
  });

  it("shortage: jumlah lokasi + total kg; nol ditulis apa adanya", () => {
    const shortageTile = tiles()[2];
    expect(shortageTile.value).toBe("2");
    expect(shortageTile.note).toContain("786 kg");
    expect(shortageTile.tone).toBe("warn");
    const tidakAda = tiles({ locations: [] })[2];
    expect(tidakAda.value).toBe("0");
    expect(tidakAda.note).toMatch(/tidak ada kekurangan/i);
  });

  it("KPI: 'terisi/total' dari metrics yang ada; belum ada jawaban → '—'", () => {
    const kpiTile = tiles()[3];
    expect(kpiTile.value).toBe("2/2");
    expect(kpiTile.tone).toBe("ok");
    const sebagian = tiles({
      metrics: [
        { name: "A", unit: "percent", value: "1", state: "available" },
        { name: "B", unit: "percent", value: null, state: "no_data" },
      ],
    })[3];
    expect(sebagian.value).toBe("1/2");
    expect(sebagian.tone).toBe("warn");
    const kosong = tiles({ metrics: null })[3];
    expect(kosong.value).toBe("—");
    expect(kosong.tone).toBe("none");
  });

  it("rantai audit: utuh → aman, terputus → bahaya, tanpa jawaban → '—'", () => {
    expect(tiles()[4].value).toBe("Rantai utuh");
    expect(tiles()[4].tone).toBe("ok");
    const putus = tiles({ ledger: { valid: false, broken_at: 12, blocks: 40 } })[4];
    expect(putus.value).toContain("terputus");
    expect(putus.tone).toBe("danger");
    const belum = tiles({ ledger: null })[4];
    expect(belum.value).toBe("—");
    expect(belum.tone).toBe("none");
  });
});

describe("label waktu di kepala halaman (desain ulang 2026-10-17)", () => {
  it("menulis kapan data diperbarui, memakai WIB — bukan zona perangkat pengguna", () => {
    // Referensi (shieldthemes.com): dashboard yang menampilkan data basi tanpa
    // memberi tahu kapan terakhir diperbarui lebih buruk daripada tanpa dashboard
    // — orang bertindak atas angka yang mereka sangka baru.
    expect(updatedLabel(new Date("2026-10-17T04:05:00Z"))).toBe("Diperbarui 11.05 WIB");
    expect(zonaLabel(ZONA_DEFAULT)).toBe("WIB");
  });

  it("periode KPI ditulis hanya bila kedua ujungnya ada di data", () => {
    expect(
      kpiPeriodLabel({
        start: "2026-10-16T04:05:00Z",
        end: "2026-10-17T04:05:00Z",
      }),
    ).toBe("Periode 16 Okt 11.05 → 17 Okt 11.05 WIB");
    expect(kpiPeriodLabel({ start: "2026-10-16T04:05:00Z" })).toBeNull();
    expect(kpiPeriodLabel(null)).toBeNull();
  });
});

