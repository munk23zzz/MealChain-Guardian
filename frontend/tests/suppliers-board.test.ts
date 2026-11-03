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
  directoryReachTagLabel,
  exclusionRows,
  filterDirectoryByReach,
  reliabilityLabel,
  reliabilityMeter,
  supplierDirectory,
  supplierMetaLine,
} from "../lib/suppliers-board";
import { LOW_RELIABILITY } from "../lib/supplier-pins";

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

describe("reliabilityMeter", () => {
  it("skor 0..1 jadi lebar bar + nada; skor tak ada jadi null, BUKAN lebar 0", () => {
    expect(reliabilityMeter(0.93)).toEqual({ pct: 93, tone: "ok" });
    expect(reliabilityMeter("0.65")).toEqual({ pct: 65, tone: "warn" });
    expect(reliabilityMeter(0.38)).toEqual({ pct: 38, tone: "danger" });
    expect(reliabilityMeter(null)).toBeNull();
    expect(reliabilityMeter(undefined)).toBeNull();
    expect(reliabilityMeter("")).toBeNull();
    expect(reliabilityMeter("bukan angka")).toBeNull();
  });

  it("ambang memakai LOW_RELIABILITY yang sudah ada — bukan angka karangan baru", () => {
    expect(LOW_RELIABILITY).toBe(0.6);
    expect(reliabilityMeter(LOW_RELIABILITY)).toEqual({ pct: 60, tone: "warn" });
    expect(reliabilityMeter(0.59)).toEqual({ pct: 59, tone: "danger" });
    expect(reliabilityMeter(0.8)).toEqual({ pct: 80, tone: "ok" });
    expect(reliabilityMeter(0.79)).toEqual({ pct: 79, tone: "warn" });
  });

  it("skor di luar 0..1: bar dijepit ke rentang, label tetap apa adanya", () => {
    // Bar tidak boleh melewati jalurnya; angkanya sendiri ditulis apa adanya
    // (label) supaya data aneh tetap terlihat, bukan disembunyikan.
    expect(reliabilityMeter(1.4)).toEqual({ pct: 100, tone: "ok" });
    expect(reliabilityMeter(-0.2)).toEqual({ pct: 0, tone: "danger" });
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

  it("bentuk PRODUKSI: source_decision_id + created_at ISO → nama, WIB, id keputusan", () => {
    // Audit 26 Okt 2026: endpoint mengirim `source_decision_id` dan `created_at`,
    // sedangkan fixture lama memakai `decision_id`/`excluded_at`. Akibatnya kolom
    // Keputusan selalu "—" dan kolom Waktu menampilkan ISO UTC mentah.
    const rows = exclusionRows([
      {
        id: "e2",
        supplier_id: "s1",
        supplier_name: "UD Cibinong Telur Berkah",
        status: "active",
        reason: "dua kiriman di atas ambang suhu",
        source_decision_id: "d2c7131c-bf7b-5428-bcb5-899b31e0fe86",
        created_at: "2026-10-25T20:43:30.217503+00:00",
      },
    ]);
    expect(rows[0].supplier).toBe("UD Cibinong Telur Berkah");
    expect(rows[0].decisionId).toBe("d2c7131c-bf7b-5428-bcb5-899b31e0fe86");
    // 20.43 UTC = 03.43 WIB keesokan harinya, tanpa mikrodetik.
    expect(rows[0].at).toBe("26 Okt 2026 03.43");
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
      name: "Toko Sayur Bu Endang",
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
      name: "CV Hortikultura Subang Lestari",
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
      name: "CV Bandungan Sayur Lestari",
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
    expect(byName.get("Toko Sayur Bu Endang")?.distanceLabel).toBe("8,6 km");
    expect(byName.get("CV Hortikultura Subang Lestari")?.distanceLabel).toBe("109 km");
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
      "CV Hortikultura Subang Lestari",
      "Toko Sayur Bu Endang",
    ]);
    expect(directoryMetrics(rows, 150).outOfReach).toBe(1);
    expect(directoryMetrics(rows, 150).unknownDistance).toBe(1);
    // Di luar jangkauan (1) + jarak tak diketahui (1) = 2 baris hilang; tidak ada
    // baris ketiga yang ikut terbuang diam-diam.
    expect(rows.length - filterDirectoryByReach(rows, 150).length).toBe(2);
  });

  it("label baris & ringkasan menyebut rujukan apa adanya", () => {
    const rows = supplierDirectory(JARAK);
    const subang = rows.find((row) => row.name === "CV Hortikultura Subang Lestari");
    const bandungan = rows.find((row) => row.name === "CV Bandungan Sayur Lestari");
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

describe("supplierMetaLine — baris kedua sel 'Pemasok' (Fase 12c)", () => {
  const ITEM = {
    id: "s1",
    name: "Wortel Lestari Cianjur",
    location: "Cianjur",
    commodity: "wortel",
    certification_status: "haccp",
    reliability_score: 0.93,
    latitude: -6.824,
    longitude: 107.1636,
  };

  it("menggabungkan hub & koordinat supaya keduanya tidak makan kolom sendiri", () => {
    const [row] = supplierDirectory({ items: [ITEM] });
    expect(supplierMetaLine(row)).toBe("Cianjur · -6,8240 / 107,1636");
  });

  it("bagian yang tidak ada TIDAK ditulis '—' (tidak ada garis miring menggantung)", () => {
    const [tanpaKoordinat] = supplierDirectory({ items: [{ ...ITEM, latitude: null, longitude: null }] });
    expect(supplierMetaLine(tanpaKoordinat)).toBe("Cianjur");

    const [tanpaHub] = supplierDirectory({ items: [{ ...ITEM, location: null }] });
    expect(supplierMetaLine(tanpaHub)).toBe("-6,8240 / 107,1636");
  });
});

describe("directoryReachTagLabel — pil ringkas jangkauan (Fase 12c)", () => {
  const ITEM = {
    id: "s1",
    name: "Wortel Berkah Surabaya",
    location: "Surabaya",
    commodity: "wortel",
    latitude: -7.2395,
    longitude: 112.7731,
    reliability_score: 0.7,
    distance_km: 665,
  };

  it("pil menyebut KEADAAN, bukan mengulang km (km sudah ada di kolom Jarak)", () => {
    const [row] = supplierDirectory({ items: [ITEM] });

    expect(directoryReachTagLabel(row, 150)).toBe("di luar jangkauan");
    // Kalimat penuhnya tetap ada — dipakai sebagai `title` pil.
    expect(directoryReachLabel(row, 150)).toBe("di luar jangkauan (665 km)");
  });

  it("jarak tidak diketahui tidak disamarkan jadi 'di luar jangkauan'", () => {
    const [row] = supplierDirectory({ items: [{ ...ITEM, distance_km: null }] });

    expect(directoryReachTagLabel(row, 150)).toBe("jarak tidak diketahui");
    expect(directoryReachLabel(row, 150)).toBe("jarak tidak diketahui");
  });
});
