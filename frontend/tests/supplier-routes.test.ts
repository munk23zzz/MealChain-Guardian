// Fase 10: garis jalur kiriman (pemasok → tujuan) di peta.
//
// Angka di tes ini diambil dari respons nyata `GET /supplier-routes` untuk
// kiriman kanonik Supplier A Cianjur → SPPG Jakarta (lihat
// docs/verification/fase-10.md): jalur jalan OSRM 110,434 km, 5.060 s,
// jarak lurus 78,35 km → rasio 1,41×.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  MISSING_REASON_LABEL,
  ROUTE_LINE_COLORS,
  durationLabel,
  journeyTone,
  nearestEta,
  roadKmLabel,
  routeBoundsPoints,
  routeEtaLines,
  routeGeoJson,
  routeJourneyLine,
  routeJourneyRows,
  routeLabel,
  routeLayerSummary,
  routeLayerTag,
  routeLegendEntries,
  routeLineClass,
  routeLineTone,
  routeCellLabel,
  routeCellTitle,
  routePopupLines,
  routeToggleLabel,
  routeToggleAction,
  supplierRouteSummaries,
  supplierRoutes,
} from "../lib/supplier-routes";

const GEOMETRI: [number, number][] = [
  [107.1306, -6.854],
  [107.0, -6.7],
  [106.8456, -6.2088],
];

function kiriman(ubah: Record<string, unknown> = {}) {
  return {
    batch_id: "b-1",
    supplier_id: "s-1",
    supplier_name: "Supplier A Cianjur",
    origin: { latitude: -6.854, longitude: 107.1306, name: "Supplier A Cianjur" },
    destination_id: "l-1",
    destination_name: "Jakarta",
    destination: { latitude: -6.2088, longitude: 106.8456, name: "Jakarta" },
    commodity: "telur",
    quantity_kg: 800,
    harvested_at: "2026-10-15T00:30:00+00:00",
    usable_until: "2026-11-07T12:00:00+00:00",
    safety_status: "pass",
    straight_km: 78.35,
    route_key: "driving:-6.854,107.1306>-6.2088,106.8456",
    // Perjalanan kiriman (Fase 12): angka dari respons nyata — berangkat 21.30 WIB,
    // tiba ± 22.54 WIB (84,3 menit perjalanan OSRM), 24 menit lagi saat dibaca.
    journey: {
      dispatched_at: "2026-10-16T14:30:00+00:00",
      eta_at: "2026-10-16T15:54:18+00:00",
      state: "di_jalan",
      state_label: "Di jalan",
      travel_s: 5058,
      travel_min: 84.3,
      travel_source: "osrm",
      elapsed_min: 60,
      remaining_min: 24.3,
      progress: 0.712,
      usable_until: "2026-11-07T12:00:00+00:00",
      arrives_before_usable_until: true,
    },
    road: {
      distance_km: 110.4,
      duration_min: 84.3,
      ratio_vs_straight: 1.41,
      geometry: { type: "LineString", coordinates: GEOMETRI },
      source: "osrm",
      fetched_at: "2026-10-16T00:00:00+00:00",
    },
    road_missing_reason: null,
    ...ubah,
  };
}

describe("supplierRoutes", () => {
  it("membaca amplop {routes} maupun array langsung", () => {
    expect(supplierRoutes({ routes: [kiriman()] })).toHaveLength(1);
    expect(supplierRoutes([kiriman()])).toHaveLength(1);
  });

  it("membuang baris tanpa dua ujung berkoordinat", () => {
    const rusak = kiriman({ destination: { latitude: null, longitude: null, name: "?" } });
    expect(supplierRoutes({ routes: [rusak, kiriman()] })).toHaveLength(1);
  });

  it("jatuh ke nama tujuan di dalam blok destination bila nama atas kosong", () => {
    const [row] = supplierRoutes({ routes: [kiriman({ destination_name: "  " })] });
    expect(row.destinationName).toBe("Jakarta");
  });

  it("membuang baris yang nama tujuannya tidak ada di mana pun", () => {
    const tanpaNama = kiriman({
      destination_name: "",
      destination: { latitude: -6.2088, longitude: 106.8456, name: null },
    });
    expect(supplierRoutes({ routes: [tanpaNama] })).toHaveLength(0);
  });

  it("mengurai rute jalan apa adanya", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    expect(row.road?.distanceKm).toBeCloseTo(110.4, 5);
    expect(row.road?.durationMin).toBeCloseTo(84.3, 5);
    expect(row.road?.ratioVsStraight).toBeCloseTo(1.41, 5);
    expect(row.road?.source).toBe("osrm");
    expect(row.road?.coordinates).toHaveLength(3);
    expect(row.straightKm).toBeCloseTo(78.35, 5);
  });

  it("geometri kurang dari dua titik berarti tidak ada rute", () => {
    const rusak = kiriman({
      road: {
        distance_km: 110.4,
        duration_min: 84.3,
        geometry: { type: "LineString", coordinates: [[107.1306, -6.854]] },
        source: "osrm",
      },
      road_missing_reason: "belum_disinkron",
    });
    const [row] = supplierRoutes({ routes: [rusak] });
    expect(row.road).toBeNull();
    expect(row.missingReason).toBe("belum_disinkron");
  });
});

describe("warna garis", () => {
  it("nilai paint MapLibre sama dengan token CSS (webgl tak bisa baca CSS var)", () => {
    const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");
    const token = (nama: string) => {
      const match = css.match(new RegExp(`${nama}\\s*:\\s*(#[0-9A-Fa-f]{6})`));
      expect(match, `token ${nama} tidak ditemukan di app/globals.css`).not.toBeNull();
      return (match as RegExpMatchArray)[1].toUpperCase();
    };
    expect(ROUTE_LINE_COLORS.ok.toUpperCase()).toBe(token("--status-safe"));
    expect(ROUTE_LINE_COLORS.fail.toUpperCase()).toBe(token("--status-danger"));
  });
});

describe("nada & kelas garis", () => {
  it("kiriman gagal uji dapat nada bahaya", () => {
    const [gagal] = supplierRoutes({ routes: [kiriman({ safety_status: "fail" })] });
    expect(routeLineTone(gagal)).toBe("fail");
    expect(routeLineClass(gagal)).toBe("ship-route ship-route-fail");
  });

  it("kiriman biasa memakai nada aman", () => {
    const [aman] = supplierRoutes({ routes: [kiriman()] });
    expect(routeLineTone(aman)).toBe("ok");
    expect(routeLineClass(aman)).toBe("ship-route ship-route-ok");
  });

  it("legenda hanya menyebut nada yang memang ada di peta", () => {
    // "gagal uji" hanya muncul kalau ada kiriman bergaris seperti itu — legenda
    // yang menyebut warna yang tidak dipakai membuat pembaca mencarinya.
    const entri = routeLegendEntries(supplierRoutes({ routes: [kiriman()] }));
    // K1: dua butir untuk satu nada — padat (sudah ditempuh) & putus (sisa).
    expect(entri.map((e) => e.tone)).toEqual(["ok", "sisa"]);
    expect(entri.map((e) => e.gaya)).toEqual(["padat", "putus"]);
    expect(entri[0].label).toContain("Sudah ditempuh");
    expect(entri[1].label).toContain("Sisa perjalanan");

    const denganGagal = routeLegendEntries(
      supplierRoutes({ routes: [kiriman(), kiriman({ safety_status: "fail", destination_name: "Bogor" })] })
    );
    expect(denganGagal.map((e) => e.tone)).toEqual(["ok", "sisa", "fail"]);
    expect(denganGagal[2].label).toContain("gagal uji");

    // Tanpa data kiriman sama sekali: hanya butir dasar, tidak mengarang entri.
    expect(routeLegendEntries().map((e) => e.tone)).toEqual(["ok", "sisa"]);
  });
});

describe("layer GeoJSON", () => {
  it("hanya menggambar kiriman yang punya geometri jalan", () => {
    const tanpaRute = kiriman({
      road: null,
      road_missing_reason: "belum_disinkron",
      destination_name: "Bogor",
    });
    const fc = routeGeoJson({ routes: [kiriman(), tanpaRute] });
    expect(fc.type).toBe("FeatureCollection");
    // K1: satu kiriman "di jalan" menghasilkan DUA fitur — bagian ditempuh
    // (padat) dan bagian sisa (putus-putus). Kiriman tanpa geometri tidak ikut.
    expect(fc.features).toHaveLength(2);
    expect(fc.features.map((f) => f.properties.kind)).toEqual(["done", "todo"]);
    for (const fitur of fc.features) expect(fitur.geometry.type).toBe("LineString");
  });

  it("keadaan perjalanan menentukan bentuk garis (K1: padat = ditempuh)", () => {
    const dengan = (ubah: Record<string, unknown>) => {
      const dasar = kiriman();
      return { ...dasar, journey: { ...dasar.journey, ...ubah } };
    };

    // Sudah tiba → satu garis padat penuh, tanpa bagian putus-putus.
    const tiba = routeGeoJson({ routes: [dengan({ state: "sudah_tiba", progress: null })] });
    expect(tiba.features).toHaveLength(1);
    expect(tiba.features[0].properties.kind).toBe("done");
    expect(tiba.features[0].geometry.coordinates).toEqual(GEOMETRI);

    // Belum berangkat → satu garis putus-putus penuh (belum ada yang ditempuh).
    const belum = routeGeoJson({ routes: [dengan({ state: "belum_berangkat", progress: null })] });
    expect(belum.features).toHaveLength(1);
    expect(belum.features[0].properties.kind).toBe("todo");
    expect(belum.features[0].geometry.coordinates).toEqual(GEOMETRI);

    // Perjalanan tidak dilaporkan → putus-putus (perkiraan), bukan padat palsu.
    const tanpaJourney = routeGeoJson({ routes: [{ ...kiriman(), journey: null }] });
    expect(tanpaJourney.features.map((f) => f.properties.kind)).toEqual(["todo"]);
  });

  it("bagian garis yang ditempuh dimulai di asal, sisanya berakhir di tujuan", () => {
    const fc = routeGeoJson({ routes: [kiriman()] });
    const [done, todo] = fc.features;
    expect(done.geometry.coordinates[0]).toEqual(GEOMETRI[0]);
    expect(todo.geometry.coordinates[todo.geometry.coordinates.length - 1]).toEqual(
      GEOMETRI[GEOMETRI.length - 1]
    );
    // Titik potong sama untuk kedua bagian — tidak ada celah atau tumpang tindih.
    expect(done.geometry.coordinates[done.geometry.coordinates.length - 1]).toEqual(
      todo.geometry.coordinates[0]
    );
  });

  it("properti fitur cukup untuk label & popup", () => {
    const fc = routeGeoJson({ routes: [kiriman()] });
    const props = fc.features[0].properties;
    expect(props.supplierName).toBe("Supplier A Cianjur");
    expect(props.destinationName).toBe("Jakarta");
    expect(props.tone).toBe("ok");
    expect(props.roadKm).toBeCloseTo(110.4, 5);
    expect(props.quantityKg).toBe(800);
    expect(props.label).toContain("→ Jakarta");
  });

  it("payload kosong menghasilkan koleksi kosong, bukan error", () => {
    expect(routeGeoJson(null).features).toEqual([]);
    expect(routeGeoJson({ routes: [] }).features).toEqual([]);
  });
});

describe("batas peta", () => {
  it("menyertakan dua ujung kiriman walau rutenya belum disinkron", () => {
    const tanpaRute = kiriman({ road: null, road_missing_reason: "belum_disinkron" });
    const titik = routeBoundsPoints({ routes: [tanpaRute] });
    expect(titik).toEqual([
      [107.1306, -6.854],
      [106.8456, -6.2088],
    ]);
  });
});

describe("label & popup", () => {
  it("label pendek gaya id-ID", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    expect(routeLabel(row)).toBe("Supplier A Cianjur → Jakarta · 110,4 km jalan · 800 kg telur");
  });

  it("popup jalur hanya menyebut jalur jalan — tanpa jarak lurus/rasio (arah pemilik 16 Okt)", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    const baris = routePopupLines(row);
    expect(baris[0]).toContain("OSRM");
    expect(baris[0]).toContain("110,4 km");
    expect(baris[0]).toContain("84 menit");
    // Arah pemilik 2026-10-16: "Jarak lurus: 78,4 km", "Jalur jalan 1,41× jarak lurus
    // (jalan berkelok, bukan garis lurus)" dan "Tiba sebelum batas layak" DIHAPUS dari
    // popup jalur — pembaca peta tidak memakai derajat presisi itu, dan tanggal layak
    // pakai tetap tertulis sekali di baris "Layak dipakai s/d ...".
    const gabung = baris.join(" | ");
    expect(gabung).not.toContain("Jarak lurus");
    expect(gabung).not.toContain("jarak lurus");
    expect(gabung).not.toContain("berkelok");
    expect(gabung).not.toContain("Tiba sebelum batas layak");
    expect(gabung).toContain("Layak dipakai s/d 7 Nov 2026");
    // K4 (17 Okt 2026): dua baris jam digabung jadi SATU baris — popup 240×176 px
    // dengan dua baris jam adalah 2 dari 5 baris untuk satu fakta yang sama.
    expect(gabung).toContain("tiba ± 22.54 WIB · 24 menit lagi");
  });

  it("popup menyebut alasan bila rute belum ada, tanpa angka karangan", () => {
    const [row] = supplierRoutes({
      routes: [kiriman({ road: null, road_missing_reason: "belum_disinkron" })],
    });
    const baris = routePopupLines(row);
    expect(baris[0]).toBe(`Jalur jalan: belum ada — ${MISSING_REASON_LABEL.belum_disinkron}`);
    expect(baris.join(" ")).not.toContain("110,4");
  });

  it("popup menandai kiriman gagal uji", () => {
    const [row] = supplierRoutes({ routes: [kiriman({ safety_status: "fail" })] });
    expect(routePopupLines(row).join(" ")).toContain("GAGAL UJI");
  });

  it("roadKmLabel mempertahankan satu desimal pada jarak jauh", () => {
    expect(roadKmLabel(110.43)).toBe("110,4 km");
    expect(roadKmLabel(3.2)).toBe("3,2 km");
    expect(roadKmLabel(null)).toBe("—");
  });
});

describe("ringkasan layer", () => {
  it("menghitung jalur yang sudah & belum punya rute", () => {
    const tanpaRute = kiriman({
      road: null,
      road_missing_reason: "belum_disinkron",
      destination_name: "Bogor",
    });
    const ringkasan = routeLayerSummary({ routes: [kiriman(), tanpaRute] });
    expect(ringkasan.routes).toBe(2);
    expect(ringkasan.withRoad).toBe(1);
    expect(ringkasan.missing).toBe(1);
    expect(ringkasan.label).toBe("2 jalur kiriman · 1 belum disinkronkan");
  });

  it("menyebut semuanya lewat jalur jalan bila lengkap", () => {
    const ringkasan = routeLayerSummary({ routes: [kiriman()] });
    expect(ringkasan.label).toBe("1 jalur kiriman · semua lewat jalur jalan");
  });

  it("label sakelar memuat jumlah jalur", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    // Yang terlihat ringkas; kalimat lengkapnya jadi tooltip tombol.
    expect(routeToggleLabel([row])).toBe("Jalur kiriman (1)");
    expect(routeToggleAction([row], false)).toBe("Tampilkan jalur kiriman (1)");
    expect(routeToggleAction([row], true)).toBe("Sembunyikan jalur kiriman (1)");
  });

  it("tag ringkas menyebut jumlah jalur + estimasi tiba terdekat", () => {
    // Bilah lapisan memakai tag ini supaya angkanya tetap terbaca walau kalimat
    // penjelasnya dilipat (keputusan pemilik 2026-10-16). Sejak Fase 12, saat ada
    // kiriman yang sedang berjalan, estimasi tibanya ikut di tag — arah pemilik:
    // "ketika mengaktifkan jalur kiriman tampilkan juga waktu estimasi sampai".
    expect(
      routeLayerTag(routeLayerSummary({ routes: [kiriman()] }), supplierRoutes({ routes: [kiriman()] }))
    ).toBe("1 jalur kiriman · 1 di jalan · tiba terdekat ± 22.54");

    // Tanpa kiriman berjalan: jatuh kembali ke keterangan asal geometri / jumlah
    // yang belum disinkronkan — bukan jam yang dikarang.
    const tiba = kiriman({
      journey: {
        ...(kiriman().journey as Record<string, unknown>),
        state: "sudah_tiba",
        eta_at: "2026-10-16T12:00:00+00:00",
        remaining_min: -60,
      },
    });
    expect(routeLayerTag(routeLayerSummary({ routes: [tiba] }), supplierRoutes({ routes: [tiba] }))).toBe(
      "1 jalur kiriman · jalur jalan OSRM"
    );

    const tanpaRute = kiriman({
      road: null,
      road_missing_reason: "belum_disinkron",
      destination_name: "Bogor",
      journey: null,
    });
    expect(
      routeLayerTag(
        routeLayerSummary({ routes: [kiriman(), tanpaRute] }),
        supplierRoutes({ routes: [kiriman(), tanpaRute] })
      )
    ).toBe("2 jalur kiriman · 1 di jalan · tiba terdekat ± 22.54");
    expect(
      routeLayerTag(routeLayerSummary({ routes: [tanpaRute] }), supplierRoutes({ routes: [tanpaRute] }))
    ).toBe("1 jalur kiriman · 1 belum disinkronkan");

    // Tanpa baris sama sekali: tidak ada jam, tidak ada klaim.
    expect(routeLayerTag(routeLayerSummary({ routes: [] }))).toBe("belum ada jalur kiriman");
  });
});

// Fase 12 (permintaan pemilik 2026-10-16): "ketika mengaktifkan jalur kiriman
// tampilkan juga waktu estimasi sampai … pastikan sinkron dengan database".
// Angka perjalanan datang UTUH dari server (`journey`); klien hanya menuliskannya
// — tidak ada jam tiba yang dihitung di peramban.
describe("perjalanan kiriman", () => {
  it("membaca blok journey dari server apa adanya", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    expect(row.journey?.state).toBe("di_jalan");
    expect(row.journey?.stateLabel).toBe("Di jalan");
    expect(row.journey?.etaAt).toBe("2026-10-16T15:54:18+00:00");
    expect(row.journey?.remainingMin).toBeCloseTo(24.3, 5);
    expect(row.batchId).toBe("b-1");
    expect(row.routeKey).toContain("driving:");
    expect(row.harvestedAt).toBe("2026-10-15T00:30:00+00:00");
  });

  it("keadaan tak dikenal → journey null, bukan keadaan karangan", () => {
    const [row] = supplierRoutes({ routes: [kiriman({ journey: { state: "entah" } })] });
    expect(row.journey).toBeNull();
    expect(routeJourneyRows([row])).toEqual([]);
  });

  it("nada visual mengikuti keadaan", () => {
    expect(journeyTone("di_jalan")).toBe("moving");
    expect(journeyTone("sudah_tiba")).toBe("done");
    expect(journeyTone("belum_berangkat")).toBe("pending");
    expect(journeyTone("tidak_diketahui")).toBe("unknown");
    expect(journeyTone(null)).toBe("unknown");
  });

  it("kalimat perjalanan: jam tiba hanya saat ada, tidak dikarang", () => {
    const [jalan] = supplierRoutes({ routes: [kiriman()] });
    expect(routeJourneyLine(jalan)).toBe("Jakarta · di jalan · tiba ± 22.54 (24 menit lagi)");

    const tiba = kiriman({
      journey: { ...(kiriman().journey as Record<string, unknown>), state: "sudah_tiba" },
    });
    expect(routeJourneyLine(supplierRoutes({ routes: [tiba] })[0])).toBe("Jakarta · sudah tiba 22.54");

    const belum = kiriman({
      journey: {
        ...(kiriman().journey as Record<string, unknown>),
        state: "belum_berangkat",
        dispatched_at: null,
        eta_at: null,
        remaining_min: null,
        progress: null,
      },
    });
    const barisBelum = routeJourneyLine(supplierRoutes({ routes: [belum] })[0]);
    expect(barisBelum).toBe("Jakarta · belum berangkat · estimasi tiba belum ada");
    expect(barisBelum).not.toContain("22.54");

    const takDiketahui = kiriman({
      journey: {
        ...(kiriman().journey as Record<string, unknown>),
        state: "tidak_diketahui",
        eta_at: null,
        remaining_min: null,
      },
    });
    expect(routeJourneyLine(supplierRoutes({ routes: [takDiketahui] })[0])).toContain(
      "sudah berangkat · estimasi tiba belum ada"
    );
  });

  it("daftar perjalanan dibatasi supaya kotak Info map tetap kecil", () => {
    const rows = supplierRoutes({
      routes: [
        kiriman(),
        kiriman({ destination_name: "Bogor" }),
        kiriman({ destination_name: "Bandung" }),
        kiriman({ destination_name: "Surabaya" }),
      ],
    });
    const tampil = routeJourneyRows(rows, 2);
    expect(tampil).toHaveLength(3);
    expect(tampil[2].teks).toBe("+2 kiriman lain");
    expect(tampil[0].kelas).toContain("map-journey-moving");
    expect(routeJourneyRows(rows).every((baris) => baris.kelas.startsWith("map-journey-item"))).toBe(true);
  });

  it("estimasi tiba paling awal dipakai untuk tag", () => {
    const rows = supplierRoutes({
      routes: [
        kiriman({ destination_name: "Bogor" }),
        kiriman({
          destination_name: "Surabaya",
          journey: {
            ...(kiriman().journey as Record<string, unknown>),
            eta_at: "2026-10-16T19:00:00+00:00",
          },
        }),
      ],
    });
    expect(nearestEta(rows)).toBe("2026-10-16T15:54:18+00:00");
    expect(nearestEta([])).toBeNull();
  });

  it("popup menyebut jam berangkat, estimasi tiba, dan sisa waktu", () => {
    const [row] = supplierRoutes({ routes: [kiriman()] });
    const baris = routeEtaLines(row).join(" | ");
    expect(routeEtaLines(row)).toHaveLength(1);
    expect(baris).toContain("Berangkat 16 Okt 2026 21.30 WIB");
    expect(baris).toContain("tiba ± 22.54 WIB · 24 menit lagi");
    // Kalimat "Tiba sebelum batas layak (7 Nov 2026)" dibuang atas permintaan
    // pemilik 2026-10-16: tanggalnya sudah ada di baris "Layak dipakai s/d ...",
    // dan popup tidak perlu mengulangnya sebagai kalimat penghibur.
    expect(baris).not.toContain("Tiba sebelum batas layak");
    // Popup lengkap memuat semuanya, tanpa menghitung ulang apa pun.
    expect(routePopupLines(row).join(" | ")).toContain("tiba ± 22.54 WIB");
  });

  it("tanpa waktu tempuh: tidak ada estimasi, keadaan tidak diklaim", () => {
    const [row] = supplierRoutes({
      routes: [
        kiriman({
          road: null,
          road_missing_reason: "belum_disinkron",
          journey: {
            ...(kiriman().journey as Record<string, unknown>),
            state: "tidak_diketahui",
            eta_at: null,
            travel_min: null,
            remaining_min: null,
            arrives_before_usable_until: null,
          },
        }),
      ],
    });
    const baris = routeEtaLines(row).join(" | ");
    expect(baris).toContain("tiba belum ada — jalur jalan belum disinkronkan");
    expect(baris).not.toContain("Tiba sebelum batas layak");
  });

  it("label satuan durasi gaya Indonesia", () => {
    expect(durationLabel(24.3)).toBe("24 menit");
    expect(durationLabel(84.3)).toBe("1 jam 24 menit");
    expect(durationLabel(120)).toBe("2 jam");
    expect(durationLabel(null)).toBe("—");
  });
});

describe("Ringkasan jalur per pemasok (kolom 'Jalur kirim' di tabel Pemasok)", () => {
  const bogor = kiriman({
    batch_id: "b-2",
    destination_id: "l-2",
    destination_name: "Bogor",
    road: {
      distance_km: 62.8,
      duration_min: 49.3,
      ratio_vs_straight: 1.19,
      geometry: { type: "LineString", coordinates: GEOMETRI },
      source: "osrm",
      fetched_at: "2026-10-16T00:00:00+00:00",
    },
  });

  it("mengelompokkan jalur per pemasok (bukan per batch)", () => {
    const peta = supplierRouteSummaries({ routes: [kiriman(), bogor, kiriman({ batch_id: "b-3", supplier_id: "s-2" })] });
    expect(Array.from(peta.keys()).sort()).toEqual(["s-1", "s-2"]);
    expect(peta.get("s-1")?.count).toBe(2);
    expect(peta.get("s-2")?.count).toBe(1);
  });

  it("baris utama = jalur TERPENDEK yang geometrinya sudah ada; yang belum sinkron ditaruh belakang", () => {
    const belumSinkron = kiriman({ batch_id: "b-4", destination_name: "Semarang", road: null, road_missing_reason: "belum_disinkron" });
    const peta = supplierRouteSummaries({ routes: [kiriman(), belumSinkron, bogor] });
    const ringkas = peta.get("s-1");
    expect(ringkas?.withRoad).toBe(2);
    expect(ringkas?.primary.destinationName).toBe("Bogor");
    expect(ringkas?.ordered.map((row) => row.destinationName)).toEqual(["Bogor", "Jakarta", "Semarang"]);
  });

  it("pemasok tanpa kiriman aktif ditulis '—' tanpa judul", () => {
    expect(routeCellLabel(null)).toBe("—");
    expect(routeCellTitle(null)).toBeNull();
  });

  it("jalur yang belum disinkron dilaporkan 'belum disinkronkan', bukan 0 km", () => {
    const peta = supplierRouteSummaries({
      routes: [
        kiriman({ road: null, road_missing_reason: "belum_disinkron" }),
        kiriman({ batch_id: "b-5", destination_name: "Bogor", road: null, road_missing_reason: "belum_disinkron" }),
      ],
    });
    const ringkas = peta.get("s-1") ?? null;
    expect(routeCellLabel(ringkas)).toBe("belum disinkronkan");
    // Urutan baris tanpa geometri = urutan server (keduanya tak berjarak), dan
    // sufiks sumber tidak muncul karena memang belum ada jalur untuk ditulis.
    expect(routeCellTitle(ringkas)).toBe(
      "Jakarta — rute jalan belum disinkronkan dari OSRM · Bogor — rute jalan belum disinkronkan dari OSRM"
    );
  });

  it("alasan gagal yang BUKAN 'belum disinkron' tidak disamarkan jadi 'belum disinkronkan'", () => {
    const peta = supplierRouteSummaries({
      routes: [kiriman({ road: null, road_missing_reason: "layanan_rute_tidak_terjangkau" })],
    });
    const ringkas = peta.get("s-1") ?? null;
    expect(routeCellLabel(ringkas)).toBe("jalur tidak tersedia");
    expect(routeCellTitle(ringkas)).toBe("Jakarta — layanan rute OSRM tidak terjangkau saat sinkronisasi");
  });

  it("satu jalur: tujuan + jarak JALAN (angka lurus tetap urusan kolom Jarak)", () => {
    const peta = supplierRouteSummaries({ routes: [kiriman()] });
    expect(routeCellLabel(peta.get("s-1") ?? null)).toBe("→ Jakarta · 110,4 km");
    expect(routeCellTitle(peta.get("s-1") ?? null)).toBe("Jakarta 110,4 km (jarak jalan dari OSRM)");
  });

  it("beberapa jalur: baris utama + jumlah tujuan lain, judul memuat semua tujuan terurut", () => {
    const peta = supplierRouteSummaries({ routes: [kiriman(), bogor] });
    const ringkas = peta.get("s-1") ?? null;
    expect(routeCellLabel(ringkas)).toBe("→ Bogor · 62,8 km · +1 tujuan");
    expect(routeCellTitle(ringkas)).toBe("Bogor 62,8 km · Jakarta 110,4 km (jarak jalan dari OSRM)");
  });
});
