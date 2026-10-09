/**
 * Kontrak IntegrityPanel (P1-P3, paket 1-6, keputusan Roy 2026-10-09):
 * - api client: verifyLedger → GET /ledger/verify (Bearer)
 * - api client: fetchDossier → GET /decisions/{id}/dossier (Bearer)
 * - error di-status non-2xx ditolak (tidak ditelan diam-diam)
 */

import { describe, expect, it, vi } from "vitest";

import { fetchDossier, verifyLedger } from "../lib/api";

describe("api integritas (kontrak backend P1-P3)", () => {
  it("verifyLedger GET /ledger/verify dengan Bearer", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ valid: true, blocks: 0 }), text: () => Promise.resolve(JSON.stringify({ valid: true, blocks: 0 })),
    });
    vi.stubGlobal("fetch", fetchMock);
    await verifyLedger("jwt-x");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/ledger/verify");
    expect(init.headers.Authorization).toBe("Bearer jwt-x");
    vi.unstubAllGlobals();
  });

  it("fetchDossier GET /decisions/{id}/dossier dengan Bearer", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ content_address: "mc1-x" }), text: () => Promise.resolve(JSON.stringify({ content_address: "mc1-x" })),
    });
    vi.stubGlobal("fetch", fetchMock);
    await fetchDossier("dec-1", "jwt-y");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/decisions/dec-1/dossier");
    expect(init.headers.Authorization).toBe("Bearer jwt-y");
    vi.unstubAllGlobals();
  });

  it("verifyLedger menolak status non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: "unauthorized" }), text: () => Promise.resolve(JSON.stringify({ detail: "unauthorized" })),
      })
    );
    await expect(verifyLedger("bad")).rejects.toThrow();
    vi.unstubAllGlobals();
  });
});
