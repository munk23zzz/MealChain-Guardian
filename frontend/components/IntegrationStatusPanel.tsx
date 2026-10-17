/**
 * Papan status integrasi per komponen (W-3, 2026-10-17 · PLAN-012).
 *
 * Tujuan: bukti status integrasi yang selama ini hanya ada di dokumen kini
 * terlihat di konsol — tanpa satu pun klaim berlebih. Aturannya:
 *
 * 1. Setiap komponen menyebut JENIS BUKTI-nya (`category_label`), bukan
 *    "operasional". Hijau hanya untuk `probe_passed`; dan endpoint ini tidak
 *    menjalankan probe, jadi di praktiknya tidak ada baris hijau.
 * 2. Komponen tanpa bukti berbunyi "tidak tersedia"/"belum dimulai" (merah),
 *    tidak pernah hijau.
 * 3. Panel menyebutkan jumlah probe yang benar-benar dijalankan, supaya pembaca
 *    tahu ini papan KONFIGURASI + ARTEFAK, bukan hasil pemeriksaan hidup.
 *
 * Panel ini read-only dan berada di dalam tab Agent Log (tidak menambah tab).
 */
import { formatDateTime } from "../lib/datetime";

export type IntegrationComponent = {
  id: string;
  name: string;
  category: string;
  category_label?: string | null;
  evidence?: string | null;
  artifact?: string | null;
  note?: string | null;
  checked_at?: string | null;
};

export type IntegrationStatus = {
  checked_at?: string | null;
  probes_run?: number | null;
  components?: IntegrationComponent[] | null;
};

/** Nada visual — hijau HANYA untuk bukti probe nyata. */
export function categoryTone(category: string | null | undefined): "ok" | "warn" | "danger" | "plain" {
  if (category === "probe_passed") return "ok";
  if (category === "unavailable" || category === "not_started") return "danger";
  if (category === "fail_closed") return "warn";
  return "plain";
}

/** Kalimat kejujuran tentang apa yang (tidak) diperiksa panel ini. */
export function probesNote(probesRun: number | null | undefined): string {
  const jumlah = typeof probesRun === "number" ? probesRun : 0;
  return jumlah > 0
    ? `${jumlah} probe nyata dijalankan untuk papan ini.`
    : "Tidak ada probe jaringan dijalankan: status di bawah menyebut jenis bukti (env/artefak/kontrak), bukan klaim operasional.";
}

export default function IntegrationStatusPanel({
  data,
  loading = false,
  error = null,
  onRetry,
}: {
  data: IntegrationStatus | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}) {
  const komponen = Array.isArray(data?.components) ? data!.components! : [];
  return (
    <section className="card integration-status" aria-busy={loading || undefined}>
      <header className="integration-head">
        <h2>Bukti integrasi per komponen</h2>
        <p className="evidence-note">
          {probesNote(data?.probes_run)}
          {data?.checked_at ? ` Diperiksa: ${formatDateTime(data.checked_at)}.` : ""}
        </p>
      </header>

      {loading && <p className="evidence-note">Memuat status integrasi…</p>}
      {error && (
        <p className="evidence-note">
          Status integrasi tidak bisa dibaca: {error}
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </p>
      )}

      {komponen.length === 0 && !loading && !error && (
        <p className="evidence-note">Belum ada komponen yang dilaporkan.</p>
      )}

      {komponen.length > 0 && (
        <ul className="integration-list">
          {komponen.map((item) => {
            const tone = categoryTone(item.category);
            return (
              <li key={item.id} className={`integration-row integration-tone-${tone}`}>
                <span className="integration-name">{item.name}</span>
                <span className={`integration-badge integration-badge-${tone}`}>
                  {item.category_label || item.category}
                </span>
                {item.evidence && (
                  <span className="integration-evidence" title={item.artifact ?? undefined}>
                    Bukti: {item.evidence}
                  </span>
                )}
                {item.artifact && !item.evidence && (
                  <span className="integration-evidence" title={item.artifact}>
                    Bukti: dokumen teknis tersimpan
                  </span>
                )}
                {item.note && <span className="integration-note">{item.note}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
