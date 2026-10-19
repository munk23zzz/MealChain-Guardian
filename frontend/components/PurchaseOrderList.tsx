/**
 * Daftar purchase order (W-5, 2026-10-17 · ditulis ulang 19 Okt 2026).
 *
 * Kenapa panel ini ada: `sap_mock_purchase_orders` selalu ditulis saat keputusan
 * dieksekusi, tetapi dulu tidak ada satu layar pun yang bisa menunjukkannya —
 * nomor PO hanya sempat muncul sebagai toast sesaat. Jadi klaim "dua approval →
 * PO terbit" tidak bisa diverifikasi di depan penilai.
 *
 * Aturan tampilan (semuanya dipaku tes):
 *
 * 1. **Sumber disebut, tapi dengan bahasa produk**: chip `SAP simulasi` +
 *    `sourceNote()`. Penanda ini WAJIB (Rules.md §4: data dari mock SAP harus
 *    jelas berlabel) — yang dibuang adalah bahasa internal seperti "tabel
 *    transaksi mock di DB demo", bukan kejujurannya.
 * 2. **Status diterjemahkan** (`submitted` → "terkirim"), bukan ditampilkan
 *    mentah, dan status asing dibiarkan apa adanya (tidak dikarang).
 * 3. **Status hantu tidak dipamerkan**: backend tidak pernah menulis `draft`
 *    (hanya CHECK yang mengizinkannya), jadi chip "draf 0" tidak dirender.
 * 4. **Arti status dijelaskan**: `lifecycleNote()` menulis bahwa PO yang terbit
 *    dari aplikasi selalu "terkirim", sedangkan "terkonfirmasi" adalah baris
 *    yang diimpor dari SAP — bukan klaim aplikasi mengonfirmasi ke SAP.
 * 5. **Asal baris jujur**: `execution` (punya decision_id) → "dari keputusan";
 *    `demo` (baris impor tanpa keputusan) → "impor SAP"; selain itu "asal tidak
 *    tercatat". Kata "dari eksekusi" dibuang karena seeder demo juga menulis PO
 *    ber-decision_id tanpa melewati `POST /actions/execute`.
 * 6. **PO milik keputusan yang sedang dibuka ditandai** ("keputusan ini"),
 *    karena panel ini berada di bawah detail keputusan: tanpa penanda, pembaca
 *    menyimpulkan seluruh daftar milik keputusan tersebut.
 * 7. **Kosong ≠ nol rupiah**, dan **ringkasan yang belum termuat ≠ Rp 0,00**:
 *    total hanya berarti kalau `/summary` benar-benar menjawab.
 * 8. **Daftar terpotong batas limit mengatakannya** (`progressNote`).
 * 9. **Galat tetap galat**: tidak pernah dilaporkan sebagai daftar kosong.
 * 10. **Dokumen PO hanya untuk yang sudah disetujui** (20 Okt 2026): tombol
 *     "Unduh PDF" muncul pada baris yang keputusannya `approved`/`executed`,
 *     dan baris lain mendapat kalimat sebabnya. Tombol yang hilang tanpa
 *     penjelasan terbaca sebagai fitur rusak; tombol yang selalu ada padahal
 *     backend menolak 409 terbaca sebagai janji palsu.
 */

import { useState } from "react";

import { statusWord } from "../lib/decision-picker";
import { downloadPoPdf } from "../lib/export";

export type PurchaseOrderRow = {
  po_number: string;
  status: string;
  created_at: string;
  decision_id: string | null;
  decision_status?: string | null;
  location_id?: string | null;
  location_name?: string | null;
  supplier_id?: string | null;
  supplier_name?: string | null;
  material_number: string;
  /** Nama komoditas dari relasi keputusan; `null` untuk baris impor tanpa keputusan. */
  commodity_name?: string | null;
  ordered_quantity_kg: number;
  price_per_kg: number;
  total_value: number;
  source?: string | null;
  /** "execution" = punya decision_id (tertaut keputusan), "demo" = baris impor tanpa keputusan. */
  origin?: string | null;
};

export type PurchaseOrderPayload = {
  items?: PurchaseOrderRow[] | null;
  count?: number | null;
  limit?: number | null;
  scope?: string | null;
  source?: string | null;
};

export type PurchaseOrderSummary = {
  by_status?: Record<string, number> | null;
  count?: number | null;
  total_value?: number | null;
  scope?: string | null;
  source?: string | null;
};

/**
 * Status keputusan yang boleh punya dokumen PO — cermin dari pagar backend
 * (`services/po_document.STATUS_BOLEH_PDF`). Kalau keduanya berbeda, tombol
 * akan menawarkan unduhan yang pasti ditolak 409; itu sebabnya daftar ini
 * dipaku di tes, bukan ditulis ulang di JSX.
 */
export const PDF_DECISION_STATUS = ["approved", "executed"] as const;

export function bolehUnduhPdf(statusKeputusan: string | null | undefined): boolean {
  const kunci = String(statusKeputusan ?? "").trim().toLowerCase();
  return (PDF_DECISION_STATUS as readonly string[]).includes(kunci);
}

/**
 * Kalimat untuk baris yang TIDAK punya tombol PDF. Tombol yang hilang tanpa
 * penjelasan membuat pembaca mengira fiturnya rusak; kalimat ini menyebut
 * sebabnya apa adanya (tanpa keputusan / keputusan belum disetujui).
 */
export function pdfHint(po: PurchaseOrderRow): string | null {
  if (bolehUnduhPdf(po.decision_status)) return null;
  if (!po.decision_id) {
    return "PDF hanya untuk PO yang lahir dari keputusan yang sudah disetujui";
  }
  return `PDF tersedia setelah keputusan disetujui (kini: ${statusWord(po.decision_status)})`;
}

const STATUS_LABEL: Record<string, string> = {
  draft: "draf",
  submitted: "terkirim",
  confirmed: "terkonfirmasi",
};

/** Urutan tampil chip = urutan hidup PO, bukan urutan alfabet. */
const STATUS_ORDER = ["draft", "submitted", "confirmed"] as const;

/** Status PO → kata Indonesia. Status asing dibiarkan apa adanya. */
export function statusLabel(status: string | null | undefined): string {
  if (!status) return "tidak dikenal";
  return STATUS_LABEL[status] ?? status;
}

/**
 * Asal baris PO → kata yang jujur dan bisa dibuktikan.
 *
 * `execution` = punya `decision_id` (tertaut ke keputusan).
 * `demo` = baris impor SAP tanpa keputusan (tidak pernah melewati approval).
 * Selain itu tidak dikarang: "asal tidak tercatat".
 */
export function originLabel(origin: string | null | undefined): string {
  if (origin === "execution") return "dari keputusan";
  if (origin === "demo") return "impor SAP";
  return "asal tidak tercatat";
}

/**
 * Bahan yang ditampilkan: nama komoditas dari DB bila ada, kalau tidak kode
 * bahannya apa adanya. TIDAK diterjemahkan dengan menebak — seeder memakai
 * `MAT-{nama[:4]}` (`MAT-BERA`), dan tebakan menghasilkan kata rusak ("Bera").
 */
export function materialLabel(
  commodityName: string | null | undefined,
  materialNumber: string | null | undefined
): string {
  if (commodityName) return commodityName;
  if (!materialNumber) return "bahan tidak tercatat";
  // Nomor bahan SAP memang numerik (`1000`); diberi awalan supaya tidak terbaca
  // sebagai angka acak di tengah baris.
  return /^\d+$/.test(materialNumber) ? `Bahan ${materialNumber}` : materialNumber;
}

const ANGKA = new Intl.NumberFormat("id-ID", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Rupiah dengan format Indonesia; tidak membulatkan ke ribuan. */
export function formatRupiah(nilai: number | null | undefined): string {
  const angka = typeof nilai === "number" && Number.isFinite(nilai) ? nilai : 0;
  return `Rp ${ANGKA.format(angka)}`;
}

/**
 * Rupiah untuk nilai yang boleh tidak diketahui — `null` jadi "—", bukan
 * "Rp 0,00". Dipakai ringkasan yang belum atau gagal termuat.
 */
export function formatRupiahOpsional(nilai: number | null | undefined): string {
  if (typeof nilai !== "number" || !Number.isFinite(nilai)) return "—";
  return formatRupiah(nilai);
}

const KG = new Intl.NumberFormat("id-ID", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

/** Kuantitas kg: satu desimal bila perlu, tanpa ",0" yang mengarang presisi. */
export function formatKg(nilai: number | null | undefined): string {
  const angka = typeof nilai === "number" && Number.isFinite(nilai) ? nilai : 0;
  return `${KG.format(angka)} kg`;
}

const BULAT = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });

/** Kalimat sumber — satu-satunya tempat asal data dijelaskan. */
export function sourceNote(scope: string | null | undefined): string {
  const asal =
    "Data dari SAP simulasi di lingkungan ini (bukan SAP S/4HANA produksi).";
  return scope === "nasional"
    ? `${asal} Cakupan nasional: seluruh lokasi, termasuk PO tanpa keputusan.`
    : `${asal} Anda melihat PO untuk SPPG Anda.`;
}

/** Label penanda simulasi; `null` bila sumbernya bukan tabel mock. */
export function simulationLabel(source: string | null | undefined): string | null {
  return source === "mock_sap_table" ? "SAP simulasi" : null;
}

/**
 * Arti status yang benar-benar terjadi di sistem ini.
 *
 * Fakta backend: `POST /actions/execute` selalu menulis `submitted`; status
 * `confirmed` hanya ada pada baris yang diimpor dari SAP. Menjelaskan ini
 * mencegah pembaca mengira aplikasi punya langkah konfirmasi ke SAP.
 */
export function lifecycleNote(
  byStatus: Record<string, number> | null | undefined
): string | null {
  const b = byStatus ?? {};
  const adaKonfirmasi = (b.confirmed ?? 0) > 0;
  const adaDraf = (b.draft ?? 0) > 0;
  if (!adaKonfirmasi && !adaDraf) return null;
  const bagian: string[] = [];
  if (adaDraf) bagian.push("Draf berarti PO belum dikirim ke SAP");
  if (adaKonfirmasi)
    bagian.push(
      "Terkonfirmasi adalah PO yang sudah ada di data SAP dan diimpor ke aplikasi ini"
    );
  bagian.push(
    "PO yang diterbitkan dari eksekusi keputusan di aplikasi ini tercatat Terkirim"
  );
  return `${bagian.join("; ")}.`;
}

/** Kalimat saat tidak ada baris — dibedakan per cakupan, tidak memakai angka 0. */
export function emptyNote(scope: string | null | undefined): string {
  return scope === "nasional"
    ? "Belum ada purchase order tercatat."
    : "Belum ada purchase order untuk SPPG Anda.";
}

/**
 * Pemberitahuan kalau daftar terpotong batas limit server: `null` bila seluruh
 * PO sudah tampil. Tanpa ini, pembaca mengira daftar = seluruh populasi.
 */
export function progressNote(
  ditampilkan: number | null | undefined,
  total: number | null | undefined
): string | null {
  if (typeof ditampilkan !== "number" || typeof total !== "number") return null;
  if (!Number.isFinite(ditampilkan) || !Number.isFinite(total)) return null;
  if (total <= ditampilkan) return null;
  return `Menampilkan ${BULAT.format(ditampilkan)} dari ${BULAT.format(
    total
  )} PO terbaru.`;
}

export default function PurchaseOrderList({
  data,
  summary,
  loading = false,
  error = null,
  decisionId = null,
  token = null,
  onOpenDecision,
  onRetry,
}: {
  data: PurchaseOrderPayload | null;
  summary?: PurchaseOrderSummary | null;
  loading?: boolean;
  error?: string | null;
  /** Keputusan yang sedang dibuka — dipakai menandai baris "keputusan ini". */
  decisionId?: string | null;
  /** Token sesi: dokumen PO diunduh dengan kredensial pemilik sesi, bukan URL publik. */
  token?: string | null;
  /** Dipanggil saat "Lihat keputusan" diklik: pindahkan pilihan di dalam aplikasi. */
  onOpenDecision?: (decisionId: string) => void;
  onRetry?: () => void;
}) {
  // Umpan balik unduhan per nomor PO: satu baris yang gagal tidak boleh
  // mematikan tombol baris lain, dan pesannya harus menyebut sebabnya.
  const [unduhan, setUnduhan] = useState<
    Record<string, { state: "jalan" | "sukses" | "gagal"; nama?: string; pesan?: string }>
  >({});

  async function unduhDokumen(po: PurchaseOrderRow) {
    if (!token) return;
    setUnduhan((lama) => ({ ...lama, [po.po_number]: { state: "jalan" } }));
    try {
      const nama = await downloadPoPdf(po.po_number, token);
      setUnduhan((lama) => ({ ...lama, [po.po_number]: { state: "sukses", nama } }));
    } catch (galat) {
      const pesan =
        (galat as { detail?: string | null; message?: string })?.detail ||
        (galat as { message?: string })?.message ||
        "gagal mengunduh dokumen";
      setUnduhan((lama) => ({ ...lama, [po.po_number]: { state: "gagal", pesan } }));
    }
  }

  const items = data?.items ?? [];
  const jumlah = data?.count ?? items.length;
  const scope = data?.scope ?? summary?.scope ?? null;
  const byStatus = summary?.by_status ?? {};
  const adaRingkasan = summary !== null && summary !== undefined;
  const total = adaRingkasan ? summary?.total_value ?? null : null;
  const simulasi = simulationLabel(data?.source ?? summary?.source ?? null);
  const artiStatus = lifecycleNote(byStatus);
  const terpotong = progressNote(jumlah, summary?.count ?? null);

  return (
    <section className="po-panel" aria-labelledby="po-panel-title">
      <div className="po-panel-head">
        <div className="po-panel-titles">
          <div className="po-panel-title-row">
            <h3 id="po-panel-title">Purchase order</h3>
            {simulasi ? (
              <span className="po-source-chip" title="Data berasal dari SAP simulasi">
                {simulasi}
              </span>
            ) : null}
          </div>
          <p className="po-panel-sub">{sourceNote(scope)}</p>
        </div>
        {onRetry ? (
          <button type="button" className="btn-ghost" onClick={onRetry} disabled={loading}>
            {loading ? "Memuat…" : "Muat ulang"}
          </button>
        ) : null}
      </div>

      {error ? (
        <p className="po-panel-error" role="alert">
          Purchase order tidak bisa dimuat: {error}
        </p>
      ) : null}

      {!error && loading && items.length === 0 ? (
        <p className="po-panel-loading">Memuat purchase order…</p>
      ) : null}

      {!error && !loading && jumlah === 0 ? (
        <p className="empty-state">{emptyNote(scope)}</p>
      ) : null}

      {!error && jumlah > 0 ? (
        <>
          <div className="po-summary">
            {STATUS_ORDER.filter((status) => (byStatus[status] ?? 0) > 0).map(
              (status) => (
                <span key={status} className={`po-chip po-chip-${status}`}>
                  {statusLabel(status)} {BULAT.format(byStatus[status] ?? 0)}
                </span>
              )
            )}
            <span className="po-total">
              Total nilai <b>{formatRupiahOpsional(total)}</b>
            </span>
          </div>

          {artiStatus ? <p className="po-lifecycle">{artiStatus}</p> : null}
          {terpotong ? <p className="po-progress">{terpotong}</p> : null}

          <ul className="po-list">
            {items.map((po) => {
              const iniKeputusan = Boolean(decisionId) && po.decision_id === decisionId;
              return (
                <li
                  key={po.po_number}
                  className={`po-row${iniKeputusan ? " po-row-current" : ""}`}
                >
                  <div className="po-row-main">
                    <span className="po-number">{po.po_number}</span>
                    <span className={`po-status po-status-${po.status}`}>
                      {statusLabel(po.status)}
                    </span>
                    {iniKeputusan ? (
                      <span className="po-current-flag">keputusan ini</span>
                    ) : null}
                    <span className="po-note po-origin">{originLabel(po.origin)}</span>
                    {po.location_name ? (
                      <span className="po-note">{po.location_name}</span>
                    ) : null}
                  </div>
                  <div className="po-row-meta">
                    {po.supplier_name ?? "pemasok tidak tercatat"} ·{" "}
                    {materialLabel(po.commodity_name, po.material_number)} ·{" "}
                    {formatKg(po.ordered_quantity_kg)} · {formatRupiah(po.price_per_kg)}/kg
                  </div>
                  <div className="po-row-foot">
                    <span className="po-value">{formatRupiah(po.total_value)}</span>
                    {po.decision_id ? (
                      <a
                        className="po-link"
                        href={`?keputusan=${po.decision_id}`}
                        onClick={(e) => {
                          // Tanpa penangan ini klik = navigasi penuh: halaman
                          // dimuat ulang dan pengguna tetap melihat daftar PO
                          // ("tombolnya tidak berfungsi", 19 Okt 2026).
                          if (!onOpenDecision) return;
                          // Biarkan Ctrl/Cmd/Shift-klik membuka tab baru.
                          if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                          e.preventDefault();
                          onOpenDecision(po.decision_id as string);
                        }}
                      >
                        {iniKeputusan ? "Buka keputusan" : "Lihat keputusan"}
                      </a>
                    ) : (
                      <span className="po-note">tanpa keputusan</span>
                    )}
                    {/* Dokumen PO: hanya untuk baris yang approval-nya sudah
                        tercatat. Baris lain menyebut sebabnya, bukan tombol
                        mati tanpa keterangan. */}
                    {bolehUnduhPdf(po.decision_status) ? (
                      <button
                        type="button"
                        className="po-pdf-button"
                        onClick={() => void unduhDokumen(po)}
                        disabled={!token || unduhan[po.po_number]?.state === "jalan"}
                        aria-busy={unduhan[po.po_number]?.state === "jalan" || undefined}
                        aria-label={`Unduh dokumen PDF untuk PO ${po.po_number}`}
                        title={!token ? "Sesi tidak aktif — masuk ulang untuk mengunduh" : undefined}
                      >
                        {/* Ikon garis 12px, bukan emoji (aturan ikon sistem). */}
                        <svg
                          width="12"
                          height="12"
                          viewBox="0 0 16 16"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden="true"
                          focusable="false"
                        >
                          <path d="M8 2v8" />
                          <path d="M4.8 7.2 8 10.4l3.2-3.2" />
                          <path d="M2.5 13h11" />
                        </svg>
                        <span>
                          {unduhan[po.po_number]?.state === "jalan"
                            ? "Menyiapkan PDF…"
                            : "Unduh PDF"}
                        </span>
                      </button>
                    ) : pdfHint(po) ? (
                      <span className="po-note po-pdf-hint">{pdfHint(po)}</span>
                    ) : null}
                  </div>
                  {unduhan[po.po_number]?.state === "sukses" ? (
                    <p className="po-pdf-note" role="status">
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 16 16"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                        focusable="false"
                      >
                        <path d="m3 8.5 3.2 3.2L13 4.8" />
                      </svg>
                      Dokumen terunduh sebagai {unduhan[po.po_number]?.nama}.
                    </p>
                  ) : null}
                  {unduhan[po.po_number]?.state === "gagal" ? (
                    <p className="po-pdf-error" role="alert">
                      Dokumen tidak bisa diunduh: {unduhan[po.po_number]?.pesan}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
    </section>
  );
}
