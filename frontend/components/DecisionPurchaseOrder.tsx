// PO untuk SATU keputusan — bagian "Jejak & hasil" halaman Decision & Evidence.
//
// Rencana: docs/plans/decision-evidence-rebuild.md §3. Dulu daftar PO SELURUH
// jaringan (`<PurchaseOrderList>`) dipasang di bawah satu keputusan, sehingga
// pembaca mengira baris-baris itu milik keputusan yang sedang dibuka. Komponen
// ini menggantinya dengan satu PO milik keputusan ini saja, dan bila belum ada,
// sebabnya ditulis — bukan diisi daftar lain sebagai penghibur.

"use client";

import { useState } from "react";

import { poKeputusan } from "../lib/decision-dossier";
import { tahapPo } from "../lib/detail-keputusan";
import { downloadPoPdf } from "../lib/export";
import { bolehUnduhPdf } from "./PurchaseOrderList";

export default function DecisionPurchaseOrder({
  purchaseOrders,
  decisionId,
  token = null,
  decisionStatus = null,
}: {
  purchaseOrders: unknown;
  decisionId: string | null | undefined;
  /** Sesi; tanpa token tombol unduh tidak ditawarkan (server akan menolak). */
  token?: string | null;
  /** Status keputusan — aturan PDF sama dengan server: approved/executed. */
  decisionStatus?: string | null;
}) {
  const [unduhan, setUnduhan] = useState<
    { state: "diam" } | { state: "jalan" } | { state: "sukses"; nama: string } | { state: "gagal"; pesan: string }
  >({ state: "diam" });
  if (!decisionId) {
    return (
      <p className="evidence-note" data-testid="po-keputusan">
        Belum ada keputusan yang dibuka — PO tidak bisa ditampilkan.
      </p>
    );
  }

  const po = poKeputusan(purchaseOrders, decisionId);
  if (!po) {
    return (
      <p className="evidence-note" data-testid="po-keputusan">
        Belum ada PO untuk keputusan ini; PO terbit setelah persetujuan lengkap.
      </p>
    );
  }

  // Label & tahap dari sumber kanonik (`lib/detail-keputusan`), supaya status
  // mentah backend ("draft"/"submitted"/"confirmed") tidak pernah tercetak.
  const tahap = tahapPo({ po_number: po.poNumber, status: po.status });

  async function unduh() {
    if (!token) return;
    setUnduhan({ state: "jalan" });
    try {
      const nama = await downloadPoPdf(po!.poNumber, token);
      setUnduhan({ state: "sukses", nama });
    } catch (galat) {
      const pesan =
        (galat as { detail?: string | null; message?: string })?.detail ||
        (galat as { message?: string })?.message ||
        "gagal mengunduh dokumen";
      setUnduhan({ state: "gagal", pesan });
    }
  }

  return (
    <div className="po-keputusan" data-testid="po-keputusan">
      <p className="po-keputusan-nomor">{po.poNumber}</p>
      <p className="po-keputusan-status" data-status={po.status}>
        {tahap.statusLabel}
      </p>
      {po.createdAt && (
        <p className="po-keputusan-waktu">
          Dibuat {new Date(po.createdAt).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })}
        </p>
      )}
      {/* Dokumen resmi PO (permintaan pemilik 29 Okt 2026). Dulu tombol ini
          hidup di daftar PO; setelah kartu ini jadi ringkasan satu PO, dokumen
          tidak bisa diambil dari tempat orang mencarinya. */}
      {token && bolehUnduhPdf(decisionStatus) ? (
        <div className="po-keputusan-dokumen">
          <button
            type="button"
            className="button button-secondary po-keputusan-unduh"
            data-unduh-po={po.poNumber}
            onClick={() => void unduh()}
            disabled={unduhan.state === "jalan"}
            aria-busy={unduhan.state === "jalan" || undefined}
            aria-label={`Unduh dokumen PDF PO ${po.poNumber}`}
          >
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
            <span>{unduhan.state === "jalan" ? "Menyiapkan PDF…" : "Unduh PDF"}</span>
          </button>
          {unduhan.state === "sukses" && (
            <p className="evidence-note" role="status">
              Tersimpan: {unduhan.nama}
            </p>
          )}
          {unduhan.state === "gagal" && (
            <p className="evidence-note po-keputusan-galat" role="alert">
              {unduhan.pesan}
            </p>
          )}
        </div>
      ) : (
        <p className="evidence-note" data-po-dokumen="belum">
          {bolehUnduhPdf(decisionStatus)
            ? "Masuk ulang untuk mengunduh dokumen PO."
            : "PDF terbit setelah keputusan disetujui."}
        </p>
      )}
      <p className="evidence-note">
        Hanya PO keputusan ini yang ditampilkan; daftar PO seluruh jaringan ada di
        halaman Pemasok.
      </p>
    </div>
  );
}
