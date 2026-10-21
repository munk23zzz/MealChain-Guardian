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

// Label masa berlaku. Angka hanya dicetak kalau memang berupa angka yang sah:
// `seconds_remaining ?? 0` dulu menampilkan "berlaku 0 dtk" saat backend tidak
// mengirim sisa waktu — angka karangan, bertentangan dengan aturan anti-fabricate.
// Satuan detik tidak dipakai di kartu: "600 dtk" sulit dibaca. Nilai tetap
// dihitung dari detik, lalu dibulatkan ke bawah ke menit/jam/hari supaya
// pengguna tidak dibuat merasa punya waktu lebih panjang dari yang sebenarnya.
function validityDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  if (total < 60) return "kurang dari 1 menit";
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} menit`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const restMinutes = minutes % 60;
    return restMinutes ? `${hours} jam ${restMinutes} menit` : `${hours} jam`;
  }
  const days = Math.floor(hours / 24);
  const restHours = hours % 24;
  return restHours ? `${days} hari ${restHours} jam` : `${days} hari`;
}

function validityBadge(decision: { valid?: boolean; seconds_remaining?: unknown }): string {
  // "Lewat tenggat" — bukan "kedaluwarsa": yang dibaca pengguna adalah bahwa
  // TINDAKAN tidak mungkin lagi, dan kalimatnya sama dengan lonceng top bar
  // ("menunggu tindakan"/"lewat tenggat") supaya satu kosakata di seluruh app.
  if (!decision.valid) return "Lewat tenggat";
  const sisa = decision.seconds_remaining;
  return typeof sisa === "number" && Number.isFinite(sisa)
    ? `berlaku ${validityDuration(sisa)}`
    : "berlaku";
}

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
  // Restorasi pengecualian adalah keputusan administratif terpisah; tanpa label
  // ini halaman Hari Ini jatuh ke fallback dan menampilkan slug mentah
  // "supplier exclusion restoration" ke layar pengguna.
  supplier_exclusion_restoration: "Pemulihan status pemasok",
  // Demo Control 2026-10-19: pengadaan dari pemasok yang memasok SPPG itu —
  // jangan diberi label "Alokasi regional" yang artinya pemindahan antar SPPG.
  supplier_procurement: "Pengadaan dari pemasok",
};

// Catatan yang isinya hanya kata penanda: bukan narasi, jangan dicetak.
const PLACEHOLDER_NOTES = new Set(["unavailable", "n/a", "na", "-", "none", "null", "undefined"]);


// Ajakan pada kartu. Hanya berlaku di FEED, karena di sana seluruh kartu
// dibungkus <button> yang membuka halaman Decision & Evidence. Di halaman bukti
// kartu ini dirender tanpa pembungkus, jadi teks ajakannya jadi janji kosong
// (terukur: kursor auto, tak ada induk yang bisa diklik, klik tidak mengubah
// apa pun) — karena itu pemanggil di sana mengirim `hint={null}`.
export const CARD_HINT = "Klik untuk rincian & jejak agen";

/**
 * Badge "kasus demo" dari `decision.demo_case` — SATU sumber untuk kartu feed DAN
 * kepala halaman Decision & Evidence (dua peta label cepat menyimpang).
 */
export function caseLabelOf(decision: any): string | null {
  if (!decision?.demo_case) return null;
  return CASE_LABELS[decision.demo_case] ?? `Kasus: ${String(decision.demo_case).replace(/-/g, " ")}`;
}

export default function RecommendationCard({
  decision,
  mockSourced = false,
  hint = CARD_HINT,
}: {
  decision: any;
  mockSourced?: boolean;
  /** Teks ajakan; null/"" = tidak ditampilkan (kartu tidak bisa diklik). */
  hint?: string | null;
}) {
  const typeLabel = DECISION_TYPE_LABELS[decision.decision_type] ?? "Rekomendasi baru";
  const caseLabel = caseLabelOf(decision);
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
            {validityBadge(decision)}
          </span>
        </div>
      </div>

      <div className="rec-foot">
        {caseLabel && <span className="badge rec-case">{caseLabel}</span>}
        {mockSourced && <span className="badge mock-badge">Data Simulasi</span>}
        {hint ? (
          <span className="rec-hint" aria-hidden="true">
            {hint}
          </span>
        ) : null}
      </div>

      {narrative && <p className="rec-narrative">{narrative}</p>}
    </article>
  );
}
