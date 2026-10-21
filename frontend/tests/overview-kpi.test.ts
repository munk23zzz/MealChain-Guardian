// Kontrak copy kartu "Rekomendasi menunggu" Overview.
//
// Bug yang dikunci: `rest` = sisa di luar batas tampil, BUKAN sisa pekerjaan.
// Saat 1..limit rekomendasi masih menunggu, `rest` = 0; cabang lama menulis
// "semua sudah ditindaklanjuti" — klaim yang bertentangan dengan angka di
// atasnya. Semua keadaan diuji supaya kalimat dan angka tidak bisa berpisah.
import { describe, expect, it } from "vitest";

import { pendingKpiCopy, queueQuantityLabel } from "../lib/overview-kpi";

describe("pendingKpiCopy", () => {
  it("3 menunggu dari 4 yang dipantau: menyebut pekerjaan, bukan 'semua selesai'", () => {
    const copy = pendingKpiCopy({ total: 3, monitored: 4, limit: 4 });
    expect(copy.value).toBe("3");
    expect(copy.foot).toBe("3 menunggu tindakan · 4 total dipantau");
    expect(copy.mini).toBe("semua rekomendasi tampil di antrean");
    expect(copy.mini).not.toContain("semua sudah ditindaklanjuti");
  });

  it("lebih dari batas tampil: sisa disebut sebagai tambahan, bukan total", () => {
    const copy = pendingKpiCopy({ total: 6, monitored: 12, limit: 4 });
    expect(copy.value).toBe("6");
    expect(copy.foot).toBe("6 menunggu tindakan · 12 total dipantau");
    expect(copy.mini).toBe("+2 lain menunggu tindakan");
  });

  it("0 menunggu tetapi ada keputusan lain: 0 jujur, bukan tanda data hilang", () => {
    const copy = pendingKpiCopy({ total: 0, monitored: 4, limit: 4 });
    expect(copy.value).toBe("0");
    expect(copy.foot).toBe("4 keputusan dipantau");
    expect(copy.mini).toBe("tidak ada yang menunggu");
  });

  it("belum ada data sama sekali: nilai '—' dan alasan, bukan 0 palsu", () => {
    const copy = pendingKpiCopy({ total: 0, monitored: 0, limit: 4 });
    expect(copy.value).toBe("—");
    expect(copy.foot).toBe("belum ada data keputusan");
    expect(copy.mini).toBe("siapkan data demo atau tunggu sinkronisasi");
  });

  it("sedang memuat: '—' dan status memuat, bukan 0", () => {
    const copy = pendingKpiCopy({ total: 0, monitored: 0, loading: true });
    expect(copy.value).toBe("—");
    expect(copy.foot).toBe("memuat daftar keputusan");
    expect(copy.mini).toBe("menunggu data");
  });

  it("lewat tenggat tetap dihitung terpisah dan tidak disembunyikan", () => {
    const copy = pendingKpiCopy({ total: 0, monitored: 2, expired: 3 });
    expect(copy.value).toBe("0");
    expect(copy.foot).toBe("3 lewat tenggat — tidak bisa ditindak lagi");
    expect(copy.mini).toBe("tidak ada yang bisa ditindak");
  });
});

describe("queueQuantityLabel", () => {
  it("nilai kosong menjelaskan alasannya, bukan '—' telanjang", () => {
    expect(queueQuantityLabel(null)).toBe("jumlah tidak tercatat");
    expect(queueQuantityLabel(undefined)).toBe("jumlah tidak tercatat");
    expect(queueQuantityLabel("")).toBe("jumlah tidak tercatat");
    expect(queueQuantityLabel("bukan-angka")).toBe("jumlah tidak tercatat");
  });

  it("nol yang terukur tetap nol, bukan dianggap tidak tercatat", () => {
    expect(queueQuantityLabel(0)).toBe("0 kg");
  });

  it("angka memakai formatter kg yang sama dengan halaman lain", () => {
    expect(queueQuantityLabel("1257.14")).toBe("1.257,14 kg");
  });
});
