// Lapisan data untuk DEMO STATIS (GitHub Pages).
//
// Halaman di GitHub Pages hanya menyajikan berkas statis: tidak ada server Next,
// tidak ada FastAPI. Saat `NEXT_PUBLIC_USE_MOCK=true`, semua panggilan di
// `lib/api.ts` tidak menyentuh jaringan — jawabannya diambil dari berkas
// `public/mock/api.json` yang direkam dari API sungguhan oleh
// `scripts/rekam_fixture_demo.py`.
//
// Aturan penting:
//   * Peran dipilih dari token: login mock mengembalikan token `mock:<peran>`,
//     sehingga berkas fixture per peran dipakai apa adanya (cakupan data sama
//     seperti backend: SPPG hanya lokasinya, BGN global).
//   * Kunci dicari tiga tingkat: path+kueri persis → path tanpa kueri → pola
//     path dengan UUID diganti `{id}`. Ini perlu karena UI mengirim id/kueri
//     yang tidak selalu sama dengan yang terekam.
//   * Panggilan TULIS (POST/PATCH) tidak mengubah data: demo statis hanya
//     membalas sukses. Setelah menulis, UI menyegarkan diri dan menerima angka
//     yang sama — jujur, bukan pura-pura berubah.
//   * Tidak ada rahasia di berkas fixture: hanya data demo yang memang publik.

export type Fixture = { status: number; body: unknown };

/** Peran demo yang dikenali token mock. */
export const PERAN_MOCK = ["sppg_head", "sppg_nutritionist", "bgn_monitor"] as const;
export type PeranMock = (typeof PERAN_MOCK)[number];

const POLA_UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

type PetaPeran = Record<string, { status: number; body: unknown }>;
const simpanan: Record<string, PetaPeran> = {};
const sedangMemuat: Record<string, Promise<PetaPeran>> = {};

/** Basis path aset statis (GitHub Pages memakai /<repo>). */
function basisAset(): string {
  return process.env.NEXT_PUBLIC_BASE_PATH || "";
}

/**
 * Fixture dipisah per peran (`mock/api-<peran>.json`) supaya halaman hanya
 * mengunduh data peran yang sedang dipakai — bukan seluruh 3 peran sekaligus.
 */
async function muatPeran(peran: PeranMock): Promise<PetaPeran> {
  if (simpanan[peran]) return simpanan[peran];
  if (!sedangMemuat[peran]) {
    sedangMemuat[peran] = (async () => {
      const resp = await fetch(`${basisAset()}/mock/api-${peran}.json`, { cache: "force-cache" });
      if (!resp.ok) {
        throw new Error(
          `Fixture demo "${peran}" tidak bisa dimuat (HTTP ${resp.status}). ` +
            "Jalankan scripts/rekam_fixture_demo.py lalu build ulang."
        );
      }
      simpanan[peran] = (await resp.json()) as PetaPeran;
      return simpanan[peran];
    })();
  }
  return sedangMemuat[peran];
}

/** Ambil peran dari header Authorization berisi token demo berformat JWT. */
export function peranDariHeader(headers: HeadersInit | undefined): PeranMock | null {
  if (!headers) return null;
  const mentah =
    headers instanceof Headers
      ? headers.get("Authorization") ?? headers.get("authorization")
      : Array.isArray(headers)
        ? (headers.find(([k]) => k.toLowerCase() === "authorization")?.[1] ?? null)
        : ((headers as Record<string, string>).Authorization ??
          (headers as Record<string, string>).authorization ??
          null);
  if (!mentah) return null;
  const token = mentah.trim().replace(/^Bearer\s+/i, "");
  const peran = peranDariToken(token);
  return peran;
}

/** Baca klaim `role` dari payload token demo (tiga bagian dipisah titik). */
export function peranDariToken(token: string | null): PeranMock | null {
  if (!token) return null;
  const bagian = token.split(".");
  if (bagian.length !== 3) return null;
  try {
    let b64 = bagian[1].replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4) b64 += "=";
    const payload = JSON.parse(atob(b64)) as { role?: string };
    const role = payload?.role ?? "";
    return (PERAN_MOCK as readonly string[]).includes(role) ? (role as PeranMock) : null;
  } catch {
    return null;
  }
}

/** Metode yang dianggap menulis (sama dengan `lib/refresh.ts`). */
function menulis(method: string | undefined): boolean {
  const m = (method ?? "GET").toUpperCase();
  return m === "POST" || m === "PATCH" || m === "PUT" || m === "DELETE";
}

/**
 * Sesi demo di memori. Demo statis tidak punya database, jadi "Muat Demo" tidak
 * bisa benar-benar menyemai data — tetapi statusnya harus berubah, kalau tidak
 * tombolnya terlihat rusak. Setelah aksi demo apa pun, /demo/session dilaporkan
 * aktif selama tab ini terbuka; data yang tampil tetap data terekam.
 */
let sesiDemoAktif = (() => {
  try {
    return typeof sessionStorage !== "undefined" && sessionStorage.getItem("mealchain.demo.sesi") === "aktif";
  } catch {
    return false;
  }
})();

function tandaiSesi(aktif: boolean) {
  sesiDemoAktif = aktif;
  try {
    if (typeof sessionStorage !== "undefined") {
      if (aktif) sessionStorage.setItem("mealchain.demo.sesi", "aktif");
      else sessionStorage.removeItem("mealchain.demo.sesi");
    }
  } catch {
    // sessionStorage diblokir: status sesi cukup di memori.
  }
}

function sesiDemoAktifkan(contoh: Record<string, unknown>) {
  const sekarang = new Date();
  const kedaluwarsa = new Date(sekarang.getTime() + 4 * 3600 * 1000);
  return {
    ...contoh,
    active: true,
    enforced: true,
    session_id: "demo-statis",
    status: "aktif",
    mode: "realtime",
    expires_at: kedaluwarsa.toISOString(),
    anchor_now: sekarang.toISOString(),
    server_now: sekarang.toISOString(),
    remaining_seconds: 4 * 3600,
  };
}

function kunci(path: string): { utuh: string; polos: string; pola: string } {
  const [tanpaKueri] = path.split("?");
  return {
    utuh: path,
    polos: tanpaKueri,
    pola: tanpaKueri.replace(POLA_UUID, "{id}"),
  };
}

/** Jawaban untuk satu panggilan; null bila tidak ada data demo yang cocok. */
export async function jawabMock(
  peran: PeranMock,
  path: string,
  init: RequestInit
): Promise<Fixture | null> {
  const method = (init.method ?? "GET").toUpperCase();
  const polosPath = path.split("?")[0];

  const peta = await muatPeran(peran);
  if (!peta) return null;
  const { utuh, polos, pola } = kunci(path);
  const contohSesi = (peta["GET /demo/session"]?.body ?? {}) as Record<string, unknown>;

  // Tulisan: dibalas sukses tanpa mengubah data. Aksi demo tetap mengubah
  // status sesi di memori supaya tombol "Muat Demo"/"Akhiri sesi" tidak diam,
  // dan balasannya berbentuk sesi — UI memakai balasan itu sebagai state.
  if (menulis(method)) {
    if (polosPath === "/demo/session/end") {
      tandaiSesi(false);
      return {
        status: 200,
        body: { ...contohSesi, active: false, status: "kosong", session_id: null, remaining_seconds: 0 },
      };
    }
    if (polosPath.startsWith("/demo/")) {
      tandaiSesi(true);
      return { status: 200, body: sesiDemoAktifkan(contohSesi) };
    }
    return { status: 200, body: { ok: true, simulated: true, mode: "demo-statis" } };
  }

  const langsung = peta[`${method} ${utuh}`] ?? peta[`${method} ${polos}`];
  if (polos === "/demo/session") {
    if (!langsung) return null;
    return sesiDemoAktif
      ? { status: 200, body: sesiDemoAktifkan(langsung.body as Record<string, unknown>) }
      : langsung;
  }
  if (langsung) return langsung;

  // Pola: UUID pada kunci terekam diganti `{id}` supaya id lain tetap kena.
  const awalan = `${method} `;
  for (const [k, v] of Object.entries(peta)) {
    if (!k.startsWith(awalan)) continue;
    if (k.slice(awalan.length).split("?")[0].replace(POLA_UUID, "{id}") === pola) return v;
  }
  return null;
}

/** Token demo berformat JWT: UI membaca klaim `role` dari payload (lib/auth.ts). */
export function tokenMock(peran: PeranMock): string {
  const b64url = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const header = b64url({ alg: "none", typ: "JWT" });
  const payload = b64url({
    sub: `demo-${peran}`,
    role: peran,
    demo: true,
    exp: Math.floor(Date.now() / 1000) + 4 * 3600,
  });
  // Tanda tangan palsu: tidak ada verifikasi di demo statis.
  return `${header}.${payload}.demo-statis`;
}

/** Peran dari email demo; null bila bukan akun demo yang dikenal. */
export function peranDariEmail(email: string): PeranMock | null {
  const e = email.trim().toLowerCase();
  if (e.startsWith("sppg.head@")) return "sppg_head";
  if (e.startsWith("sppg.nutritionist@")) return "sppg_nutritionist";
  if (e.startsWith("bgn.monitor@")) return "bgn_monitor";
  return null;
}
