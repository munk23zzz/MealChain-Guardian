import { describe, expect, it } from "vitest";

import { pageSlots, paginate } from "../lib/pagination";

const baris = (n: number) => Array.from({ length: n }, (_, i) => ({ id: i + 1 }));

describe("paginate", () => {
  it("memotong daftar sesuai ukuran halaman dan menomori 1-based", () => {
    const hasil = paginate(baris(60), 1, 10);
    expect(hasil.page).toBe(1);
    expect(hasil.pageCount).toBe(6);
    expect(hasil.total).toBe(60);
    expect(hasil.items).toHaveLength(10);
    expect(hasil.items[0].id).toBe(1);
    expect(hasil.items[9].id).toBe(10);
    expect(hasil.start).toBe(1);
    expect(hasil.end).toBe(10);
    expect(hasil.hasPrev).toBe(false);
    expect(hasil.hasNext).toBe(true);
  });

  it("halaman terakhir boleh terisi sebagian dan menutup rentang di total", () => {
    const hasil = paginate(baris(23), 3, 10);
    expect(hasil.items).toHaveLength(3);
    expect(hasil.start).toBe(21);
    expect(hasil.end).toBe(23);
    expect(hasil.hasNext).toBe(false);
    expect(hasil.hasPrev).toBe(true);
  });

  it("halaman di luar rentang dijepit ke halaman terakhir yang ada", () => {
    // Data menyusut (penyaring/segarkan) — bukan halaman kosong.
    expect(paginate(baris(23), 9, 10).page).toBe(3);
    expect(paginate(baris(23), 9, 10).items).toHaveLength(3);
    expect(paginate(baris(23), 0, 10).page).toBe(1);
    expect(paginate(baris(23), -4, 10).page).toBe(1);
  });

  it("daftar kosong tetap satu halaman dengan rentang 0–0", () => {
    const hasil = paginate([], 1, 10);
    expect(hasil.pageCount).toBe(1);
    expect(hasil.total).toBe(0);
    expect(hasil.items).toEqual([]);
    expect(hasil.start).toBe(0);
    expect(hasil.end).toBe(0);
    expect(hasil.hasPrev).toBe(false);
    expect(hasil.hasNext).toBe(false);
  });

  it("ukuran halaman tidak sah diperlakukan sebagai 1 (tidak membagi nol)", () => {
    expect(paginate(baris(5), 1, 0).items).toHaveLength(1);
    expect(paginate(baris(5), 1, -3).items).toHaveLength(1);
    expect(paginate(baris(5), 2, 2.7).items).toHaveLength(2);
  });

  it("tidak mengubah array masukan", () => {
    const asli = baris(30);
    const salinan = asli.map((row) => row.id);
    paginate(asli, 2, 10);
    expect(asli.map((row) => row.id)).toEqual(salinan);
  });
});

describe("pageSlots", () => {
  it("menampilkan semua nomor bila halaman sedikit", () => {
    expect(pageSlots(1, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(pageSlots(3, 5)).toEqual([1, 2, 3, 4, 5]);
  });

  it("memakai elipsis saat halaman banyak dan menyorot halaman aktif", () => {
    const slot = pageSlots(10, 20);
    expect(slot[0]).toBe(1);
    expect(slot[slot.length - 1]).toBe(20);
    expect(slot).toContain(10);
    expect(slot).toContain("…");
    expect(slot.length).toBeLessThanOrEqual(7);
  });

  it("dekat awal tidak menaruh elipsis di kiri", () => {
    expect(pageSlots(1, 20)[0]).toBe(1);
    expect(pageSlots(1, 20)).toEqual([1, 2, 3, 4, 5, "…", 20]);
  });

  it("dekat akhir tidak menaruh elipsis di kanan", () => {
    expect(pageSlots(20, 20)).toEqual([1, "…", 16, 17, 18, 19, 20]);
  });

  it("jumlah maksimum slot bisa diatur dan tidak pernah melewatinya", () => {
    expect(pageSlots(10, 20, 5).length).toBeLessThanOrEqual(5);
    expect(pageSlots(1, 1)).toEqual([1]);
  });
});
