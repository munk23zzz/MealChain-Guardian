"use client";

/**
 * IntegrityPanel (P1-P3, paket 1-6, keputusan Roy 2026-10-09).
 *
 * Panel integritas kripto yang JUJUR:
 * - Merkle ledger: verifikasi rantai hash dari genesis (append-only).
 * - Dossier: alamat konten (ala-CID offline) + tanda tangan ECDSA
 *   secp256k1 per keputusan; state unsigned ditampilkan apa adanya.
 * Tanpa angka karangan — semua dari endpoint backend deterministik.
 */

import { useCallback, useEffect, useState } from "react";

import { fetchDossier, verifyLedger } from "../lib/api";
import ComplianceEvidencePanel from "./ComplianceEvidencePanel";
import { dossierToCsv, dossierToJson, downloadText } from "../lib/export";
import type { ComplianceDossier } from "../lib/evidence";

type LedgerResult = {
  valid: boolean;
  blocks: number;
  head?: string | null;
  broken_at?: number | null;
  reason?: string | null;
};

type DossierResult = ComplianceDossier & {
  decision_id: string;
  content_address: string;
  signature: { state: string; algorithm?: string; reason?: string };
  verify: boolean | null;
};

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
    try {
      const lv = (await verifyLedger(token)) as LedgerResult;
      setLedger(lv);
      if (decisionId) {
        const dz = (await fetchDossier(decisionId, token)) as DossierResult;
        setDossier(dz);
      } else {
        setDossier(null);
      }
    } catch (e: any) {
      setError(e?.message ?? "gagal memuat integritas");
    } finally {
      setBusy(false);
    }
  }, [token, decisionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <section className="integrity-panel card" data-testid="integrity-panel">
      <h3>Integritas Bukti</h3>

    <div className="integrity-ledger" data-testid="ledger-status">
      <strong>Merkle Ledger (append-only)</strong>
        {ledger === null && <p>memeriksa rantai…</p>}
        {ledger !== null && (
          <p>
            {ledger.valid ? "✅ Rantai valid" : "❌ RANTAI PUTUS"} ·{" "}
            {ledger.blocks} block
            {ledger.valid && ledger.head ? (
              <span title={ledger.head}>
                {" "}
                · head {ledger.head.slice(0, 12)}…
              </span>
            ) : null}
            {!ledger.valid && ledger.broken_at ? (
              <span>
                {" "}
                · putus di height {ledger.broken_at} ({ledger.reason})
              </span>
            ) : null}
          </p>
        )}
        <button
          type="button"
          data-testid="btn-verify-ledger"
          onClick={() => void refresh()}
          disabled={busy}
        >
          {busy ? "memeriksa…" : "Verifikasi ulang"}
        </button>
      </div>

      <div className="integrity-dossier" data-testid="dossier-status">
        <strong>Dossier Keputusan</strong>
        {!decisionId && <p>pilih keputusan untuk melihat dossier</p>}
        {decisionId && dossier === null && <p>memuat dossier…</p>}
        {dossier !== null && (
          <>
            <dl>
              <dt>Alamat konten</dt>
              <dd data-testid="dossier-address">
                {dossier.content_address.slice(0, 24)}…
              </dd>
              <dt>Tanda tangan</dt>
              <dd data-testid="dossier-signature">
                {dossier.signature.state === "signed"
                  ? `✅ ${dossier.signature.algorithm} · verifikasi ${
                      dossier.verify ? "BERHASIL" : "GAGAL"
                    }`
                  : `⚠️ unsigned — ${dossier.signature.reason ?? "kunci tidak diset"}`}
              </dd>
            </dl>
            <ComplianceEvidencePanel dossier={dossier} />
            <div className="integrity-export-actions" data-testid="dossier-export-actions">
              <button type="button" onClick={() => downloadText(`dossier-${dossier.decision_id}.json`, dossierToJson(dossier), "application/json;charset=utf-8")}>Export JSON dossier</button>
              <button type="button" onClick={() => downloadText(`evidence-${dossier.decision_id}.csv`, dossierToCsv(dossier), "text/csv;charset=utf-8")}>Export CSV bukti</button>
            </div>
          </>
        )}
      </div>

      {error && <p className="integrity-error">{error}</p>}
    </section>
  );
}
