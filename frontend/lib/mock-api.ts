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

/** Ambil peran dari header Authorization berisi token `mock:<peran>`. */
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
  const cocok = /^Bearer mock:([a-z_]+)$/.exec(mentah.trim());
  if (!cocok) return null;
  return (PERAN_MOCK as readonly string[]).includes(cocok[1]) ? (cocok[1] as PeranMock) : null;
}

/** Metode yang dianggap menulis (sama dengan `lib/refresh.ts`). */
function menulis(method: string | undefined): boolean {
  const m = (method ?? "GET").toUpperCase();
  return m === "POST" || m === "PATCH" || m === "PUT" || m === "DELETE";
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

  // Tulisan: dibalas sukses tanpa mengubah apa pun.
  if (menulis(method)) {
    return { status: 200, body: { ok: true, simulated: true, mode: "demo-statis" } };
  }

  const peta = await muatPeran(peran);
  if (!peta) return null;

  const { utuh, polos, pola } = kunci(path);
  const langsung = peta[`${method} ${utuh}`] ?? peta[`${method} ${polos}`];
  if (langsung) return langsung;

  // Pola: UUID pada kunci terekam diganti `{id}` supaya id lain tetap kena.
  const awalan = `${method} `;
  for (const [k, v] of Object.entries(peta)) {
    if (!k.startsWith(awalan)) continue;
    if (k.slice(awalan.length).split("?")[0].replace(POLA_UUID, "{id}") === pola) return v;
  }
  return null;
}

/** Token palsu untuk sesi demo — bentuknya tidak pernah dipakai backend. */
export function tokenMock(peran: PeranMock): string {
  return `mock:${peran}`;
}

/** Peran dari email demo; null bila bukan akun demo yang dikenal. */
export function peranDariEmail(email: string): PeranMock | null {
  const e = email.trim().toLowerCase();
  if (e.startsWith("sppg.head@")) return "sppg_head";
  if (e.startsWith("sppg.nutritionist@")) return "sppg_nutritionist";
  if (e.startsWith("bgn.monitor@")) return "bgn_monitor";
  return null;
}
