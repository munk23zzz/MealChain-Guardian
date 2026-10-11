// TopBar — header global 64px: kiri = peran + nama SPPG + jam; kanan = notifikasi + akun + logout.
// Brand "MealChain Guardian" dipindah ke sidebar.
import { useEffect, useState } from "react";
import {
  BellIcon,
  RoleIcon,
} from "./NavIcon";
import {
  ALL_LOCATIONS,
  countActionable,
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
  const pending = countActionable(decisions);
  // Model cakupan lokasi (murni, teruji): hanya monitor nasional boleh memilih;
  // peran SPPG terkunci ke lokasinya; lokasi belum diketahui → fail-closed.
  const scope = scopeModel({ role, locations, ownLocation });
  // Nilai awal: lokasi aktif, atau "seluruh lokasi" selama belum dipilih.
  const scopeValue = activeLocation ?? scope.options[0]?.value ?? ALL_LOCATIONS;

  // Jam real-time — dirender client only (null saat SSR supaya tidak hidrasi mismatch)
  const [clock, setClock] = useState<string | null>(null);
  useEffect(() => {
    const fmt = () =>
      new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    setClock(fmt());
    const iv = setInterval(() => setClock(fmt()), 30000);
    return () => clearInterval(iv);
  }, []);

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        {/* Peran */}
        <span className="top-bar-role">
          <RoleIcon />
          <span className="top-bar-role-text">{roleLabel}</span>
        </span>

        {/* Nama / lokasi SPPG */}
        {userSub && (
          <span className="top-bar-sppg">{userSub}</span>
        )}

        {/* Pemilih cakupan lokasi — aturan peran dijaga scopeModel (murni,
            teruji): monitor bebas memilih, SPPG terkunci, belum diketahui →
            fail-closed. Dihilangkan pada 11 Okt lalu DIPULIHKAN di sini karena
            tanpa itu tidak ada UI yang bisa mengubah lokasi aktif di peta. */}
        <label className="top-bar-scope">
          <span className="sr-only">Cakupan lokasi yang ditampilkan</span>
          <select
            className="top-bar-select"
            value={scopeValue}
            disabled={scope.disabled}
            onChange={(event) => onSelectLocation(event.target.value)}
            title={
              scope.disabled
                ? "Peran SPPG hanya memantau SPPG-nya sendiri"
                : "Pilih lokasi yang disorot di peta"
            }
          >
            {/* Opsi kosong = placeholder (mis. lokasi pemakai belum diketahui). */}
            {scope.options.length === 0 && <option value="">{scope.placeholder}</option>}
            {scope.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        {/* Jam */}
        {clock && (
          <span className="top-bar-clock" aria-label={`Waktu saat ini: ${clock}`}>
            {clock}
          </span>
        )}
      </div>

      <div className="top-bar-right">
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
      </div>
    </header>
  );
}
