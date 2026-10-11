// TopBar — header global 64px mengikuti mockup acuan
// (mockupui/overview_map_supply_status/code.html): brand → dropdown cakupan
// lokasi → pill status jaringan → chip peran → lonceng notifikasi →
// avatar pemakai → tombol keluar.
//
// Aturan yang dipegang:
// - semua angka/label di sini berasal dari props yang diisi data REAL
//   (peta /balance/map, keputusan /decisions, identitas /auth/me);
// - cakupan peran tidak bisa diperluas dari sini (lihat lib/topbar.ts);
// - ikon dekoratif aria-hidden, tombol punya nama aksesibel dari labelnya.
import {
  BellIcon,
  LogoMark,
  LogoutIcon,
  RoleIcon,
} from "./NavIcon";
import {
  ALL_LOCATIONS,
  countActionable,
  initialsOf,
  networkState,
  scopeModel,
  type TopBarLocation,
} from "../lib/topbar";

export type TopBarProps = {
  /** Peran dari JWT (display-only; otorisasi tetap di backend). */
  role: string | null;
  /** Persona label PRD 2.4 (mis. "SPPG Operations Lead"). */
  roleLabel: string;
  /** Nama/email pemakai untuk klaster identitas. */
  userName: string;
  /** Baris kedua klaster identitas (mis. lokasi SPPG). */
  userSub?: string | null;
  /** Lokasi dari data peta (angka REAL, tanpa karangan). */
  locations: readonly TopBarLocation[];
  /** Lokasi aktif yang disorot di peta; null = tanpa sorotan. */
  activeLocation: string | null;
  onSelectLocation: (value: string) => void;
  /** Lokasi milik pemakai (dari GET /auth/me) — pengunci cakupan SPPG. */
  ownLocation?: string | null;
  /** Keputusan yang perlu dipilih backend-nya dari /decisions. */
  decisions?: readonly { status?: string | null }[] | null;
  /** Teks "terakhir diperbarui" dari polling peta. */
  updatedAtLabel?: string | null;
  onOpenNotifications: () => void;
  onLogout: () => void;
};

export default function TopBar({
  role,
  roleLabel,
  userName,
  userSub,
  locations,
  activeLocation,
  onSelectLocation,
  ownLocation,
  decisions,
  updatedAtLabel,
  onOpenNotifications,
  onLogout,
}: TopBarProps) {
  const scope = scopeModel({ role, locations, ownLocation });
  const net = networkState(locations);
  const pending = countActionable(decisions);
  const initials = initialsOf(userName, roleLabel);
  // Nilai dropdown: lokasi aktif, atau "seluruh lokasi" selama belum dipilih.
  const value = activeLocation ?? ALL_LOCATIONS;

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <span className="top-bar-logo" aria-hidden="true">
          <LogoMark />
        </span>
        <span className="top-bar-brand">
          <strong>MealChain Guardian</strong>
          <span className="top-bar-sub">
            Cold-Chain Integrity &amp; Food Supply Intelligence
          </span>
        </span>

        <label className="top-bar-scope">
          <span className="sr-only">Cakupan lokasi yang ditampilkan</span>
          <select
            className="top-bar-select"
            value={value}
            disabled={scope.disabled}
            onChange={(event) => onSelectLocation(event.target.value)}
            title={
              scope.disabled
                ? "Peran SPPG hanya memantau SPPG-nya sendiri"
                : "Pilih lokasi yang disorot di peta"
            }
          >
            {/* Opsi kosong = placeholder (mis. lokasi pemakai belum diketahui). */}
            {scope.options.length === 0 && (
              <option value="">{scope.placeholder}</option>
            )}
            {scope.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <span className={`top-bar-net top-bar-net-${net.tone}`}>
          <i className="top-bar-net-dot" aria-hidden="true" />
          {net.label}
        </span>
      </div>

      <div className="top-bar-right">
        {updatedAtLabel && (
          <span className="top-bar-updated" aria-live="polite">
            {updatedAtLabel}
          </span>
        )}

        <span className="top-bar-role">
          <RoleIcon />
          <span className="top-bar-role-text">Peran: {roleLabel}</span>
        </span>

        <button
          type="button"
          className="top-bar-bell"
          onClick={onOpenNotifications}
          aria-label={`Notifikasi: ${pending} keputusan menunggu tindakan`}
          title="Lihat rekomendasi yang menunggu tindakan"
        >
          <BellIcon size={18} />
          {pending > 0 && (
            <span className="top-bar-bell-count" aria-hidden="true">
              {pending > 9 ? "9+" : pending}
            </span>
          )}
        </button>

        <span className="top-bar-user">
          <span className="top-bar-avatar" aria-hidden="true">
            {initials}
          </span>
          <span className="top-bar-user-meta">
            <span className="top-bar-user-name">{userName}</span>
            {userSub && <span className="top-bar-user-sub">{userSub}</span>}
          </span>
        </span>

        <button
          type="button"
          className="top-bar-logout"
          onClick={onLogout}
          aria-label="Keluar akun"
          title="Keluar"
        >
          <LogoutIcon />
        </button>
      </div>
    </header>
  );
}
