"use client";

import { evidenceRowsFromDossier, type ComplianceDossier } from "../lib/evidence";
// Satuan diterjemahkan di satu tempat (WS-C): "percent" → "persen".
import { unitLabel } from "./KPIDashboard";
import styles from "./ComplianceEvidencePanel.module.css";

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
          PASS {counts.PASS ?? 0} · FAIL {counts.FAIL ?? 0} · NEEDS_VERIFICATION {counts.NEEDS_VERIFICATION ?? 0}
        </span>
      </div>
      {rows.length === 0 ? <p>Belum ada bukti pengukuran untuk keputusan ini.</p> : (
        <ul className={styles.list}>
          {rows.map((row) => (
            <li className={styles.item} key={row.id} data-testid="compliance-evidence-row">
              <div><strong>{row.evidenceType}</strong> <span className={`${styles.status} ${styles[row.status.toLowerCase() as keyof typeof styles] ?? ""}`}>{row.status}</span></div>
              <div>Hasil: {row.reading === null ? "Belum diukur" : String(row.reading)}{unitLabel(row.unit) ? ` ${unitLabel(row.unit)}` : ""}</div>
              <small className={styles.small}>
                Sumber: {row.source == null ? "Tidak tersedia" : String(row.source)} · Waktu: {row.recordedAt ?? "Tidak tersedia"}
                {row.rule ? ` · Rule: ${String(row.rule)}` : ""}
                {row.consistency === false ? " · Konsistensi: tidak konsisten" : row.consistency === true ? " · Konsistensi: konsisten" : " · Konsistensi: Tidak tersedia"}
              </small>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
