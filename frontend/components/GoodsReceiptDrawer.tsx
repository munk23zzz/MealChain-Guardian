"use client";

// GoodsReceiptDrawer — status penerimaan barang satu keputusan (Fase 9 MG butir 2 & 4).
//
// Yang dijaga komponen ini:
//   1. Tombol "Tandai diterima" HANYA tampil bila server mengirim `can_receive`
//      true (dan ada catatan penerimaan `menunggu` yang bisa diputuskan).
//      `on_hold` tidak pernah menawarkannya; `quarantined` menawarkan langkah
//      yang BERBEDA (lepas karantina / nyatakan gagal, dari `next_step` server).
//   2. Peran non-head tetap read-only: tanpa `can_receive`/`can_quarantine` dari
//      server, tidak ada satu pun tombol mutasi yang dirender.
//   3. Galat 409 ditampilkan apa adanya dari `detail` server, supaya pengguna
//      tahu apa yang harus diperbaiki — bukan "terjadi kesalahan".
//   4. Tidak menghitung apa pun: status, alasan, dan langkah berikutnya berasal
//      dari `receipt_gate` (`app/services/receipt_gate.py`).
//
// Sumber data: `summary` = `GET /decisions/{id}/approval-summary`; catatan
// penerimaan per batch = `GET /receipts?batch_id=…` (prop `receipts` untuk tes).

import { useCallback, useEffect, useState } from "react";

import { approveReceipt, fetchReceipts, rejectReceipt } from "../lib/api";
import {
  QUARANTINE_HOLD_LABEL,
  RECEIPT_APPROVE_LABEL,
  RECEIPT_REJECT_LABEL,
  canDecideReceipt,
  pendingReceipt,
  receiptGateView,
  serverDetail,
} from "../lib/goods-receipt";

type BarisCatatan = Record<string, any>;

export default function GoodsReceiptDrawer({
  summary,
  token,
  role,
  receipts,
  onChanged,
}: {
  summary: unknown;
  token: string | null;
  role: string | null;
  /** Catatan penerimaan per batch (batch_id → baris). Diisi tes; runtime memuat sendiri. */
  receipts?: Record<string, BarisCatatan[]>;
  onChanged?: () => void;
}) {
  const gate = receiptGateView(summary);
  const [muatan, setMuatan] = useState<Record<string, BarisCatatan[]>>(receipts ?? {});
  const [galat, setGalat] = useState<string | null>(null);
  const [pesan, setPesan] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [alasanTolak, setAlasanTolak] = useState("");
  const [batchTolak, setBatchTolak] = useState<string | null>(null);

  const muat = useCallback(async () => {
    if (receipts) {
      setMuatan(receipts);
      return;
    }
    if (!token || gate.rows.length === 0) return;
    const hasil: Record<string, BarisCatatan[]> = {};
    for (const baris of gate.rows) {
      try {
        const data = await fetchReceipts(baris.batchId, token, 5);
        hasil[baris.batchId] = Array.isArray(data?.items) ? data.items : [];
      } catch {
        // Batch tanpa riwayat penerimaan bukan galat: catatan memang belum ada.
        hasil[baris.batchId] = [];
      }
    }
    setMuatan(hasil);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, receipts, JSON.stringify(gate.rows)]);

  useEffect(() => {
    void muat();
  }, [muat]);

  if (!gate.present) {
    return null;
  }

  async function terima(batchId: string, receiptId: string) {
    if (!token) return;
    setBusy(receiptId);
    setGalat(null);
    setPesan(null);
    try {
      const balasan = await approveReceipt(receiptId, token);
      setPesan(
        balasan?.sudah
          ? "Penerimaan ini sudah disetujui sebelumnya — stok tidak digandakan."
          : "Barang ditandai diterima; stok bertambah di server."
      );
      await muat();
      onChanged?.();
    } catch (e) {
      // Butir 4: 409 wajib menyebut detail server (alasan bisa diperbaiki).
      setGalat(serverDetail(e) || "Penerimaan ditolak server tanpa keterangan.");
    } finally {
      setBusy(null);
    }
  }

  async function tolak(receiptId: string) {
    if (!token) return;
    const alasan = alasanTolak.trim();
    if (!alasan) {
      setGalat("Alasan penolakan wajib diisi.");
      return;
    }
    setBusy(receiptId);
    setGalat(null);
    setPesan(null);
    try {
      await rejectReceipt(receiptId, alasan, token);
      setPesan("Penerimaan ditolak; stok tidak bertambah.");
      setAlasanTolak("");
      setBatchTolak(null);
      await muat();
      onChanged?.();
    } catch (e) {
      setGalat(serverDetail(e) || "Penolakan gagal tanpa keterangan server.");
    } finally {
      setBusy(null);
    }
  }

  const bolehPutuskan = canDecideReceipt(role);

  return (
    <article className="card goods-receipt" aria-label="Status penerimaan barang">
      <div className="card-header">
        <h2>Penerimaan barang</h2>
        <span className="evidence-note">
          Status dan tombol mengikuti penilaian server untuk dapur penerima.
        </span>
      </div>

      {galat ? (
        <p className="board-alert" role="alert">
          {galat}
        </p>
      ) : null}
      {pesan ? (
        <p className="evidence-note" role="status">
          {pesan}
        </p>
      ) : null}

      {gate.rows.length === 0 ? (
        <p className="evidence-note">
          Belum ada barang keputusan ini di dapur penerima — belum ada yang bisa
          diterima atau ditahan.
        </p>
      ) : (
        <ul className="goods-receipt-list">
          {gate.rows.map((baris) => {
            const menunggu = pendingReceipt(muatan[baris.batchId]);
            const bisaTerima = baris.canReceive && menunggu !== null && bolehPutuskan;
            return (
              <li key={baris.batchId} className="goods-receipt-row" data-batch={baris.batchId}>
                <p className="goods-receipt-status">
                  <strong>{baris.statusLabel}</strong>
                  <span className="evidence-note"> · batch {baris.batchId.slice(0, 8)}</span>
                </p>

                {baris.reasons.length > 0 ? (
                  <ul className="goods-receipt-reasons">
                    {baris.reasons.map((alasan) => (
                      <li key={alasan}>{alasan}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="evidence-note">Tidak ada penghalang penerimaan.</p>
                )}

                {baris.nextStep ? (
                  <p className="goods-receipt-next">
                    <strong>Langkah berikutnya:</strong> {baris.nextStep}
                  </p>
                ) : null}

                {bolehPutuskan || baris.canQuarantine ? (
                  <div className="goods-receipt-actions">
                    {bisaTerima ? (
                      <button
                        type="button"
                        className="btn btn-primary"
                        data-action="receive"
                        disabled={busy !== null}
                        onClick={() => void terima(baris.batchId, String(menunggu!.id))}
                      >
                        {RECEIPT_APPROVE_LABEL}
                      </button>
                    ) : null}

                    {menunggu !== null && bolehPutuskan ? (
                      batchTolak === baris.batchId ? (
                        <span className="goods-receipt-reject">
                          <label>
                            Alasan penolakan
                            <input
                              type="text"
                              value={alasanTolak}
                              onChange={(e) => setAlasanTolak(e.target.value)}
                              placeholder="mis. suhu tidak sesuai saat tiba"
                            />
                          </label>
                          <button
                            type="button"
                            className="btn"
                            data-action="reject-confirm"
                            disabled={busy !== null}
                            onClick={() => void tolak(String(menunggu.id))}
                          >
                            Kirim penolakan
                          </button>
                          <button
                            type="button"
                            className="btn"
                            data-action="reject-cancel"
                            onClick={() => {
                              setBatchTolak(null);
                              setAlasanTolak("");
                            }}
                          >
                            Batal
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="btn"
                          data-action="reject"
                          disabled={busy !== null}
                          onClick={() => setBatchTolak(baris.batchId)}
                        >
                          {RECEIPT_REJECT_LABEL}
                        </button>
                      )
                    ) : null}

                    {baris.canQuarantine ? (
                      <span className="goods-receipt-quarantine" data-action="quarantine-hint">
                        {QUARANTINE_HOLD_LABEL} tersedia di papan Keamanan Pangan
                      </span>
                    ) : null}
                  </div>
                ) : (
                  <p className="evidence-note">
                    Peran ini hanya dapat melihat status penerimaan (read-only).
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {gate.blockedSentence ? (
        <p className="evidence-note">{gate.blockedSentence}</p>
      ) : null}
    </article>
  );
}
