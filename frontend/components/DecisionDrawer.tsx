"use client";

// DecisionDrawer — panel samping (drawer) detail satu keputusan.
//
// Bentuk & urutan isi mengikuti dokumen acuan `01-detail-keputusan.md`:
//   §1  panel KANAN 520 px (layar penuh di mobile), backdrop gelap, ESC/klik
//       backdrop/tombol tutup menutup panel — bukan modal tengah, supaya tabel
//       di belakangnya tetap terbaca;
//   §2  dua belas bagian berurutan: kepala → strip alur → fakta dasar → biaya →
//       PO → catatan verifier → kewajiban approval → aksi → usulan → jejak
//       iterasi → pemasok → bukti & audit;
//   §6.1 satu baris rumus di bawah angka turunan ("Rp7.358.754 ÷ 600 kg");
//   §6.2 tiga lapis biaya, bukan tabel datar enam baris;
//   §6.4 status PO sebagai langkah, bukan label;
//   §6.5 bagian kosong tetap tampil dengan SATU kalimat penjelasan.
//
// Yang TIDAK dikarang: dokumen §6.3 meminta kalimat akibat per komponen risiko
// ("susut 4% setara 31 kg") yang sumbernya backend; payload belum punya kalimat
// itu, jadi drawer hanya menampilkan komponen rupiahnya dan menyebut sebabnya.
//
// Semua angka lewat `lib/detail-keputusan.ts` (murni, teruji). Komponen anak
// yang sudah ada dipakai ulang: ApprovalOverview, DecisionActions,
// RecommendationCard, DecisionChain, SupplierExclusionView, AgentTraceViewer.

import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

import Popup from "./Popup";
import ApprovalOverview from "./ApprovalOverview";
import DecisionActions from "./DecisionActions";
import DecisionChain from "./DecisionChain";
import RecommendationCard, { caseLabelOf } from "./RecommendationCard";
import StatusBadge from "./StatusBadge";
import { SupplierExclusionView } from "./SupplierExclusionPanel";
import AgentTraceViewer from "./AgentTraceViewer";
import { formatDateTime } from "../lib/datetime";
import { decisionHeadline } from "../lib/evidence";
import { shortId } from "../lib/agent-quality";
import { downloadDossier, downloadPoPdf } from "../lib/export";
import {
  alurKeputusan,
  jenisKeputusan,
  kg,
  perbandinganHarga,
  rupiah,
  tahapPo,
  tigaLapisBiaya,
} from "../lib/detail-keputusan";
import type { SupplierContext } from "../lib/supplier-exclusions";

// Dua hal berbeda: `Tampilan` = isi yang sedang dirender popup, `TampilanAwal`
// = pilihan yang ditawarkan kartu feed ("Rincian" / "Persetujuan"). Keduanya
// bukan tab di dalam popup (keputusan pemilik 28 Okt 2026).
type Tampilan = "rincian" | "jejak";
type TampilanAwal = "rincian" | "persetujuan";

/** Satu baris fakta; nilai kosong ditulis "—", bukan dikarang. */
function Fakta({ label, nilai }: { label: string; nilai: string | null }) {
  return (
    <div className="detail-fact">
      <dt>{label}</dt>
      <dd>{nilai && nilai !== "" ? nilai : "—"}</dd>
    </div>
  );
}

/**
 * Bagian yang bisa dilipat (`<details>`), dipakai untuk isi sekunder supaya
 * panel tidak menjadi gulungan 2.000 px. Kepala lipatan tetap menyebut
 * isinya secara ringkas, jadi menutup bukan berarti menyembunyikan.
 */
function Lipat({
  judul,
  catatan,
  lebarPenuh = false,
  terbuka = false,
  children,
}: {
  judul: string;
  catatan?: string;
  lebarPenuh?: boolean;
  terbuka?: boolean;
  children: ReactNode;
}) {
  return (
    <details className={`detail-fold${lebarPenuh ? " detail-sec--full" : ""}`} open={terbuka}>
      <summary className="detail-fold-head">
        <span className="detail-h">{judul}</span>
        {catatan ? <span className="detail-fold-note">{catatan}</span> : null}
        <span className="detail-fold-caret" aria-hidden="true" />
      </summary>
      <div className="detail-fold-body">{children}</div>
    </details>
  );
}

export default function DecisionDrawer({
  open,
  onClose,
  decision,
  summary,
  chain,
  traces,
  supplierContext,
  role,
  token,
  now,
  onSupplierCreated,
  onOpenFullPage,
  returnFocusRef,
  tampilanAwal = "rincian",
}: {
  open: boolean;
  onClose: () => void;
  decision: any | null;
  summary: any;
  chain: any[];
  traces: any[];
  supplierContext: SupplierContext | null;
  role: string;
  token: string | null;
  now: Date | null;
  onSupplierCreated?: (decisionId: string) => void;
  /** Pindah ke halaman "Decision & Evidence" untuk bukti kepatuhan lengkap. */
  onOpenFullPage?: (decisionId: string) => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  /**
   * Bagian yang tampil saat popup dibuka. Pemanggil yang memilih — dua tombol
   * di kartu feed ("Rincian" / "Persetujuan"), bukan tab di dalam popup.
   * `persetujuan` tetap memakai tampilan rincian, tetapi panel persetujuan di
   * dalamnya sudah terbuka dan digulir ke tampilan.
   */
  tampilanAwal?: TampilanAwal;
}) {
  const decisionId = decision?.decision_id ? String(decision.decision_id) : null;
  const jumlahJejak = Array.isArray(traces) ? traces.length : 0;
  const [tampilan, setTampilan] = useState<Tampilan>("rincian");
  // Panel persetujuan hanya membuka DIRINYA SENDIRI saat popup dibuka dari
  // tombol "Persetujuan" di kartu. Setelah pengguna berpindah tampilan, panel
  // itu tidak boleh terbuka lagi dengan sendirinya: ia akan menutupi bagian
  // yang justru sedang dibaca.
  const [panelLangsung, setPanelLangsung] = useState(tampilanAwal === "persetujuan");
  // Unduhan dokumen PO: endpoint PDF-nya hanya melayani keputusan yang sudah
  // disetujui/dieksekusi (`boleh_pdf` di backend), jadi tombolnya pun hanya
  // muncul pada keadaan itu — tombol yang pasti ditolak server lebih buruk
  // daripada tombol yang tidak ada.
  const [unduhPo, setUnduhPo] = useState<{ jalan: boolean; pesan: string | null }>({
    jalan: false,
    pesan: null,
  });
  const [unduh, setUnduh] = useState<{ jalan: boolean; pesan: string | null }>({
    jalan: false,
    pesan: null,
  });
  const aksiRef = useRef<HTMLElement | null>(null);

  // Keputusan lain atau panel dibuka ulang = mulai dari rincian (atau panel
  // persetujuan, bila itu yang dipilih di kartu). `open` wajib ada di
  // dependensi: menutup panel tidak melepas komponennya.
  useEffect(() => {
    setTampilan("rincian");
    setPanelLangsung(tampilanAwal === "persetujuan");
    setUnduh({ jalan: false, pesan: null });
    setUnduhPo({ jalan: false, pesan: null });
  }, [decisionId, open, tampilanAwal]);

  // Popup "Persetujuan" menaruh tombolnya tepat di bawah pita angka, jadi
  // gulungan selalu dimulai dari ATAS: menggulir ke seksi aksi justru
  // menyembunyikan angka yang menjelaskan keputusannya. Popup "Rincian" tidak
  // digulir sama sekali.
  useEffect(() => {
    if (!open) return;
    const badan = document.querySelector<HTMLElement>(".popup-keputusan .popup-body");
    if (badan) badan.scrollTop = 0;
  }, [open, decisionId, tampilanAwal]);

  if (!decision || !decisionId) return null;

  const jenis = jenisKeputusan(decision.decision_type ?? summary?.decision_type);
  const headline = decisionHeadline(decision, summary);
  const status = String(summary?.status ?? decision.status ?? "");
  const alur = alurKeputusan(decision, summary);
  const komersial = summary?.commercial_cost ?? decision.commercial_cost;
  const biaya = tigaLapisBiaya(komersial, decision.quantity_kg ?? summary?.quantity_kg);
  const banding = perbandinganHarga(decision.market_reference ?? summary?.market_reference, komersial);
  const po = tahapPo(summary?.purchase_order);
  const qty = kg(decision.quantity_kg ?? summary?.quantity_kg);
  const supplier =
    decision.supplier?.name ?? summary?.supplier?.name ?? decision.supplier_name ?? null;
  const asal = decision.source_location ?? summary?.source_location ?? null;
  const tujuan = decision.target_location ?? summary?.target_location ?? null;
  const kasus = caseLabelOf(decision) ?? caseLabelOf(summary);
  // Ringkasan approval untuk kepala lipatan: jumlah penyetuju vs syarat minimum,
  // supaya isi yang dilipat tetap "terbaca" tanpa harus dibuka.
  const jumlahSetuju = Array.isArray(summary?.approvals) ? summary.approvals.length : 0;
  const syaratSetuju = summary?.approval_requirement?.min_approvals ?? null;
  const ringkasApproval =
    syaratSetuju === null
      ? `${jumlahSetuju} penyetuju`
      : `${jumlahSetuju} dari ${syaratSetuju} disetujui`;

  async function unduhBukti() {
    if (!token) {
      setUnduh({ jalan: false, pesan: "Berkas bukti butuh sesi aktif." });
      return;
    }
    setUnduh({ jalan: true, pesan: null });
    try {
      const nama = await downloadDossier(decisionId!, token);
      setUnduh({ jalan: false, pesan: `Terunduh: ${nama}` });
    } catch {
      setUnduh({ jalan: false, pesan: "Gagal mengunduh berkas bukti." });
    }
  }

  async function unduhDokumenPo() {
    if (!token || !po.nomor) return;
    setUnduhPo({ jalan: true, pesan: null });
    try {
      const nama = await downloadPoPdf(po.nomor, token);
      setUnduhPo({ jalan: false, pesan: `Terunduh: ${nama}` });
    } catch {
      setUnduhPo({ jalan: false, pesan: "Gagal mengunduh dokumen PO." });
    }
  }

  // Label tautan kepala popup: saat rincian menawarkan jejak (hanya bila ada
  // jejak tercatat — tautan ke halaman kosong bukan tawaran), saat jejak
  // menawarkan jalan kembali.
  const labelTautan =
    tampilan === "jejak"
      ? "Kembali ke rincian"
      : jumlahJejak > 0
        ? `Jejak agen (${jumlahJejak})`
        : null;

  // Perpindahan rincian ↔ jejak lewat tautan tenang di kepala popup.
  function keJejak() {
    setPanelLangsung(false);
    setTampilan("jejak");
  }
  function keRincian() {
    setPanelLangsung(false);
    setTampilan("rincian");
  }

  /**
   * Dua popup, dua pekerjaan — susunan isinya sengaja TIDAK sama:
   *  - "rincian"     = popup baca  -> alur, angka, fakta, biaya, PO, bukti.
   *  - "persetujuan" = popup putus -> ringkas, siapa yang dibutuhkan, tombol,
   *                    akibatnya, baru konteks angka (dok 02 §7.1).
   * Kepala popup tetap sama supaya orang tidak merasa pindah aplikasi.
   */
  const modeAksi = tampilanAwal === "persetujuan" && tampilan === "rincian";
  // Sama dengan STATUS_BOLEH_PDF di backend; kalau backend menambah keadaan
  // lain, tombolnya tetap benar karena server yang memutuskan (403 → pesan).
  const bolehUnduhPo = ["approved", "executed"].includes(String(status ?? "").toLowerCase());
  const hargaPerKg = rupiah(komersial?.sdc_unit_price);

  /** Satu kalimat: apa yang terjadi sesudah tombol di panel aksi ditekan. */
  const akibatSetelah =
    jenis === "administratif"
      ? "Keputusan administratif dieksekusi lokal - tidak menerbitkan PO."
      : po.terbit
        ? `PO ${po.nomor} sudah terbit (${po.statusLabel}); tidak ada PO baru yang dibuat.`
        : "Setelah disetujui dan dieksekusi, PO terbit dengan harga terkirim sebagai harga satuan.";

  const pitaRingkas = (
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
  );

  const blokAlur = (
    <section className="detail-sec detail-sec--full detail-alur" aria-label="Alur keputusan">
      <ol className="detail-steps">
        {alur.steps.map((tahap) => (
          <li key={tahap.label} className={`detail-step detail-step--${tahap.state}`}>
            <span className="detail-step-dot" aria-hidden="true" />
            <span className="detail-step-label">{tahap.label}</span>
          </li>
        ))}
      </ol>
      {alur.buntu ? <span className="detail-deadend">{alur.buntu}</span> : null}
    </section>
  );

  const blokFakta = (
    <section className="detail-sec">
      <h4 className="detail-h">Fakta dasar</h4>
      <dl className="detail-facts">
        <Fakta label="Komoditas" nilai={decision.commodity ?? summary?.commodity ?? null} />
        <Fakta
          label={asal ? "Rute" : "Tujuan"}
          nilai={asal && tujuan ? `${asal} → ${tujuan}` : (tujuan ?? asal ?? null)}
        />
        <Fakta label="Jumlah" nilai={qty ? `${qty} kg` : null} />
        <Fakta label="Pemasok" nilai={supplier} />
        <Fakta label="Alasan" nilai={kasus} />
        <Fakta label="Berlaku sampai" nilai={formatDateTime(decision.expires_at) || null} />
      </dl>
    </section>
  );

  /* Dok 01 §4: keputusan administratif tidak merender bagian biaya sama sekali. */
  const blokBiaya =
    jenis !== "pembelian" ? null : (
      <section className="detail-sec">
        <h4 className="detail-h">Biaya, harga &amp; penerimaan</h4>
        {biaya.adaData ? (
          <>
            {biaya.total ? (
              <div className="detail-total">
                <div className="detail-total-teks">
                  <span className="detail-total-label">{biaya.total.label}</span>
                  <strong className="detail-total-nilai">
                    {biaya.total.nilai ?? "tidak tercatat"}
                  </strong>
                  {biaya.total.rumus ? (
                    <span className="detail-formula">{biaya.total.rumus}</span>
                  ) : null}
                </div>
                {banding ? <span className="detail-banding">{banding.kalimat}</span> : null}
              </div>
            ) : null}
            <dl className="detail-layers">
              {biaya.lapis.map((lapis) => (
                <div className="detail-layer" key={lapis.judul}>
                  <dt>{lapis.judul}</dt>
                  <dd>
                    <span className="detail-layer-value">{lapis.nilai ?? "tidak tercatat"}</span>
                    {lapis.rumus ? <span className="detail-formula">{lapis.rumus}</span> : null}
                  </dd>
                  {lapis.baris.length > 1 ? (
                    <dd className="detail-layer-rows">
                      {lapis.baris.map((baris) => (
                        <span key={baris.label} className="detail-layer-row">
                          <span>{baris.label}</span>
                          <span>{baris.nilai ?? "tidak tercatat"}</span>
                        </span>
                      ))}
                    </dd>
                  ) : null}
                </div>
              ))}
            </dl>
            {banding ? (
              <p className="detail-note">
                Harga acuan {banding.acuanPerKg}/kg (pihps_reference, kota tujuan).
              </p>
            ) : (
              <p className="detail-note">
                Perbandingan harga belum bisa dihitung: harga acuan di kota tujuan belum
                tercatat untuk komoditas ini.
              </p>
            )}
          </>
        ) : (
          <p className="detail-note">
            Belum tercatat pada keputusan ini: rincian biaya. Angkanya tidak ditampilkan sebagai
            nol, karena &quot;tidak tercatat&quot; dan &quot;nol rupiah&quot; dua keadaan berbeda.
          </p>
        )}
      </section>
    );

  const blokPo =
    jenis !== "pembelian" ? null : (
      <section className="detail-sec">
        <h4 className="detail-h">Pesanan pembelian</h4>
        <ol className="detail-po" aria-label="Tahap pesanan pembelian">
          {po.steps.map((tahap) => (
            <li key={tahap.label} className={`detail-po-step detail-po-step--${tahap.state}`}>
              <span className="detail-step-dot" aria-hidden="true" />
              <span>{tahap.label}</span>
            </li>
          ))}
        </ol>
        {po.terbit ? (
          <dl className="detail-facts">
            <Fakta label="Nomor PO" nilai={po.nomor} />
            <Fakta label="Status PO" nilai={po.statusLabel} />
            <Fakta label="Harga terkirim per kg" nilai={rupiah(komersial?.sdc_unit_price)} />
            <Fakta
              label="Diterbitkan"
              nilai={formatDateTime(summary?.purchase_order?.created_at) || null}
            />
          </dl>
        ) : (
          <p className="detail-note">PO baru terbit setelah usulan disetujui dan dieksekusi.</p>
        )}
        {po.terbit ? (
          <p className="detail-note">
            Harga satuan PO sama dengan harga terkirim (sudah memuat logistik, susut, risiko
            kesegaran, dan penalti keamanan) — bukan harga beli.
          </p>
        ) : null}
        {/* Dokumen PO baru boleh terbit setelah keputusan disetujui/dieksekusi
            (dok 01 §2 butir 5). Gerbangnya milik server (`boleh_pdf`); di sini
            hanya tidak menawarkan tombol yang pasti ditolak. */}
        {po.terbit && token && bolehUnduhPo ? (
          <div className="detail-export">
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void unduhDokumenPo()}
              disabled={unduhPo.jalan}
            >
              {unduhPo.jalan ? "Menyiapkan…" : "Unduh dokumen PO (PDF)"}
            </button>
            {unduhPo.pesan ? (
              <span className="detail-note" role="status">
                {unduhPo.pesan}
              </span>
            ) : null}
          </div>
        ) : null}
      </section>
    );

  const blokVerifier = summary?.verifier?.verdict ? (
    <section className="detail-sec detail-sec--full">
      <h4 className="detail-h">Catatan verifier</h4>
      <p className="detail-note">
        Verdict verifier: <strong>{verdictWord(summary.verifier.verdict)}</strong>
        {summary.verifier.verified_by ? ` · oleh ${summary.verifier.verified_by}` : ""}.
        {summary.verifier.verdict === "unavailable"
          ? " Verifier tidak memberi jawaban untuk keputusan ini."
          : ""}
      </p>
    </section>
  ) : null;

  const blokKewajiban = (terbuka: boolean) => (
    <Lipat judul="Kewajiban persetujuan" catatan={ringkasApproval} lebarPenuh terbuka={terbuka}>
      <ApprovalOverview summary={summary} role={role} now={now} />
    </Lipat>
  );

  const blokAksi = (utama: boolean) => (
    <section
      className={`detail-sec detail-sec--full detail-aksi${utama ? " detail-aksi--utama" : ""}`}
      ref={aksiRef}
    >
      {utama ? <h4 className="detail-h">Putuskan sekarang</h4> : null}
      <DecisionActions
        decisionId={decisionId}
        role={role}
        status={status}
        token={token}
        summary={summary}
        // Konfirmasi dirender di dalam panel ini, bukan jendela kedua di atasnya
        // (permintaan pemilik: "tidak ada popup dalam popup").
        tampil="panel"
        terbukaAwal={panelLangsung}
      />
      {utama ? <p className="detail-setelah">{akibatSetelah}</p> : null}
    </section>
  );

  const blokUsulan = (
    <section className="detail-sec detail-sec--full">
      <h4 className="detail-h">Usulan</h4>
      <div className="detail-usulan">
        <RecommendationCard
          decision={decision}
          mockSourced={status === "executed"}
          hint="Usulan yang menjadi dasar keputusan ini"
        />
      </div>
    </section>
  );

  const blokJejakIterasi =
    Array.isArray(chain) && chain.length > 0 ? (
      <Lipat judul="Jejak iterasi" catatan={`${chain.length} langkah`} lebarPenuh>
        <DecisionChain chain={chain} />
      </Lipat>
    ) : null;

  const blokPemasok = supplierContext ? (
    <section className="detail-sec">
      <h4 className="detail-h">Pemasok</h4>
      <SupplierExclusionView
        key={decisionId}
        context={supplierContext}
        role={role}
        // `SupplierExclusionView` menuntut token string + callback wajib;
        // panel ini boleh dibuka tanpa sesi tulis, jadi nilai kosongnya
        // diteruskan apa adanya (tanpa sesi ia tidak menawarkan aksi).
        token={token ?? ""}
        onCreated={onSupplierCreated ?? (() => {})}
      />
    </section>
  ) : null;

  const blokBukti = (
    <Lipat judul="Bukti & audit" catatan="berkas JSON · halaman lengkap" lebarPenuh>
      <p className="detail-note">
        Berkas bukti memuat rantai keputusan, evaluasi batch, dan tanda tangan integritas untuk
        keputusan ini.
      </p>
      <div className="detail-export">
        <button
          type="button"
          className="button button-secondary"
          onClick={() => void unduhBukti()}
          disabled={unduh.jalan}
        >
          {unduh.jalan ? "Menyiapkan…" : "Unduh bukti (JSON)"}
        </button>
        {onOpenFullPage ? (
          <button
            type="button"
            className="button button-secondary"
            onClick={() => onOpenFullPage(decisionId)}
          >
            Buka halaman lengkap
          </button>
        ) : null}
      </div>
      {unduh.pesan ? (
        <p className="detail-note" role="status">
          {unduh.pesan}
        </p>
      ) : null}
    </Lipat>
  );

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
          {/* Jejak agen dulu tombol di kartu feed. Sekarang tautan tenang di
              sini supaya kartu hanya menawarkan dua pekerjaan nyata (Rincian &
              Persetujuan) dan jejak tetap terjangkau satu klik. SATU elemen
              untuk kedua arah: mengganti label saja membuat fokus keyboard
              tidak hilang ke <body> saat pengguna berpindah tampilan. */}
          {labelTautan ? (
            <button
              type="button"
              className="detail-tautan"
              onClick={tampilan === "jejak" ? keRincian : keJejak}
            >
              {labelTautan}
            </button>
          ) : null}
          {/* Kasus sengaja tidak diulang di sini: ia sudah menjadi baris "Alasan"
              pada Fakta dasar, dan kepala popup cukup label + judul + status + id. */}
        </>
      }
    >
      {tampilan === "jejak" ? (
        <section className="detail-sec detail-sec--full detail-jejak" aria-label="Jejak agen">
          <div className="detail-jejak-kepala">
            <h4 className="detail-h">Jejak agen</h4>
            <span className="detail-fold-note">{jumlahJejak} langkah tercatat · waktu UTC</span>
          </div>
          <AgentTraceViewer steps={traces} decisionId={decisionId} now={now} />
        </section>
      ) : modeAksi ? (
        <>
          {pitaRingkas}
          {/* Tombol dulu, daftar penyetuju sesudahnya: pada popup putus, CTA
              utama tidak boleh berada di bawah gulungan layar. */}
          {blokAksi(true)}
          {blokKewajiban(true)}
          {blokVerifier}
          <Lipat
            judul="Konteks angka"
            catatan={`${qty ? `${qty} kg` : "jumlah belum tercatat"} · ${po.terbit ? `PO ${po.nomor}` : "PO belum terbit"}`}
            lebarPenuh
          >
            <div className="detail-konteks">
              {blokFakta}
              {blokBiaya}
              {blokPo}
            </div>
          </Lipat>
          {blokBukti}
        </>
      ) : (
        <>
          {blokAlur}
          {pitaRingkas}
          {blokFakta}
          {blokBiaya}
          {blokPo}
          {blokVerifier}
          {blokKewajiban(false)}
          {blokAksi(false)}
          {blokUsulan}
          {blokJejakIterasi}
          {blokPemasok}
          {blokBukti}
        </>
      )}
    </Popup>
  );
}

/** Verdict verifier dalam bahasa Indonesia (jangan cetak istilah mentah). */
function verdictWord(verdict: unknown): string {
  switch (String(verdict)) {
    case "consistent":
      return "konsisten";
    case "flagged":
      return "ditandai";
    case "unavailable":
      return "belum tersedia";
    default:
      return String(verdict ?? "—");
  }
}
