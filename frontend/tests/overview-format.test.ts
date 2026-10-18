// Label periode data peta (audit angka 18 Okt 2026).
//
// MASALAH yang dipaku di sini: `GET /balance/map` mengambil baris TERBARU per
// lokasi tanpa batas waktu, dan deret demo sudah diperluas sampai 5 Nov
// (ACTUAL_REF). Di layar "Hari Ini" angka pasokan bisa berasal dari 4 Nov
// sementara permintaan masih dari 8 Okt — dua tanggal berbeda, tanpa label.
// Pengguna lalu membaca angka itu sebagai "kondisi hari ini".
//
// ATURAN: payload sudah membawa `supply_recorded_at`/`demand_recorded_at`
// (PLAN-023), jadi tanggalnya DIBACA, tidak ditebak dan tidak diisi tanggal
// sistem. Tidak ada baris → sisi itu tidak disebut. Tidak ada keduanya → null
// (tidak ada label karangan).
import { describe, expect, it } from "vitest";

import { snapshotNote } from "../lib/overview-format";

describe("snapshotNote — tanggal data yang benar-benar dipakai", () => {
  it("menyebut kedua sisi bila tanggalnya berbeda", () => {
    const note = snapshotNote([
      {
        location: "Jakarta",
        status: "shortage",
        supply_recorded_at: "2026-11-04T12:00:00+00:00",
        demand_recorded_at: "2026-10-08T12:00:00+00:00",
      },
    ]);
    expect(note).toBe("Pasokan per 4 Nov 2026 · permintaan per 8 Okt 2026");
  });

  it("meringkas jadi satu tanggal bila kedua sisi segaris", () => {
    const note = snapshotNote([
      {
        location: "Bogor",
        status: "surplus",
        supply_recorded_at: "2026-10-18T12:00:00+00:00",
        demand_recorded_at: "2026-10-18T00:00:00+00:00",
      },
    ]);
    expect(note).toBe("Data per 18 Okt 2026");
  });

  it("memakai tanggal TERBARU dari baris yang dipakai, bukan baris pertama", () => {
    const note = snapshotNote([
      {
        location: "Jakarta",
        status: "shortage",
        supply_recorded_at: "2026-10-18T12:00:00+00:00",
        demand_recorded_at: "2026-10-08T12:00:00+00:00",
      },
      {
        location: "Bogor",
        status: "surplus",
        supply_recorded_at: "2026-11-04T12:00:00+00:00",
        demand_recorded_at: "2026-10-08T12:00:00+00:00",
      },
    ]);
    expect(note).toBe("Pasokan per 4 Nov 2026 · permintaan per 8 Okt 2026");
  });

  it("tidak mengarang tanggal untuk sisi tanpa catatan", () => {
    const note = snapshotNote([
      {
        location: "Bandung",
        status: "surplus",
        supply_recorded_at: "2026-11-04T12:00:00+00:00",
        demand_recorded_at: null,
      },
    ]);
    expect(note).toBe("Pasokan per 4 Nov 2026 · permintaan belum ada catatan");
  });

  it("null bila tidak ada satu pun tanggal (tanpa label karangan)", () => {
    expect(
      snapshotNote([
        { location: "TEST-a", status: "balanced", supply_recorded_at: null, demand_recorded_at: null },
      ])
    ).toBeNull();
    expect(snapshotNote([])).toBeNull();
  });

  it("membaca tanggal dalam zona Asia/Jakarta, bukan UTC mentah", () => {
    // 18.30 UTC = 01.30 WIB tanggal berikutnya di Jakarta.
    const note = snapshotNote([
      {
        location: "Medan",
        status: "shortage",
        supply_recorded_at: "2026-11-04T18:30:00+00:00",
        demand_recorded_at: "2026-11-04T18:30:00+00:00",
      },
    ]);
    expect(note).toBe("Data per 5 Nov 2026");
  });

  it("timestamp rusak diabaikan, bukan ditampilkan sebagai tanggal palsu", () => {
    const note = snapshotNote([
      {
        location: "Medan",
        status: "shortage",
        supply_recorded_at: "bukan-tanggal",
        demand_recorded_at: "2026-10-08T12:00:00+00:00",
      },
    ]);
    expect(note).toBe("Permintaan per 8 Okt 2026");
  });
});

// Label jam SINKRON (jam pengambilan data), bukan jam data. Dipisah supaya
// tidak ada lagi pill "Diperbarui 15.14 WIB" yang terbaca sebagai waktu data.
import { syncLabel } from "../lib/overview-format";

describe("syncLabel — jam sinkron eksplisit", () => {
  it("menulis jam WIB dengan detik", () => {
    expect(syncLabel(new Date("2026-10-18T13:20:22Z"))).toBe("Sinkron 20.20.22 WIB");
  });

  it("menerima angka milidetik dan string ISO", () => {
    const ms = Date.parse("2026-10-18T13:20:22Z");
    expect(syncLabel(ms)).toBe("Sinkron 20.20.22 WIB");
    expect(syncLabel("2026-10-18T13:20:22Z")).toBe("Sinkron 20.20.22 WIB");
  });

  it("nilai kosong/rusak menjadi null, bukan jam karangan", () => {
    expect(syncLabel(null)).toBeNull();
    expect(syncLabel(undefined)).toBeNull();
    expect(syncLabel("bukan-jam")).toBeNull();
  });
});
