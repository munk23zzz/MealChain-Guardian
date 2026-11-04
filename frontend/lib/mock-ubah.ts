// Lapisan "perubahan" untuk demo statis: membaca dan menulis dijawab dari
// rekaman, TAPI aksi tulis harus benar-benar mengubah apa yang dilihat pengguna.
//
// Kenapa dipisah dari mock-api.ts: mock-api menjawab satu panggilan; modul ini
// yang memegang keadaan (status keputusan, karantina batch, penerimaan) dan
// menerapkannya kembali pada respons baca berikutnya. Tanpa keadaan bersama,
// tombol Setuju menulis "sukses" lalu daftar keputusan tetap bilang "menunggu"
// — kontradiksi yang persis ditanyakan juri.
//
// Keadaan disimpan di sessionStorage supaya bertahan saat panel memuat ulang,
// tetapi tidak mengotori kunjungan berikutnya (tab baru = data rekaman bersih).

const KUNCI = "mealchain.demo.ubahan";

type Ubahan = {
  keputusan: Record<
    string,
    {
      status?: string;
      approved_at?: string;
      executed_at?: string;
      verdict?: string;
      po_number?: string;
    }
  >;
  batch: Record<string, { quarantine_status?: string | null }>;
  penerimaan: Record<string, { status?: string }>;
  /** Status PO per nomor: hasil "Review & kirim" di sesi ini. */
  po: Record<string, { status?: string }>;
};

function kosong(): Ubahan {
  return { keputusan: {}, batch: {}, penerimaan: {}, po: {} };
}

function muat(): Ubahan {
  try {
    const mentah = sessionStorage.getItem(KUNCI);
    if (!mentah) return kosong();
    const isi = JSON.parse(mentah) as Partial<Ubahan>;
    return {
      keputusan: isi.keputusan ?? {},
      batch: isi.batch ?? {},
      penerimaan: isi.penerimaan ?? {},
      po: isi.po ?? {},
    };
  } catch {
    return kosong();
  }
}

function simpan(u: Ubahan): void {
  try {
    sessionStorage.setItem(KUNCI, JSON.stringify(u));
  } catch {
    /* mode privat: perubahan tetap berlaku selama tab hidup */
  }
}

export function lupakanUbahan(): void {
  try {
    sessionStorage.removeItem(KUNCI);
  } catch {
    /* abaikan */
  }
}

function uuidDemo(): string {
  const hex = (n: number) =>
    Array.from({ length: n }, () => Math.floor(Math.random() * 16).toString(16)).join("");
  return `${hex(8)}-${hex(4)}-4${hex(3)}-a${hex(3)}-${hex(12)}`;
}

function q(url: string, nama: string): string | null {
  const tanya = url.indexOf("?");
  if (tanya < 0) return null;
  return new URLSearchParams(url.slice(tanya + 1)).get(nama);
}

function qSemua(url: string, nama: string): string[] {
  const tanya = url.indexOf("?");
  if (tanya < 0) return [];
  return new URLSearchParams(url.slice(tanya + 1)).getAll(nama);
}

function body(isi: unknown): Record<string, unknown> {
  return (isi ?? {}) as Record<string, unknown>;
}

function angkakan(nilai: unknown): number | null {
  const n = Number(nilai);
  return Number.isFinite(n) ? n : null;
}

/* ------------------------------------------------------------------ baca */

/**
 * Terapkan keadaan demo pada satu respons baca. Mengembalikan `null` bila
 * endpoint ini tidak perlu disentuh (pakai badan rekaman apa adanya).
 */
export function terapkanBaca(
  utuh: string,
  polos: string,
  isi: unknown
): Record<string, unknown> | null {
  const u = muat();

  if (polos === "/decisions") return saringKeputusan(utuh, body(isi), u);
  if (polos === "/batches") return ubahBatch(body(isi), u);
  if (polos === "/receipts/menunggu") {
    const b = body(isi);
    const daftar = Array.isArray(b.items) ? (b.items as Record<string, unknown>[]) : [];
    const sisa = daftar.filter((r) => !u.penerimaan[String(r.id ?? "")]);
    if (sisa.length === daftar.length) return null;
    return { ...b, items: sisa, total: sisa.length };
  }

  if (polos.startsWith("/decisions/")) {
    const pecah = polos.split("/");
    const id = pecah[2] ?? "";
    const ubah = u.keputusan[id];
    if (!ubah) return null;
    const b = body(isi);
    if (polos.endsWith("/approval-summary")) return ringkasGerbang(b, ubah, u.po);
    if (pecah.length === 3) return { ...b, status: ubah.status ?? b.status };
    return null;
  }

  if (polos === "/sap/purchase-orders") {
    const b = body(isi);
    const daftar = Array.isArray(b.items) ? (b.items as Record<string, unknown>[]) : null;
    if (!daftar) return null;
    let tersentuhPo = false;
    const hasilPo = daftar.map((r) => {
      const ubah = u.po[String(r.po_number ?? "")];
      if (!ubah) return r;
      tersentuhPo = true;
      return { ...r, ...ubah };
    });
    if (!tersentuhPo) return null;
    return { ...b, items: hasilPo };
  }
  if (polos === "/price/monitor") return saringHarga(utuh, body(isi));
  if (polos === "/agenda") return geserAgenda(utuh, body(isi));
  return null;
}

function saringKeputusan(utuh: string, b: Record<string, unknown>, u: Ubahan): Record<string, unknown> | null {
  const daftar = Array.isArray(b.items) ? (b.items as Record<string, unknown>[]) : null;
  if (!daftar) return null;

  const ubahanKeputusan = u.keputusan;
  let tersentuh = false;
  let hasil = daftar.map((baris) => {
    const id = String(baris.decision_id ?? "");
    const ubah = ubahanKeputusan[id];
    if (!ubah) return baris;
    tersentuh = true;
    return {
      ...baris,
      ...ubah,
      valid: ubah.status === "approved" || ubah.status === "executed" ? false : baris.valid,
    };
  });

  // `?window=24h` — panel Overview meminta jendela tertentu; rekaman memuat
  // seluruh riwayat, jadi tanpa saringan ini judul bilang "24 jam terakhir"
  // padahal barisnya dari tiga hari lalu.
  const jendela = q(utuh, "window");
  if (jendela) {
    const jam = /^(\d+)([hd])$/.exec(jendela);
    if (jam) {
      // Jam acuan = jam REKAMAN (baris terbaru), bukan Date.now(): pada demo
      // statis data bisa berumur beberapa hari, dan memakai jam dinding membuat
      // chip "24 jam" kosong sementara lonceng masih menghitung 2 keputusan.
      const cap = daftar
        .map((r) => Date.parse(String(r.created_at ?? "")))
        .filter((n) => Number.isFinite(n));
      const acuan = cap.length ? Math.max(...cap) : Date.now();
      const satuan = jam[2] === "d" ? 86_400_000 : 3600_000;
      const batas = acuan - Number(jam[1]) * satuan;
      hasil = hasil.filter((baris) => {
        const waktu = Date.parse(String(baris.created_at ?? ""));
        return Number.isFinite(waktu) && waktu >= batas;
      });
    }
  }

  const status = q(utuh, "status");
  if (status) {
    hasil = hasil.filter((baris) => String(baris.status ?? "") === status);
  }

  if (hasil.length !== daftar.length) tersentuh = true;
  if (!tersentuh) return null;
  return {
    ...b,
    items: hasil,
    count: hasil.length,
    total: typeof b.total === "number" ? hasil.length : b.total,
  };
}

function ubahBatch(b: Record<string, unknown>, u: Ubahan): Record<string, unknown> | null {
  const kunciDaftar = Array.isArray(b.batches) ? "batches" : Array.isArray(b.items) ? "items" : null;
  if (!kunciDaftar) return null;
  const daftar = b[kunciDaftar] as Record<string, unknown>[];
  let berubah = false;
  const hasil = daftar.map((baris) => {
    const id = String(baris.batch_id ?? baris.id ?? "");
    const ubah = u.batch[id];
    if (!ubah) return baris;
    berubah = true;
    return { ...baris, quarantine_status: ubah.quarantine_status };
  });
  return berubah ? { ...b, [kunciDaftar]: hasil } : null;
}

function ringkasGerbang(
  b: Record<string, unknown>,
  ubah: { status?: string; verdict?: string; po_number?: string },
  poSesi: Record<string, { status?: string }> = {}
): Record<string, unknown> {
  const status = ubah.status ?? "pending_approval";
  const selesai = status === "executed";
  const disetujui = status === "approved";
  const terverifikasi = Boolean(ubah.verdict);
  return {
    ...b,
    status,
    can_approve: status === "pending_approval" && terverifikasi,
    can_reject: status === "pending_approval",
    can_execute: disetujui,
    can_verify: status === "pending_approval" && !terverifikasi,
    verifier: terverifikasi
      ? { verdict: ubah.verdict, verified_by: "demo-statis" }
      : (b.verifier ?? { verdict: "unavailable", verified_by: null }),
    expiry: { ...(b.expiry as Record<string, unknown> | undefined), valid: status === "pending_approval" },
    blocking_reasons: terverifikasi || selesai ? [] : (b.blocking_reasons ?? []),
    // PO yang terbit setelah Eksekusi harus terlihat di panel Detail; rekaman
    // selalu `purchase_order: null` sehingga tanpa ini "Unduh PDF"/"Review PO"
    // tetap mati walau PO benar-benar dibuat.
    purchase_order: (() => {
      const dasar = (b.purchase_order ?? null) as Record<string, unknown> | null;
      const nomor = ubah.po_number ?? (dasar?.po_number as string | undefined);
      if (!nomor) return null;
      const statusSesi = poSesi[nomor]?.status;
      return {
        ...(dasar ?? {}),
        po_number: nomor,
        status: statusSesi ?? (dasar?.status as string | undefined) ?? "confirmed",
      };
    })(),
  };
}

function saringHarga(utuh: string, b: Record<string, unknown>): Record<string, unknown> | null {
  const baris = Array.isArray(b.rows) ? (b.rows as Record<string, unknown>[]) : null;
  if (!baris) return null;
  const wilayah = q(utuh, "region");
  const komoditas = q(utuh, "commodity");
  const kode = komoditas ? komoditas.split(",").filter(Boolean) : null;
  const adaHari = Number(q(utuh, "days") ?? 0) > 0;
  if (!wilayah && !kode && !adaHari) return null;

  let hasil = baris;
  if (wilayah) {
    const cari = wilayah.trim().toLowerCase();
    const cocokPersis = hasil.filter((r) => String(r.region_name ?? "").toLowerCase() === cari);
    // Nama lokasi SPPG ("Jakarta") tidak selalu sama dengan nama wilayah PIHPS
    // ("DKI Jakarta"), jadi jatuh ke pencocokan mengandung sebelum menyerah.
    hasil = cocokPersis.length
      ? cocokPersis
      : hasil.filter((r) => String(r.region_name ?? "").toLowerCase().includes(cari));
  }
  if (kode && kode.length) {
    const label = String((b.commodities as unknown[])?.length ? "" : "");
    void label;
    hasil = hasil.filter((r) => {
      const kodeBaris = String(r.commodity_code ?? "");
      if (kodeBaris) return kode.some((k) => kodeBaris === k || kodeBaris.toLowerCase() === k.toLowerCase());
      const teks = `${String(r.commodity_label ?? "")}`.toLowerCase();
      return kode.some((k) => teks.includes(k.toLowerCase()));
    });
  }
  // Pilihan rentang 7/30/90 hari: rekaman hanya punya satu jendela 30 hari,
  // jadi saring baris menurut `days` dan tulis ulang jendela + cakupannya.
  // Tanpa ini pil "7 hari" menyala sementara judul tetap "28 Sep – 28 Okt".
  const mintaHari = Number(q(utuh, "days") ?? 0);
  if (Number.isFinite(mintaHari) && mintaHari > 0) {
    const jendela = (b.window ?? {}) as Record<string, unknown>;
    const akhir = Date.parse(String(jendela.end ?? ""));
    if (Number.isFinite(akhir)) {
      const mulaiMs = akhir - (mintaHari - 1) * 86_400_000;
      hasil = hasil.filter((r) => {
        const t = Date.parse(String(r.observed_on ?? ""));
        return Number.isFinite(t) && t >= mulaiMs && t <= akhir;
      });
      const tanggal = new Set(hasil.map((r) => String(r.observed_on ?? "")));
      return {
        ...b,
        days: mintaHari,
        window: { ...jendela, start: new Date(mulaiMs).toISOString().slice(0, 10) },
        coverage: {
          ...((b.coverage ?? {}) as Record<string, unknown>),
          tanggal_terisi: tanggal.size,
          tanggal_diminta: mintaHari,
        },
        rows: hasil,
        row_count: hasil.length,
      };
    }
  }
  return { ...b, rows: hasil, row_count: hasil.length };
}

/**
 * Kalender: jendela rekaman dibekukan pada tanggal perekaman, sedangkan UI
 * meminta jendela yang bergerak (bulan berjalan). Geser tanggalnya sebesar
 * selisih hari supaya hari ini benar-benar ada di dalam rentang.
 */
function geserAgenda(utuh: string, b: Record<string, unknown>): Record<string, unknown> | null {
  const diminta = q(utuh, "start");
  const lama = (b.period as Record<string, unknown> | undefined)?.start;
  const akhirRekaman = (b.period as Record<string, unknown> | undefined)?.end;
  const hari = Array.isArray(b.days) ? (b.days as Record<string, unknown>[]) : null;
  if (!diminta || !lama || !hari) return null;
  // Jangkar di UJUNG rekaman, bukan di awal. Dulu selisih dihitung dari `start`
  // yang diminta (grid 42 sel bisa mulai 5 hari sebelum awal rekaman), sehingga
  // sel "hari ini" menampilkan entri 5 hari lalu — mis. menu 1.200 porsi ada,
  // padahal hari ini tidak ada menu, dan keputusan hari ini hilang.
  const jangkar = Date.parse(String(akhirRekaman ?? lama));
  const kini = Date.now() + 7 * 3600_000; // WIB
  const hariIni = Date.UTC(
    new Date(kini).getUTCFullYear(),
    new Date(kini).getUTCMonth(),
    new Date(kini).getUTCDate()
  );
  const selisih = Math.round((hariIni - Date.UTC(
    new Date(jangkar).getUTCFullYear(),
    new Date(jangkar).getUTCMonth(),
    new Date(jangkar).getUTCDate()
  )) / 86_400_000);
  if (!Number.isFinite(selisih) || selisih === 0) return null;
  const geser = (tgl: unknown) => {
    const t = Date.parse(String(tgl ?? ""));
    if (!Number.isFinite(t)) return tgl;
    return new Date(t + selisih * 86_400_000).toISOString().slice(0, 10);
  };
  return {
    ...b,
    period: { ...(b.period as Record<string, unknown>), start: geser((b.period as Record<string, unknown>).start), end: geser((b.period as Record<string, unknown>).end) },
    days: hari.map((h) => ({ ...h, date: geser(h.date) })),
  };
}

/* ----------------------------------------------------------------- tulis */

/** Jawaban untuk satu aksi tulis; `null` = pakai balasan umum `{ok:true}`. */
export function terapkanTulisan(
  polos: string,
  isi: unknown
): Record<string, unknown> | null {
  const u = muat();
  const b = body(isi);
  const sekarang = new Date().toISOString();

  if (polos === "/actions/approve") {
    const id = String(b.decision_id ?? "");
    u.keputusan[id] = { ...(u.keputusan[id] ?? {}), status: "approved", approved_at: sekarang };
    simpan(u);
    return { ok: true, decision_id: id, status: "approved", approved_at: sekarang, iteration: b.iteration ?? 1 };
  }

  if (polos === "/actions/execute") {
    const id = String(b.decision_id ?? "");
    const nomorPo = `PO-DEMO-${id.slice(0, 6).toUpperCase()}`;
    // PO harus ikut tercatat pada ringkasan: setelah Eksekusi, panel Detail
    // membaca `purchase_order` dari approval-summary. Tanpa ini UI berkata
    // "PO … dibuat" lalu panelnya menulis "Belum ada PO untuk keputusan ini".
    u.keputusan[id] = {
      ...(u.keputusan[id] ?? {}),
      status: "executed",
      executed_at: sekarang,
      po_number: nomorPo,
    };
    simpan(u);
    return {
      ok: true,
      decision_id: id,
      status: "executed",
      executed_at: sekarang,
      po_number: nomorPo,
      po_status: "confirmed",
      dikirim: 1,
      ditahan: 0,
    };
  }

  if (polos === "/actions/verify") {
    const id = String(b.decision_id ?? "");
    const verdict = String(b.verdict ?? "pass");
    u.keputusan[id] = { ...(u.keputusan[id] ?? {}), verdict };
    simpan(u);
    return {
      ok: true,
      decision_id: id,
      verdict: String(b.verdict ?? "pass"),
      recorded: true,
      provider: "demo-statis",
      verified_at: sekarang,
    };
  }

  if (polos === "/actions/propose" || polos === "/actions/repropose") {
    const asal = String(b.decision_id ?? b.supersedes_id ?? "");
    const id = uuidDemo();
    u.keputusan[id] = { status: "pending_approval" };
    // Keputusan asal IKUT berpindah status; kalau tidak, tombol "Ajukan" tampak
    // tidak melakukan apa pun (baris lama tetap "proposed"/"ditolak").
    if (asal) u.keputusan[asal] = { ...(u.keputusan[asal] ?? {}), status: "pending_approval" };
    simpan(u);
    return {
      ok: true,
      decision_id: id,
      supersedes_id: asal || null,
      status: "pending_approval",
      iteration: Number(b.iteration ?? 1) + 1,
      expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
    };
  }

  const setujuPo = /^\/actions\/purchase-orders\/([^/]+)\/approve$/.exec(polos);
  if (setujuPo) {
    const nomor = decodeURIComponent(setujuPo[1]);
    u.po[nomor] = { status: "confirmed" };
    simpan(u);
    return { ok: true, po_number: nomor, status: "confirmed", approved_at: sekarang };
  }

  const karantina = /^\/batches\/([^/]+)\/quarantine$/.exec(polos);
  if (karantina) {
    const id = decodeURIComponent(karantina[1]);
    const status = String(b.action ?? b.mode ?? "hold") === "release" ? null : "quarantined";
    u.batch[id] = { quarantine_status: status };
    simpan(u);
    return { ok: true, batch_id: id, quarantine_status: status, recorded_at: sekarang };
  }

  if (polos === "/supplier-exclusions/proposals") {
    const id = uuidDemo();
    return {
      ok: true,
      id,
      supplier_id: String(b.supplier_id ?? ""),
      scope_location_id: String(b.scope_location_id ?? ""),
      status: "proposed",
      reason: String(b.reason ?? ""),
      evidence_refs: b.evidence_refs ?? [],
      source_decision_id: String(b.decision_id ?? b.source_decision_id ?? ""),
      restoration_decision_id: null,
      activated_at: null,
      revoked_at: null,
      revocation_reason: null,
    };
  }

  const pulih = /^\/supplier-exclusions\/([^/]+)\/restore$/.exec(polos);
  if (pulih) {
    return {
      ok: true,
      id: decodeURIComponent(pulih[1]),
      status: "proposed",
      reason: String(b.reason ?? ""),
      evidence_refs: b.evidence_refs ?? [],
      // Panel pemulihan membaca `restoration_decision_id`; tanpa field ini ia
      // melesak saat memanggil onRestored (TypeError, bukan pesan).
      restoration_decision_id: String(b.decision_id ?? b.restoration_decision_id ?? ""),
      revoked_at: sekarang,
      revocation_reason: String(b.reason ?? ""),
    };
  }

  const terima = /^\/receipts\/([^/]+)\/(approve|reject)$/.exec(polos);
  if (terima) {
    const id = decodeURIComponent(terima[1]);
    const status = terima[2] === "approve" ? "approved" : "rejected";
    u.penerimaan[id] = { status };
    simpan(u);
    return { ok: true, receipt_id: id, status, reviewed_at: sekarang };
  }

  // Periksa ulang keamanan & kesegaran: balasan WAJIB punya bentuk yang dibaca
  // panel (`safety.safety_status`, `freshness.freshness_score`), kalau tidak
  // toast-nya justru menampilkan TypeError.
  if (polos === "/safety/evaluate") {
    const batch = String(b.batch_id ?? "");
    const lolos = batch.length % 2 === 0;
    return {
      ok: true,
      batch_id: batch,
      safety: {
        safety_status: lolos ? "passed" : "needs_verification",
        checked_at: sekarang,
        provider: "demo-statis",
        reasons: lolos ? [] : ["Verifikasi laboratorium belum dilampirkan"],
      },
      simulated: true,
    };
  }

  if (polos === "/freshness/evaluate") {
    const batch = String(b.batch_id ?? "");
    const komoditas = String(b.commodity ?? b.commodity_name ?? "bahan");
    void komoditas;
    const skor = 0.72 + ((batch.length % 7) * 0.03);
    const layakSampai = new Date(Date.now() + 36 * 3600_000).toISOString();
    return {
      ok: true,
      batch_id: batch,
      freshness: {
        freshness_score: Number(skor.toFixed(2)),
        usable_until: layakSampai,
        evaluated_at: sekarang,
        method_version: "demo-statis",
      },
      simulated: true,
    };
  }

  void angkakan;
  return null;
}

/** Angka permintaan untuk panel "Kecukupan" bila endpoint saldo tidak terekam. */
export function perkiraanSaldo(isi: unknown): Record<string, unknown> {
  const b = body(isi);
  return {
    commodity: b.commodity ?? null,
    location: b.location ?? null,
    available: false,
    reason: null,
    simulated: true,
  };
}

export { qSemua };
