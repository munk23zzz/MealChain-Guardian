// Filter pemilih keputusan (redesign 19 Okt 2026) — logika murni.
//
// Kenapa: daftar keputusan bisa puluhan baris dan labelnya berbentuk
// "jenis · waktu · #id". Tanpa pencarian, pengguna harus menggulir buta.
// Aturan:
//   - kueri kosong = daftar utuh (tidak mengubah urutan kelompok);
//   - pencocokan case-insensitive pada LABEL opsi (jenis, status, waktu, #id);
//   - kelompok tanpa hasil dibuang, bukan ditampilkan kosong;
//   - pemisah label " · " dipecah untuk tampilan (judul vs meta), tanpa
//     mengubah nilai `value` yang dikirim ke pemanggil.
import { describe, expect, it } from "vitest";

import { pecahLabel, saringGrup, type PickerGroup } from "../lib/decision-picker";

const GRUP: PickerGroup[] = [
  {
    id: "action",
    label: "Menunggu tindakan (2)",
    options: [
      { value: "aaa", label: "Alihkan pasokan · sisa 6 jam · #aaa111" },
      { value: "bbb", label: "Tambah pasokan · sisa 2 jam · #bbb222" },
    ],
  },
  {
    id: "rest",
    label: "Tidak menunggu tindakan (2)",
    options: [
      { value: "ccc", label: "Kurangi pasokan · dieksekusi · #ccc333" },
      { value: "ddd", label: "Alihkan pasokan · kedaluwarsa · #ddd444" },
    ],
  },
];

describe("saringGrup", () => {
  it("kueri kosong mengembalikan daftar utuh apa adanya", () => {
    expect(saringGrup(GRUP, "")).toBe(GRUP);
    expect(saringGrup(GRUP, "   ")).toBe(GRUP);
  });

  it("mencocokkan isi label, tanpa peduli huruf besar/kecil", () => {
    const hasil = saringGrup(GRUP, "ALIHKAN");
    expect(hasil.map((g) => g.id)).toEqual(["action", "rest"]);
    expect(hasil[0].options.map((o) => o.value)).toEqual(["aaa"]);
    expect(hasil[1].options.map((o) => o.value)).toEqual(["ddd"]);
  });

  it("mencocokkan nomor keputusan walau hanya sebagian", () => {
    const hasil = saringGrup(GRUP, "ccc333");
    expect(hasil).toHaveLength(1);
    expect(hasil[0].options.map((o) => o.value)).toEqual(["ccc"]);
  });

  it("kelompok tanpa hasil dibuang, bukan ditampilkan kosong", () => {
    const hasil = saringGrup(GRUP, "tambah");
    expect(hasil.map((g) => g.id)).toEqual(["action"]);
  });

  it("tidak ada hasil = daftar kosong (pemanggil yang menampilkan pesan)", () => {
    expect(saringGrup(GRUP, "tidak-ada-yang-cocok")).toEqual([]);
  });
});

describe("pecahLabel", () => {
  it("memecah label menjadi judul + bagian meta", () => {
    expect(pecahLabel("Alihkan pasokan · sisa 6 jam · #aaa111")).toEqual({
      judul: "Alihkan pasokan",
      meta: ["sisa 6 jam", "#aaa111"],
    });
  });

  it("label tanpa pemisah tetap utuh, meta kosong", () => {
    expect(pecahLabel("Keputusan")).toEqual({ judul: "Keputusan", meta: [] });
  });

  it("pemisah berlebih tidak menghasilkan bagian kosong", () => {
    expect(pecahLabel("Alihkan pasokan ·  · #a1").meta).toEqual(["#a1"]);
  });
});
