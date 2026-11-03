// ApprovalModal — approval adalah friksi yang disengaja (design.md §1.3):
// ringkasan WAJIB tampil sebelum tombol approve. Tidak ada approve-all.
// S4-04: isi modal = read model kanonik dari GET /decisions/{id}/
// approval-summary — UI TIDAK menghitung requirement/verdict sendiri;
// can_execute & blocking_reasons murni keputusan server; field yang
// hilang tampil "unavailable", bukan default palsu (plan §S4-04).

import type { ReactNode } from "react";
import { formatIDR } from "../lib/auth";
import {
  executionTargetLabel,
  humanizeBlocker,
  roleList,
  safetyLabel,
  statusLabel,
} from "../lib/bahasa";
import { batchGateView } from "../lib/safety-gate";

function Show({ value }: { value: any }) {
  // Semua nilai dari server ditampilkan apa adanya; null → unavailable.
  return <>{value === null || value === undefined ? "belum tercatat" : String(value)}</>;
}

// Angka ditampilkan gaya Indonesia (koma desimal) untuk konsistensi UI.
function fmtNum(value: any): string {
  if (value === null || value === undefined) return "unavailable";
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("id-ID") : String(value);
}

/** Satu baris fakta: label (dt) di kiri, nilai (dd) di kanan. */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="approval-fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** Ikon peringatan SVG — bukan emoji, supaya bentuknya sama di semua sistem. */
function BlockerIcon() {
  return (
    <svg
      className="approval-blocker-icon"
      width="14"
      height="14"
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M8 1.6 15 14H1L8 1.6Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M8 6.2v3.4M8 11.6v.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function ApprovalModal({
  summary,
  onConfirm,
  dalamPanel = false,
  onCancel,
  showActions = true,
  busy = false,
}: {
  summary: any;
  onConfirm?: () => void;
  /** Panel inline di popup: tidak perlu tombol "Batal" kedua. */
  dalamPanel?: boolean;
  onCancel?: () => void;
  /** false → tanpa tombol Setuju (mis. bgn_monitor, atau status `rejected`). */
  showActions?: boolean;
  /** true → aksi sedang berjalan: tombol dikunci, label berubah. */
  busy?: boolean;
}) {
  if (!summary) {
    return (
      <p className="empty-state">
        Tidak ada ringkasan keputusan — approval massal tidak tersedia.
      </p>
    );
  }
  const req = summary.approval_requirement ?? {};
  const state = summary.approval_state ?? {};
  const safety = summary.safety ?? {};
  const verdict = summary.verifier?.verdict ?? null;
  // MG/phase-04 poin 7: `blocking_reasons` kini membawa KODE stabil
  // (`safety_pending`, `quarantined`, `temperature_evidence_incomplete`, …).
  // Menampilkannya mentah membuat layar berbicara bahasa API. `batchGateView`
  // menerjemahkan kode → kalimat + langkah berikutnya, dan peta itu SATU untuk
  // popup, ringkasan ini, serta papan Keamanan Pangan.
  const gate = batchGateView(summary);
  // S4-05 regression (rehearsal 2026-10-08): tombol Setuju di-gate
  // can_approve (approve masih sah), BUKAN can_execute — can_execute
  // selalu false sebelum approval terpenuhi → deadlock approval.
  const canApprove = summary.can_approve === true;
  // Keputusan owner 17 Okt: `approved_by_me` datang dari server (baris approval
  // user yang sedang login). Tanpa ini, kepala SPPG menekan "Setuju" pada
  // keputusan yang approval-nya sudah tercatat sejak seed → 409
  // "approval sudah tercatat" yang terbaca seperti tombol rusak.
  const alreadyApproved = summary.approved_by_me === true;
  // `can_execute` dulu dihitung di sini lalu TIDAK pernah dipakai, sementara
  // tombol Eksekusi di ApprovalMenu tetap ditawarkan dan klik-nya berakhir 409.
  // Pagar eksekusi kini di komponen yang memegang tombolnya
  // (components/ApprovalMenu.tsx), memakai field yang sama dari read model ini.
  const administrative = ["supplier_exclusion", "supplier_exclusion_restoration"].includes(summary.decision_type);
  const governance = summary.supplier_governance;
  // Ringkasan ini dibaca sebelum orang menekan tombol, jadi isinya disusun
  // empat bagian tetap: apa yang diputuskan, apa hasil pemeriksaannya, siapa
  // yang harus setuju, dan apa yang akan terjadi. Semua nilai mentah backend
  // (uuid, kode peran, `MOCK`, detik) diterjemahkan lebih dulu.
  const peranWajib = roleList((req.required_roles ?? []).flat());
  const peranBelum = roleList((state.missing ?? []).flat());
  // Satu peran bisa muncul lebih dari sekali (grup syarat berbeda); di layar
  // pengulangan itu terbaca seperti dua orang berbeda.
  const peranBelumUnik = Array.from(new Set(peranBelum));
  // Nada kotak penahan: merah hanya untuk alasan yang FINAL atau kegagalan.
  // "Persetujuan belum lengkap" adalah keadaan normal yang sedang berjalan —
  // mengecatnya merah membuat penyetuju mengira sistemnya bermasalah.
  // Tanda kurung dibuang dulu: kode server "approval belum memenuhi requirement
  // (missing/rejected)" memuat kata "rejected" padahal artinya BELUM lengkap,
  // bukan ditolak.
  // Peran yang ditunggu hanya relevan bila ANTIREANNYA persetujuan. Kalau
  // keputusan tertahan karena safety, daftar peran di bawahnya cuma bising.
  const tungguPeran = gate.reasons.some((alasan: string) =>
    /approval belum memenuhi requirement/i.test(alasan)
  );
  const nadaPenahan = gate.reasons.some((alasan: string) =>
    /ditolak|kedaluwarsa|expired|gagal|fail|quarantin|tidak aman/i.test(
      alasan.replace(/\(.*?\)/g, "")
    )
  )
    ? "danger"
    : "warn";
  const sudahTercatat = Array.isArray(state.approved_roles) ? state.approved_roles.length : 0;
  const butuh = Number(req.min_approvals ?? peranWajib.length) || peranWajib.length;
  const sisaDetik = Number(summary.expiry?.seconds_remaining ?? NaN);
  const berlaku = !summary.expiry?.valid
    ? "Sudah kedaluwarsa"
    : Number.isFinite(sisaDetik)
      ? `Masih ${durasiManusia(sisaDetik)}`
      : "Belum tercatat";
  const jalurEksekusi = administrative
    ? "Tindakan administratif lokal — tidak menerbitkan PO"
    : summary.execution_target
      ? `${executionTargetLabel(summary.execution_target)} — PO simulasi, bukan PO SAP sungguhan`
      : "Belum tercatat";
  return (
    // Sejak 14 Okt 2026 komponen ini SELALU hidup di dalam Popup (yang memegang
    // role="dialog" + aria-modal). Root-nya karena itu sebuah <section>: dialog
    // bersarang membuat pembaca layar mengumumkan dua konteks modal sekaligus.
    <section className="approval-modal" aria-label="Ringkasan approval">
      <header className="approval-modal-head">
        <div className="approval-modal-heading">
          <p className="approval-modal-eyebrow">Ringkasan bukti</p>
          <h3>Konfirmasi persetujuan</h3>
        </div>
        <p className="approval-modal-id">
          #{idPendek(summary.decision_id)} · versi {summary.iteration ?? 1}
        </p>
      </header>

      {/* Empat bagian disusun 2×2 (`.approval-isi-grid`) supaya penyetuju bisa
          memindai Isi/Pemeriksaan/Persetujuan/Setelah disetujui tanpa
          menggulir satu kolom panjang. Isi tiap bagian tidak berubah. */}
      <div className="approval-isi-grid">
      {/* 1. Apa yang diputuskan */}
      <section className="approval-bagian">
        <h4 className="approval-bagian-h">Isi keputusan</h4>
        <dl className="approval-grid">
          {administrative ? (
            <>
              <Fact label="Jenis">
                {summary.decision_type === "supplier_exclusion_restoration"
                  ? "Pemulihan pemasok"
                  : "Pengecualian pemasok"}
              </Fact>
              <Fact label="Pemasok">
                <Show value={summary.supplier?.name} />
              </Fact>
              <Fact label="SPPG">
                <Show value={summary.target_location} />
              </Fact>
              <Fact label="Alasan">
                <Show value={governance?.reason} />
              </Fact>
              <Fact label="Berkas bukti">
                {(governance?.evidence_refs ?? [])
                  .map((ref: { type: string; id: string }) => `${ref.type}: ${ref.id}`)
                  .join(", ") || "belum tersedia"}
              </Fact>
              <Fact label="Masa berlaku">
                Aktif sampai pemulihan terbukti lewat persetujuan baru; batch yang gagal
                pemeriksaan tetap diblokir.
              </Fact>
            </>
          ) : (
            <>
              <Fact
                label={summary.decision_type === "supplier_procurement" ? "Pemasok → SPPG" : "Alokasi"}
              >
                {/* Pengadaan: asal = pemasok (source_location memang null). */}
                <Show
                  value={
                    summary.decision_type === "supplier_procurement"
                      ? summary.supplier?.name ?? null
                      : summary.source_location
                  }
                />{" "}
                → <Show value={summary.target_location} />
              </Fact>
              <Fact label="Komoditas">
                <Show value={summary.commodity} />{" "}
                <span className="approval-fact-note">· {fmtNum(summary.quantity_kg)} kg</span>
              </Fact>
              <Fact label="Pemasok">
                <Show value={summary.supplier?.name ?? null} />
                {summary.material_number ? (
                  <span className="approval-fact-note"> · kode {summary.material_number}</span>
                ) : null}
              </Fact>
              <Fact label="Total biaya">{formatIDR(summary.safe_delivered_cost)}</Fact>
            </>
          )}
        </dl>
      </section>

      {/* 2. Hasil pemeriksaan */}
      <section className="approval-bagian">
        <h4 className="approval-bagian-h">Pemeriksaan</h4>
        <dl className="approval-grid">
          <Fact label="Status">
            <Show value={statusLabel(summary.status)} />
          </Fact>
          <Fact label="Keamanan batch sumber">
            <Show value={safetyLabel(safety.worst_status)} />
            {safety.blocked ? " — dikecualikan, gagal pemeriksaan" : ""}
          </Fact>
          {/* 29 Okt 2026: baris verdict hanya dicetak bila verdict-nya berbicara.
              "Konsisten" adalah keadaan normal setiap keputusan yang lolos
              verifier, jadi ia mengulang hal yang sama di setiap panel dan
              mendorong "Masa berlaku" + tombol Setuju ke bawah. Temuan
              ("Ditandai perlu diperiksa") dan "Belum tersedia" tetap dicetak —
              itu yang mengubah keputusan penyetuju. */}
          {verdict !== "consistent" ? (
            <Fact label="Hasil verifier">
              {verdictManusia(verdict)}
              {summary.verifier?.verified_by ? (
                <span className="approval-fact-note"> · oleh agen verifikator</span>
              ) : null}
            </Fact>
          ) : null}
          <Fact label="Masa berlaku">{berlaku}</Fact>
        </dl>
      </section>

      {/* 3. Siapa yang harus setuju */}
      <section className="approval-bagian">
        <h4 className="approval-bagian-h">Persetujuan</h4>
        <dl className="approval-grid">
          <Fact label="Dibutuhkan">{butuh} persetujuan</Fact>
          <Fact label="Peran">{peranWajib.join(" + ") || "belum tercatat"}</Fact>
          <Fact label="Tercatat">
            {sudahTercatat} dari {butuh}
            {/* Daftar peran hanya diulang bila sebagian sudah setuju; saat masih
                nol, baris "Peran" di atas sudah menyebut semuanya. */}
            {peranBelum.length > 0 && sudahTercatat > 0 ? (
              <span className="approval-fact-note"> · menunggu {peranBelum.join(", ")}</span>
            ) : null}
          </Fact>
        </dl>
      </section>

      {/* 4. Apa yang akan terjadi */}
      <section className="approval-bagian">
        <h4 className="approval-bagian-h">Setelah disetujui</h4>
        <dl className="approval-grid">
          <Fact label="Jalur">{jalurEksekusi}</Fact>
        </dl>
      </section>

      </div>{/* /approval-isi-grid */}

      {gate.reasons.length > 0 && (
        // 29 Okt 2026 (laporan pemilik): "Belum bisa dieksekusi" + satu kalimat
        // panjang yang menumpuk nama peran di dalam tanda baca terbaca padat.
        // Susunannya kini: ikon + judul (satu baris), sebab sebagai daftar
        // pendek, lalu peran yang ditunggu sebagai chip yang bisa dipindai —
        // bukan terselip di tengah kalimat.
        <div className="approval-modal-blockers" data-tone={nadaPenahan} role="note">
          <BlockerIcon />
          <div className="approval-modal-blockers-isi">
            <p className="approval-modal-blockers-title">Belum bisa dieksekusi</p>
            <ul className="approval-modal-blockers-list">
              {gate.reasons.map((reason: string) => (
                <li key={reason}>{alasanTertahan(reason)}</li>
              ))}
            </ul>
            {tungguPeran && peranBelumUnik.length > 0 ? (
              <p className="approval-modal-blockers-peran">
                <span>Menunggu</span>
                {peranBelumUnik.map((peran) => (
                  <span className="blocker-chip" key={peran}>
                    {peran}
                  </span>
                ))}
              </p>
            ) : null}
            {gate.nextStep ? (
              <p className="approval-modal-blockers-next">
                <strong>Langkah berikutnya:</strong> {gate.nextStep}
              </p>
            ) : null}
          </div>
        </div>
      )}

      {showActions && (
        <div className="approval-modal-actions">
          <button
            type="button"
            className="button"
            onClick={onConfirm}
            disabled={
              !canApprove || alreadyApproved || (administrative && !governance) || busy
            }
            aria-busy={busy}
            title={
              alreadyApproved
                ? "Persetujuan Anda sudah tercatat — menunggu peran lain"
                : canApprove
                  ? undefined
                  : "Approve tidak tersedia: keputusan kedaluwarsa, ditolak, atau belum diverifikasi"
            }
          >
            {/* 29 Okt 2026: tanda centang hanya saat tombol memang bisa ditekan —
                ikon pada tombol mati terbaca sebagai "sudah disetujui". */}
            {alreadyApproved || busy || !canApprove ? null : (
              <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
                <path
                  d="M3 8.5l3.2 3.2L13 5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
            <span>
              {alreadyApproved
                ? "Sudah Anda setujui"
                : busy
                  ? "Memproses…"
                  : "Setuju"}
            </span>
          </button>
          {alreadyApproved && (
            <p className="approval-modal-note" role="status">
              Persetujuan Anda sudah tercatat.
              {peranBelumUnik.length
                ? ` Keputusan ini menunggu ${daftarDan(peranBelumUnik)}.`
                : " Menunggu peran lain yang masih kurang."}
            </p>
          )}
          {/* Di panel inline tidak ada tombol batal kedua: menutup panel adalah
              "Tutup panel" di kepala panel, bukan keputusan. Dulu "Batal" di
              sini melakukan hal yang sama sehingga tiga kontrol menutup hal
              yang sama. */}
          {dalamPanel ? null : (
            <button
              type="button"
              className="button-secondary button"
              onClick={onCancel}
              disabled={busy}
            >
              Batal
            </button>
          )}
        </div>
      )}
    </section>
  );
}

/** UUID panjang di kepala ringkasan hanya menambah bising: 8 aksara cukup. */
function idPendek(value: unknown): string {
  const teks = String(value ?? "").trim();
  return teks ? teks.slice(0, 8) : "belum tercatat";
}

/** 6996 detik -> "1 jam 56 menit"; angka mentah tidak pernah tampil. */
function durasiManusia(detik: number): string {
  if (!Number.isFinite(detik) || detik <= 0) return "kurang dari satu menit";
  const menitTotal = Math.floor(detik / 60);
  const hari = Math.floor(menitTotal / 1440);
  const jam = Math.floor((menitTotal % 1440) / 60);
  const menit = menitTotal % 60;
  const bagian: string[] = [];
  if (hari > 0) bagian.push(`${hari} hari`);
  if (jam > 0) bagian.push(`${jam} jam`);
  if (menit > 0 && hari === 0) bagian.push(`${menit} menit`);
  return bagian.length > 0 ? bagian.join(" ") + " lagi" : "kurang dari satu menit lagi";
}

/** Verdict verifier: konsisten / ditandai / belum tersedia. */
function verdictManusia(verdict: unknown): string {
  switch (String(verdict ?? "")) {
    case "consistent":
      return "Konsisten";
    case "flagged":
      return "Ditandai perlu diperiksa";
    case "unavailable":
      return "Belum tersedia";
    default:
      return verdict ? String(verdict) : "Belum tersedia";
  }
}

/**
 * Kalimat server "approval belum memenuhi requirement (missing/rejected)" itu
 * kode yang kebetulan berbentuk kalimat. Diterjemahkan di sini, bukan di peta
 * bersama, supaya permukaan lain yang sudah punya kalimatnya sendiri tidak
 * ikut berubah.
 */
/** Daftar nama gaya Indonesia: "A", "A dan B", "A, B, dan C". */
function daftarDan(nama: string[]): string {
  const bersih = nama.filter(Boolean);
  if (bersih.length === 0) return "";
  if (bersih.length === 1) return bersih[0];
  if (bersih.length === 2) return `${bersih[0]} dan ${bersih[1]}`;
  return `${bersih.slice(0, -1).join(", ")}, dan ${bersih[bersih.length - 1]}`;
}

/**
 * Sebab tertahan → kalimat penyetuju.
 *
 * 29 Okt 2026 (laporan pemilik): kalimat lama berbunyi "Persetujuan belum
 * lengkap — masih ada peran yang belum menyetujui." — dua klausa dengan tanda
 * pisah, dan klausa kedua tidak menambah apa pun padahal server SUDAH mengirim
 * daftar peran yang kurang. Sekarang daftar itu disebut namanya.
 *
 * Untuk sebab lain, peta bersama `humanizeBlocker` yang dipakai (satu kosakata
 * dengan dialog aksi), bukan terjemahan lokal yang hanya mengenal dua kode —
 * sebelumnya "decision expired" tampil sebagai "Decision expired".
 */
function alasanTertahan(reason: string): string {
  if (/approval belum memenuhi requirement/i.test(reason)) {
    // Nama peran TIDAK lagi diselipkan di kalimat ini; ia tampil sebagai chip
    // di barisnya sendiri (lihat `.approval-modal-blockers-peran`).
    return "Persetujuan belum lengkap.";
  }
  const manusia = humanizeBlocker(reason);
  const kalimat = manusia ?? reason;
  return kalimat.charAt(0).toUpperCase() + kalimat.slice(1);
}
