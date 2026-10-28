"use client";

// DecisionDrawer — popup AKSI CEPAT satu keputusan, dibuka dari kartu
// Recommendation Feed.
//
// Keputusan pemilik 29 Okt 2026 ("Paket B", seleksi blok kembar
// Recommendations ↔ Decision & Evidence): popup hanya memuat yang dibutuhkan
// untuk MEMUTUSKAN SEKARANG — angka ringkas, tombol putuskan, kewajiban
// persetujuan, lalu satu tautan ke dossier.
//
// Jalur persetujuan, rincian biaya, PO, pemasok, jejak agen, dan ekspor TIDAK
// dirender lagi di sini. Bukan karena tempat, tetapi karena kebenaran: blok yang
// disalin ke dua tempat akan menyimpang (versi popup dan versi halaman tidak
// pernah diuji bersamaan), dan pembaca mengulang bacaan yang sama. Semuanya
// tinggal di halaman Decision & Evidence — satu keputusan, satu dossier.
//
// Kepala popup sengaja tidak diubah (label + judul + status + id): orang yang
// berpindah dari feed ke halaman bukti tidak boleh merasa pindah aplikasi.

import { useEffect, useState, type RefObject } from "react";

import Popup from "./Popup";
import ApprovalOverview from "./ApprovalOverview";
import DecisionActions from "./DecisionActions";
import StatusBadge from "./StatusBadge";
import { decisionHeadline } from "../lib/evidence";
import { shortId } from "../lib/agent-quality";
import { jenisKeputusan, kg, perbandinganHarga, rupiah, tahapPo } from "../lib/detail-keputusan";

// `TampilanAwal` = pilihan yang ditawarkan kartu feed ("Rincian" /
// "Persetujuan"), bukan tab di dalam popup (keputusan pemilik 28 Okt 2026).
// Keduanya membuka isi yang SAMA; bedanya hanya panel persetujuan sudah
// terbuka atau belum.
type TampilanAwal = "rincian" | "persetujuan";

export default function DecisionDrawer({
  open,
  onClose,
  decision,
  summary,
  role,
  token,
  now,
  onOpenFullPage,
  returnFocusRef,
  tampilanAwal = "rincian",
}: {
  open: boolean;
  onClose: () => void;
  decision: any | null;
  summary: any;
  role: string;
  token: string | null;
  now: Date | null;
  /** Pindah ke halaman "Decision & Evidence" untuk dossier lengkap. */
  onOpenFullPage?: (decisionId: string) => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  /** Panel persetujuan dibuka langsung bila kartu memintanya. */
  tampilanAwal?: TampilanAwal;
}) {
  const decisionId = decision?.decision_id ? String(decision.decision_id) : null;
  // Panel persetujuan hanya membuka DIRINYA SENDIRI saat popup dibuka dari
  // tombol "Persetujuan" di kartu. Setelah itu ia tidak boleh terbuka sendiri:
  // ia akan menutupi angka yang justru sedang dibaca.
  const [panelLangsung, setPanelLangsung] = useState(tampilanAwal === "persetujuan");

  // Keputusan lain atau panel dibuka ulang = mulai lagi dari pilihan kartu.
  // `open` wajib ada di dependensi: menutup panel tidak melepas komponennya.
  useEffect(() => {
    setPanelLangsung(tampilanAwal === "persetujuan");
  }, [decisionId, open, tampilanAwal]);

  // Gulungan selalu dimulai dari ATAS: pita angka menjelaskan keputusannya,
  // jadi ia tidak boleh terlewat karena posisi gulir keputusan sebelumnya.
  useEffect(() => {
    if (!open) return;
    const badan = document.querySelector<HTMLElement>(".popup-keputusan .popup-body");
    if (badan) badan.scrollTop = 0;
  }, [open, decisionId, tampilanAwal]);

  if (!decision || !decisionId) return null;

  const headline = decisionHeadline(decision, summary);
  const status = String(summary?.status ?? decision.status ?? "");
  const jenis = jenisKeputusan(decision.decision_type ?? summary?.decision_type);
  const komersial = summary?.commercial_cost ?? decision.commercial_cost;
  const banding = perbandinganHarga(decision.market_reference ?? summary?.market_reference, komersial);
  const po = tahapPo(summary?.purchase_order);
  const qty = kg(decision.quantity_kg ?? summary?.quantity_kg);
  const hargaPerKg = rupiah(komersial?.sdc_unit_price);
  const modeAksi = tampilanAwal === "persetujuan";

  /** Satu kalimat: apa yang terjadi sesudah tombol di panel aksi ditekan. */
  const akibatSetelah =
    jenis === "administratif"
      ? "Keputusan administratif dieksekusi lokal - tidak menerbitkan PO."
      : po.terbit
        ? `PO ${po.nomor} sudah terbit (${po.statusLabel}); tidak ada PO baru yang dibuat.`
        : "Setelah disetujui dan dieksekusi, PO terbit dengan harga terkirim sebagai harga satuan.";

  /** Jumlah penyetuju vs syarat minimum, untuk kepala bagian kewajiban. */
  const jumlahSetuju = Array.isArray(summary?.approvals) ? summary.approvals.length : 0;
  const syaratSetuju = summary?.approval_requirement?.min_approvals ?? null;
  const ringkasApproval =
    syaratSetuju === null
      ? `${jumlahSetuju} penyetuju`
      : `${jumlahSetuju} dari ${syaratSetuju} disetujui`;

  return (
    <Popup
      open={open}
      onClose={onClose}
      eyebrow="Detail Keputusan"
      title={headline}
      labelledBy="popup-keputusan-judul"
      className={`popup-keputusan${modeAksi ? " popup-keputusan--aksi" : ""}`}
      returnFocusRef={returnFocusRef}
      meta={
        <>
          <StatusBadge status={status} />
          <span className="detail-id">#{shortId(decisionId)}</span>
        </>
      }
    >
      {/* 1. Angka ringkas — satu-satunya angka yang dibutuhkan untuk menilai
          usulan ini sebelum menekan tombol. */}
      <section className="detail-sec detail-sec--full detail-kpi" aria-label="Angka ringkas">
        <div className="detail-kpi-item">
          <span className="detail-kpi-label">Jumlah</span>
          <strong className="detail-kpi-value">{qty ? `${qty} kg` : "—"}</strong>
        </div>
        <div className="detail-kpi-item">
          <span className="detail-kpi-label">Harga terkirim</span>
          <strong className="detail-kpi-value">
            {jenis === "pembelian" ? (hargaPerKg ? `${hargaPerKg}/kg` : "—") : "Tanpa pembelian"}
          </strong>
        </div>
        <div className="detail-kpi-item">
          <span className="detail-kpi-label">Dibanding harga acuan</span>
          <strong className="detail-kpi-value">
            {banding
              ? banding.arah === "sama"
                ? "Sama"
                : `${banding.arah === "lebih murah" ? "−" : "+"}${banding.perKg}/kg`
              : "—"}
          </strong>
          <span className="detail-kpi-sub">
            {banding ? `${banding.persen} dari acuan ${banding.acuanPerKg}/kg` : "acuan belum tercatat"}
          </span>
        </div>
      </section>

      {/* 2. Aksi — tombol dulu, daftar penyetuju sesudahnya: pada popup putus,
          CTA utama tidak boleh berada di bawah gulungan layar. */}
      <section className="detail-sec detail-sec--full detail-aksi detail-aksi--utama">
        <h4 className="detail-h">Putuskan sekarang</h4>
        <DecisionActions
          decisionId={decisionId}
          role={role}
          status={status}
          token={token}
          summary={summary}
          // Konfirmasi dirender di dalam panel ini, bukan jendela kedua di
          // atasnya (permintaan pemilik: "tidak ada popup dalam popup").
          tampil="panel"
          terbukaAwal={panelLangsung}
        />
        <p className="detail-setelah">{akibatSetelah}</p>
      </section>

      {/* 3. Kewajiban persetujuan — siapa lagi yang dibutuhkan. */}
      <section className="detail-sec detail-sec--full" aria-label="Kewajiban persetujuan">
        <h4 className="detail-h">
          Kewajiban persetujuan <span className="detail-fold-note">{ringkasApproval}</span>
        </h4>
        <ApprovalOverview summary={summary} role={role} now={now} />
      </section>

      {/* 4. Satu tautan keluar, bukan salinan dossier. */}
      {onOpenFullPage ? (
        <section className="detail-sec detail-sec--full detail-tautan-lengkap">
          <p className="detail-note">
            Jalur persetujuan, rincian biaya, PO, pemasok, jejak agen, dan berkas bukti ada di
            halaman Decision &amp; Evidence — satu keputusan, satu dossier.
          </p>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => onOpenFullPage(decisionId)}
          >
            Buka halaman lengkap
          </button>
        </section>
      ) : null}
    </Popup>
  );
}
