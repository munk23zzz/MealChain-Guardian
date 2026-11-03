import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBatches } from "../lib/api";

// Regresi 20 Okt 2026: `GET /batches` tanpa `limit` hanya mengirim 50 baris
// terbaru (plafon server 500). Dengan 161 batch di DB, barang baru datang
// (ayam 90 kg) tidak sampai ke layar sehingga kartu Penerimaan tampak kosong.
describe("fetchBatches meminta inventaris penuh", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("menyertakan limit=500 pada permintaan", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => ({ batches: [] }),
      text: async () => JSON.stringify({ batches: [] }),
    }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchBatches("token-uji");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/batches?limit=500");
  });
});
