"use client";

import { evidenceRowsFromDossier, type ComplianceDossier } from "../lib/evidence";
import { safetyLabel } from "../lib/bahasa";
import { formatDateTime } from "../lib/datetime";
// Satuan diterjemahkan di satu tempat (WS-C): "percent" → "persen".
import { unitLabel } from "./KPIDashboard";
import styles from "./ComplianceEvidencePanel.module.css";

/** Nama bukti dalam bahasa manusia — kunci backend tidak dicetak mentah. */
const JENIS_BUKTI: Record<string, string> = {
  human_inspection: "Pemeriksaan manusia",
  temperature: "Suhu",
  gps: "Lokasi GPS",
  sap_purchase_order: "Pesanan pembelian (SAP)",
  sap_goods_receipt: "Penerimaan barang (SAP)",
  market_price: "Harga pasar",
};

export default function ComplianceEvidencePanel({ dossier }: { dossier: ComplianceDossier }) {
  const rows = evidenceRowsFromDossier(dossier);
  const counts = rows.reduce<Record<string, number>>((acc, row) => {
    acc[row.status] = (acc[row.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <section className={styles.panel} data-testid="compliance-evidence-panel">
      <div className={styles.header}>
        <strong>Bukti kepatuhan tersimpan</strong>
        <span data-testid="compliance-counts">
          {safetyLabel("PASS")} {counts.PASS ?? 0} · {safetyLabel("FAIL")} {counts.FAIL ?? 0} ·{" "}
          {safetyLabel("NEEDS_VERIFICATION")} {counts.NEEDS_VERIFICATION ?? 0}
        </span>
      </div>
      {rows.length === 0 ? <p>Belum ada bukti pengukuran untuk keputusan ini.</p> : (
        <ul className={styles.list}>
          {rows.map((row) => (
            <li className={styles.item} key={row.id} data-testid="compliance-evidence-row">
              {/* Kunci backend tidak dicetak mentah (audit 29 Okt 2026):
                  "human_inspection"/"NEEDS_VERIFICATION" di layar terbaca
                  sebagai bocoran istilah, bukan keterangan bukti. */}
              <div>
                <strong>{JENIS_BUKTI[row.evidenceType] ?? row.evidenceType.replace(/_/g, " ")}</strong>{" "}
                <span className={`${styles.status} ${styles[row.status.toLowerCase() as keyof typeof styles] ?? ""}`}>
                  {safetyLabel(row.status)}
                </span>
              </div>
              <div>Hasil: {row.reading === null ? "Belum diukur" : String(row.reading)}{unitLabel(row.unit) ? ` ${unitLabel(row.unit)}` : ""}</div>
              <small className={styles.small}>
                Sumber: {row.source == null ? "Tidak tersedia" : String(row.source)} · Waktu:{" "}
                {row.recordedAt ? formatDateTime(row.recordedAt) : "Tidak tersedia"}
                {row.rule ? ` · Aturan: ${String(row.rule)}` : ""}
                {row.consistency === false ? " · Konsistensi: tidak konsisten" : row.consistency === true ? " · Konsistensi: konsisten" : " · Konsistensi: Tidak tersedia"}
              </small>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
