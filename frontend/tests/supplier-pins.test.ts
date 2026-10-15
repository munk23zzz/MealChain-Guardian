// Fase 3 (permintaan pemilik proyek 2026-10-14): layer pemasok di peta.
//
// Kontrak yang diuji di sini murni (tanpa DOM, tanpa MapLibre) supaya aturan
// tampilan bisa diperiksa tanpa WebGL:
// - `GET /suppliers` → baris pin: hanya baris yang PUNYA koordinat layak jadi
//   pin (baris tanpa koordinat tidak boleh diam-diam dipasang di 0,0);
// - pemasok tanpa fokus komoditas tidak dicocokkan ke komoditas mana pun
//   (jangan menebak saat filter komoditas aktif);
// - nada pin: dikecualikan > keandalan rendah > normal, dan keandalan yang
//   tidak diketahui BUKAN "normal" (jangan mengklaim);
// - label aksesibilitas & isi popup menyebut angka dan status apa adanya;
// - gerbang zoom: pin hanya muncul saat zoom >= 8 (peta Indonesia penuh akan
//   jadi gumpalan kalau 30 pin kota kecil dipaksa tampil).
import { describe, expect, it } from "vitest";

import {
  SUPPLIER_LABEL_MIN_ZOOM,
  SUPPLIER_PIN_LEGEND,
  SUPPLIER_PIN_MIN_ZOOM,
  SUPPLIER_REACH_KM,
  SPPG_ROLES,
  distanceLabel,
  distanceReachLabel,
  isWithinReach,
  reachLabel,
  supplierAccessibleLabel,
  supplierDistanceReference,
  supplierLabelsVisible,
  supplierPinsForMap,
  supplierReachKmForRole,
  supplierReachMeta,
  supplierReachNote,
  withinReachKm,
  supplierLayerSummary,
  supplierPinClass,
  supplierPinRows,
  supplierPinTone,
  supplierPopupLines,
  supplierPinsVisible,
  supplierToggleLabel,
  suppliersForCommodity,
  shouldLoadSuppliers,
} from "../lib/supplier-pins";

const ITEMS = [
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
    latitude: -6.824,
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
    name: "Pemasok Tanpa Titik",
    location: "Cianjur",
    commodity: "ayam",
    reliability_score: 0.9,
    latitude: null,
    longitude: null,
    excluded_at_hub: false,
    excluded_scope_locations: [],
  },
];

describe("supplierPinRows", () => {
  it("menormalkan payload API (termasuk skor string) dan membuang baris tanpa koordinat", () => {
    const rows = supplierPinRows(ITEMS);
    expect(rows.map((r) => r.name)).toEqual([
      "Wortel Lestari Cianjur",
      "Telur Berkah Cianjur",
      "Supplier A Cianjur",
    ]);
    expect(rows[0]).toMatchObject({
      id: "s1",
      hub: "Cianjur",
      commodity: "wortel",
      reliability: 0.93,
      certification: "haccp",
      excludedAtHub: false,
    });
    expect(rows[2].reliability).toBe(0.8);
    // Baris "Pemasok Tanpa Titik" hilang karena koordinatnya null.
    expect(rows.some((r) => r.name === "Pemasok Tanpa Titik")).toBe(false);
  });

  it("tahan payload aneh (null / bukan array / id hilang)", () => {
    expect(supplierPinRows(null)).toEqual([]);
    expect(supplierPinRows({ items: [] })).toEqual([]);
    expect(supplierPinRows([{ name: "Tanpa Id", latitude: -6, longitude: 106 }])[0].id).toBe(
      "Tanpa Id"
    );
    expect(supplierPinRows([{ latitude: -6, longitude: 106 }])).toEqual([]);
  });
});

describe("suppliersForCommodity", () => {
  const rows = supplierPinRows(ITEMS);

  it("tanpa komoditas terpilih: semua baris", () => {
    expect(suppliersForCommodity(rows, null)).toHaveLength(3);
    expect(suppliersForCommodity(rows, "")).toHaveLength(3);
  });

  it("komoditas terpilih: hanya pemasok berfokus komoditas itu", () => {
    expect(suppliersForCommodity(rows, "wortel").map((r) => r.name)).toEqual([
      "Wortel Lestari Cianjur",
    ]);
    expect(suppliersForCommodity(rows, "TELUR")).toHaveLength(1);
    // Pemasok tanpa fokus komoditas TIDAK dicocokkan (jangan menebak).
    expect(suppliersForCommodity(rows, "ayam")).toEqual([]);
  });
});

describe("nada pin", () => {
  const rows = supplierPinRows(ITEMS);

  it("dikecualikan > keandalan rendah > normal; keandalan tak diketahui bukan normal", () => {
    expect(supplierPinTone(rows[1])).toBe("excluded"); // 0.38 + dikecualikan
    expect(supplierPinTone(rows[0])).toBe("ok"); // 0.93
    expect(supplierPinTone({ ...rows[0], excludedAtHub: false, reliability: 0.44 })).toBe("low");
    expect(supplierPinTone({ ...rows[0], reliability: null })).toBe("unknown");
  });

  it("kelas pin memakai prefiks pemasok supaya tidak tertukar dengan pin SPPG", () => {
    expect(supplierPinClass(rows[0])).toBe("map-pin map-pin-supplier map-pin-supplier-ok");
    expect(supplierPinClass(rows[1])).toBe(
      "map-pin map-pin-supplier map-pin-supplier-excluded"
    );
  });

  it("mode titik (tanpa nama) menambah kelas compact, bukan mengubah nada", () => {
    expect(supplierPinClass(rows[1], false)).toBe(
      "map-pin map-pin-supplier map-pin-supplier-excluded map-pin-supplier-compact"
    );
    expect(supplierPinClass(rows[1], true)).not.toContain("compact");
  });
});

describe("teks untuk pengguna", () => {
  const rows = supplierPinRows(ITEMS);

  it("label aksesibilitas menyebut komoditas, keandalan, hub, dan eksklusi", () => {
    expect(supplierAccessibleLabel(rows[0])).toBe(
      "Wortel Lestari Cianjur — pemasok wortel, keandalan 93%, hub Cianjur"
    );
    expect(supplierAccessibleLabel(rows[1])).toBe(
      "Telur Berkah Cianjur — pemasok telur, keandalan 38%, hub Cianjur (dikecualikan di Cianjur, Jakarta)"
    );
    expect(supplierAccessibleLabel({ ...rows[2], commodity: null, reliability: null })).toBe(
      "Supplier A Cianjur — pemasok tanpa fokus komoditas, keandalan tidak diketahui, hub Cianjur"
    );
  });

  it("popup memuat baris yang bisa dibaca manusia (tanpa kode internal)", () => {
    const popup = supplierPopupLines(rows[1]);
    expect(popup.title).toBe("Telur Berkah Cianjur");
    // "none" BUKAN "—": tidak bersertifikat itu informasi nyata, sedangkan "—"
    // dipakai untuk data yang tidak ada/ tidak diketahui. Enum internal
    // ('none'/'hygiene'/'haccp') tidak pernah tampil di layar.
    expect(popup.lines).toEqual([
      "Komoditas: telur",
      "Hub: Cianjur",
      "Keandalan: 38%",
      "Sertifikasi: Tidak bersertifikat",
      "Dikecualikan di: Cianjur, Jakarta",
    ]);
    expect(popup.lines.join(" ")).not.toContain("none");
    expect(popup.lines.join(" ")).not.toContain("_");
    expect(supplierPopupLines(rows[0]).lines).toEqual([
      "Komoditas: wortel",
      "Hub: Cianjur",
      "Keandalan: 93%",
      "Sertifikasi: HACCP",
    ]);
  });
});

describe("ringkasan layer & gerbang zoom", () => {
  const rows = supplierPinRows(ITEMS);

  it("hitungan per nada untuk label tombol & legenda", () => {
    // Hitungan dihitung dari PREDIKAT MASING-MASING (bukan dari nada pin yang
    // saling menutup): pemasok skor rendah yang juga dikecualikan tetap
    // terhitung di kedua kolom, karena keduanya fakta yang berbeda.
    expect(supplierLayerSummary(rows)).toMatchObject({
      total: 3,
      excluded: 1,
      low: 1,
      ok: 2,
      unknown: 0,
    });
    expect(supplierToggleLabel(rows, false)).toBe("Tampilkan pemasok (3)");
    expect(supplierToggleLabel(rows, true)).toBe("Sembunyikan pemasok (3)");
    expect(supplierToggleLabel([], false)).toBe("Tampilkan pemasok (0)");
  });

  it("pin hanya tampil saat zoom cukup dekat", () => {
    expect(SUPPLIER_PIN_MIN_ZOOM).toBe(6);
    expect(supplierPinsVisible(4.5)).toBe(false);
    expect(supplierPinsVisible(5.99)).toBe(false);
    expect(supplierPinsVisible(6)).toBe(true);
    expect(supplierPinsVisible(12)).toBe(true);
    expect(supplierPinsVisible(Number.NaN)).toBe(false);
  });

  it("nama pemasok muncul lebih lambat daripada titiknya", () => {
    expect(SUPPLIER_LABEL_MIN_ZOOM).toBeGreaterThan(SUPPLIER_PIN_MIN_ZOOM);
    expect(supplierLabelsVisible(6)).toBe(false); // titik saja
    expect(supplierLabelsVisible(7.99)).toBe(false);
    expect(supplierLabelsVisible(8)).toBe(true);
    expect(supplierLabelsVisible(Number.NaN)).toBe(false);
  });

  it("legenda pemasok memuat SETIAP nada yang bisa dipakai pin", () => {
    // "far" masuk di Fase 7b; kalau nada baru ditambahkan tanpa legenda, tes ini
    // gagal — peta tidak boleh punya makna yang tidak dijelaskan.
    expect(SUPPLIER_PIN_LEGEND.map((entry) => entry.tone)).toEqual([
      "ok",
      "low",
      "excluded",
      "far",
    ]);
    expect(SUPPLIER_PIN_LEGEND.map((entry) => entry.label)).toEqual([
      "Pemasok",
      "Keandalan rendah",
      "Dikecualikan",
      "Di luar jangkauan",
    ]);
  });
});

describe("shouldLoadSuppliers", () => {
  it("dimuat di tab yang memang memakainya (peta Overview + halaman Pemasok)", () => {
    expect(shouldLoadSuppliers("overview")).toBe(true);
    expect(shouldLoadSuppliers("suppliers")).toBe(true);
    expect(shouldLoadSuppliers("kpi-kualitas")).toBe(false);
    expect(shouldLoadSuppliers("evidence")).toBe(false);
    expect(shouldLoadSuppliers("agent")).toBe(false);
    expect(shouldLoadSuppliers("demo")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Fase 7b (2026-10-15) — jarak & "terjangkau" sebagai RELEVANSI, bukan scope
// ---------------------------------------------------------------------------

const JARAK_ITEMS = [
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
];

const PAYLOAD_JANGKAUAN = {
  count: 4,
  total: 30,
  limit: 200,
  offset: 0,
  distance_reference: { location: "Jakarta", latitude: -6.2088, longitude: 106.8456 },
  reach: { max_distance_km: 150, excluded_out_of_reach: 23, excluded_unknown_distance: 1 },
  items: JARAK_ITEMS,
};

describe("jarak & jangkauan (Fase 7b)", () => {
  it("membaca distance_km dari server apa adanya, null bila tidak dilaporkan", () => {
    const rows = supplierPinRows(PAYLOAD_JANGKAUAN);
    expect(rows.map((row) => row.distanceKm)).toEqual([8.6, 108.6, 401.3, null]);
  });

  it("ambang jangkauan per peran: SPPG dibatasi, monitor nasional", () => {
    expect(supplierReachKmForRole("sppg_head")).toBe(SUPPLIER_REACH_KM);
    expect(supplierReachKmForRole("sppg_nutritionist")).toBe(SUPPLIER_REACH_KM);
    expect(supplierReachKmForRole(" SPPG_Head ")).toBe(SUPPLIER_REACH_KM);
    expect(supplierReachKmForRole("bgn_monitor")).toBeNull();
    expect(supplierReachKmForRole(null)).toBeNull();
    expect(supplierReachKmForRole(undefined)).toBeNull();
    expect(SPPG_ROLES).toEqual(["sppg_head", "sppg_nutritionist"]);
  });

  it("jarak yang tak diketahui TIDAK dianggap dalam jangkauan", () => {
    expect(withinReachKm(8.6, 150)).toBe(true);
    expect(withinReachKm(401.3, 150)).toBe(false);
    expect(withinReachKm(null, 150)).toBe(false);
    // Tanpa ambang (tampilan nasional) tidak ada yang dibuang.
    expect(withinReachKm(401.3, null)).toBe(true);
    expect(withinReachKm(null, null)).toBe(true);
  });

  it("menulis jarak gaya id-ID, satu desimal di bawah 100 km", () => {
    expect(distanceLabel(8.6)).toBe("8,6 km");
    expect(distanceLabel(108.6)).toBe("109 km");
    expect(distanceLabel(null)).toBe("—");
  });

  it("kalimat jangkauan jujur: dalam, luar, tak diketahui, atau tanpa ambang", () => {
    const rows = supplierPinRows(PAYLOAD_JANGKAUAN);
    expect(reachLabel(rows[0], SUPPLIER_REACH_KM)).toBe("dalam jangkauan (8,6 km)");
    expect(reachLabel(rows[2], SUPPLIER_REACH_KM)).toBe("di luar jangkauan (401 km)");
    expect(reachLabel(rows[3], SUPPLIER_REACH_KM)).toBe("jarak tidak diketahui");
    expect(reachLabel(rows[2], null)).toBe("jarak 401 km");
    expect(distanceReachLabel(43.4, SUPPLIER_REACH_KM)).toBe("dalam jangkauan (43,4 km)");
  });

  it("nada pin: di luar jangkauan ≠ keandalan rendah, dan eksklusi tetap menang", () => {
    const rows = supplierPinRows(PAYLOAD_JANGKAUAN);
    expect(supplierPinTone(rows[0], SUPPLIER_REACH_KM)).toBe("ok");
    expect(supplierPinTone(rows[2], SUPPLIER_REACH_KM)).toBe("far");
    // Tanpa ambang, pemasok Semarang itu kembali "ok" — bukan dihukum tanpa dasar.
    expect(supplierPinTone(rows[2], null)).toBe("ok");

    const dikecualikan = supplierPinRows([
      { ...JARAK_ITEMS[2], excluded_at_hub: true, excluded_scope_locations: ["Jakarta"] },
    ])[0];
    expect(supplierPinTone(dikecualikan, SUPPLIER_REACH_KM)).toBe("excluded");
    expect(supplierPinClass(dikecualikan, true, SUPPLIER_REACH_KM)).toContain(
      "map-pin-supplier-excluded"
    );
  });

  it("peta hanya memasang pin dalam jangkauan (tanpa ambang: semua)", () => {
    const rows = supplierPinRows(PAYLOAD_JANGKAUAN);
    expect(supplierPinsForMap(rows, SUPPLIER_REACH_KM).map((row) => row.name)).toEqual([
      "Sayur Segar Kramat Jati",
      "Wortel Lestari Subang",
    ]);
    expect(supplierPinsForMap(rows, null)).toHaveLength(4);
  });

  it("ringkasan layer menghitung 'far' hanya saat ada ambang", () => {
    const rows = supplierPinRows(PAYLOAD_JANGKAUAN);
    // far = Semarang (401 km) + baris tanpa jarak: keduanya tidak bisa diklaim dekat.
    expect(supplierLayerSummary(rows, SUPPLIER_REACH_KM).far).toBe(2);
    expect(supplierLayerSummary(rows, null).far).toBe(0);
    expect(supplierLayerSummary(rows, SUPPLIER_REACH_KM).total).toBe(4);
  });

  it("kalimat status menyebut rujukan dan jumlah yang TIDAK dipasang", () => {
    const rows = supplierPinRows(PAYLOAD_JANGKAUAN);
    // 4 baris dikirim + 23 dibuang server = 27 (fixture kecil; di aplikasi nyata
    // angkanya 22 + 13 = 35). Yang penting: jumlah TOTAL tidak menyusut sendiri.
    expect(supplierReachNote(rows, SUPPLIER_REACH_KM, "Jakarta", 23)).toBe(
      "2 dari 27 pemasok dalam jangkauan 150 km dari Jakarta · 25 di luar jangkauan tidak dipasang di peta"
    );
    expect(supplierReachNote(rows, null)).toBe(
      "4 pemasok ditampilkan (nasional, tanpa ambang jarak)"
    );
  });

  it("membaca blok reach & distance_reference dari respons server", () => {
    expect(supplierReachMeta(PAYLOAD_JANGKAUAN)).toEqual({
      maxDistanceKm: 150,
      excludedOutOfReach: 23,
      excludedUnknownDistance: 1,
    });
    expect(supplierReachMeta({ items: [] })).toEqual({
      maxDistanceKm: null,
      excludedOutOfReach: 0,
      excludedUnknownDistance: 0,
    });
    expect(supplierDistanceReference(PAYLOAD_JANGKAUAN)).toEqual({
      location: "Jakarta",
      latitude: -6.2088,
      longitude: 106.8456,
    });
    expect(supplierDistanceReference({ items: [] })).toBeNull();

    const rows = supplierPinRows(PAYLOAD_JANGKAUAN);
    expect(isWithinReach(rows[3], SUPPLIER_REACH_KM)).toBe(false);
  });
});
