"use client";

// EvidenceEmptyState — keadaan "belum ada keputusan terbaca" di halaman
// Decision & Evidence.
//
// Tahap 8 (29 Okt 2026) memindahkan blok ini keluar dari cabang lama
// `DecisionEvidence` sebelum cabang itu dihapus. Isinya BUKAN karangan baru:
// tiga penyebab yang dibedakan (sedang memuat · baris diganti "Muat Demo" ·
// tautan menunjuk keputusan di luar cakupan peran) sudah ada di halaman versi
// lama dan harus tetap ada — menghapusnya berarti tautan bersama yang tidak
// terbuka lagi berhenti menjelaskan sebabnya.
//
// Perubahan yang disengaja: rujukan "kanan atas" diganti "pemilih di atas",
// karena pemilih keputusan kini berada di dalam kartu kepala halaman ini.
import type { TodayDecision } from "../lib/today";
import { shortId } from "../lib/agent-quality";

export default function EvidenceEmptyState({
  loading,
  selectedId,
  diganti,
  suggestions,
  onSelect,
  onOpenRecommendations,
}: {
  loading: boolean;
  selectedId: string | null;
  diganti: boolean;
  suggestions: TodayDecision[];
  onSelect: (decisionId: string) => void;
  onOpenRecommendations?: () => void;
}) {
  if (loading) {
    return (
      <article className="card evidence-empty" role="status" data-testid="memuat-keputusan">
        <h2>Memuat keputusan…</h2>
        <p className="evidence-note">
          Daftar keputusan sedang diambil dari API. Kalau halaman ini dibuka lewat
          tautan bersama, keputusan yang dituju ditampilkan begitu daftarnya tiba.
        </p>
      </article>
    );
  }

  return (
    <article className="card evidence-empty" data-testid="belum-pilih-keputusan">
      {/* Tautan yang dibagikan bisa menunjuk keputusan di luar cakupan peran
          penerima — katakan itu, jangan berpura-pura tidak ada yang dipilih. */}
      <h2>
        {diganti
          ? "Keputusan ini sudah diganti oleh Muat Demo"
          : selectedId
            ? "Keputusan itu tidak ada di cakupan akun ini"
            : "Belum ada keputusan dipilih"}
      </h2>
      <p className="evidence-note">
        {diganti
          ? 'Baris keputusan yang dituju tautan sudah tidak ada — "Muat Demo" mengganti baris operasional (batch, keputusan, pesanan). Pilih keputusan terbaru di pemilih di atas; data yang tampil setelah ini berasal dari dataset baru.'
          : selectedId
            ? `Tautan menunjuk keputusan #${shortId(String(selectedId))}, tetapi keputusan itu tidak ada di daftar yang boleh dilihat peran ini — peran & lokasi membatasi daftar. Pilih keputusan lain di pemilih di atas, atau minta tautan dari akun yang cakupannya memuat keputusan itu.`
            : "Pilih keputusan di pemilih di atas, atau buka salah satu yang menunggu tindakan di bawah ini. Halaman ini menampilkan bukti satu keputusan — bukan ringkasan seluruh feed."}
      </p>
      {suggestions.length === 0 ? (
        <p className="evidence-note">
          Tidak ada keputusan yang menunggu tindakan saat ini
          {onOpenRecommendations ? "." : " — buka tab Recommendations untuk melihat semua."}
        </p>
      ) : (
        <ul className="evidence-suggest">
          {suggestions.map((decision) => (
            <li key={String(decision.decision_id)}>
              <button
                type="button"
                className="button evidence-suggest-button"
                onClick={() => onSelect(String(decision.decision_id))}
              >
                <span className="evidence-suggest-title">
                  {String(decision.decision_type ?? "keputusan").replace(/_/g, " ")}
                </span>
                <span className="evidence-suggest-meta">
                  {String(decision.status ?? "—")} ·{" "}
                  {String(decision.decision_id ?? "").slice(0, 8)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {onOpenRecommendations && (
        <button type="button" className="button button-secondary" onClick={onOpenRecommendations}>
          Buka Recommendation Feed
        </button>
      )}
    </article>
  );
}
