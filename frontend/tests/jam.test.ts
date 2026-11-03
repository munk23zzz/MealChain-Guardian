import { describe, expect, it } from "vitest";

import { formatJam, zonaLabel } from "../lib/jam";

// Jam header: harus memuat DETIK dan label zona Indonesia (WIB/WITA/WIT),
// supaya jelas waktu mana yang ditampilkan (permintaan 11 Okt).
describe("formatJam", () => {
  it("menampilkan jam:menit:DETIK dalam gaya Indonesia", () => {
    // 08.42.30 UTC = 15.42.30 WIB
    const hasil = formatJam(new Date("2026-10-11T08:42:30Z"));
    expect(hasil.jam).toBe("15.42.30");
    expect(hasil.teks).toBe("15.42.30 WIB");
  });

  it("detik ikut berubah (bukan dipotong ke menit)", () => {
    const a = formatJam(new Date("2026-10-11T08:42:07Z")).jam;
    const b = formatJam(new Date("2026-10-11T08:42:58Z")).jam;
    expect(a).toBe("15.42.07");
    expect(b).toBe("15.42.58");
    expect(a).not.toBe(b);
  });

  it("memakai WIB walau zona mesin bukan Indonesia", () => {
    const hasil = formatJam(new Date("2026-10-11T00:05:09Z"));
    expect(hasil.jam).toBe("07.05.09");
    expect(hasil.zona).toBe("WIB");
  });

  it("label zona mengikuti IANA dan selalu ada (tak pernah kosong)", () => {
    expect(zonaLabel("Asia/Jakarta")).toBe("WIB");
    expect(zonaLabel("Asia/Pontianak")).toBe("WIB");
    expect(zonaLabel("Asia/Makassar")).toBe("WITA");
    expect(zonaLabel("Asia/Jayapura")).toBe("WIT");
    expect(zonaLabel("Asia/Tokyo")).toBe("WIB"); // tak dikenal → default aman
    expect(zonaLabel()).toBe("WIB");
  });

  it("zona bisa diganti untuk SPPG di WITA/WIT", () => {
    const hasil = formatJam(new Date("2026-10-11T08:42:30Z"), "Asia/Jayapura");
    expect(hasil.jam).toBe("17.42.30");
    expect(hasil.teks).toBe("17.42.30 WIT");
  });

  it("teks aksesibel menyebut waktu + zona + nama zona IANA", () => {
    const hasil = formatJam(new Date("2026-10-11T08:42:30Z"));
    expect(hasil.aria).toBe("Waktu saat ini: 15.42.30 WIB (Asia/Jakarta)");
  });
});
