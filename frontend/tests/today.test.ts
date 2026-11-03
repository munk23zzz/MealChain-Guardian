// Logika murni halaman "Hari Ini" (Langkah 3, arah Roy 2026-10-11): rekap
// operasional dari data NYATA. Semua fungsi menerima `now` agar hasilnya
// deterministic dan tidak ada selisih hidrasi server/klien.
//
// Aturan angka yang dipin di sini:
// - Nilai kosong/tidak diketahui ditulis "—", TIDAK PERNAH diganti 0.
// - Urutan keputusan: yang sudah lewat dulu (paling baru lewat), lalu yang
//   akan datang (paling dekat jatuh tempo).
// - Batch hanya masuk daftar kalau tanggalnya bisa dibaca — kalau tidak,
//   batch itu tidak diklaim kedaluwarsa maupun aman.
import { describe, expect, it } from "vitest";

import {
  DUE_SOON_HOURS,
  batchExpiry,
  dueLabel,
  freshnessLabel,
  ledgerSummary,
  pendingDecisions,
  shortageSummary,
} from "../lib/today";

const NOW = new Date("2026-10-11T04:00:00Z");
const iso = (offsetMs: number) => new Date(NOW.getTime() + offsetMs).toISOString();
const H = 60 * 60 * 1000;
const M = 60 * 1000;

function decision(over: Record<string, unknown> = {}) {
  return {
    decision_id: "d1",
    decision_type: "regional_balance",
    status: "pending_approval",
    quantity_kg: 600,
    expires_at: iso(2 * H),
    ...over,
  } as any;
}

describe("dueLabel — sisa/lewat waktu dalam bahasa manusia", () => {
  it("masa depan: jam, hari, dan menit", () => {
    expect(dueLabel(iso(3 * H), NOW)).toBe("3 jam lagi");
    expect(dueLabel(iso(2 * H + 6 * M), NOW)).toBe("2 jam 6 menit lagi");
    expect(dueLabel(iso(40 * M), NOW)).toBe("40 menit lagi");
    expect(dueLabel(iso(50 * H), NOW)).toBe("2 hari 2 jam lagi");
    expect(dueLabel(iso(48 * H), NOW)).toBe("2 hari lagi");
  });

  it("masa lalu memakai kata 'Lewat'", () => {
    expect(dueLabel(iso(-(2 * H + 5 * M)), NOW)).toBe("Lewat 2 jam 5 menit");
    expect(dueLabel(iso(-5 * H), NOW)).toBe("Lewat 5 jam");
    expect(dueLabel(iso(-26 * H), NOW)).toBe("Lewat 1 hari 2 jam");
  });

  it("kurang dari satu menit tetap terbaca manusia", () => {
    expect(dueLabel(iso(30 * 1000), NOW)).toBe("kurang dari 1 menit lagi");
    expect(dueLabel(iso(-30 * 1000), NOW)).toBe("Lewat kurang dari 1 menit");
  });

  it("tanggal tak terbaca tidak diklaim — ditulis '—'", () => {
    expect(dueLabel(null, NOW)).toBe("—");
    expect(dueLabel(undefined, NOW)).toBe("—");
    expect(dueLabel("", NOW)).toBe("—");
    expect(dueLabel("bukan-tanggal", NOW)).toBe("—");
  });
});

describe("pendingDecisions — yang menunggu tindakan manusia", () => {
  it("hanya status actionable; yang bukan diabaikan", () => {
    const items = [
      decision({ decision_id: "a", status: "pending_approval" }),
      decision({ decision_id: "b", status: "verifier_flagged" }),
      // Kuorum penuh tetap menuntut tindakan: Kepala SPPG harus menekan Eksekusi.
      decision({ decision_id: "c", status: "approved" }),
      decision({ decision_id: "d", status: "rejected" }),
      decision({ decision_id: "e", status: "proposed" }),
      decision({ decision_id: "f", status: "executed" }),
    ];
    const out = pendingDecisions(items, NOW);
    expect(out.count).toBe(3);
    expect(out.items.map((d: any) => d.decision_id)).toEqual(["a", "b", "c"]);
  });

  it("status dicocokkan tanpa peduli besar-kecil huruf", () => {
    const out = pendingDecisions([decision({ status: "Pending_Approval" })], NOW);
    expect(out.count).toBe(1);
  });

  it("urutan: sudah lewat dulu (paling baru lewat), lalu terdekat jatuh tempo", () => {
    const items = [
      decision({ decision_id: "akan-datang", expires_at: iso(2 * H) }),
      decision({ decision_id: "lewat-lama", expires_at: iso(-9 * H) }),
      decision({ decision_id: "lewat-baru", expires_at: iso(-1 * H) }),
    ];
    const out = pendingDecisions(items, NOW);
    expect(out.items.map((d: any) => d.decision_id)).toEqual([
      "lewat-baru",
      "lewat-lama",
      "akan-datang",
    ]);
    expect(out.overdueCount).toBe(2);
  });

  it("prioritas berikutnya = yang paling dekat jatuh tempo (bukan yang lewat)", () => {
    const out = pendingDecisions(
      [
        decision({ decision_id: "lewat", expires_at: iso(-3 * H) }),
        decision({ decision_id: "dekat", expires_at: iso(45 * M) }),
        decision({ decision_id: "jauh", expires_at: iso(30 * H) }),
      ],
      NOW
    );
    expect(out.nextDue).toBe(iso(45 * M));
    expect(out.nextDueLabel).toBe("45 menit lagi");
  });

  it("tanpa agenda berikutnya, label ditulis '—' (tidak dikarang)", () => {
    const out = pendingDecisions([decision({ expires_at: iso(-3 * H) })], NOW);
    expect(out.nextDue).toBeNull();
    expect(out.nextDueLabel).toBe("—");
    expect(out.overdueCount).toBe(1);
  });

  it("daftar kosong tetap aman", () => {
    const out = pendingDecisions([], NOW);
    expect(out).toMatchObject({ count: 0, overdueCount: 0, nextDue: null, nextDueLabel: "—" });
    expect(out.items).toEqual([]);
  });
});

describe("batchExpiry — kedaluwarsa vs segera", () => {
  const batch = (over: Record<string, unknown> = {}) => ({
    id: "b1",
    location: "Bandung",
    commodity: "telur",
    quantity_kg: 400,
    freshness_score: 0.69,
    usable_until: iso(10 * H),
    ...over,
  }) as any;

  it("memisahkan yang sudah lewat dan yang <48 jam", () => {
    const out = batchExpiry(
      [
        batch({ id: "expired", usable_until: iso(-2 * H), quantity_kg: 100 }),
        batch({ id: "soon", usable_until: iso(10 * H), quantity_kg: 200 }),
        batch({ id: "later", usable_until: iso(72 * H), quantity_kg: 400 }),
      ],
      NOW
    );
    expect(out.expired.map((b: any) => b.id)).toEqual(["expired"]);
    expect(out.dueSoon.map((b: any) => b.id)).toEqual(["soon"]);
    expect(out.expiredKg).toBe(100);
    expect(out.dueSoonKg).toBe(200);
  });

  it("urut menaik menurut usable_until", () => {
    const out = batchExpiry(
      [
        batch({ id: "b", usable_until: iso(20 * H) }),
        batch({ id: "a", usable_until: iso(4 * H) }),
      ],
      NOW
    );
    expect(out.dueSoon.map((b: any) => b.id)).toEqual(["a", "b"]);
  });

  it("tanggal tak terbaca tidak diklaim kedaluwarsa maupun aman", () => {
    const out = batchExpiry(
      [batch({ id: "x", usable_until: null }), batch({ id: "y", usable_until: "??" })],
      NOW
    );
    expect(out.expired).toEqual([]);
    expect(out.dueSoon).toEqual([]);
    expect(out.expiredKg).toBeNull();
    expect(out.dueSoonKg).toBeNull();
  });

  it("ambang 'segera' bisa diatur, default 48 jam", () => {
    expect(DUE_SOON_HOURS).toBe(48);
    const one = [batch({ id: "b", usable_until: iso(60 * H) })];
    expect(batchExpiry(one, NOW).dueSoon).toEqual([]);
    expect(batchExpiry(one, NOW, 72).dueSoon.map((b: any) => b.id)).toEqual(["b"]);
  });

  it("kuantitas tidak sah tidak dijumlahkan jadi angka palsu", () => {
    const out = batchExpiry(
      [batch({ id: "a", usable_until: iso(5 * H), quantity_kg: null })],
      NOW
    );
    expect(out.dueSoon).toHaveLength(1);
    expect(out.dueSoonKg).toBeNull();
  });
});

describe("freshnessLabel — skor 0..1 ke persen", () => {
  it("dibulatkan, tanpa desimal", () => {
    expect(freshnessLabel(0.69)).toBe("69%");
    expect(freshnessLabel(0.6949)).toBe("69%");
    expect(freshnessLabel(1)).toBe("100%");
    expect(freshnessLabel(0)).toBe("0%");
  });

  it("kosong/tidak masuk akal ditulis '—'", () => {
    expect(freshnessLabel(null)).toBe("—");
    expect(freshnessLabel(undefined)).toBe("—");
    expect(freshnessLabel(NaN)).toBe("—");
    expect(freshnessLabel("abc" as any)).toBe("—");
  });
});

describe("shortageSummary — lokasi yang kekurangan", () => {
  const row = (location: string, status: string, shortage_kg: number | null) => ({
    location,
    status,
    shortage_kg,
    region: "Jawa",
  });

  it("hanya status shortage, urut dari kekurangan terbesar", () => {
    const out = shortageSummary([
      row("Jakarta", "shortage", 780),
      row("Bandung", "surplus", null),
      row("Cianjur", "balanced", null),
      row("Medan", "shortage", 6),
      row("Surabaya", "shortage", 12),
    ]);
    expect(out.count).toBe(3);
    expect(out.items.map((r: any) => r.location)).toEqual(["Jakarta", "Surabaya", "Medan"]);
    expect(out.items[0].label).toBe("kurang 780 kg");
    expect(out.totalKg).toBe(798);
  });

  it("tanpa shortage: nol lokasi, total '—' (bukan 0)", () => {
    const out = shortageSummary([row("Bandung", "surplus", null)]);
    expect(out.count).toBe(0);
    expect(out.items).toEqual([]);
    expect(out.totalKg).toBeNull();
  });
});

describe("ledgerSummary — status rantai Merkle", () => {
  it("rantai utuh: jumlah blok + head disingkat", () => {
    const out = ledgerSummary({
      valid: true,
      blocks: 758,
      head: "0fb6bff271d50349f1d56722b4f9f078a48a776da143c7c23c6cf85e14abef12",
    });
    expect(out.ok).toBe(true);
    expect(out.statusLabel).toBe("Rantai utuh");
    expect(out.blocksLabel).toBe("758 blok");
    expect(out.headShort).toBe("0fb6bff271");
    expect(out.headFull).toBe("0fb6bff271d50349f1d56722b4f9f078a48a776da143c7c23c6cf85e14abef12");
  });

  it("rantai terputus menyebut blok yang gagal", () => {
    const out = ledgerSummary({ valid: false, blocks: 758, broken_at: 612 });
    expect(out.ok).toBe(false);
    expect(out.statusLabel).toBe("Rantai terputus di blok 612");
  });

  it("belum ada jawaban server: semua '—'", () => {
    const out = ledgerSummary(null);
    expect(out.ok).toBeNull();
    expect(out.statusLabel).toBe("—");
    expect(out.blocksLabel).toBe("—");
    expect(out.headShort).toBe("—");
  });
});
