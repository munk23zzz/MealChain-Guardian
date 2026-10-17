/**
 * Daftar purchase order mock SAP (W-5, 2026-10-17).
 *
 * Kenapa panel ini ada: `sap_mock_purchase_orders` selalu ditulis saat keputusan
 * dieksekusi, tetapi sebelum hari ini tidak ada satu layar pun yang bisa
 * menunjukkannya — nomor PO hanya sempat muncul sebagai toast sesaat. Jadi
 * klaim "dua approval → PO terbit" tidak bisa diverifikasi di depan penilai.
 *
 * Aturan tampilan (semuanya dipaku tes):
 *
 * 1. **Sumber disebut apa adanya**: `sourceNote()` menulis "tabel transaksi mock
 *    di DB demo — bukan SAP S/4HANA nyata". Endpoint mengirim
 *    `source = "mock_sap_table"`; UI tidak boleh menaikkannya jadi klaim SAP
 *    sungguhan.
 * 2. **Status diterjemahkan** (`submitted` → "terkirim"), bukan ditampilkan
 *    mentah, dan status asing dibiarkan apa adanya (tidak dikarang).
 * 3. **PO tanpa keputusan** (baris seed/adapter, `decision_id = null`) menulis
 *    "tanpa keputusan" dan TIDAK menaut ke mana pun — PO itu tidak punya
 *    keputusan yang bisa dibuka.
 * 4. **Kosong ≠ nol rupiah**: tidak ada baris berarti kalimat "belum ada
 *    purchase order", bukan deret angka 0.
 * 5. **Galat tetap galat**: tidak pernah dilaporkan sebagai daftar kosong.
 */

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
  ordered_quantity_kg: number;
  price_per_kg: number;
  total_value: number;
  source?: string | null;
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

const STATUS_LABEL: Record<string, string> = {
  draft: "draf",
  submitted: "terkirim",
  confirmed: "terkonfirmasi",
};

/** Status PO → kata Indonesia. Status asing dibiarkan apa adanya. */
export function statusLabel(status: string | null | undefined): string {
  if (!status) return "tidak dikenal";
  return STATUS_LABEL[status] ?? status;
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

const KG = new Intl.NumberFormat("id-ID", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

/** Kuantitas kg: satu desimal bila perlu, tanpa ",0" yang mengarang presisi. */
export function formatKg(nilai: number | null | undefined): string {
  const angka = typeof nilai === "number" && Number.isFinite(nilai) ? nilai : 0;
  return `${KG.format(angka)} kg`;
}

/** Kalimat sumber — satu-satunya tempat asal data dijelaskan. */
export function sourceNote(scope: string | null | undefined): string {
  const asal =
    "Dibaca dari tabel transaksi mock di DB demo — bukan SAP S/4HANA nyata.";
  return scope === "nasional"
    ? `${asal} Cakupan nasional: seluruh lokasi, termasuk PO yang tidak terikat keputusan.`
    : `${asal} Anda hanya melihat PO untuk SPPG Anda.`;
}

/** Kalimat saat tidak ada baris — dibedakan per cakupan, tidak memakai angka 0. */
export function emptyNote(scope: string | null | undefined): string {
  return scope === "nasional"
    ? "Belum ada purchase order di DB demo."
    : "Belum ada purchase order untuk SPPG Anda.";
}

export default function PurchaseOrderList({
  data,
  summary,
  loading = false,
  error = null,
  onRetry,
}: {
  data: PurchaseOrderPayload | null;
  summary?: PurchaseOrderSummary | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}) {
  const items = data?.items ?? [];
  const jumlah = data?.count ?? items.length;
  const scope = data?.scope ?? summary?.scope ?? null;
  const byStatus = summary?.by_status ?? {};
  const total = summary?.total_value ?? 0;

  return (
    <section className="po-panel" aria-labelledby="po-panel-title">
      <div className="po-panel-head">
        <div>
          <h3 id="po-panel-title">Purchase order (mock SAP)</h3>
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
            <span className="po-chip po-chip-draft">draf {byStatus.draft ?? 0}</span>
            <span className="po-chip po-chip-submitted">terkirim {byStatus.submitted ?? 0}</span>
            <span className="po-chip po-chip-confirmed">
              terkonfirmasi {byStatus.confirmed ?? 0}
            </span>
            <span className="po-total">
              Total nilai <b>{formatRupiah(total)}</b>
            </span>
          </div>

          <ul className="po-list">
            {items.map((po) => (
              <li key={po.po_number} className="po-row">
                <div className="po-row-main">
                  <span className="po-number">{po.po_number}</span>
                  <span className={`po-status po-status-${po.status}`}>
                    {statusLabel(po.status)}
                  </span>
                  {po.location_name ? (
                    <span className="po-note">{po.location_name}</span>
                  ) : null}
                </div>
                <div className="po-row-meta">
                  {po.supplier_name ?? "pemasok tidak tercatat"} · {po.material_number} ·{" "}
                  {formatKg(po.ordered_quantity_kg)} · {formatRupiah(po.price_per_kg)}/kg
                </div>
                <div className="po-row-foot">
                  <span className="po-value">{formatRupiah(po.total_value)}</span>
                  {po.decision_id ? (
                    <a className="po-link" href={`?keputusan=${po.decision_id}`}>
                      Lihat keputusan
                    </a>
                  ) : (
                    <span className="po-note">tanpa keputusan</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
