// Kontrak logika tabel keputusan Agent Log (dokumen 06-agent-log §1, §2.5).
//
// Yang diuji: pemetaan status → keadaan verifikasi, penyaring yang dipakai
// bersama pencarian/komoditas/status, ringkasan yang menyebut sebab, dan
// paginasi. Komponen tabel hanya menyusun markup dari fungsi-fungsi ini.
import { describe, expect, it } from "vitest";

import {
  commodityOptions,
  decisionTypeLabel,
  filterDecisions,
  pageCount,
  pageSlice,
  statusLabel,
  tableSummary,
  verificationCounts,
  verificationState,
  DECISION_PAGE_SIZE,
} from "../lib/decision-table";

const baris = (over: Record<string, unknown> = {}) => ({
  decision_id: "aaaa1111-2222-3333-4444-555566667777",
  decision_type: "supplier_procurement",
  status: "pending_approval",
  quantity_kg: 640,
  commodity_name: "beras",
  supplier_name: "CV Tunas",
  target_location_name: "Bandung",
  ...over,
});

describe("verificationState", () => {
  it("approved/executed = terverifikasi (tak mungkin tanpa verifikasi)", () => {
    expect(verificationState(baris({ status: "approved" }))).toBe("terverifikasi");
    expect(verificationState(baris({ status: "executed" }))).toBe("terverifikasi");
  });

  it("pending = menunggu, rejected = ditolak", () => {
    expect(verificationState(baris({ status: "pending_approval" }))).toBe("menunggu");
    expect(verificationState(baris({ status: "rejected" }))).toBe("ditolak");
  });

  it("status tak dikenal tidak dikarang menjadi salah satu keadaan", () => {
    expect(verificationState(baris({ status: "draft" }))).toBe("lainnya");
    expect(verificationState(baris({ status: "" }))).toBe("lainnya");
  });
});

describe("label manusia", () => {
  it("jenis keputusan diterjemahkan; kode tak dikenal ditampilkan apa adanya", () => {
    expect(decisionTypeLabel("supplier_procurement")).toBe("Pengadaan dari pemasok");
    expect(decisionTypeLabel("regional_balance")).toBe("Penyeimbangan pasokan regional");
    expect(decisionTypeLabel("sesuatu_baru")).toBe("sesuatu_baru");
    expect(decisionTypeLabel(null)).toBe("—");
  });

  it("status diterjemahkan; kosong jadi —", () => {
    expect(statusLabel("pending_approval")).toBe("Menunggu persetujuan");
    expect(statusLabel("executed")).toBe("Dieksekusi");
    expect(statusLabel(undefined)).toBe("—");
  });
});

describe("filterDecisions", () => {
  const rows = [
    baris(),
    baris({ decision_id: "bbbb2222-2222-3333-4444-555566667777", status: "executed", commodity_name: "telur", decision_type: "regional_balance" }),
    baris({ decision_id: "cccc3333-2222-3333-4444-555566667777", status: "rejected", commodity_name: null }),
  ];

  it("tanpa filter mengembalikan semua", () => {
    expect(filterDecisions(rows)).toHaveLength(3);
  });

  it("teks mencari kode DAN label (pengguna mengetik bahasa manusia)", () => {
    // Dua baris jenisnya supplier_procurement (baris 2 punya status rejected).
    expect(filterDecisions(rows, { query: "pengadaan" })).toHaveLength(2);
    expect(filterDecisions(rows, { query: "supplier_procurement" })).toHaveLength(2);
    expect(filterDecisions(rows, { query: "dieksekusi" })).toHaveLength(1);
    expect(filterDecisions(rows, { query: "tunas" })).toHaveLength(3);
  });

  it("id pendek (8 karakter) bisa dicari — itulah yang tampil di tabel", () => {
    expect(filterDecisions(rows, { query: "cccc3333" })).toHaveLength(1);
  });

  it("komoditas dicocokkan persis, bukan sebagian", () => {
    expect(filterDecisions(rows, { commodity: "telur" })).toHaveLength(1);
    expect(filterDecisions(rows, { commodity: "tel" })).toHaveLength(0);
  });

  it("status verifikasi memakai pemetaan yang sama dengan kolom", () => {
    expect(filterDecisions(rows, { verification: "menunggu" })).toHaveLength(1);
    expect(filterDecisions(rows, { verification: "terverifikasi" })).toHaveLength(1);
    expect(filterDecisions(rows, { verification: "ditolak" })).toHaveLength(1);
  });

  it("filter digabung dengan AND", () => {
    expect(
      filterDecisions(rows, { query: "telur", commodity: "telur", verification: "terverifikasi" })
    ).toHaveLength(1);
    expect(
      filterDecisions(rows, { query: "telur", commodity: "beras" })
    ).toHaveLength(0);
  });

  it("query spasi tidak menyaring apa pun", () => {
    expect(filterDecisions(rows, { query: "   " })).toHaveLength(3);
  });
});

describe("commodityOptions & counts", () => {
  const rows = [
    baris({ commodity_name: "beras" }),
    baris({ commodity_name: "Beras" }),
    baris({ commodity_name: "telur" }),
    baris({ commodity_name: null }),
  ];

  it("komoditas diambil dari data (case-insensitive), yang kosong dilewati", () => {
    const opts = commodityOptions(rows);
    expect(opts.map((o) => o.value.toLowerCase())).toEqual(["beras", "telur"]);
    expect(opts[0].count).toBe(2);
  });

  it("hitungan status = hitungan baris yang sama dengan filter", () => {
    const counts = verificationCounts(rows);
    expect(counts.all).toBe(4);
    expect(counts.menunggu).toBe(4);
    expect(counts.terverifikasi + counts.ditolak).toBe(0);
  });
});

describe("tableSummary", () => {
  it("menyebut jumlah tampil/total + sebab penyaringan", () => {
    expect(tableSummary({ shown: 3, total: 9, query: "beras" })).toBe(
      '3 dari 9 keputusan · cocok "beras"'
    );
    expect(
      tableSummary({ shown: 1, total: 9, commodity: "telur", verification: "menunggu" })
    ).toContain("komoditas telur");
  });

  it("total nol punya kalimat sendiri, bukan '0 dari 0'", () => {
    expect(tableSummary({ shown: 0, total: 0 })).toBe(
      "Belum ada keputusan pada periode ini."
    );
  });
});

describe("paginasi", () => {
  it("memotong per halaman dan tidak pernah halaman 0", () => {
    const rows = Array.from({ length: DECISION_PAGE_SIZE * 2 + 1 }, (_, i) => ({ i }));
    expect(pageSlice(rows, 1)).toHaveLength(DECISION_PAGE_SIZE);
    expect(pageSlice(rows, 3)).toHaveLength(1);
    expect(pageSlice(rows, 0)[0]).toEqual({ i: 0 });
    expect(pageCount(rows.length)).toBe(3);
  });

  it("data kosong tetap 1 halaman (tabel tidak menghilang)", () => {
    expect(pageCount(0)).toBe(1);
  });
});
