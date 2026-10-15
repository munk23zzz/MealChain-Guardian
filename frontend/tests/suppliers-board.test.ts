// Kontrak halaman "Pemasok" (halaman sidebar acuan /suppliers).
//
// Fase 3 (2026-10-14): daftarnya TIDAK lagi disusun dari pemasok yang kebetulan
// muncul pada sampel keputusan — backend sekarang punya `GET /suppliers`
// (Fase 2), jadi halaman memakai sumber itu apa adanya: seluruh pemasok di
// jaringan, bukan "pemasok yang terlihat pada N keputusan terakhir".
import { describe, expect, it } from "vitest";

import {
  directoryMetrics,
  directoryReachLabel,
  directoryReachSummary,
  exclusionRows,
  filterDirectoryByReach,
  reliabilityLabel,
  supplierDirectory,
} from "../lib/suppliers-board";

const ITEMS = {
  count: 4,
  total: 4,
  items: [
    {
      id: "s1",
      name: "Wortel Lestari Cianjur",
      location: "Cianjur",
      commodity: "wortel",
      certification_status: "haccp",
      reliability_score: 0.93,
      latitude: -6.824,
      longitude: 107.1636,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "s2",
      name: "Telur Berkah Cianjur",
      location: "Cianjur",
      commodity: "telur",
      certification_status: "none",
      reliability_score: 0.38,
      latitude: -6.811,
      longitude: 107.1636,
      excluded_at_hub: true,
      excluded_scope_locations: ["Cianjur", "Jakarta"],
    },
    {
      id: "s3",
      name: "Supplier A Cianjur",
      location: "Cianjur",
      commodity: null,
      certification_status: null,
      reliability_score: "0.80",
      latitude: -6.854,
      longitude: 107.1306,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "s4",
      name: "Pemasok Tanpa Profil",
      location: "Medan",
      commodity: "ayam",
      certification_status: "hygiene",
      reliability_score: null,
      latitude: null,
      longitude: null,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
  ],
};

describe("reliabilityLabel", () => {
  it("skor 0..1 jadi persen, kosong jadi '—'", () => {
    expect(reliabilityLabel(0.8)).toBe("80%");
    expect(reliabilityLabel("0.65")).toBe("65%");
    expect(reliabilityLabel(null)).toBe("—");
    expect(reliabilityLabel("bukan angka")).toBe("—");
  });
});

describe("supplierDirectory", () => {
  it("memetakan payload GET /suppliers ke baris tabel (hub, komoditas, sertifikat, koordinat)", () => {
    const rows = supplierDirectory(ITEMS);
    expect(rows).toHaveLength(4);
    const wortel = rows.find((r) => r.name === "Wortel Lestari Cianjur")!;
    expect(wortel).toMatchObject({
      hub: "Cianjur",
      commodity: "wortel",
      reliabilityLabel: "93%",
      certification: "HACCP",
      coordinates: "-6,8240 / 107,1636",
      excluded: false,
    });
  });

  it("data yang tidak ada ditulis '—', dan enum internal tidak pernah tampil", () => {
    const rows = supplierDirectory(ITEMS);
    const tanpaProfil = rows.find((r) => r.name === "Pemasok Tanpa Profil")!;
    expect(tanpaProfil.commodity).toBe("ayam");
    expect(tanpaProfil.certification).toBe("Higienis"); // bukan "hygiene"
    expect(tanpaProfil.reliabilityLabel).toBe("—");
    expect(tanpaProfil.coordinates).toBe("—");

    const kanonik = rows.find((r) => r.name === "Supplier A Cianjur")!;
    expect(kanonik.commodity).toBe("—");
    expect(kanonik.certification).toBe("—");
    // "none" = tidak bersertifikat (informasi nyata), bukan "—".
    expect(rows.find((r) => r.name === "Telur Berkah Cianjur")!.certification).toBe(
      "Tidak bersertifikat"
    );
    const labels = rows.map((r) => r.certification).join(" ");
    expect(labels).not.toContain("hygiene");
    expect(labels).not.toContain("haccp");
    expect(labels).not.toContain("none");
  });

  it("diurutkan risiko dulu: dikecualikan → skor terendah → terbaik → tanpa skor", () => {
    expect(supplierDirectory(ITEMS).map((r) => r.name)).toEqual([
      "Telur Berkah Cianjur", // dikecualikan (0,38)
      "Supplier A Cianjur", // 80%
      "Wortel Lestari Cianjur", // 93%
      "Pemasok Tanpa Profil", // skor tidak diketahui → terakhir
    ]);
  });

  it("urutan tidak bergantung urutan kedatangan dari API", () => {
    const reversed = { ...ITEMS, items: [...ITEMS.items].reverse() };
    expect(supplierDirectory(reversed).map((r) => r.name)).toEqual(
      supplierDirectory(ITEMS).map((r) => r.name)
    );
  });

  it("membawa status eksklusi apa adanya (lokal-cakupan, bukan nasional)", () => {
    const telur = supplierDirectory(ITEMS).find((r) => r.name === "Telur Berkah Cianjur")!;
    expect(telur.excluded).toBe(true);
    expect(telur.excludedScopes).toEqual(["Cianjur", "Jakarta"]);
  });

  it("tahan payload aneh", () => {
    expect(supplierDirectory(null)).toEqual([]);
    expect(supplierDirectory({ items: [] })).toEqual([]);
    expect(supplierDirectory([{ id: "x" }])).toEqual([]); // tanpa nama → dilewati
  });
});

describe("directoryMetrics", () => {
  it("ringkasan jujur: rata-rata hanya dari skor yang ada, koordinat dihitung", () => {
    const metrics = directoryMetrics(supplierDirectory(ITEMS));
    expect(metrics.suppliers).toBe(4);
    // (0,93 + 0,38 + 0,80) / 3 — pemasok tanpa skor tidak dianggap 0.
    expect(metrics.avgReliabilityLabel).toBe("70%");
    expect(metrics.lowReliability).toBe(1);
    expect(metrics.excluded).toBe(1);
    expect(metrics.withCoordinates).toBe(3);
  });

  it("tanpa data: rata-rata '—', bukan 0%", () => {
    const metrics = directoryMetrics([]);
    expect(metrics).toMatchObject({ suppliers: 0, lowReliability: 0, withCoordinates: 0 });
    expect(metrics.avgReliabilityLabel).toBe("—");
  });
});

describe("exclusionRows", () => {
  it("membaca register eksklusi dari endpoint", () => {
    const rows = exclusionRows([
      { id: "e1", supplier_name: "Supplier C Jakarta", reason: "dua kiriman suhu menyimpang", excluded_at: "2026-10-11T02:00:00Z", decision_id: "d9", status: "excluded" },
    ]);
    expect(rows[0]).toMatchObject({
      supplier: "Supplier C Jakarta",
      reason: "dua kiriman suhu menyimpang",
      decisionId: "d9",
      status: "excluded",
    });
  });

  it("daftar kosong → tidak ada baris (halaman menjelaskan keadaannya)", () => {
    expect(exclusionRows({ items: [], count: 0 })).toEqual([]);
    expect(exclusionRows(null)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Fase 7b (2026-10-15) — kolom Jarak + penyaring jangkauan di halaman Pemasok
// ---------------------------------------------------------------------------

const JARAK = {
  count: 4,
  total: 4,
  distance_reference: { location: "Jakarta", latitude: -6.2088, longitude: 106.8456 },
  reach: { max_distance_km: 150, excluded_out_of_reach: 0, excluded_unknown_distance: 0 },
  items: [
    {
      id: "j1",
      name: "Sayur Segar Kramat Jati",
      location: "Jakarta",
      commodity: "telur",
      reliability_score: 0.88,
      latitude: -6.28,
      longitude: 106.87,
      distance_km: 8.6,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "j2",
      name: "Wortel Lestari Subang",
      location: "Jakarta",
      commodity: "wortel",
      reliability_score: 0.83,
      latitude: -6.5711,
      longitude: 107.7583,
      distance_km: 108.6,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "j3",
      name: "Wortel Bandungan",
      location: "Semarang",
      commodity: "wortel",
      reliability_score: 0.9,
      latitude: -7.2,
      longitude: 110.4,
      distance_km: 401.3,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "j4",
      name: "Pemasok Tanpa Jarak",
      location: "Jakarta",
      commodity: "ayam",
      reliability_score: 0.7,
      latitude: -6.2,
      longitude: 106.8,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
  ],
};

describe("kolom jarak & penyaring jangkauan (Fase 7b)", () => {
  it("menuliskan jarak dari server, \"—\" bila tidak dilaporkan", () => {
    const rows = supplierDirectory(JARAK);
    const byName = new Map(rows.map((row) => [row.name, row]));
    expect(byName.get("Sayur Segar Kramat Jati")?.distanceLabel).toBe("8,6 km");
    expect(byName.get("Wortel Lestari Subang")?.distanceLabel).toBe("109 km");
    expect(byName.get("Pemasok Tanpa Jarak")?.distanceLabel).toBe("—");
  });

  it("tanpa ambang, daftar apa adanya (nasional) — perilaku lama tidak berubah", () => {
    const rows = supplierDirectory(JARAK);
    expect(filterDirectoryByReach(rows, null)).toHaveLength(4);
    expect(directoryMetrics(rows, null).outOfReach).toBe(0);
    expect(directoryMetrics(rows, null).unknownDistance).toBe(1);
  });

  it("penyaring jangkauan membuang yang jauh DAN yang jaraknya tak diketahui", () => {
    const rows = supplierDirectory(JARAK);
    // Urutan tabel = risiko dulu (keandalan naik), bukan urutan jarak: Subang 0,83
    // tampil sebelum Kramat Jati 0,88.
    expect(filterDirectoryByReach(rows, 150).map((row) => row.name)).toEqual([
      "Wortel Lestari Subang",
      "Sayur Segar Kramat Jati",
    ]);
    expect(directoryMetrics(rows, 150).outOfReach).toBe(1);
    expect(directoryMetrics(rows, 150).unknownDistance).toBe(1);
    // Di luar jangkauan (1) + jarak tak diketahui (1) = 2 baris hilang; tidak ada
    // baris ketiga yang ikut terbuang diam-diam.
    expect(rows.length - filterDirectoryByReach(rows, 150).length).toBe(2);
  });

  it("label baris & ringkasan menyebut rujukan apa adanya", () => {
    const rows = supplierDirectory(JARAK);
    const subang = rows.find((row) => row.name === "Wortel Lestari Subang");
    const bandungan = rows.find((row) => row.name === "Wortel Bandungan");
    expect(subang && directoryReachLabel(subang, 150)).toBe("dalam jangkauan (109 km)");
    expect(bandungan && directoryReachLabel(bandungan, 150)).toBe("di luar jangkauan (401 km)");
    expect(directoryReachSummary(rows, 150, "Jakarta")).toBe(
      "2 dari 4 pemasok dalam jangkauan 150 km dari Jakarta"
    );
    expect(directoryReachSummary(rows, null)).toBe(
      "4 pemasok ditampilkan (semua, tanpa ambang jarak) · 1 tanpa jarak"
    );
  });
});
