/**
 * Keadaan memuat yang seragam — standar repo dari audit UI/UX (11 Okt):
 * setiap pemuat memakai pola yang sama (skeleton + pengumuman pembaca layar),
 * bukan teks "Memuat…" yang berkedip tanpa status.
 */
export function LoadingState({ label, inline = true }: { label: string; inline?: boolean }) {
  return (
    <span className={inline ? "state-loading" : "state-loading state-loading-block"} role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      <span className="skeleton skeleton-inline" aria-hidden="true" />
    </span>
  );
}
