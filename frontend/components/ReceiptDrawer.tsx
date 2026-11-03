"use client";

// Popup penerimaan barang (Dokumen 05 §2) — drawer kanan, TIGA langkah berurutan.
//
// Kenapa dipisah dari kartu: sebelum ini seluruh ceklis hidup inline di kartu
// "Penerimaan barang" (terukur 796 px di 1262 px), sehingga dua kartu bertindak
// (Penerimaan dan Menunggu persetujuan) berjauhan dan halaman terasa seperti
// formulir, bukan papan pengawasan. Dok 05 §1–§2 menyebut bentuknya tegas:
// popup drawer kanan dengan tiga langkah yang tidak boleh dilompati.
//
// Pemetaan konsep dokumen ke repo ini — sengaja disebut, karena tidak 1:1:
//   §3 tujuh butir berbobot -> repo ini punya LIMA titik periksa boolean
//      (`RECEIVING_CHECKS`), tanpa skor/poin. Mesin skor Dok 05
//      (`bobot × faktor`) tidak ada di backend ini, jadi bobot TIDAK dikarang.
//      Yang diambil dari §2 adalah GERBANGNYA: tombol simpan mati selama ada
//      titik yang belum dijawab, dan peran non-penerima tidak bisa mengisi.
//   §4 putusan berjenjang -> putusan di repo ini datang dari evaluator server
//      (`safety_status` hasil hitung ulang), bukan dari skor ceklis.
//   §5 nilai rupiah -> kg × harga satuan PO, dihitung server
//      (`estimated_value_idr`), asalnya ditulis apa adanya (§8.3).
//   §2 langkah 3 "tandai barang" -> tombol terima/tolak hanya dirender bila
//      server menyatakan catatan masih `menunggu` DAN peran berhak memutuskan.
//
// Yang TIDAK dikarang: skor 0–100, poin per butir, `acceptance_advice`, dan
// foto bukti (§8.4 butuh kolom baru — keputusan, bukan desain).

import { useState } from "react";

import type { ReceiptChecklist, ReceiptPoint } from "../lib/api";
import type { ReceiptCardRow } from "../lib/food-safety";
import { RECEIVING_OTHER } from "../lib/food-safety";
import own from "./ReceiptDrawer.module.css";

export type ReceiptHasil = {
  score: number | null;
  verdict: string;
  verdictLabel: string;
  advice: string | null;
  points: ReceiptPoint[] | null;
  orderedKg: number | null;
  acceptedKg: number | null;
  nilaiLabel: string;
  nilaiStatus: "tersimpan" | "perkiraan" | "tidak_tercatat";
  asalHarga: string | null;
  riwayat: ReceiptCardRow[];
};

export type ReceiptBatchInfo = {
  commodity: string;
  kgLabel: string;
  orderedKg: number | null;
  statusLabel: string;
  usableUntil: string;
  expired: boolean;
};

export type ReceiptBukti = {
  stateLabel: string;
  observationLabel: string;
  sourceLabel: string;
  observedAt: string | null;
  sufficient: boolean;
};

export type ReceiptPutusan = {
  pendingId: string | null;
  boleh: boolean;
  expired: boolean;
  alasanTolak: string;
  onAlasanTolak: (nilai: string) => void;
  tolakTerbuka: boolean;
  onBukaTolak: () => void;
  onBatalTolak: () => void;
  onSetujui: (id: string) => void;
  onTolak: (id: string) => void;
};

type Props = {
  batch: ReceiptBatchInfo | null;
  bukti: ReceiptBukti | null;
  komoditas: string;
  /** Daftar butir dari server; `null` = belum termuat. */
  checklist: ReceiptChecklist | null;
  checklistGalat: string | null;
  jawaban: Record<string, string>;
  onJawab: (kunci: string, opsi: string) => void;
  /** Berat timbangan sebagai teks: kosong ≠ 0, jadi jangan dipaksa number. */
  berat: string;
  onBerat: (nilai: string) => void;
  beratGalat: string | null;
  catatan: string;
  onCatatan: (nilai: string) => void;
  /** Peran yang boleh mengisi ceklis (sppg_head / sppg_nutritionist). */
  canMutate: boolean;
  /** Jalur simpan tersedia (`onRecordReceipt` + `onRecheck`). */
  adaJalurSimpan: boolean;
  menyimpan: boolean;
  onSimpan: () => void;
  /** Terisi setelah ceklis dinilai server → langkah 2 dan 3 terbuka. */
  hasil: ReceiptHasil | null;
  putusan: ReceiptPutusan;
  aksi: { nada: "ok" | "danger"; teks: string } | null;
  /** Jumlah butir yang sudah dijawab (gerbang tombol simpan). */
  terjawab: number;
  totalButir: number;
};

/** Angka kg tanpa nol ekor: 150 → "150", 149,5 → "149,5". */
function kgRingkas(nilai: number | string | null): string {
  if (nilai === null || nilai === "") return "—";
  const angka = typeof nilai === "number" ? nilai : Number(String(nilai).replace(",", "."));
  if (!Number.isFinite(angka)) return "—";
  return angka.toLocaleString("id-ID", { maximumFractionDigits: 2 });
}

function Step({
  no,
  title,
  state,
  children,
}: {
  no: number;
  title: string;
  state: "aktif" | "selesai" | "menunggu";
  children: React.ReactNode;
}) {
  return (
    <section className={own.step} data-state={state} data-testid={`receipt-step-${no}`}>
      <header className={own.stepHead}>
        <span className={own.stepNo} aria-hidden="true">
          {state === "selesai" ? "✓" : no}
        </span>
        <h3 className={own.stepTitle}>
          {no}. {title}
        </h3>
        <span className={own.stepState}>
          {state === "selesai" ? "selesai" : state === "aktif" ? "sekarang" : "belum"}
        </span>
      </header>
      {state === "menunggu" ? null : children}
    </section>
  );
}

/**
 * Isi popup — dipisah dari cangkang supaya bisa dirender tes tanpa portal.
 */
export function ReceiptSheet({
  batch,
  bukti,
  komoditas,
  checklist,
  checklistGalat,
  jawaban,
  onJawab,
  berat,
  onBerat,
  beratGalat,
  catatan,
  onCatatan,
  canMutate,
  adaJalurSimpan,
  menyimpan,
  onSimpan,
  hasil,
  putusan,
  aksi,
  terjawab,
  totalButir,
}: Props) {
  // Tahap 4 redesign (30 Okt 2026): aksi tulis tidak boleh terjadi pada klik
  // pertama. Tombol utama membuka layar konfirmasi; penyimpanan hanya jalan
  // setelah orang membaca apa yang akan dicatat.
  const [konfirmasi, setKonfirmasi] = useState(false);
  const semuaDijawab = totalButir > 0 && terjawab === totalButir;
  const bolehSimpan =
    canMutate &&
    adaJalurSimpan &&
    semuaDijawab &&
    berat.trim() !== "" &&
    !beratGalat &&
    !menyimpan;
  const adaPutusan = putusan.pendingId !== null;
  const gagal = hasil?.verdict === "fail";
  const bolehTandai =
    adaPutusan && putusan.boleh && !putusan.expired && !gagal && hasil?.verdict !== "fail";

  return (
    <div className={own.sheet}>
      {aksi ? (
        <p
          className={aksi.nada === "danger" ? own.alert : own.note}
          role={aksi.nada === "danger" ? "alert" : "status"}
          data-testid="receipt-aksi"
        >
          {aksi.teks}
        </p>
      ) : null}

      {/* ---------- langkah 1: periksa kondisi barang ---------- */}
      <Step no={1} title="Periksa kondisi barang" state={hasil ? "selesai" : "aktif"}>
        {batch ? (
          <p className={own.batchLine} data-testid="receipt-batch-line">
            <strong>{batch.commodity}</strong> · {batch.kgLabel} · {batch.statusLabel}
            <span className={own.batchMeta}>
              {" · "}layak s/d <span className={own.nobr}>{batch.usableUntil}</span>
              {batch.expired ? " · sudah kedaluwarsa" : ""}
            </span>
          </p>
        ) : null}

        {bukti ? (
          <p className={own.note} data-role="bukti-terima">
            Bukti suhu kiriman ini: <strong>{bukti.stateLabel}</strong> · {bukti.observationLabel} ·{" "}
            {bukti.sourceLabel}
            {bukti.observedAt ? ` · diamati ${bukti.observedAt}` : ""}
            {bukti.sufficient ? " — boleh dicentang dan dipakai." : " — periksa dulu sebelum dipakai."}
          </p>
        ) : null}

        {checklistGalat ? (
          <p className={own.alert} role="alert">
            {checklistGalat}
          </p>
        ) : null}

        {checklist ? (
          <ol className={own.items}>
            {checklist.butir.map((butir, urut) => {
              const dipilih = jawaban[butir.kunci] ?? "";
              return (
                <li className={own.item} key={butir.kunci} data-testid={`butir-${butir.kunci}`}>
                  <div className={own.itemHead}>
                    <span className={own.itemNo} aria-hidden="true">
                      {urut + 1}
                    </span>
                    <span className={own.itemLabel}>{butir.label}</span>
                    <span
                      className={own.itemWeight}
                      title={`Bobot ${butir.bobot} dari ${checklist.total_bobot}`}
                    >
                      {butir.bobot} poin
                    </span>
                  </div>
                  {butir.petunjuk ? <p className={own.itemHint}>{butir.petunjuk}</p> : null}
                  {butir.dari_timbangan ? (
                    // Butir ini TIDAK dipilih petugas: server menurunkannya dari
                    // berat timbangan (Dok 05 §5.1) supaya jawaban tidak bisa
                    // bertentangan dengan kg yang masuk stok.
                    <p className={own.itemMeta} data-testid="butir-jumlah">
                      Dihitung dari timbangan sesudah disimpan
                      {berat.trim()
                        ? ` — ${kgRingkas(berat)} kg diterima dari ${kgRingkas(
                            batch?.orderedKg ?? null
                          )} kg pesanan.`
                        : " — isi berat diterima dulu."}
                    </p>
                  ) : (
                    <div className={own.options} role="radiogroup" aria-label={butir.label}>
                      {butir.opsi.map((opsi) => {
                        const aktif = dipilih === opsi.kunci;
                        return (
                          <label
                            key={opsi.kunci}
                            className={own.option}
                            data-state={aktif ? "aktif" : "kosong"}
                            data-kritis={opsi.kritis ? "true" : "false"}
                          >
                            <input
                              type="radio"
                              name={`butir-${butir.kunci}`}
                              value={opsi.kunci}
                              checked={aktif}
                              disabled={!canMutate || Boolean(hasil)}
                              onChange={() => onJawab(butir.kunci, opsi.kunci)}
                            />
                            <span className={own.optionLabel}>{opsi.label}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        ) : null}

        {/* Berat timbangan: dasar nilai rupiah (§5.1) dan butir "jumlah". */}
        <div className={own.weighRow}>
          <label className={own.weighLabel} htmlFor="berat-diterima">
            Berat diterima (kg)
          </label>
          <input
            id="berat-diterima"
            className={own.weighInput}
            type="number"
            inputMode="decimal"
            min={0}
            step="0.1"
            value={berat}
            placeholder={batch?.orderedKg ? String(batch.orderedKg) : "0"}
            disabled={!canMutate || Boolean(hasil)}
            aria-invalid={beratGalat ? true : undefined}
            aria-describedby="berat-diterima-bantuan"
            onChange={(event) => onBerat(event.target.value)}
          />
          <span
            className={beratGalat ? own.weighError : own.weighHint}
            id="berat-diterima-bantuan"
            aria-live="polite"
          >
            {beratGalat
              ? beratGalat
              : batch?.orderedKg
                ? `Pesanan ${kgRingkas(batch.orderedKg)} kg. Nilai rupiah dihitung dari angka ini, bukan dari berat batch.`
                : "Nilai rupiah dihitung dari angka ini, bukan dari berat batch."}
          </span>
        </div>

        <div className={own.other}>
          <label htmlFor="catatan-penerimaan">{RECEIVING_OTHER.label}</label>
          <textarea
            id="catatan-penerimaan"
            value={catatan}
            maxLength={500}
            rows={2}
            placeholder={RECEIVING_OTHER.hint}
            disabled={!canMutate || Boolean(hasil)}
            onChange={(event) => onCatatan(event.target.value)}
          />
          <span className="evidence-note">
            {catatan.trim()
              ? `${catatan.trim().length} karakter — ikut tersimpan saat dinilai.`
              : "Ikut tersimpan bersama catatan penerimaan ini."}
          </span>
        </div>

        <p className={own.progress} aria-live="polite" data-testid="receipt-kemajuan">
          {totalButir === 0
            ? "Daftar butir belum termuat."
            : semuaDijawab
              ? `${terjawab} dari ${totalButir} butir sudah dijawab — semua wajib, tidak ada yang boleh dilewati.`
              : `${terjawab} dari ${totalButir} butir sudah dijawab — ${totalButir - terjawab} belum. Tombol simpan aktif setelah semuanya dijawab dan berat diterima diisi.`}
        </p>

        {hasil ? null : canMutate && adaJalurSimpan ? (
          konfirmasi ? (
            <div
              className={own.konfirmasi}
              role="group"
              aria-labelledby="konfirmasi-terima-judul"
              data-testid="receipt-konfirmasi"
            >
              <h4 className={own.konfirmasiJudul} id="konfirmasi-terima-judul">
                Konfirmasi sebelum dicatat
              </h4>
              <p className={own.note}>
                Sesudah dicatat, server menghitung ulang status keamanan dan kesegaran batch
                ini, dan catatannya tidak bisa dibatalkan dari halaman ini.
              </p>
              <dl className={own.konfirmasiFakta}>
                <div>
                  <dt>Komoditas</dt>
                  <dd>{komoditas || "—"}</dd>
                </div>
                <div>
                  <dt>Batch</dt>
                  <dd>
                    {batch ? `${batch.kgLabel} · ${batch.statusLabel}` : "—"}
                  </dd>
                </div>
                <div>
                  <dt>Berat diterima</dt>
                  <dd>{berat.trim() ? `${kgRingkas(berat)} kg` : "belum diisi"}</dd>
                </div>
                <div>
                  <dt>Butir dijawab</dt>
                  <dd>
                    {terjawab} dari {totalButir}
                  </dd>
                </div>
                <div>
                  <dt>Catatan</dt>
                  <dd>{catatan.trim() ? `${catatan.trim().length} karakter` : "tanpa catatan"}</dd>
                </div>
              </dl>
              <div className={own.konfirmasiAksi}>
                <button
                  type="button"
                  className="button button-primary"
                  disabled={menyimpan}
                  onClick={() => {
                    setKonfirmasi(false);
                    onSimpan();
                  }}
                >
                  {menyimpan ? "Menilai…" : "Catat & hitung nilai"}
                </button>
                <button
                  type="button"
                  className="button button-secondary"
                  disabled={menyimpan}
                  onClick={() => setKonfirmasi(false)}
                >
                  Kembali perbaiki
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="button button-primary"
              disabled={!bolehSimpan}
              onClick={() => setKonfirmasi(true)}
            >
              Lanjut: konfirmasi
            </button>
          )
        ) : (
          <p className="evidence-note">
            {canMutate
              ? "Jalur simpan tidak tersedia di halaman ini — titik yang dicentang tidak ikut tersimpan."
              : "Hanya kepala SPPG dan ahli gizi yang bisa mencatat hasil terima."}
          </p>
        )}
        {komoditas ? null : <p className={own.note}>Pilih komoditas lebih dulu.</p>}
      </Step>

      {/* ---------- langkah 2: nilai dan putusan batch ---------- */}
      <Step
        no={2}
        title="Nilai dan putusan batch"
        state={hasil ? (adaPutusan ? "selesai" : "aktif") : "menunggu"}
      >
        <div className={own.scoreRow} data-testid="receipt-score">
          <div className={own.scoreBox} data-verdict={hasil?.verdict ?? "kosong"}>
            <span className={own.scoreValue}>{hasil?.score ?? "—"}</span>
            <span className={own.scoreMax}>dari 100</span>
          </div>
          <div className={own.scoreSide}>
            <span className={own.verdict} data-verdict={hasil?.verdict ?? "kosong"}>
              {hasil?.verdictLabel ?? "—"}
            </span>
            <p className={own.note} data-testid="receipt-advice">
              {hasil?.advice ??
                "Kalimat alasan muncul di sini sesudah ceklis dinilai."}
            </p>
          </div>
        </div>

        <div className={own.figures} data-testid="receipt-figures">
          <div className={own.figure}>
            <span className={own.figureLabel}>Dipesan</span>
            <strong className={own.figureValue}>
              {kgRingkas(hasil?.orderedKg ?? batch?.orderedKg ?? null)} kg
            </strong>
          </div>
          <div className={own.figure}>
            <span className={own.figureLabel}>Diterima</span>
            <strong className={own.figureValue}>{kgRingkas(hasil?.acceptedKg ?? null)} kg</strong>
          </div>
          <div className={`${own.figure} ${own.figureWide}`}>
            <span className={own.figureLabel}>
              Nilai diterima
              {hasil?.nilaiStatus === "perkiraan" ? (
                <span className={own.figureBadge}>perkiraan</span>
              ) : null}
            </span>
            <strong
              className={own.figureValue}
              data-status={hasil?.nilaiStatus ?? "tidak_tercatat"}
              data-testid="receipt-value"
            >
              {hasil?.nilaiLabel ?? "—"}
            </strong>
            {hasil?.asalHarga ? (
              <span className={own.priceOrigin} data-testid="receipt-value-origin">
                {hasil.asalHarga}
              </span>
            ) : null}
          </div>
        </div>

        {hasil?.points && hasil.points.length > 0 ? (
          <div className={own.pointTable} data-testid="receipt-points">
            <p className={own.subhead}>Rincian poin per butir</p>
            <table className={own.table}>
              <thead>
                <tr>
                  <th scope="col">Butir</th>
                  <th scope="col">Jawaban</th>
                  <th scope="col" className={own.num}>
                    Poin
                  </th>
                </tr>
              </thead>
              <tbody>
                {hasil.points.map((baris) => (
                  <tr key={baris.kunci} data-kritis={baris.kritis ? "true" : "false"}>
                    <td>{baris.label}</td>
                    <td>{baris.opsi_label}</td>
                    <td className={own.num}>
                      {baris.poin} / {baris.max_points}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {hasil && hasil.riwayat.length > 0 ? (
          <>
            <p className={own.subhead}>Catatan penerimaan tersimpan</p>
            <ul className={own.riwayat}>
              {hasil.riwayat.map((r) => (
                <li key={r.id}>
                  <span className={own.riwayatHead}>
                    {r.note ?? <em>tanpa catatan tambahan</em>}
                    <span className={`board-badge board-badge-${r.statusNada}`}>{r.statusLabel}</span>
                  </span>
                  <span className={own.riwayatMeta}>
                    {r.checkedCount === null ? "—" : `${r.checkedCount} titik`} · dicatat{" "}
                    {r.byName ?? "—"} · {r.waktuLabel}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </Step>

      {/* ---------- langkah 3: tandai barang ---------- */}
      <Step no={3} title="Tandai barang" state={bolehTandai ? "aktif" : adaPutusan ? "aktif" : "menunggu"}>
        {!adaPutusan ? (
          <p className={own.note}>Catat ceklis dulu; tombol terima dan tolak muncul setelah itu.</p>
        ) : gagal ? (
          <p className={own.alert} data-testid="receipt-blocked">
            Putusan server <strong>tidak boleh diterima</strong> — barang tidak masuk stok sebesar apa
            pun jumlah fisiknya, jadi tombol setuju tidak ditampilkan. Tolak penerimaan dengan alasan,
            lalu minta barang pengganti.
          </p>
        ) : putusan.expired ? (
          <p className={own.alert}>
            Batch ini sudah kedaluwarsa — tidak bisa disetujui masuk stok. Tolak penerimaan dan
            minta barang pengganti.
          </p>
        ) : !putusan.boleh ? (
          <p className={own.note}>
            Catatan terbaru berstatus <strong>menunggu persetujuan kepala SPPG</strong> — stok belum
            bertambah sampai disetujui. Kepala SPPG memutuskannya di kartu “Menunggu persetujuan”.
          </p>
        ) : (
          <>
            <p className={own.note}>
              Menyetujui berarti <strong>{kgRingkas(hasil?.acceptedKg ?? null)} kg</strong> masuk stok
              (berat timbangan, bukan berat batch). Menolak tidak menambah stok.
            </p>
            <div className={own.actions}>
              <button
                type="button"
                className="button button-primary"
                disabled={menyimpan}
                onClick={() => putusan.onSetujui(putusan.pendingId as string)}
              >
                Setujui & masukkan stok
              </button>
              <button
                type="button"
                className="button"
                disabled={menyimpan}
                aria-expanded={putusan.tolakTerbuka}
                onClick={() => (putusan.tolakTerbuka ? putusan.onBatalTolak() : putusan.onBukaTolak())}
              >
                Tolak penerimaan
              </button>
            </div>
            {putusan.tolakTerbuka ? (
              <div className="safety-other">
                <label htmlFor="alasan-tolak-penerimaan">Alasan penolakan (wajib)</label>
                <textarea
                  id="alasan-tolak-penerimaan"
                  value={putusan.alasanTolak}
                  maxLength={500}
                  rows={2}
                  placeholder="Contoh: kemasan penyok dan suhu 12 °C — minta ganti barang."
                  onChange={(event) => putusan.onAlasanTolak(event.target.value)}
                />
                <span className="evidence-note">
                  Tersimpan bersama keputusan; petugas membacanya di riwayat.
                </span>
                <button
                  type="button"
                  className="button button-primary"
                  disabled={menyimpan}
                  onClick={() => putusan.onTolak(putusan.pendingId as string)}
                >
                  Kirim penolakan
                </button>
              </div>
            ) : null}
          </>
        )}
      </Step>
    </div>
  );
}

export default ReceiptSheet;
