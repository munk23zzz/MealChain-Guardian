// Tes murni penyusun halaman "Decision & Evidence" (rencana:
// docs/plans/decision-evidence-rebuild.md, langkah 1).
//
// Yang dikunci di sini adalah ATURAN HALAMAN, bukan tata letak:
//   - lima bagian, urutannya tetap (kepala → keputusan → jalur → bukti → jejak);
//   - bagian yang datanya tidak ada MENYEBUT SEBABNYA, tidak pernah kosong diam;
//   - PO yang tampil hanya milik keputusan yang dibuka (tidak ada daftar jaringan);
//   - ceklis hanya untuk batch yang tertaut ke keputusan itu, dan bila tidak ada
//     tautan hal itu dinyatakan — bukan dikarang.

import { describe, expect, it } from "vitest";

import {
  ID_BAGIAN,
  poKeputusan,
  ringkasCeklis,
  susunBagian,
} from "../lib/decision-dossier";

describe("susunBagian", () => {
  it("selalu lima bagian dengan urutan tetap", () => {
    const bagian = susunBagian({});
    expect(bagian.map((b) => b.id)).toEqual([...ID_BAGIAN]);
    expect(bagian.map((b) => b.label)).toEqual([
      "Kepala",
      "Keputusan",
      "Jalur",
      "Bukti",
      "Jejak & hasil",
    ]);
  });

  it("menyebut sebab ketika sebuah bagian belum punya data", () => {
    const bagian = susunBagian({});
    const cari = (id: string) => bagian.find((b) => b.id === id)!.kosong;
    expect(cari("kepala")).toMatch(/keputusan belum dipilih/i);
    expect(cari("jalur")).toMatch(/belum ada jejak persetujuan/i);
    expect(cari("jejak")).toMatch(/belum ada PO untuk keputusan ini/i);
  });

  it("bagian berisi data tidak lagi punya alasan kosong", () => {
    const bagian = susunBagian({
      decision: { decision_id: "d1", status: "pending_approval" },
      chain: [{ step: "diajukan" }],
      packet: { costs: { total: 1 } },
      purchaseOrders: [{ po_number: "MC-1", status: "draft", decision_id: "d1" }],
    });
    expect(bagian.find((b) => b.id === "kepala")!.kosong).toBeNull();
    expect(bagian.find((b) => b.id === "jalur")!.kosong).toBeNull();
    expect(bagian.find((b) => b.id === "bukti")!.kosong).toBeNull();
    expect(bagian.find((b) => b.id === "jejak")!.kosong).toBeNull();
  });

  it("kekurangan di bagian jejak dicatat sebagai catatan, bukan alasan kosong", () => {
    const bagian = susunBagian({
      decision: { decision_id: "d1" },
      packet: { costs: { total: 1 } },
      purchaseOrders: [{ po_number: "MC-1", status: "submitted", decision_id: "d1" }],
    });
    const jejak = bagian.find((b) => b.id === "jejak")!;
    expect(jejak.kosong).toBeNull();
    expect(jejak.catatan).toMatch(/belum menautkan batch/i);
  });

  it("bagian keputusan punya sebab tersendiri ketika ringkasan persetujuan belum terbaca", () => {
    const bagian = susunBagian({ decision: { decision_id: "d1" } });
    expect(bagian.find((b) => b.id === "keputusan")!.kosong).toMatch(
      /ringkasan persetujuan belum terbaca/i
    );
  });
});

describe("poKeputusan", () => {
  const daftar = [
    { po_number: "MC-1", status: "submitted", decision_id: "d1", created_at: "2026-10-20T00:00:00Z" },
    { po_number: "MC-2", status: "draft", decision_id: "d1", created_at: "2026-10-28T00:00:00Z" },
    { po_number: "MC-3", status: "submitted", decision_id: "lain", created_at: "2026-10-29T00:00:00Z" },
  ];

  it("hanya mengambil PO milik keputusan yang dibuka", () => {
    expect(poKeputusan(daftar, "d1")?.poNumber).toBe("MC-2");
  });

  it("mengambil yang terbaru, bukan yang pertama di daftar", () => {
    const terbalik = [...daftar].reverse();
    expect(poKeputusan(terbalik, "d1")?.poNumber).toBe("MC-2");
  });

  it("tidak menampilkan PO keputusan lain walau hanya satu baris yang ada", () => {
    expect(poKeputusan([daftar[2]], "d1")).toBeNull();
  });

  it("mengembalikan null bila keputusan belum punya id", () => {
    expect(poKeputusan(daftar, undefined)).toBeNull();
  });

  it("menerima bentuk balasan server ({items: []}) maupun array langsung", () => {
    expect(poKeputusan({ items: daftar }, "d1")?.poNumber).toBe("MC-2");
  });
});

describe("ringkasCeklis", () => {
  const packet = { batches: [{ id: "b1" }, { id: "b2" }] };

  it("menghitung ceklis yang sudah ada dan yang sudah diputuskan", () => {
    const ringkas = ringkasCeklis({
      packet,
      receipts: [
        { batch_id: "b1", status: "disetujui", recorded_at: "2026-10-27T00:00:00Z" },
        { batch_id: "b2", status: "menunggu", recorded_at: "2026-10-28T00:00:00Z" },
      ],
    });
    expect(ringkas.batchIds).toEqual(["b1", "b2"]);
    // Kedua batch punya baris ceklis — satu sudah diputuskan, satu masih menunggu.
    expect(ringkas.terisi).toBe(2);
    expect(ringkas.disetujui).toBe(1);
    expect(ringkas.menunggu).toBe(1);
    expect(ringkas.belumDiisi).toBe(0);
    expect(ringkas.tanpaTautan).toBe(false);
  });

  it("menandai batch yang belum punya baris ceklis", () => {
    const ringkas = ringkasCeklis({
      packet,
      receipts: [{ batch_id: "b1", status: "disetujui", recorded_at: "2026-10-27T00:00:00Z" }],
    });
    expect(ringkas.terisi).toBe(1);
    expect(ringkas.belumDiisi).toBe(1);
  });

  it("menyatakan bila keputusan tidak menautkan batch sama sekali", () => {
    const ringkas = ringkasCeklis({ packet: { batches: [] }, receipts: [] });
    expect(ringkas.batchIds).toEqual([]);
    expect(ringkas.tanpaTautan).toBe(true);
  });

  it("tidak menghitung ceklis batch lain sebagai milik keputusan ini", () => {
    const ringkas = ringkasCeklis({
      packet,
      receipts: [{ batch_id: "b-lain", status: "disetujui", recorded_at: "2026-10-27T00:00:00Z" }],
    });
    expect(ringkas.terisi).toBe(0);
    expect(ringkas.belumDiisi).toBe(2);
  });
});
