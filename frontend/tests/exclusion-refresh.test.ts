/**
 * Jalur tulis yang memakai pembungkus fetch SENDIRI (supplier-exclusions.ts)
 * wajib ikut aturan penyegaran terpusat. Tanpa ini, menyetujui/mencabut
 * pengecualian pemasok meninggalkan panel lain (peta, Pemasok, KPI) basi.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { daftarkanPenyegar } from "../lib/refresh";
import {
  fetchExclusions,
  proposeSupplierExclusion,
  proposeSupplierRestoration,
} from "../lib/supplier-exclusions";

describe("supplier-exclusions — penyegaran setelah tulis", () => {
  let penyegar: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    penyegar = vi.fn();
    daftarkanPenyegar(penyegar);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }))
    );
  });

  afterEach(() => {
    daftarkanPenyegar(null);
    vi.unstubAllGlobals();
  });

  it("POST usulan pengecualian menyegarkan seluruh cache", async () => {
    await proposeSupplierExclusion(
      { supplier_id: "s-1", scope_location_id: "l-1", reason: "uji", evidence_refs: [] },
      "tok"
    );
    expect(penyegar).toHaveBeenCalledTimes(1);
  });

  it("POST pemulihan pengecualian juga menyegarkan", async () => {
    await proposeSupplierRestoration("ex-1", { reason: "uji", evidence_refs: [] }, "tok");
    expect(penyegar).toHaveBeenCalledTimes(1);
  });

  it("GET register pengecualian TIDAK menyegarkan apa pun", async () => {
    await fetchExclusions("tok");
    expect(penyegar).not.toHaveBeenCalled();
  });
});
