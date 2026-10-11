// RecommendationCard — item feed (design.md §3.2), disusun mengikuti kartu
// keputusan acuan (`components/decisions/recommendation-card.tsx`):
// judul + baris meta (jumlah · SDC · waktu) di kiri, badge status bertumpuk di
// kanan, lalu baris chip + keterangan singkat. Tepi kiri berwarna tetap dipakai
// sebagai penanda tingkat (danger/warning/netral) — seperan dengan badge urgensi
// di acuan, tetapi terbaca bahkan saat kartu dipindai cepat.
//
// Data yang dipakai HANYA yang ada di envelope /decisions (envelope itu tidak
// membawa komoditas/lokasi). Tidak ada baris yang dikarang: bila suatu nilai
// tidak ada, ia ditulis apa adanya ("—" dari formatKg/formatIDR).

import StatusBadge from "./StatusBadge";
import { cardEdge } from "../lib/recommendations";
import { ClockIcon } from "./NavIcon";
import { formatIDR } from "../lib/auth";
import { formatDateTime } from "../lib/datetime";
import { formatKg } from "../lib/overview-format";

const CASE_LABELS: Record<string, string> = {
  "rejection-loop-kuota": "Kasus: Rejection Loop (Kuota)",
  "shortage-darurat": "Kasus: Shortage Darurat",
  "supplier-janggal": "Kasus: Supplier Janggal",
  "gangguan-logistik": "Kasus: Gangguan Logistik",
};

// Judul dari decision_type — kosakatanya mengikuti schema backend. Diekspor
// karena dipakai dua tempat (kartu rekomendasi + halaman "Hari Ini") dan dua
// peta label akan cepat menyimpang.
export const DECISION_TYPE_LABELS: Record<string, string> = {
  regional_balance: "Alokasi regional direkomendasikan",
  safety_disruption: "Pengalihan pasokan (gangguan keamanan)",
  price_anomaly: "Penyesuaian harga direkomendasikan",
  surplus_redistribution: "Redistribusi surplus direkomendasikan",
  supplier_exclusion: "Usulan pengecualian pemasok",
};

// Catatan yang isinya hanya kata penanda: bukan narasi, jangan dicetak.
const PLACEHOLDER_NOTES = new Set(["unavailable", "n/a", "na", "-", "none", "null", "undefined"]);


export default function RecommendationCard({
  decision,
  mockSourced = false,
}: {
  decision: any;
  mockSourced?: boolean;
}) {
  const typeLabel = DECISION_TYPE_LABELS[decision.decision_type] ?? "Rekomendasi baru";
  const caseLabel = decision.demo_case
    ? (CASE_LABELS[decision.demo_case] ??
      `Kasus: ${decision.demo_case.replace(/-/g, " ")}`)
    : null;
  const edge = cardEdge(decision);
  // Alasan penolakan / catatan verifier = satu-satunya narasi yang benar-benar
  // ada di data; kalau dua-duanya kosong, tidak ada paragraf yang ditampilkan.
  // Backend kadang mengisi catatan dengan kata penanda ("unavailable") — itu
  // bukan narasi dan tidak boleh muncul sebagai paragraf di kartu.
  const rawNarrative = decision.rejection_reason || decision.verifier_note || null;
  const narrative =
    typeof rawNarrative === "string" && PLACEHOLDER_NOTES.has(rawNarrative.trim().toLowerCase())
      ? null
      : rawNarrative;

  return (
    <article className={`card recommendation-card rec-edge ${edge}`}>
      <div className="rec-head">
        <div className="rec-head-text">
          <p className="rec-title">
            {typeLabel}
            {decision.iteration && decision.iteration > 1 && (
              <span className="badge version-badge">v{decision.iteration}</span>
            )}
          </p>
          <p className="rec-meta-line">
            <span className="rec-qty">{formatKg(decision.quantity_kg)}</span>
            <span className="rec-sep" aria-hidden="true">·</span>
            <span>SDC {formatIDR(decision.safe_delivered_cost)}</span>
            <span className="rec-sep" aria-hidden="true">·</span>
            <span className="rec-time">
              <ClockIcon />
              {formatDateTime(decision.created_at)}
            </span>
          </p>
        </div>
        <div className="rec-badges">
          <StatusBadge status={decision.status} />
          <span
            className={`badge ${decision.valid ? "badge-neutral" : "badge-expired"}`}
          >
            {!decision.valid && <ClockIcon />}
            {decision.valid
              ? `berlaku ${decision.seconds_remaining ?? 0} dtk`
              : "kedaluwarsa"}
          </span>
        </div>
      </div>

      <div className="rec-foot">
        {caseLabel && <span className="badge rec-case">{caseLabel}</span>}
        {mockSourced && <span className="badge mock-badge">Data Simulasi</span>}
        <span className="rec-hint" aria-hidden="true">
          Klik untuk rincian &amp; jejak agen
        </span>
      </div>

      {narrative && <p className="rec-narrative">{narrative}</p>}
    </article>
  );
}
