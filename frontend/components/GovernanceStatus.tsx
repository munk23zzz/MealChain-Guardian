import type { GovernanceView } from "../lib/governance";

/**
 * Kepala "Governance & persetujuan": chip status, progres peran syarat,
 * daftar peran penyetuju, dan alasan tertahan.
 *
 * Prinsip yang dijaga (ui-ux-pro-max prioritas 1):
 *  - makna TIDAK dibawa warna saja: tiap keadaan punya bentuk penanda berbeda
 *    (○ menunggu, ◐ sebagian, ✓ siap, ✕ ditolak, ✓✓ selesai) plus teks;
 *  - angka progres tidak hanya visual: ada teks "1 dari 2 peran syarat" dan
 *    `role="progressbar"` dengan `aria-valuenow/valuemax`;
 *  - status per peran diumumkan lewat `.sr-only` ("sudah menyetujui"), bukan
 *    hanya lewat tanda ✓;
 *  - semua angka berasal dari `GovernanceView` (read model server).
 */

const TANDA: Record<GovernanceView["state"], string> = {
  menunggu: "○",
  sebagian: "◐",
  /** Semua peran syarat setuju, eksekusi masih tertahan server. */
  lengkap: "◉",
  siap: "✓",
  ditolak: "✕",
  selesai: "✓✓",
};

export default function GovernanceStatus({
  view,
  variant = "full",
}: {
  view: GovernanceView;
  /**
   * `chip` dipakai di kepala popup: hanya chip + progres. Daftar peran dan
   * alasan tertahan TIDAK diulang di sana karena `ApprovalModal` sudah
   * menampilkan syarat, verdict, peran yang kurang, dan penghalang — satu
   * fakta satu tempat.
   */
  variant?: "full" | "chip";
}) {
  const persen = view.total > 0 ? Math.round((view.done / view.total) * 100) : 0;
  return (
    <div className="gov-status" data-state={view.state}>
      <p className="gov-chip" data-state={view.state}>
        <span className="gov-chip-mark" aria-hidden="true">
          {TANDA[view.state]}
        </span>
        {view.label}
      </p>

      {view.total > 0 ? (
        <div className="gov-progress">
          <span className="gov-progress-text">
            {view.done} dari {view.total} peran syarat terpenuhi
          </span>
          <div
            className="gov-progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={view.total}
            aria-valuenow={view.done}
            aria-label="Peran syarat yang sudah menyetujui"
          >
            <span className="gov-progress-fill" style={{ width: `${persen}%` }} />
          </div>
        </div>
      ) : null}

      {variant === "full" && view.groups.length > 0 ? (
        <ul className="gov-roles" aria-label="Peran penyetuju">
          {view.groups.map((grup) => (
            <li key={grup.roles.join("+")} data-done={grup.done ? "true" : "false"}>
              <span className="gov-role-mark" aria-hidden="true">
                {grup.done ? "✓" : "○"}
              </span>
              <span className="gov-role-label">{grup.label}</span>
              <span className="sr-only">{grup.done ? "sudah menyetujui" : "belum menyetujui"}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {variant === "full" && view.missingLabels.length > 0 && view.state !== "ditolak" ? (
        <p className="gov-wait">Menunggu {view.missingLabels.join(" dan ")}.</p>
      ) : null}

      {variant === "full" && view.blocker.length > 0 ? (
        <div className="gov-blocker" role="status">
          <span className="gov-blocker-title">Tertahan</span>
          <ul>
            {view.blocker.map((alasan) => (
              <li key={alasan}>{alasan}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
