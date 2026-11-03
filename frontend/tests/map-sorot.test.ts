import { afterEach, describe, expect, it, vi } from "vitest";
import {
  daftarkanSorot,
  langgananSorot,
  resetSorotUntukTes,
  sorotLokasiTerenregistrasi,
  sorotTersedia,
} from "../lib/map-sorot";

describe("lib/map-sorot — jembatan peta ↔ daftar lokasi", () => {
  afterEach(() => resetSorotUntukTes());

  it("tanpa peta terdaftar: tidak tersedia dan sorot mengembalikan false", () => {
    expect(sorotTersedia()).toBe(false);
    expect(sorotLokasiTerenregistrasi("Jakarta")).toBe(false);
  });

  it("setelah peta mendaftar: sorot diteruskan ke penangan peta", () => {
    const terima: string[] = [];
    const lepas = daftarkanSorot((nama) => terima.push(nama));
    expect(sorotTersedia()).toBe(true);
    expect(sorotLokasiTerenregistrasi("Bandung")).toBe(true);
    expect(terima).toEqual(["Bandung"]);
    lepas();
    expect(sorotTersedia()).toBe(false);
  });

  it("pembatalan hanya melepas penangan yang sama (peta kedua tidak tercabut)", () => {
    const pertama = daftarkanSorot(() => {});
    const kedua: string[] = [];
    daftarkanSorot((nama) => kedua.push(nama));
    pertama(); // membatalkan pendaftaran lama, bukan yang baru
    expect(sorotLokasiTerenregistrasi("Bogor")).toBe(true);
    expect(kedua).toEqual(["Bogor"]);
  });

  it("pelanggan diberi tahu saat peta mendaftar dan saat dilepas", () => {
    const dengar = vi.fn();
    const berhenti = langgananSorot(dengar);
    const lepas = daftarkanSorot(() => {});
    expect(dengar).toHaveBeenCalledTimes(1);
    lepas();
    expect(dengar).toHaveBeenCalledTimes(2);
    berhenti();
    daftarkanSorot(() => {});
    expect(dengar).toHaveBeenCalledTimes(2);
  });
});
