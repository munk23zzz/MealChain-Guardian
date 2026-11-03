// Kontrak galat API: pesan server harus SAMPAI ke layar apa adanya.
//
// Audit M9 (18 Okt 2026): `ApiError` hanya membawa `HTTP <status>: <path>`,
// sehingga alasan sebenarnya dari backend — mis. 409 "verdict sudah tercatat —
// hasil audit tidak bisa ditimpa" — hilang dan pengguna hanya melihat angka
// status. Tes ini mengunci janji: `detail` dari body JSON menjadi pesan galat.

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, request } from "../lib/api";

function stubFetch(status: number, body: string, contentType = "application/json") {
  const resp = new Response(body, {
    status,
    headers: { "Content-Type": contentType },
  });
  vi.stubGlobal("fetch", vi.fn(async () => resp));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request() — pesan galat dari server", () => {
  it("409 dengan detail string: pesan = detail, bukan 'HTTP 409'", async () => {
    stubFetch(
      409,
      JSON.stringify({
        detail: "verdict sudah tercatat — hasil audit tidak bisa ditimpa",
      })
    );
    let galat: unknown;
    try {
      await request("/actions/verify", { method: "POST", body: "{}" });
    } catch (err) {
      galat = err;
    }
    expect(galat).toBeInstanceOf(ApiError);
    const e = galat as ApiError;
    expect(e.status).toBe(409);
    expect(e.detail).toBe("verdict sudah tercatat — hasil audit tidak bisa ditimpa");
    expect(e.message).toBe("verdict sudah tercatat — hasil audit tidak bisa ditimpa");
  });

  it("422 validasi (detail berupa daftar): dibaca manusia, bukan [object Object]", async () => {
    stubFetch(
      422,
      JSON.stringify({
        detail: [
          {
            type: "uuid_type",
            loc: ["body", "decision_id"],
            msg: "UUID input should be a string",
          },
        ],
      })
    );
    const galat = (await request("/actions/execute", { method: "POST" }).catch(
      (err) => err
    )) as ApiError;
    expect(galat.status).toBe(422);
    expect(galat.message).toContain("decision_id");
    expect(galat.message).toContain("UUID input should be a string");
    expect(galat.message).not.toContain("[object Object]");
  });

  it("body HTML (proxy/galat halaman): jatuh ke pesan status yang jujur", async () => {
    stubFetch(502, "<html><body>Bad Gateway</body></html>", "text/html");
    const galat = (await request("/decisions", { method: "GET" }).catch(
      (err) => err
    )) as ApiError;
    expect(galat).toBeInstanceOf(ApiError);
    expect(galat.status).toBe(502);
    expect(galat.message).toBe("HTTP 502: /decisions");
    expect(galat.message).not.toContain("Unexpected token");
  });

  it("200 JSON tetap mengembalikan objek apa adanya", async () => {
    stubFetch(200, JSON.stringify({ ok: true, jumlah: 3 }));
    await expect(request("/x", { method: "GET" })).resolves.toEqual({
      ok: true,
      jumlah: 3,
    });
  });
});
