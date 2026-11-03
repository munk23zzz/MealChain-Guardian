"use client";

/**
 * IntegrityPanel (P1-P3, paket 1-6, keputusan Roy 2026-10-09).
 *
 * Panel integritas kripto yang JUJUR:
 * - Merkle ledger: verifikasi rantai hash dari genesis (append-only).
 * - Dossier: alamat konten (ala-CID offline) + tanda tangan ECDSA
 *   secp256k1 per keputusan; state unsigned ditampilkan apa adanya.
 * Tanpa angka karangan — semua dari endpoint backend deterministik.
 *
 * Tampilan (19 Okt 2026, permintaan pemilik: "desain bagian integrasi bukti …
 * pakai palet yang cocok dengan tema terang"): panel ini DULU satu-satunya
 * permukaan gelap (#0F172A) di tema terang. Kini tiap kotak bukti memakai nada
 * yang menyampaikan keadaannya sendiri — teal = tersegel/valid, amber = belum
 * ditandatangani, rose = putus/gagal, netral = belum ada data — dan lencananya
 * selalu bertitik + berteks, jadi keadaan tidak pernah bergantung pada warna
 * saja. Token `--trust-*` dipertahankan (nama sama, nilai terang) supaya aturan
 * lama di globals.css dan tes lama tetap berlaku.
 */

import { useCallback, useEffect, useState } from "react";

import { fetchDossier, verifyLedger } from "../lib/api";
import ComplianceEvidencePanel from "./ComplianceEvidencePanel";
import { dossierToCsv, dossierToJson, downloadText } from "../lib/export";
import type { ComplianceDossier } from "../lib/evidence";
import { anchorNote, coverageNote } from "../lib/ledger";

type LedgerResult = {
  valid: boolean;
  blocks: number;
  head?: string | null;
  broken_at?: number | null;
  reason?: string | null;
  generation?: number;
  entity_blocks?: number;
  linked_blocks?: number;
  orphan_blocks?: number;
  archived_blocks?: number;
  linked_ratio?: number | null;
  coverage_warning?: string | null;
  /** Checkpoint di luar database (Fase 11 MG, butir 2). */
  anchor?: {
    configured?: boolean;
    match?: boolean | null;
    reason?: string | null;
    height?: number | null;
    payload_hash?: string | null;
    created_at?: string | null;
  } | null;
};

type DossierResult = ComplianceDossier & {
  decision_id: string;
  content_address: string;
  signature: { state: string; algorithm?: string; reason?: string };
  verify: boolean | null;
};

/** Nada kotak bukti — sama dengan sistem tint app (ok/warn/danger/netral). */
export type ProofTone = "ok" | "warn" | "danger" | "plain";

/** Keadaan rantai Merkle: nada aman HANYA bila backend menyatakan valid. */
export function ledgerState(ledger: LedgerResult | null): { tone: ProofTone; label: string } {
  if (ledger === null) return { tone: "plain", label: "memeriksa rantai…" };
  return ledger.valid
    ? { tone: "ok", label: "Rantai valid" }
    : { tone: "danger", label: "Rantai putus" };
}

/** Keadaan dossier: tanda tangan yang TIDAK cocok tidak pernah diberi nada aman. */
export function dossierState(
  decisionId: string | null,
  dossier: DossierResult | null
): { tone: ProofTone; label: string } {
  if (!decisionId) return { tone: "plain", label: "belum dipilih" };
  if (dossier === null) return { tone: "plain", label: "memuat dossier…" };
  if (dossier.signature.state !== "signed") return { tone: "warn", label: "belum ditandatangani" };
  return dossier.verify
    ? { tone: "ok", label: "tersegel & terverifikasi" }
    : { tone: "danger", label: "segel tidak cocok" };
}

/**
 * Satu baris status integritas (Tahap 6 redesign, 29 Okt 2026).
 *
 * Sebelumnya dua kartu besar (rantai global + dossier) memakan hampir satu layar
 * sebelum pembaca tahu keadaan sesungguhnya. Ringkasan ini menyebut KEADAAN lebih
 * dulu — SAH / PERINGATAN / GAGAL — lalu angkanya (blok, blok yatim) dan keadaan
 * dossier. Rinciannya tidak hilang: seluruh kartu lama pindah ke balik lipatan.
 *
 * Urutan nada tidak boleh "aman" lebih cepat dari bukti:
 * - rantai putus            → GAGAL
 * - checkpoint berbeda      → GAGAL (riwayat bisa ditulis ulang di luar DB)
 * - blok yatim / cakupan    → PERINGATAN (rantai valid ≠ bukti lengkap)
 * - segel tidak cocok       → GAGAL
 * - belum ditandatangani    → PERINGATAN
 */
export function ringkasIntegritas(
  ledger: LedgerResult | null,
  dossier: DossierResult | null,
  decisionId: string | null
): { tone: ProofTone; label: string; detail: string } {
  const berkas = dossierState(decisionId, dossier);

  if (ledger === null) {
    return { tone: "plain", label: "Memeriksa…", detail: "rantai audit dan dossier sedang dimuat." };
  }

  const yatim = ledger.orphan_blocks ?? 0;
  const angka = (n: number) => new Intl.NumberFormat("id-ID").format(n);
  const bagian = [
    `${angka(ledger.blocks)} blok`,
    `${angka(yatim)} blok yatim`,
    `dossier ${berkas.label}`,
  ];
  const detail = bagian.join(" · ");

  if (!ledger.valid) return { tone: "danger", label: "GAGAL", detail };
  if (ledger.anchor?.match === false) return { tone: "danger", label: "GAGAL", detail };
  if (berkas.tone === "danger") return { tone: "danger", label: "GAGAL", detail };

  const cakupanKurang = Boolean(ledger.coverage_warning) || yatim > 0;
  if (cakupanKurang || berkas.tone === "warn") {
    return { tone: "warn", label: "PERINGATAN", detail };
  }

  return { tone: "ok", label: "SAH", detail };
}

export default function IntegrityPanel({
  token,
  decisionId,
}: {
  token: string;
  decisionId: string | null;
}) {
  const [ledger, setLedger] = useState<LedgerResult | null>(null);
  const [dossier, setDossier] = useState<DossierResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    // Dua endpoint dipisah: dulu satu `try` membungkus keduanya, sehingga
    // kegagalan ledger membuat dossier tidak pernah dimuat DAN sebaliknya —
    // panel lalu selamanya menampilkan "memeriksa rantai…"/"memuat dossier…".
    const gagal: string[] = [];
    try {
      const lv = (await verifyLedger(token)) as LedgerResult;
      setLedger(lv);
    } catch (e: any) {
      gagal.push(`rantai audit: ${e?.message ?? "gagal dimuat"}`);
    }
    if (decisionId) {
      try {
        const dz = (await fetchDossier(decisionId, token)) as DossierResult;
        setDossier(dz);
      } catch (e: any) {
        gagal.push(`dossier: ${e?.message ?? "gagal dimuat"}`);
      }
    } else {
      setDossier(null);
    }
    if (gagal.length) setError(gagal.join(" · "));
    setBusy(false);
  }, [token, decisionId]);

  // Keputusan berganti → dossier lama HARUS dibuang sebelum fetch baru selesai,
  // kalau tidak alamat konten & tanda tangan keputusan sebelumnya tampil di
  // bawah judul keputusan yang baru.
  useEffect(() => {
    setDossier(null);
  }, [decisionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const rantai = ledgerState(ledger);
  const berkas = dossierState(decisionId, dossier);
  const ringkas = ringkasIntegritas(ledger, dossier, decisionId);
  // Audit A4: rantai valid ≠ bukti lengkap — blok yatim tetap disebut.
  const sisaBukti = ledger === null ? null : coverageNote(ledger);
  // Fase 11 butir 2: rantai valid di dalam DB ≠ riwayat tidak ditulis ulang.
  const catatanAnchor = anchorNote(ledger);
  const anchorBeda = ledger?.anchor?.match === false;

  return (
    <section className="integrity-panel card" data-testid="integrity-panel">
      {/* Satu baris status (Tahap 6 redesign, 29 Okt 2026): keadaan dulu —
          SAH/PERINGATAN/GAGAL — lalu blok, blok yatim, dan keadaan dossier.
          Kalimat penjelas teknis ("Hash append-only, alamat konten, dan tanda
          tangan — dibaca dari API") dibuang: pembaca tidak perlu tahu jalurnya
          untuk memutuskan. */}
      <header className="integrity-head">
        <h3>Integritas Bukti</h3>
        <p
          className={`integrity-status integrity-tone-${ringkas.tone}`}
          role="status"
          aria-atomic="true"
          data-testid="integrity-summary"
          data-tone={ringkas.tone}
        >
          <span className="integrity-status-dot" aria-hidden="true" />
          <strong>{ringkas.label}</strong>
          <span className="integrity-status-detail">{ringkas.detail}</span>
        </p>
      </header>

      {/* Rincian tidak dibuang, hanya dilipat: dua kartu bukti + daftar
          pengukuran + ekspor tetap utuh di dalam sini. */}
      <details className="integrity-fold" data-testid="integrity-detail">
        <summary>Buka rincian integritas</summary>

      {/* Bukti kriptografis (rantai Merkle + alamat konten + tanda tangan ECDSA)
          kini bertinta TERANG seperti sisa konsol: warna di sini membawa
          keadaan, bukan suasana. Daftar pengukuran (ComplianceEvidencePanel)
          tetap netral di bawahnya — tabel pengukuran lebih enak dibaca tanpa
          tint. */}
      <div className="integrity-trust">
    <div
      className="integrity-proof integrity-ledger"
      data-tone={rantai.tone}
      data-testid="ledger-status"
    >
      <div className="integrity-proof-head">
        <span className="integrity-proof-titles">
          {/* Label menyebut cakupannya (audit 29 Okt 2026): angka di kartu ini
              milik rantai GLOBAL, bukan bukti keputusan yang sedang dipilih.
              Tanpa kata "global", pembaca wajar mengira 3128 blok itu milik
              satu keputusan. */}
          <span className="integrity-proof-name">Merkle Ledger (rantai global)</span>
          <span className="integrity-proof-kind">append-only</span>
        </span>
        <span className={`integrity-chip integrity-chip-${rantai.tone}`}>{rantai.label}</span>
      </div>
        {ledger !== null && (
          <dl className="integrity-meta">
            <div>
              <dt>Blok</dt>
              <dd className="integrity-num">{ledger.blocks}</dd>
            </div>
            {ledger.valid && ledger.head ? (
              <div>
                <dt>Head</dt>
                <dd className="integrity-hash" title={ledger.head}>
                  {ledger.head.slice(0, 12)}…
                </dd>
              </div>
            ) : null}
            {!ledger.valid && ledger.broken_at ? (
              <div>
                <dt>Putus di</dt>
                <dd className="integrity-num">blok {ledger.broken_at}</dd>
              </div>
            ) : null}
            {ledger.anchor && ledger.anchor.match !== null ? (
              <div>
                <dt>Checkpoint</dt>
                <dd
                  className="integrity-num"
                  data-testid="ledger-anchor-match"
                  data-match={ledger.anchor.match ? "true" : "false"}
                >
                  {ledger.anchor.match ? "cocok" : "berbeda"}
                  {typeof ledger.anchor.height === "number"
                    ? ` · blok ${ledger.anchor.height}`
                    : ""}
                </dd>
              </div>
            ) : null}
          </dl>
        )}
        {ledger !== null && !ledger.valid && ledger.reason ? (
          <p className="integrity-reason">{ledger.reason}</p>
        ) : null}
        {catatanAnchor ? (
          <p
            className={anchorBeda ? "integrity-warning" : "integrity-reason"}
            data-testid="ledger-anchor"
            data-tone={anchorBeda ? "danger" : "plain"}
          >
            {catatanAnchor}
          </p>
        ) : null}
        {sisaBukti ? (
          <p className="integrity-warning" data-testid="ledger-coverage">
            {sisaBukti}
          </p>
        ) : null}
        <button
          type="button"
          className="integrity-refresh"
          data-testid="btn-verify-ledger"
          onClick={() => void refresh()}
          disabled={busy}
        >
          {busy ? "memeriksa…" : "Verifikasi ulang"}
        </button>
      </div>

      <div
        className="integrity-proof integrity-dossier"
        data-tone={berkas.tone}
        data-testid="dossier-status"
      >
        <div className="integrity-proof-head">
          <span className="integrity-proof-titles">
            <span className="integrity-proof-name">Dossier keputusan ini</span>
            <span className="integrity-proof-kind">alamat konten + tanda tangan</span>
          </span>
          <span className={`integrity-chip integrity-chip-${berkas.tone}`}>{berkas.label}</span>
        </div>
        {!decisionId && <p className="integrity-hint">Pilih keputusan untuk melihat dossier.</p>}
        {decisionId && dossier === null && <p className="integrity-hint">Memuat dossier…</p>}
        {dossier !== null && (
          <dl className="integrity-meta">
            <div>
              <dt>Alamat konten</dt>
              <dd className="integrity-hash" data-testid="dossier-address" title={dossier.content_address}>
                {dossier.content_address.slice(0, 24)}…
              </dd>
            </div>
            <div>
              <dt>Tanda tangan</dt>
              <dd data-testid="dossier-signature">
                {dossier.signature.state === "signed"
                  ? `${dossier.signature.algorithm} · verifikasi ${
                      dossier.verify ? "BERHASIL" : "GAGAL"
                    }`
                  : `unsigned — ${dossier.signature.reason ?? "kunci tidak diset"}`}
              </dd>
            </div>
          </dl>
        )}
      </div>
      </div>

      {/* Dua blok di bawah sengaja TIDAK ikut gelap: daftar pengukuran dan
          tombol ekspor adalah dokumen kerja, bukan bukti kripto. Keduanya
          dilipat (F4) karena panjang, bukan karena kosong — ringkasan tombol
          menyebut isinya, dan tidak ada data yang dibuang. */}
      {dossier !== null && (
        <details className="integrity-more" data-testid="integrity-features">
          <summary>Rincian pengukuran &amp; ekspor bukti</summary>
          <ComplianceEvidencePanel dossier={dossier} />
          <div className="integrity-export-actions" data-testid="dossier-export-actions">
            <button type="button" onClick={() => downloadText(`dossier-${dossier.decision_id}.json`, dossierToJson(dossier), "application/json;charset=utf-8")}>Export JSON dossier</button>
            <button type="button" onClick={() => downloadText(`evidence-${dossier.decision_id}.csv`, dossierToCsv(dossier), "text/csv;charset=utf-8")}>Export CSV bukti</button>
          </div>
        </details>
      )}

      </details>

      {error && <p className="integrity-error">{error}</p>}
    </section>
  );
}
