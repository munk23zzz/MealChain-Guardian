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

import { terapkanBaca, terapkanTulisan } from "./mock-ubah";

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
  // Token sisa build lama ("mock:<peran>") tetap dilayani agar pengunjung lama
  // tidak melihat panel kosong hanya karena belum keluar dari sesi sebelumnya.
  const lama = /^mock:([a-z_]+)$/.exec(token);
  if (lama) return lama[1] as PeranMock;
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

let sesiPernahDibangun = false;

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

// ── Simulasi putaran agent ──────────────────────────────────────────────────
// Demo statis tidak punya pipeline sungguhan, tetapi tombol "Jalankan agent"
// harus menghasilkan jejak yang bisa diperiksa: 5 langkah, satu keputusan baru
// berstatus `proposed`, dan bukti putaran terakhir. Semuanya dibuat di klien
// lalu disimpan sampai halaman dimuat ulang.

export type LangkahPutaran = { step: string; tool: string | null; ringkas: string; at: string };

type Putaran = {
  decision_id: string;
  commodity: string;
  steps: LangkahPutaran[];
  at: string;
  quantity_kg: number;
};

let putaranTerakhir: Putaran | null = null;

/** UUID v4 acak — bentuknya penting karena UI memotong 8 karakter pertama. */
function uuidPalsu(): string {
  const hex = (n: number) =>
    Array.from({ length: n }, () => Math.floor(Math.random() * 16).toString(16)).join("");
  return `${hex(8)}-${hex(4)}-4${hex(3)}-a${hex(3)}-${hex(12)}`;
}

/** Lima langkah pipeline dengan jeda 700 ms — sama untuk SSE dan bukti putaran. */
export function langkahPutaran(komoditas: string): LangkahPutaran[] {
  const bahan = komoditas && komoditas.trim() ? komoditas.trim() : "komoditas terpilih";
  const mulai = Date.now();
  const jam = (i: number) => new Date(mulai + i * 700).toISOString();
  return [
    {
      step: "DETECT",
      tool: "stock_scan",
      ringkas: `Memindai stok dan permintaan ${bahan} di lokasi Anda`,
      at: jam(0),
    },
    {
      step: "ANALYZE",
      tool: "gap_analysis",
      ringkas: `Menghitung selisih pasokan–permintaan ${bahan} untuk 7 hari ke depan`,
      at: jam(1),
    },
    {
      step: "MATCH",
      tool: "supplier_search",
      ringkas: "Mencari pemasok dalam jangkauan yang bisa menutup celah",
      at: jam(2),
    },
    {
      step: "PROPOSE",
      tool: "propose_decision",
      ringkas: "Menyusun usulan alokasi — status proposed, belum disetujui",
      at: jam(3),
    },
    {
      step: "SUPERVISE",
      tool: "supervisor_review",
      ringkas: "Tinjauan supervisor atas usulan sebelum masuk antrean keputusan",
      at: jam(4),
    },
  ];
}

/** Catat putaran baru (dipanggil dari POST /demo/agent/run). */
function catatPutaran(komoditas: string): Putaran {
  const keputusan = {
    decision_id: uuidPalsu(),
    commodity: komoditas,
    steps: langkahPutaran(komoditas),
    at: new Date().toISOString(),
    quantity_kg: 0,
  };
  putaranTerakhir = keputusan;
  return keputusan;
}

/** Sisipkan keputusan hasil putaran ke daftar /decisions (kalau ada). */
function sisipkanKeputusan(body: unknown, putaran: Putaran): unknown {
  if (!body || typeof body !== "object") return body;
  const amplop = body as { items?: unknown[]; count?: number; total?: number };
  if (!Array.isArray(amplop.items)) return body;
  const contoh = (amplop.items[0] ?? {}) as Record<string, unknown>;
  const baru: Record<string, unknown> = {
    ...contoh,
    decision_id: putaran.decision_id,
    decision_type: "regional_balance",
    status: "proposed",
    proposed_by: "supervisor_agent",
    quantity_kg: putaran.quantity_kg || contoh.quantity_kg || 220,
    created_at: putaran.at,
    expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
    valid: true,
    seconds_remaining: 1800,
    rejection_reason: null,
    has_agent_review: true,
  };
  return {
    ...amplop,
    items: [baru, ...amplop.items.filter((x) => (x as { decision_id?: string }).decision_id !== putaran.decision_id)],
    count: typeof amplop.count === "number" ? amplop.count + 1 : amplop.count,
    total: typeof amplop.total === "number" ? amplop.total + 1 : amplop.total,
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
    if (polosPath === "/demo/agent/run") {
      let isi: Record<string, unknown> = {};
      try {
        isi = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
      } catch {
        isi = {};
      }
      const p = catatPutaran(String(isi.commodity ?? "beras"));
      tandaiSesi(true);
      // Putaran sungguhan butuh beberapa detik; panel menutup kanal langkah
      // begitu POST selesai, jadi tunda balasan agar 5 langkah sempat tampil.
      await new Promise((selesai) => setTimeout(selesai, 3800));
      return {
        status: 200,
        body: {
          ok: true,
          mode: isi.mode ?? "realtime",
          commodity: p.commodity,
          run_token: isi.run_token ?? null,
          session_id: (isi.demo_session as string) ?? "demo-statis",
          created: [
            {
              decision_id: p.decision_id,
              status: "proposed",
              commodity: p.commodity,
              quantity_kg: p.quantity_kg,
            },
          ],
          skipped: [],
          steps: p.steps,
        },
      };
    }
    if (polosPath === "/demo/session/end") {
      tandaiSesi(false);
      return {
        status: 200,
        body: { ...contohSesi, active: false, status: "kosong", session_id: null, remaining_seconds: 0 },
      };
    }
    if (polosPath.startsWith("/demo/")) {
      // Panel memakai `created` untuk memutuskan memuat ulang halaman: klik
      // pertama "Muat Demo" = dataset dibangun, klik berikutnya = sudah aktif.
      const dibuat = !sesiPernahDibangun;
      sesiPernahDibangun = true;
      tandaiSesi(true);
      return { status: 200, body: { ...sesiDemoAktifkan(contohSesi), created: dibuat } };
    }
    // Aksi lain (setujui, eksekusi, karantina, penerimaan, periksa ulang)
    // mengubah keadaan demo sehingga penyegaran berikutnya tidak lagi
    // memperlihatkan data lama di bawah pesan "berhasil".
    let isiTulis: unknown = null;
    if (init.body) {
      try {
        isiTulis = JSON.parse(String(init.body));
      } catch {
        isiTulis = null;
      }
    }
    const balasTulis = terapkanTulisan(polosPath, isiTulis);
    if (balasTulis) return { status: 200, body: balasTulis };
    return { status: 200, body: { ok: true, simulated: true, mode: "demo-statis" } };
  }

  const langsung = peta[`${method} ${utuh}`] ?? peta[`${method} ${polos}`];

  // Panel Demo Control memakai endpoint /demo/*, yang di backend hanya boleh
  // untuk peran SPPG (Monitor BGN menerima 403 — itu terekam apa adanya). Di
  // demo statis panelnya sengaja dibuka untuk semua akun, jadi datanya dipinjam
  // dari rekaman peran SPPG supaya panel tidak tampil "belum ada data".
  if (polos.startsWith("/demo/") && (!langsung || langsung.status >= 400) && peran !== "sppg_head") {
    const petaSppg = await muatPeran("sppg_head");
    const pinjam = petaSppg[`${method} ${utuh}`] ?? petaSppg[`${method} ${polos}`];
    if (pinjam && pinjam.status < 400) return pinjam;
  }

  if (polos === "/demo/session") {
    if (!langsung) return null;
    return sesiDemoAktif
      ? { status: 200, body: sesiDemoAktifkan(langsung.body as Record<string, unknown>) }
      : langsung;
  }

  // Bukti putaran terakhir: setelah "Jalankan agent", panel membaca endpoint ini
  // dan menampilkan 5 langkah + id keputusan yang benar-benar dibuat.
  if (polos === "/demo/agent/last-run" && putaranTerakhir) {
    const dasar = (langsung?.body ?? {}) as Record<string, unknown>;
    return {
      status: 200,
      body: {
        ...dasar,
        found: true,
        decision_id: putaranTerakhir.decision_id,
        steps: putaranTerakhir.steps,
        agents: ["detector", "analyst", "matcher", "proposer", "supervisor"],
        agents_run_id: `demo-statis-${putaranTerakhir.decision_id.slice(0, 8)}`,
        supervisor: {
          status: "ok",
          provider: "demo-statis",
          fallback_used: false,
          summary: `Supervisor menyetujui usulan alokasi ${putaranTerakhir.commodity} untuk ditinjau manusia.`,
        },
        agent_review: { status: "ok", error: null, run_id: "demo-statis" },
        mode: "realtime",
        supplier: dasar.supplier ?? null,
        supply_gap: dasar.supply_gap ?? null,
      },
    };
  }

  // Ringkasan gerbang untuk keputusan yang baru lahir: rekaman tidak punya
  // contoh "proposed", jadi warisi bentuknya lalu netralkan hasil eksekusi —
  // tanpa ini panel menampilkan "Sudah dieksekusi" plus daftar alasan yang
  // saling bertentangan untuk keputusan yang belum disetujui siapa pun.
  if (
    putaranTerakhir &&
    polos === `/decisions/${putaranTerakhir.decision_id}/approval-summary`
  ) {
    const cetakan = peta[`${method} ${kunci(polos).pola}`];
    const dasar = ((langsung ?? cetakan)?.body ?? {}) as Record<string, unknown>;
    const safety = (dasar.safety ?? {}) as Record<string, unknown>;
    return {
      status: 200,
      body: {
        ...dasar,
        decision_id: putaranTerakhir.decision_id,
        status: "proposed",
        proposed_by: "supervisor_agent",
        can_execute: false,
        commodity: putaranTerakhir.commodity,
        quantity_kg: putaranTerakhir.quantity_kg,
        verifier: { verdict: "pending", verified_by: null },
        safety: {
          ...safety,
          worst_status: "pending",
          blocked: false,
          block_code: null,
          reason: null,
          reasons: [],
          codes: [],
          batches_checked: 0,
          batch_ids: [],
        },
        purchase_order: null,
        execution_target: null,
      },
    };
  }

  // Daftar keputusan: keputusan hasil putaran disisipkan paling atas supaya
  // tab Recommendations dan Decision & Evidence benar-benar bertambah.
  if (putaranTerakhir && polos === "/decisions" && langsung) {
    return { status: langsung.status, body: sisipkanKeputusan(langsung.body, putaranTerakhir) };
  }

  // Bukti data: setelah sesi dibangun, "as_of" mengikuti waktu sekarang.
  if (polos === "/demo/data-status" && sesiDemoAktif && langsung) {
    const dasar = (langsung.body ?? {}) as Record<string, unknown>;
    return { status: 200, body: { ...dasar, as_of: new Date().toISOString() } };
  }

  // Surplus wilayah: UI meminta BEBERAPA komoditas sekaligus (?commodity=…&
  // commodity=…), sedangkan rekaman menyimpan satu varian per komoditas.
  // Tanpa penggabungan, panel berjudul "4 komoditas" hanya menampilkan ayam.
  if (polos === "/surplus/regions" && langsung) {
    const kueri = new URLSearchParams(utuh.split("?")[1] ?? "");
    const diminta = kueri.getAll("commodity");
    if (diminta.length > 1) {
      const gabung = new Map<string, Record<string, number>>();
      const dasar = (langsung.body ?? {}) as Record<string, unknown>;
      let totalSurplus = 0;
      let totalLayak = 0;
      for (const nama of diminta) {
        const satu = peta[`GET /surplus/regions?commodity=${nama}&limit=6`];
        const isi = (satu?.body ?? {}) as Record<string, unknown>;
        for (const r of (isi.regions ?? []) as Record<string, unknown>[]) {
          const kunciWilayah = String(r.region ?? "");
          const lama = gabung.get(kunciWilayah) ?? { surplus_kg: 0, layak_kg: 0, lokasi: 0 };
          lama.surplus_kg += Number(r.surplus_kg ?? 0);
          lama.layak_kg += Number(r.layak_kg ?? 0);
          gabung.set(kunciWilayah, lama);
          totalSurplus += Number(r.surplus_kg ?? 0);
          totalLayak += Number(r.layak_kg ?? 0);
        }
      }
      const regions = Array.from(gabung.entries())
        .map(([region, v]) => ({ region, surplus_kg: v.surplus_kg, layak_kg: v.layak_kg }))
        .sort((a, b) => b.surplus_kg - a.surplus_kg);
      return {
        status: 200,
        body: {
          ...dasar,
          commodities: diminta,
          excluded_location: kueri.get("exclude"),
          regions,
          totals: { ...(dasar.totals as Record<string, unknown> | undefined), surplus_kg: totalSurplus, layak_kg: totalLayak, regions: regions.length },
        },
      };
    }
  }

  if (langsung) {
    // Keadaan demo (status keputusan, karantina batch, saringan wilayah/agenda)
    // diterapkan di sini supaya hasil tulis langsung terlihat pada penyegaran.
    const ubah = terapkanBaca(utuh, polos, langsung.body);
    return ubah ? { status: langsung.status, body: ubah } : langsung;
  }

  // Pola: UUID pada kunci terekam diganti `{id}` supaya id lain tetap kena.
  const awalan = `${method} `;
  for (const [k, v] of Object.entries(peta)) {
    if (!k.startsWith(awalan)) continue;
    if (k.slice(awalan.length).split("?")[0].replace(POLA_UUID, "{id}") === pola) {
      const ubah = terapkanBaca(utuh, polos, v.body);
      return ubah ? { status: v.status, body: ubah } : v;
    }
  }

  // Keputusan yang lahir di sesi ini (mis. dari "Jalankan agent") tidak punya
  // rekaman rincian. Pakai baris daftarnya supaya popup tidak menampilkan galat.
  if (polos.startsWith("/decisions/")) {
    const id = polos.split("/")[2] ?? "";
    const daftar = ((peta["GET /decisions"]?.body ?? {}) as Record<string, unknown>).items;
    if (Array.isArray(daftar)) {
      const baris = (daftar as Record<string, unknown>[]).find((x) => x.decision_id === id);
      if (baris) return { status: 200, body: baris };
    }
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
