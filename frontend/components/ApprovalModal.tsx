// ApprovalModal — approval adalah friksi yang disengaja (design.md §1.3):
// ringkasan WAJIB tampil sebelum tombol approve. Tidak ada approve-all.
// S4-04: isi modal = read model kanonik dari GET /decisions/{id}/
// approval-summary — UI TIDAK menghitung requirement/verdict sendiri;
// can_execute & blocking_reasons murni keputusan server; field yang
// hilang tampil "unavailable", bukan default palsu (plan §S4-04).

import type { ReactNode } from "react";
import { formatIDR } from "../lib/auth";
import { executionTargetLabel, roleList, safetyLabel, statusLabel } from "../lib/bahasa";
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
  onCancel,
  showActions = true,
  busy = false,
}: {
  summary: any;
  onConfirm?: () => void;
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
  const missingRoles = (state.missing ?? [])
    .flat()
    .filter((r: string, i: number, a: string[]) => a.indexOf(r) === i)
    .join(" + ");
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
  const nextRole = missingRoles ? missingRoles : "";
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
  const sudahTercatat = Array.isArray(state.approved_roles) ? state.approved_roles.length : 0;
  const butuh = Number(req.min_approvals ?? peranWajib.length) || peranWajib.length;
  const sisaDetik = Number(summary.expiry?.seconds_remaining ?? NaN);
  const berlaku = !summary.expiry?.valid
    ? "Sudah kedaluwarsa"
    : Number.isFinite(sisaDetik)
      ? `Masih ${durasiManusia(sisaDetik)}`
      : "Belum tercatat";
  const jalurEksekusi = administrative
    ? "Tindakan administratif lokal - tidak menerbitkan PO"
    : summary.execution_target
      ? `${executionTargetLabel(summary.execution_target)} - PO simulasi, bukan PO SAP sungguhan`
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
          <Fact label="Hasil verifier">
            {verdictManusia(verdict)}
            {summary.verifier?.verified_by ? (
              <span className="approval-fact-note"> · oleh agen verifier</span>
            ) : null}
          </Fact>
          <Fact label="Masa berlaku">{berlaku}</Fact>
        </dl>
      </section>

      {/* 3. Siapa yang harus setuju */}
      <section className="approval-bagian">
        <h4 className="approval-bagian-h">Persetujuan</h4>
        <dl className="approval-grid">
          <Fact label="Dibutuhkan">{butuh} persetujuan</Fact>
          <Fact label="Peran">{peranWajib.join(" + ") || "belum tercatat"}</Fact>
          <Fact label="Sudah tercatat">
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

      {gate.reasons.length > 0 && (
        <div className="approval-modal-blockers">
          <p className="approval-modal-blockers-title">Tertahan</p>
          <ul>
            {gate.reasons.map((reason: string) => (
              <li key={reason}>
                <BlockerIcon />
                <span>{alasanTertahan(reason)}</span>
              </li>
            ))}
          </ul>
          {/* MG/phase-04 poin 7: "tertahan" saja tidak cukup — penyetuju harus
              tahu langkah berikutnya (uji keamanan, selesaikan verifikasi,
              lepas karantina). Satu kalimat, dari peta kode yang sama. */}
          {gate.nextStep ? (
            <p className="approval-modal-blockers-next">
              <strong>Langkah berikutnya:</strong> {gate.nextStep}
            </p>
          ) : null}
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
            title={
              alreadyApproved
                ? "Anda sudah menyetujui keputusan ini — menunggu approval role lain"
                : canApprove
                  ? undefined
                  : "Approve tidak tersedia: keputusan kedaluwarsa, ditolak, atau belum diverifikasi"
            }
          >
            {alreadyApproved
              ? "Sudah Anda setujui"
              : busy
                ? "Memproses…"
                : "Setuju"}
          </button>
          {alreadyApproved && (
            <p className="approval-modal-note" role="status">
              Approval Anda sudah tercatat. Keputusan ini menunggu role lain
              {nextRole ? ` (${nextRole})` : ""} — bukan tombol yang rusak.
            </p>
          )}
          <button
            type="button"
            className="button-secondary button"
            onClick={onCancel}
            disabled={busy}
          >
            Batal
          </button>
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
function alasanTertahan(reason: string): string {
  if (/approval belum memenuhi requirement/i.test(reason)) {
    return "Persetujuan belum lengkap - masih ada peran yang belum menyetujui.";
  }
  if (/approval.*rejected/i.test(reason)) {
    return "Persetujuan pernah ditolak - keputusan ini tidak bisa dieksekusi.";
  }
  return reason.charAt(0).toUpperCase() + reason.slice(1);
}
