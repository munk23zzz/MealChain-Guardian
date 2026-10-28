"use client";

// Riwayat penerimaan barang di halaman Pemasok — Dok 05 §8.5.
//
// Kenapa bentuknya begini:
// - Halaman Pemasok sebelumnya hanya menjawab "siapa pemasoknya". Pertanyaan
//   audit "berapa yang benar-benar diterima dari pemasok ini dan berapa
//   nilainya" dijawab tabel ini, bukan oleh kalimat penjelas.
// - Tiga angka (dipesan · diterima · nilai diterima) berdiri di kepala kartu
//   (§8.2) karena itu pembanding yang dipakai memutuskan; kolom Nilai punya
//   kolomnya sendiri (§8.5) supaya angkanya bisa dibandingkan tegak lurus.
// - Asal harga satuan ditulis kecil di bawah nilai (§8.3) — tanpa itu pembaca
//   membandingkan dengan harga pasar dan mengira ada kekeliruan.
// - Semua angka berasal dari server. Komponen ini tidak pernah mengalikan kg ×
//   harga, dan tidak pernah menampilkan Rp 0 untuk nilai yang tidak tercatat.
// - Putusan dibawa LABEL + nada pil, bukan warna saja.

import { useMemo, useState } from "react";

import Pager from "./Pager";
import { paginate } from "../lib/pagination";
import {
  receiptFilterLabel,
  receiptHeadline,
  receiptHistory,
  receiptShortfall,
  receiptTotals,
  type ReceiptVerdict,
} from "../lib/supplier-receipts";

/** Baris per halaman — sama dengan Daftar Pemasok dan Papan Kiriman. */
const BARIS_PER_HALAMAN = 10;

const FILTER: (ReceiptVerdict | "semua")[] = ["semua", "menunggu", "disetujui", "ditolak"];

export default function SupplierReceipts({
  riwayat,
  loading = false,
  error = null,
}: {
  /** Amplop `GET /receipts/riwayat`. `null` = belum dimuat. */
  riwayat: unknown;
  loading?: boolean;
  error?: string | null;
}) {
  const dimuat = riwayat !== null && riwayat !== undefined;
  const rows = useMemo(() => receiptHistory(riwayat), [riwayat]);
  const totals = useMemo(() => receiptTotals(riwayat), [riwayat]);
  const headline = receiptHeadline(totals);
  const shortfall = receiptShortfall(totals);
  const [saring, setSaring] = useState<ReceiptVerdict | "semua">("semua");
  const [halaman, setHalaman] = useState(1);
  const tampil = saring === "semua" ? rows : rows.filter((r) => r.status === saring);
  const halamanData = paginate(tampil, halaman, BARIS_PER_HALAMAN);

  const jumlah = (kunci: ReceiptVerdict) =>
    kunci === "menunggu" ? totals.menunggu : kunci === "disetujui" ? totals.disetujui : totals.ditolak;

  return (
    <article className="card supplier-receipts" data-testid="supplier-receipts" aria-busy={loading || undefined}>
      <div className="card-header">
        <div className="directory-title">
          <h2>Riwayat penerimaan</h2>
          {dimuat && totals.total > 0 ? (
            <span className="count-pill">{totals.total} catatan</span>
          ) : null}
        </div>
        {dimuat && totals.total > 0 ? (
          <div className="receipt-filter" role="group" aria-label="Saring putusan penerimaan">
            {FILTER.map((kunci) => (
              <button
                key={kunci}
                type="button"
                className="receipt-chip"
                data-aktif={saring === kunci || undefined}
                aria-pressed={saring === kunci}
                onClick={() => {
                  setSaring(kunci);
                  setHalaman(1);
                }}
              >
                {receiptFilterLabel(kunci)}
                {kunci === "semua" ? (
                  <span className="receipt-chip-n">{totals.total}</span>
                ) : (
                  <span className="receipt-chip-n">{jumlah(kunci)}</span>
                )}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {headline ? (
        <p className="receipt-headline" data-testid="receipt-headline">
          {headline}
        </p>
      ) : null}
      {shortfall ? <p className="evidence-note receipt-shortfall">{shortfall}</p> : null}

      {error ? (
        <p className="evidence-note">Riwayat penerimaan tidak bisa dibaca: {error}</p>
      ) : !dimuat ? (
        <p className="evidence-note">
          {loading ? "Memuat riwayat penerimaan…" : "Riwayat penerimaan belum dimuat."}
        </p>
      ) : totals.total === 0 ? (
        <p className="evidence-note">
          Belum ada penerimaan tercatat dalam cakupan Anda. Catatan dibuat dari popup penerimaan
          barang pada keputusan yang barangnya sudah tiba.
        </p>
      ) : tampil.length === 0 ? (
        <p className="evidence-note">
          Tidak ada catatan berstatus “{receiptFilterLabel(saring)}”. Angka di atas tetap menghitung
          seluruh cakupan.
        </p>
      ) : (
        <>
          <div className="board-table-wrap">
            <table className="location-table receipt-table">
              <thead>
                <tr>
                  <th scope="col">Waktu</th>
                  <th scope="col">Pemasok</th>
                  <th scope="col" className="num">
                    kg dipesan / diterima
                  </th>
                  <th scope="col">Putusan</th>
                  <th scope="col" className="num">
                    Nilai diterima
                  </th>
                </tr>
              </thead>
              <tbody>
                {halamanData.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className="cell-stack">
                        <span className="cell-name">{row.at}</span>
                        <span className="cell-meta">{row.checkedLabel}</span>
                      </span>
                    </td>
                    <td>
                      <span className="cell-stack">
                        <span className="cell-name">{row.supplier}</span>
                        <span className="cell-meta">
                          {row.commodity} · batch {row.batchRef}
                        </span>
                      </span>
                    </td>
                    <td className="num">
                      <span className="cell-stack">
                        <span className="cell-name">{row.orderedLabel}</span>
                        <span className="cell-meta">diterima {row.receivedLabel}</span>
                      </span>
                    </td>
                    <td>
                      <span className="cell-stack">
                        <span className="receipt-pill" data-tone={row.tone}>
                          {row.statusLabel}
                        </span>
                        {row.note ? <span className="cell-meta">{row.note}</span> : null}
                      </span>
                    </td>
                    <td className="num">
                      <span className="cell-stack">
                        <span className="cell-name" data-status={row.valueStatus}>
                          {row.valueLabel}
                        </span>
                        {row.priceOrigin ? (
                          <span className="cell-meta receipt-origin">{row.priceOrigin}</span>
                        ) : null}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={halamanData} onChange={setHalaman} label="riwayat penerimaan" />
        </>
      )}
    </article>
  );
}
