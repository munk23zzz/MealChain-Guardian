// RecommendationCard — item feed (design.md §3.2), disusun mengikuti kartu
// keputusan acuan (`components/decisions/recommendation-card.tsx`):
// Judul + baris meta (komoditas · jumlah · SDC · waktu) di kiri, badge status
// bertumpuk di kanan. Tepi kiri berwarna tetap dipakai
// sebagai penanda tingkat (danger/warning/netral) — seperan dengan badge urgensi
// di acuan, tetapi terbaca bahkan saat kartu dipindai cepat.
//
// Data yang dipakai HANYA yang ada di envelope /decisions (termasuk
// `commodity_name`, yang sejak 29 Okt 2026 dicetak sebagai label barang).
// Envelope itu tidak membawa lokasi. Tidak ada baris yang dikarang: bila suatu
// nilai tidak ada, ia ditulis apa adanya ("—" dari formatKg/formatIDR).

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
  // Demo 2026-10-23: kasus sengaja tinggal di jendela 24 jam supaya operator
  // punya satu keputusan berbukti lengkap untuk disetujui saat demo.
  "bukti-hari-ini": "Kasus: Alokasi Bandung–Jakarta",
};

// Judul dari decision_type — kosakatanya mengikuti schema backend. Diekspor
// karena dipakai dua tempat (kartu rekomendasi + halaman "Hari Ini") dan dua
// peta label akan cepat menyimpang.
export const DECISION_TYPE_LABELS: Record<string, string> = {
  // 24 Okt 2026: "Alokasi regional" tidak menjawab pertanyaan pertama pengguna
  // ("ini pengiriman dari pemasok atau dari SPPG lain?"). Jenis ini MEMANG dua-
  // duanya: menutup kekurangan satu SPPG dengan pasokan pemasok ATAU surplus
  // SPPG lain. Karena itu namanya menyebut tindakannya (penyeimbangan), dan
  // kartu menambahkan baris pengirim yang eksplisit.
  regional_balance: "Penyeimbangan pasokan regional",
  safety_disruption: "Ganti sumber pasokan (gangguan keamanan)",
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

// Catatan: baris pengirim ("Dikirim pemasok X ke Y") yang dulu dirender kartu
// feed DIHAPUS 28 Okt 2026 saat kartu diringkas (permintaan pemilik: kartu
// tinggal judul + meta + status). Pengirim tetap terbaca di Decision & Evidence
// (panel konteks pemasok) — jangan menghidupkan kembali salinannya di sini.


// Ajakan pada kartu. Hanya berlaku di FEED, karena di sana seluruh kartu
// dibungkus <button> yang membuka halaman Decision & Evidence. Di halaman bukti
// kartu ini dirender tanpa pembungkus, jadi teks ajakannya jadi janji kosong
// (terukur: kursor auto, tak ada induk yang bisa diklik, klik tidak mengubah
// apa pun) — karena itu pemanggil di sana mengirim `hint={null}`.
export const CARD_HINT = "Klik untuk rincian & jejak agen";

/**
 * Badge "kasus demo" dari `decision.demo_case` — SATU sumber untuk kepala
 * halaman Decision & Evidence (dan pencarian feed, `lib/decision-feed.ts`).
 * 28 Okt 2026: badge ini tidak lagi dicetak di kartu feed — pemilik meminta
 * kartu rekomendasi diringkas (judul + meta + status saja).
 */
export function caseLabelOf(decision: any): string | null {
  if (!decision?.demo_case) return null;
  return CASE_LABELS[decision.demo_case] ?? `Kasus: ${String(decision.demo_case).replace(/-/g, " ")}`;
}

export default function RecommendationCard({
  decision,
  mockSourced = false,
  hint = CARD_HINT,
  onBuka,
  tampilPersetujuan = true,
}: {
  decision: any;
  mockSourced?: boolean;
  /** Teks ajakan; null/"" = tidak ditampilkan (kartu tidak bisa diklik). */
  hint?: string | null;
  /**
   * Bila diisi, ajakan teks diganti SATU tombol "Tinjau" (permintaan pemilik
   * 28 Okt 2026: dua tombol "Rincian"/"Persetujuan" digabung). `tampilanAwal`
   * yang dikirim ke popup ikut `tampilPersetujuan`: kartu yang boleh disetujui
   * dibuka dengan panel persetujuan terbuka, sisanya dibuka di rincian —
   * peran pengawas dan keputusan selesai tidak ditawari tindakan yang pasti
   * ditolak server (dok 02 §7.5).
   */
  onBuka?: (tampilan: "rincian" | "persetujuan", pemicu: HTMLElement | null) => void;
  tampilPersetujuan?: boolean;
}) {
  const typeLabel = DECISION_TYPE_LABELS[decision.decision_type] ?? "Rekomendasi baru";
  // Komoditas ("barang apa yang direkomendasikan") ADA di payload /decisions
  // sebagai `commodity_name`, tetapi dulu tidak pernah dicetak: kartu hanya
  // menampilkan kg dan rupiah, sehingga pembaca harus membuka popup untuk tahu
  // barangnya. Bila field tidak ada, label tidak muncul (tidak dikarang "—").
  const komoditas =
    typeof decision.commodity_name === "string" && decision.commodity_name.trim()
      ? decision.commodity_name.trim()
      : null;
  const edge = cardEdge(decision);
  // Narasi kartu feed = alasan penolakan saja. `verifier_note` TIDAK dipakai:
  // isinya verdict mentah backend ("consistent", "flagged") yang muncul sebagai
  // satu kata Inggris tak bertuan di daftar (temuan 28 Okt 2026). Verdict itu
  // tetap terbaca lengkap di Decision & Evidence. Kata penanda
  // ("unavailable"/"n/a") juga bukan narasi dan tidak pernah dicetak.
  const rawReason = decision.rejection_reason;
  const narrative =
    typeof rawReason === "string" &&
    rawReason.trim() !== "" &&
    !PLACEHOLDER_NOTES.has(rawReason.trim().toLowerCase())
      ? rawReason
      : null;

  return (
    <article className={`card recommendation-card rec-edge ${edge}`}>
      <div className="rec-head">
        {/* Tahap 3 (30 Okt 2026): judul kartu adalah HEADING, bukan paragraf.
            Pembaca layar bisa melompat antar kartu dengan tombol heading;
            sebelumnya daftar 10 kartu hanya bisa ditelusuri berurutan. Urutan
            tingkatannya h1 (PageHeader) → h2 (daerah daftar, sr-only) → h3. */}
        <h3 className="rec-title">
          {typeLabel}
          {decision.iteration && decision.iteration > 1 && (
            <span className="badge version-badge">v{decision.iteration}</span>
          )}
        </h3>
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

      {/* Satu baris informasi + ajakan: kg · SDC · waktu di kiri, ajakan di kanan.
          Dulu ajakan punya barisnya sendiri sehingga ada pita kosong di antara
          keduanya (pemilik 28 Okt 2026: "hapus space-nya supaya lebih compact"). */}
      <div className="rec-foot">
        <p className="rec-meta-line">
          {komoditas && (
            <>
              <span className="rec-komoditas">{komoditas}</span>
              <span className="rec-sep" aria-hidden="true">·</span>
            </>
          )}
          <span className="rec-qty">{formatKg(decision.quantity_kg)}</span>
          <span className="rec-sep" aria-hidden="true">·</span>
          {/* 29 Okt 2026: "biaya aman", bukan "SDC". Singkatan internal (Safe
              Delivered Cost) berderet dengan kg dan jam di satu baris, tanpa
              jalan bagi pembaca untuk tahu artinya. Dipendekkan dari "biaya aman
              terkirim" karena baris ini diulang di 10 kartu; istilah panjangnya
              tetap dipakai di Decision & Evidence. */}
          <span>biaya aman {formatIDR(decision.safe_delivered_cost)}</span>
          <span className="rec-sep" aria-hidden="true">·</span>
          <span className="rec-time">
            <ClockIcon />
            {formatDateTime(decision.created_at)}
          </span>
        </p>
        {mockSourced && <span className="badge mock-badge">Data Simulasi</span>}
        {onBuka ? (
          <span className="rec-act">
            {/* SATU tombol (koreksi pemilik 28 Okt 2026: "tombol rincian dan
                persetujuan jadikan 1 saja"). Popup yang dibuka sudah memuat
                rincian DAN panel persetujuan, jadi dua tombol hanya memaksa
                pengguna memilih lebih dulu tanpa menambah kemampuan. Untuk
                kartu yang boleh disetujui, popup dibuka langsung dengan panel
                persetujuan terbuka; kartu lain dibuka di rincian. */}
            {/* 29 Okt 2026: keterangan yang dulu berdiri sebagai paragraf dua
                baris di atas daftar sekarang menempel di tombolnya sebagai
                `title`. */}
            <button
              type="button"
              className="rec-act-btn rec-act-btn--utama"
              aria-label={`Tinjau: ${typeLabel}`}
              title="Buka rincian, bukti, dan panel persetujuan. Versi lengkapnya ada di halaman Decision & Evidence."
              onClick={(event) =>
                onBuka(tampilPersetujuan ? "persetujuan" : "rincian", event.currentTarget)
              }
            >
              Tinjau
            </button>
          </span>
        ) : hint ? (
          <span className="rec-hint" aria-hidden="true">
            {hint}
          </span>
        ) : null}
      </div>

      {narrative && <p className="rec-narrative">{narrative}</p>}
    </article>
  );
}
