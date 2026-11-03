// Pembaca aliran SSE untuk log langsung Demo Control (29 Okt 2026).
//
// Ditulis lebih dulu sebagai MERAH: berkas `lib/agent-stream.ts` belum ada.
// Kontrak yang diuji sengaja kecil — memecah potongan jaringan menjadi peristiwa
// tanpa kehilangan batas baris yang belum lengkap.

import { describe, expect, it } from "vitest";
import { bacaSse, langkahDari, sumberDari, type LangkahAgent } from "../lib/agent-stream";

describe("bacaSse", () => {
  it("memecah satu peristiwa langkah menjadi JSON yang bisa dibaca", () => {
    const { peristiwa, sisa } = bacaSse(
      'event: langkah\ndata: {"step":"DETECT","tool":"supply.gap","ringkas":"gap_kg=780","at":"2026-10-29T03:21:04Z"}\n\n',
    );
    expect(peristiwa).toHaveLength(1);
    expect(peristiwa[0].nama).toBe("langkah");
    const langkah = langkahDari(peristiwa[0]);
    expect(langkah).toEqual<LangkahAgent>({
      step: "DETECT",
      tool: "supply.gap",
      ringkas: "gap_kg=780",
      at: "2026-10-29T03:21:04Z",
    });
    expect(sisa).toBe("");
  });

  it("menyimpan potongan yang belum lengkap untuk panggilan berikutnya", () => {
    const pertama = bacaSse('event: langkah\ndata: {"step":"VER');
    expect(pertama.peristiwa).toHaveLength(0);
    expect(pertama.sisa).toBe('event: langkah\ndata: {"step":"VER');

    const kedua = bacaSse(`${pertama.sisa}IFY","tool":null,"ringkas":"","at":""}\n\n`);
    expect(kedua.peristiwa).toHaveLength(1);
    expect(langkahDari(kedua.peristiwa[0])?.step).toBe("VERIFY");
  });

  it("memahami komentar sebagai penanda kanal siap", () => {
    const { peristiwa } = bacaSse(": siap\n\n");
    expect(peristiwa).toEqual([{ nama: "komentar", data: "siap" }]);
  });

  it("membuang komentar detak (`: tunggu`) dari daftar peristiwa", () => {
    const { peristiwa } = bacaSse(": tunggu\n\nevent: langkah\ndata: {}\n\n");
    expect(peristiwa.map((p) => p.nama)).toEqual(["komentar", "langkah"]);
  });

  it("menerima akhir baris CRLF dari proxy", () => {
    const { peristiwa } = bacaSse('event: langkah\r\ndata: {"step":"LOGISTICS"}\r\n\r\n');
    expect(peristiwa).toHaveLength(1);
    expect(langkahDari(peristiwa[0])?.step).toBe("LOGISTICS");
  });

  it("menggabungkan beberapa langkah dalam satu potongan", () => {
    const { peristiwa } = bacaSse(
      'event: langkah\ndata: {"step":"A"}\n\nevent: langkah\ndata: {"step":"B"}\n\n',
    );
    expect(peristiwa.map((p) => langkahDari(p)?.step)).toEqual(["A", "B"]);
  });
});

describe("langkahDari", () => {
  it("mengembalikan null untuk JSON rusak — satu baris rusak tidak menghentikan log", () => {
    expect(langkahDari({ nama: "langkah", data: "{bukan json" })).toBeNull();
  });

  it("memberi nilai kosong yang aman untuk kolom yang tidak dikirim", () => {
    const langkah = langkahDari({ nama: "langkah", data: '{"step":"LEARN"}' });
    expect(langkah).toEqual({ step: "LEARN", tool: null, ringkas: "", at: "" });
  });

  it("menolak peristiwa yang bukan langkah", () => {
    expect(langkahDari({ nama: "komentar", data: "siap" })).toBeNull();
  });
});

describe("sumberDari", () => {
  it("memecah satu langkah yang memanggil beberapa sumber", () => {
    expect(sumberDari("supply.get+demand.get+supplier.get")).toEqual([
      "supply.get",
      "demand.get",
      "supplier.get",
    ]);
  });

  it("satu sumber tetap satu", () => {
    expect(sumberDari("verifier.rest")).toEqual(["verifier.rest"]);
  });

  it("tanpa alat = daftar kosong, bukan baris kosong", () => {
    expect(sumberDari(null)).toEqual([]);
    expect(sumberDari("")).toEqual([]);
    expect(sumberDari("  +  ")).toEqual([]);
  });

  it("spasi di sekitar pemisah dibuang", () => {
    expect(sumberDari("a.get + b.get")).toEqual(["a.get", "b.get"]);
  });
});
