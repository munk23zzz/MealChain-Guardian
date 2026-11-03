/**
 * Kontrak "setiap tulis menyegarkan semua data" (permintaan pemilik 2026-10-17:
 * "ketika saya melakukan sesuatu pastikan semuanya berjalan sesuai").
 *
 * Sebelumnya tidak ada satu pun `invalidateQueries` di repo: tiap komponen
 * me-refetch query-nya sendiri setelah aksi, sehingga panel lain tetap basi
 * (terbukti pada peta setelah "Segarkan ke hari ini").
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  daftarkanPenyegar,
  metodeMenulis,
  segarkanSetelahTulis,
} from "../lib/refresh";

describe("metodeMenulis — permintaan mana yang mengubah data server", () => {
  it("GET/HEAD/OPTIONS dan metode kosong bukan tulis", () => {
    expect(metodeMenulis("GET")).toBe(false);
    expect(metodeMenulis("get")).toBe(false);
    expect(metodeMenulis("HEAD")).toBe(false);
    expect(metodeMenulis("OPTIONS")).toBe(false);
    expect(metodeMenulis(undefined)).toBe(false);
    expect(metodeMenulis(null)).toBe(false);
  });

  it("POST/PUT/PATCH/DELETE adalah tulis, huruf besar-kecil tidak penting", () => {
    for (const m of ["POST", "PUT", "PATCH", "DELETE", "post", "Patch"]) {
      expect(metodeMenulis(m)).toBe(true);
    }
  });
});

describe("segarkanSetelahTulis — satu pintu untuk seluruh cache", () => {
  afterEach(() => daftarkanPenyegar(null));

  it("tanpa penyegar terdaftar: tidak melempar dan tidak melakukan apa pun", () => {
    expect(() => segarkanSetelahTulis()).not.toThrow();
  });

  it("memanggil penyegar terdaftar satu kali per permintaan", () => {
    const penyegar = vi.fn();
    daftarkanPenyegar(penyegar);
    segarkanSetelahTulis();
    segarkanSetelahTulis();
    expect(penyegar).toHaveBeenCalledTimes(2);
  });

  it("melepas penyegar menghentikan penyegaran (mis. saat provider unmount)", () => {
    const penyegar = vi.fn();
    daftarkanPenyegar(penyegar);
    daftarkanPenyegar(null);
    segarkanSetelahTulis();
    expect(penyegar).not.toHaveBeenCalled();
  });
});
