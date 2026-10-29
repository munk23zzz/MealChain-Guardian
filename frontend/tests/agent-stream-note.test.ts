// Catatan saat kanal log tertutup lebih awal (29 Okt 2026).
//
// Ditulis MERAH lebih dulu. Aturannya sempit: satu kalimat untuk satu keadaan,
// dan tidak menumpuk pesan galat yang sudah ada.

import { describe, expect, it } from "vitest";
import { catatanAliranPutus } from "../lib/agent-stream-note";

describe("catatanAliranPutus", () => {
  it("diam saat aliran ditutup karena putaran memang selesai", () => {
    expect(catatanAliranPutus({ dibatalkan: true, galatTercatat: false })).toBeNull();
  });

  it("tidak menumpuk pesan bila galat sudah ditampilkan", () => {
    expect(catatanAliranPutus({ dibatalkan: false, galatTercatat: true })).toBeNull();
  });

  it("menjelaskan kanal yang tertutup sebelum putaran selesai", () => {
    const teks = catatanAliranPutus({ dibatalkan: false, galatTercatat: false });
    expect(teks).toContain("ditutup server");
    expect(teks).toContain("sebelum putaran selesai");
  });
});
