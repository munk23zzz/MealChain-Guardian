"use client";

// GoodsReceiptDrawer — penerimaan barang satu keputusan (Fase 9 MG butir 2 & 4),
// di-redesain mengikuti dokumen 05 §8.
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
//   4. Tidak menghitung apa pun: status, alasan, langkah berikutnya, kg, dan
//      rupiah berasal dari server (`receipt_gate`, `receipt_value`). Klien hanya
//      memilih angka mana yang tampil dan menulis kalimatnya.
//
// Sumber data: `summary` = `GET /decisions/{id}/approval-summary`; catatan
// penerimaan per batch = `GET /receipts?batch_id=…` (prop `receipts` untuk tes).
//
// Dok 05 yang diterapkan di sini:
//   §1  bentuk DRAWER kanan, dibuka per batch dari panel penerimaan;
//   §2  tiga langkah bernomor yang tidak bisa dilompati;
//   §8.1 titik periksa + berapa yang benar-benar ditandai (bukan skor karangan);
//   §8.2 tiga angka dipisah: kuantitas batch / masuk stok / nilai diterima;
//   §8.3 asal harga satuan ditulis di bawah nilai (kg × Rp/kg dari PO …).

import { useCallback, useEffect, useRef, useState } from "react";

import Popup from "./Popup";

import { approveReceipt, fetchReceipts, rejectReceipt } from "../lib/api";
import { formatRupiah } from "../lib/decision-economics";
import {
  QUARANTINE_HOLD_LABEL,
  RECEIPT_APPROVE_LABEL,
  RECEIPT_REJECT_LABEL,
  canDecideReceipt,
  checkpointState,
  pendingReceipt,
  receiptFigures,
  receiptGateView,
  serverDetail,
  valueOrigin,
} from "../lib/goods-receipt";
import { formatKg } from "../lib/overview-format";
import own from "./GoodsReceiptDrawer.module.css";

type BarisCatatan = Record<string, any>;

type BarisGate = {
  batchId: string;
  status: string;
  statusLabel: string;
  canReceive: boolean;
  canQuarantine: boolean;
  reasons: string[];
  nextStep: string | null;
};

/** Satu langkah bernomor — urutan inilah yang membuat alur penerimaan terbaca. */
function Step({
  no,
  title,
  note,
  testId,
  children,
}: {
  no: number;
  title: string;
  note?: string;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <section className={own.step} data-testid={testId}>
      <header className={own.stepHead}>
        <span className={own.stepNo} aria-hidden="true">
          {no}
        </span>
        <h3 className={own.stepTitle}>{title}</h3>
      </header>
      {note ? <p className={own.stepNote}>{note}</p> : null}
      {children}
    </section>
  );
}

/** Tiga angka yang berbeda, berjajar, dengan asal harga di bawah nilai (§8.2–§8.3). */
export function ReceiptFigures({ catatan }: { catatan: BarisCatatan | null }) {
  const angka = receiptFigures(catatan);
  const asal = valueOrigin(catatan);
  return (
    <>
      <div className={own.figures} data-testid="receipt-figures">
        <div className={own.figure}>
          <span className={own.figureLabel}>Kuantitas batch</span>
          <strong className={own.figureValue} data-testid="receipt-figure-batch">
            {formatKg(angka.kuantitasKg)}
          </strong>
        </div>
        <div className={own.figure}>
          <span className={own.figureLabel}>Masuk stok</span>
          <strong className={own.figureValue} data-testid="receipt-figure-stock">
            {angka.masukStokKg === null ? "Belum masuk stok" : formatKg(angka.masukStokKg)}
          </strong>
        </div>
        <div className={`${own.figure} ${own.figureWide}`}>
          <span className={own.figureLabel}>
            Nilai diterima
            {angka.nilaiSementara ? (
              <span className={own.figureBadge} data-testid="receipt-value-estimate">
                perkiraan
              </span>
            ) : null}
          </span>
          <strong className={own.figureValue} data-testid="receipt-value">
            {formatRupiah(angka.nilaiIdr)}
          </strong>
          {asal ? (
            <span className={own.priceOrigin} data-testid="receipt-value-origin">
              {asal}
            </span>
          ) : null}
        </div>
      </div>
      {angka.nilaiSementara ? (
        <p className={own.note} data-testid="receipt-estimate-note">
          Angka rupiah ini perkiraan dari kg × harga satuan PO; nilai pembukuan
          tercatat setelah penerimaan disetujui.
        </p>
      ) : null}
    </>
  );
}

/**
 * Isi drawer untuk SATU batch — dipisah dari komponen jaringan supaya bisa
 * dirender tes tanpa memuat apa pun.
 */
export function GoodsReceiptSheet({
  baris,
  catatan,
  bolehPutuskan,
  busy,
  galat,
  pesan,
  onTerima,
  onTolak,
  alasanTolak,
  onAlasanTolak,
  tolakTerbuka,
  onBukaTolak,
  onBatalTolak,
}: {
  baris: BarisGate;
  catatan: BarisCatatan | null;
  bolehPutuskan: boolean;
  busy: boolean;
  galat: string | null;
  pesan: string | null;
  onTerima?: () => void;
  onTolak?: () => void;
  alasanTolak?: string;
  onAlasanTolak?: (nilai: string) => void;
  tolakTerbuka?: boolean;
  onBukaTolak?: () => void;
  onBatalTolak?: () => void;
}) {
  const titik = checkpointState(catatan);
  const menunggu = String(catatan?.status ?? "") === "menunggu";
  const bisaTerima = baris.canReceive && menunggu;

  return (
    <div className={own.sheet}>
      {galat ? (
        <p className={own.error} role="alert" data-testid="receipt-error">
          {galat}
        </p>
      ) : null}
      {pesan ? (
        <p className={own.note} role="status" data-testid="receipt-info">
          {pesan}
        </p>
      ) : null}

      {/* ---------- langkah 1: kondisi barang ---------- */}
      <Step
        no={1}
        title="Periksa kondisi barang"
        testId="receipt-step-checklist"
        note="Titik periksa dicatat petugas di papan Keamanan Pangan. Yang tampil di sini adalah yang benar-benar tersimpan — bukan ringkasan karangan layar."
      >
        <p className={own.progress} data-testid="receipt-checkpoint-progress">
          <strong>
            {titik.done} dari {titik.total}
          </strong>{" "}
          titik periksa ditandai
        </p>
        <ul className={own.checkpoints}>
          {titik.items.map((item) => (
            <li
              key={item.id}
              className={own.checkpoint}
              data-checked={item.checked ? "true" : "false"}
              data-testid={`receipt-checkpoint-${item.id}`}
            >
              <span aria-hidden="true" className={own.checkpointMark}>
                {item.checked ? "✓" : "•"}
              </span>
              <span className={own.checkpointLabel}>{item.label}</span>
              <span className={own.checkpointFlag}>
                {item.checked ? "ditandai" : "tidak ditandai"}
              </span>
            </li>
          ))}
        </ul>
        {catatan === null ? (
          <p className={own.note} data-testid="receipt-no-record">
            Belum ada catatan pemeriksaan untuk batch ini. Catatan dibuat petugas
            penerima di papan Keamanan Pangan; setelah tersimpan, batch masuk
            antrean keputusan di sini.
          </p>
        ) : null}
        {catatan?.other_note ? (
          <p className={own.note} data-testid="receipt-other-note">
            Catatan lain petugas: {String(catatan.other_note)}
          </p>
        ) : null}
      </Step>

      {/* ---------- langkah 2: nilai dan putusan ---------- */}
      <Step
        no={2}
        title="Nilai dan putusan batch"
        testId="receipt-step-nilai"
        note="Kg dari batch, harga satuan dari PO invoice, dan nilainya dihitung server. Layar tidak mengalikan rupiah sendiri."
      >
        <ReceiptFigures catatan={catatan} />
        <div className={own.figureRow}>
          <span className={own.figureLabel}>Status batch</span>
          <strong className={own.figureValue} data-testid="receipt-status">
            {baris.statusLabel}
          </strong>
        </div>
        {baris.reasons.length > 0 ? (
          <ul className={own.reasons} data-testid="receipt-reasons">
            {baris.reasons.map((alasan) => (
              <li key={alasan}>{alasan}</li>
            ))}
          </ul>
        ) : (
          <p className={own.note}>Tidak ada penghalang penerimaan.</p>
        )}
        {baris.nextStep ? (
          <p className={own.note} data-testid="receipt-next-step">
            <strong>Langkah berikutnya:</strong> {baris.nextStep}
          </p>
        ) : null}
      </Step>

      {/* ---------- langkah 3: penandaan ---------- */}
      <Step
        no={3}
        title="Tandai barang"
        testId="receipt-step-marking"
        note="Arah penandaan ditentukan server: tombol yang tidak diizinkan tidak dirender, bukan hanya dinonaktifkan."
      >
        {bolehPutuskan || baris.canQuarantine ? (
          <div className={own.actions}>
            {bisaTerima && bolehPutuskan ? (
              <button
                type="button"
                className={own.primary}
                data-action="receive"
                disabled={busy}
                onClick={onTerima}
              >
                {RECEIPT_APPROVE_LABEL}
              </button>
            ) : null}

            {menunggu && bolehPutuskan ? (
              tolakTerbuka ? (
                <div className={own.rejectBox}>
                  <label className={own.field}>
                    <span className={own.fieldLabel}>Alasan penolakan</span>
                    <input
                      className={own.input}
                      type="text"
                      value={alasanTolak ?? ""}
                      onChange={(e) => onAlasanTolak?.(e.target.value)}
                      placeholder="mis. suhu tidak sesuai saat tiba"
                      data-testid="receipt-reject-note"
                    />
                  </label>
                  <div className={own.actions}>
                    <button
                      type="button"
                      className={own.danger}
                      data-action="reject-confirm"
                      disabled={busy}
                      onClick={onTolak}
                    >
                      Kirim penolakan
                    </button>
                    <button
                      type="button"
                      className={own.secondary}
                      data-action="reject-cancel"
                      onClick={onBatalTolak}
                    >
                      Batal
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  className={own.danger}
                  data-action="reject"
                  disabled={busy}
                  onClick={onBukaTolak}
                >
                  {RECEIPT_REJECT_LABEL}
                </button>
              )
            ) : null}

            {baris.canQuarantine ? (
              <span className={own.note} data-action="quarantine-hint">
                {QUARANTINE_HOLD_LABEL} tersedia di papan Keamanan Pangan
              </span>
            ) : baris.status === "quarantined" ? (
              // Batch yang SUDAH ditahan tidak bisa ditahan ulang; tindakannya
              // melepas karantina atau menolak batch, dan keduanya ada di papan
              // Keamanan Pangan. Petunjuk ini yang membedakan dari `on_hold`.
              <span className={own.note} data-action="release-hint">
                Lepas karantina atau tolak batch lewat papan Keamanan Pangan
              </span>
            ) : null}
          </div>
        ) : (
          <p className={own.note} data-testid="receipt-readonly">
            Peran ini hanya dapat melihat status penerimaan (read-only).
          </p>
        )}
      </Step>
    </div>
  );
}

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
  const [busy, setBusy] = useState(false);
  const [alasanTolak, setAlasanTolak] = useState("");
  const [tolakTerbuka, setTolakTerbuka] = useState(false);
  const [terbuka, setTerbuka] = useState<string | null>(null);
  // Fokus dikembalikan ke tombol pemicu oleh `Popup` lewat `returnFocusRef`;
  // komponen ini tidak lagi mengelola portal, kunci gulir, atau jebakan Tab
  // sendiri (lihat catatan di kepala berkas).
  const pemicuRef = useRef<HTMLElement | null>(null);

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

  const bolehPutuskan = canDecideReceipt(role);

  function bukaPanel(batchId: string, pemicu: HTMLElement | null) {
    pemicuRef.current = pemicu;
    setGalat(null);
    setPesan(null);
    setTolakTerbuka(false);
    setAlasanTolak("");
    setTerbuka(batchId);
  }

  function tutupPanel() {
    setTerbuka(null);
  }

  const barisAktif: BarisGate | null =
    gate.rows.find((b) => b.batchId === terbuka) ?? null;
  const catatanAktif: BarisCatatan | null = barisAktif
    ? pendingReceipt(muatan[barisAktif.batchId]) ?? muatan[barisAktif.batchId]?.[0] ?? null
    : null;

  async function terima(batchId: string) {
    const menunggu = pendingReceipt(muatan[batchId]);
    if (!token || !menunggu) return;
    setBusy(true);
    setGalat(null);
    setPesan(null);
    try {
      const balasan = await approveReceipt(String(menunggu.id), token);
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
      setBusy(false);
    }
  }

  async function tolak(batchId: string) {
    const menunggu = pendingReceipt(muatan[batchId]);
    if (!token || !menunggu) return;
    const alasan = alasanTolak.trim();
    if (!alasan) {
      setGalat("Alasan penolakan wajib diisi.");
      return;
    }
    setBusy(true);
    setGalat(null);
    setPesan(null);
    try {
      await rejectReceipt(String(menunggu.id), alasan, token);
      setPesan("Penerimaan ditolak; stok tidak bertambah.");
      setAlasanTolak("");
      setTolakTerbuka(false);
      setTerbuka(null);
      await muat();
      onChanged?.();
    } catch (e) {
      setGalat(serverDetail(e) || "Penolakan gagal tanpa keterangan server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="card goods-receipt" aria-label="Status penerimaan barang">
      <div className="card-header">
        <h2>Penerimaan barang</h2>
        <span className="evidence-note">
          Status, angka, dan tombol mengikuti penilaian server untuk dapur penerima.
        </span>
      </div>

      {galat && !barisAktif ? (
        <p className="board-alert" role="alert">
          {galat}
        </p>
      ) : null}

      {gate.rows.length === 0 ? (
        <p className="evidence-note">
          Belum ada barang keputusan ini di dapur penerima — belum ada yang bisa
          diterima atau ditahan.
        </p>
      ) : (
        <ul className={own.list}>
          {gate.rows.map((baris) => {
            const catatan = pendingReceipt(muatan[baris.batchId]);
            const angka = receiptFigures(catatan);
            return (
              <li key={baris.batchId} className={own.row} data-batch={baris.batchId}>
                <div className={own.rowMain}>
                  <p className={own.rowStatus}>
                    <strong>{baris.statusLabel}</strong>
                    <span className="evidence-note">
                      {" "}
                      · batch {baris.batchId.slice(0, 8)}
                    </span>
                  </p>
                  <p className={own.rowFigures}>
                    <span>{formatKg(angka.kuantitasKg)}</span>
                    <span aria-hidden="true">·</span>
                    <span data-tone={angka.nilaiSementara ? "estimate" : "final"}>
                      {formatRupiah(angka.nilaiIdr)}
                      {angka.nilaiSementara ? " (perkiraan)" : ""}
                    </span>
                  </p>
                </div>
                <button
                  type="button"
                  className={own.secondary}
                  data-testid="receipt-open-drawer"
                  onClick={(event) => bukaPanel(baris.batchId, event.currentTarget)}
                >
                  Buka penerimaan
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {gate.blockedSentence ? (
        <p className="evidence-note">{gate.blockedSentence}</p>
      ) : null}

      {/* Dok 05 §2 — tiga langkah di dalam SATU dialog. Cangkangnya `Popup`
          (bukan drawer buatan sendiri): jebakan Tab, Escape, kunci gulir,
          penutupan lewat mousedown, aria-labelledby, dan pemulihan fokus ke
          tombol pemicu sudah diuji di sana. Pemilik menolak drawer kanan untuk
          permukaan bersaudara (memory/global/decisions.md, 2026-10-28), jadi
          bentuknya popup tengah — bukan drawer kanan seperti bunyi dok 05 §1
          yang merujuk "drawer keputusan" yang di repo ini sudah popup tengah. */}
      <Popup
        open={barisAktif !== null}
        onClose={tutupPanel}
        eyebrow="Penerimaan barang"
        title={barisAktif ? `Batch ${barisAktif.batchId.slice(0, 8)}` : "Penerimaan barang"}
        meta={
          barisAktif ? (
            <span data-testid="receipt-popup-meta">
              {barisAktif.statusLabel} · dicatat petugas di papan Keamanan Pangan
            </span>
          ) : null
        }
        description="Tiga langkah berurutan: periksa kondisi barang, baca nilai dan putusan dari server, lalu tandai barang."
        labelledBy="popup-penerimaan-judul"
        className="popup-penerimaan"
        returnFocusRef={pemicuRef}
      >
        <div data-testid="receipt-drawer">
          {barisAktif ? (
            <GoodsReceiptSheet
              baris={barisAktif}
              catatan={catatanAktif}
              bolehPutuskan={bolehPutuskan}
              busy={busy}
              galat={galat}
              pesan={pesan}
              onTerima={() => void terima(barisAktif.batchId)}
              onTolak={() => void tolak(barisAktif.batchId)}
              alasanTolak={alasanTolak}
              onAlasanTolak={setAlasanTolak}
              tolakTerbuka={tolakTerbuka}
              onBukaTolak={() => setTolakTerbuka(true)}
              onBatalTolak={() => {
                setTolakTerbuka(false);
                setAlasanTolak("");
              }}
            />
          ) : null}
        </div>
      </Popup>
    </article>
  );
}
