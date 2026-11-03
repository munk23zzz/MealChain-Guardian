// Kontrak Langkah 4 (Rules.md §3): satu titik konfigurasi data-fetching.
// Modul lib/query.ts murni supaya aturan ini bisa diuji tanpa DOM.
import { describe, expect, it } from "vitest";

import {
  QUERY_POLL_MS,
  QUERY_STALE_MS,
  errorMessage,
  makeQueryClient,
  queryKeys,
} from "../lib/query";

describe("queryKeys", () => {
  it("kunci dengan input sama identik (dibandingkan per elemen)", () => {
    // 24 Okt 2026: kunci feed membawa JENDELA juga — dua jendela berbeda tidak
    // boleh berbagi cache (kalau tidak, pilih "7 hari" bisa menampilkan isi
    // "Hari ini" dari cache).
    expect([...queryKeys.decisions("jakarta")]).toEqual([
      "decisions",
      "jakarta",
      "all",
    ]);
    expect([...queryKeys.decisions("jakarta", "7d")]).toEqual([
      "decisions",
      "jakarta",
      "7d",
    ]);
    expect([...queryKeys.kpi("a", "b", "jakarta")]).toEqual(["kpi", "a", "b", "jakarta"]);
    expect([...queryKeys.batches()]).toEqual(["batches"]);
  });

  it("cakupan berbeda menghasilkan kunci berbeda", () => {
    // Kalau tidak, data satu SPPG bisa tampil di cakupan SPPG lain.
    expect([...queryKeys.today("jakarta")]).not.toEqual([...queryKeys.today("bogor")]);
  });

  it("kunci per keputusan memuat id-nya", () => {
    expect([...queryKeys.traces("d-1")]).toEqual(["traces", "d-1"]);
    expect([...queryKeys.approvalSummary("d-1")]).toEqual([
      "approval-summary",
      "d-1",
    ]);
  });
});

describe("errorMessage", () => {
  it("null/undefined berarti tidak ada galat", () => {
    expect(errorMessage(null)).toBeNull();
    expect(errorMessage(undefined)).toBeNull();
  });

  it("mengambil pesan dari Error, dan merangkai nilai lain", () => {
    expect(errorMessage(new Error("Gagal memuat"))).toBe("Gagal memuat");
    expect(errorMessage("mentah")).toBe("mentah");
  });
});

describe("makeQueryClient", () => {
  it("default proyek: staleTime, interval poll, retry, tanpa refetch saat fokus", () => {
    const defaults = makeQueryClient().getDefaultOptions().queries;
    expect(defaults?.staleTime).toBe(QUERY_STALE_MS);
    expect(defaults?.refetchInterval).toBe(QUERY_POLL_MS);
    expect(defaults?.retry).toBe(1);
    expect(defaults?.refetchOnWindowFocus).toBe(false);
  });

  it("tiap panggilan menghasilkan client baru (bukan singleton modul)", () => {
    const a = makeQueryClient();
    const b = makeQueryClient();
    expect(a).not.toBe(b);
    a.clear();
    expect(b.getDefaultOptions().queries?.staleTime).toBe(QUERY_STALE_MS);
  });
});
