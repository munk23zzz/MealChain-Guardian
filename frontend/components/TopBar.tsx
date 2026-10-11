// TopBar — header global 64px: kiri = peran + nama SPPG + jam; kanan = notifikasi + akun + logout.
// Brand "MealChain Guardian" dipindah ke sidebar.
import { useEffect, useRef, useState } from "react";
import {
  BellIcon,
  CloseIcon,
  RoleIcon,
} from "./NavIcon";
import {
  ALL_LOCATIONS,
  countActionable,
  notifList,
  scopeModel,
  type NotifDecision,
  type TopBarLocation,
} from "../lib/topbar";
import { formatJam, type JamTeks } from "../lib/jam";
import { formatKg } from "../lib/overview-format";
import { formatDateTime } from "../lib/datetime";
import { DECISION_TYPE_LABELS } from "./RecommendationCard";
import StatusBadge from "./StatusBadge";

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
  /** Keputusan dari GET /decisions — sumber isi popup notifikasi + hitungan. */
  decisions?: readonly NotifDecision[] | null;
  /** Teks "terakhir diperbarui" dari polling peta. */
  updatedAtLabel?: string | null;
  /** Dipakai tombol di dalam popup (bukan lagi klik lonceng langsung). */
  onOpenNotifications: () => void;
  onLogout: () => void;
};

export default function TopBar({
  role,
  roleLabel,
  userName,
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
  // Tidak ada pilihan lain (SPPG terkunci pada lokasinya / lokasi belum
  // diketahui): kontrol ini keterangan, bukan pilihan → tanpa panah dropdown.
  const scopeLocked = scope.disabled || scope.options.length <= 1;

  // Jam real-time — dirender client only (null saat SSR supaya tidak hidrasi
  // mismatch). Interval 1 detik karena tampilan kini memuat DETIK; zona memakai
  // waktu Indonesia (WIB), bukan zona mesin pemakai.
  const [clock, setClock] = useState<JamTeks | null>(null);
  useEffect(() => {
    const tick = () => setClock(formatJam(new Date()));
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, []);

  // Popup notifikasi (permintaan Roy 11 Okt): lonceng membuka popup di sini,
  // TIDAK lagi langsung memindahkan tab ke Recommendations.
  const [notifOpen, setNotifOpen] = useState(false);
  const bellRef = useRef<HTMLButtonElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const notifikasi = notifList(decisions);

  useEffect(() => {
    if (!notifOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setNotifOpen(false);
        bellRef.current?.focus(); // fokus kembali ke pemicu (pola dialog)
      }
    };
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (notifRef.current?.contains(target) || bellRef.current?.contains(target)) return;
      setNotifOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [notifOpen]);

  // Fokus masuk ke panel saat dibuka supaya pembaca layar langsung membacanya.
  useEffect(() => {
    if (notifOpen) notifRef.current?.focus();
  }, [notifOpen]);

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        {/* Peran */}
        <span className="top-bar-role">
          <RoleIcon />
          <span className="top-bar-role-text">{roleLabel}</span>
        </span>

        {/* Tidak ada lagi <span class="top-bar-sppg"> di sini: lokasi sudah
            diwakili pemilih cakupan di bawah (dulu teks ini duplikat). */}

        {/* Pemilih cakupan lokasi — aturan peran dijaga scopeModel (murni,
            teruji): monitor bebas memilih, SPPG terkunci, belum diketahui →
            fail-closed. Dihilangkan pada 11 Okt lalu DIPULIHKAN di sini karena
            tanpa itu tidak ada UI yang bisa mengubah lokasi aktif di peta. */}
        <label className="top-bar-scope">
          <span className="sr-only">Cakupan lokasi yang ditampilkan</span>
          <select
            className={
              scopeLocked ? "top-bar-select top-bar-select-locked" : "top-bar-select"
            }
            value={scopeValue}
            disabled={scope.disabled}
            onChange={(event) => onSelectLocation(event.target.value)}
            title={
              !scope.disabled
                ? "Pilih lokasi yang disorot di peta"
                : scope.options.length === 0
                  ? "Lokasi pemakai belum diketahui"
                  : "Peran SPPG hanya memantau SPPG-nya sendiri"
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

        {/* Jam (jam:menit:detik + zona Indonesia) */}
        {clock && (
          <span className="top-bar-clock" aria-label={clock.aria} title={clock.aria}>
            {clock.teks}
          </span>
        )}
      </div>

      <div className="top-bar-right">
        <div className="top-bar-notif">
          <button
            ref={bellRef}
            type="button"
            className="top-bar-bell"
            onClick={() => setNotifOpen((open) => !open)}
            aria-label={`Notifikasi: ${pending} keputusan menunggu tindakan`}
            aria-haspopup="dialog"
            aria-expanded={notifOpen}
            aria-controls="top-bar-notif-panel"
            title="Buka informasi notifikasi"
          >
            <BellIcon size={18} />
            {pending > 0 && (
              <span className="top-bar-bell-count" aria-hidden="true">
                {pending > 9 ? "9+" : pending}
              </span>
            )}
          </button>

          {notifOpen && (
            <div
              id="top-bar-notif-panel"
              ref={notifRef}
              className="top-bar-notif-panel"
              role="dialog"
              aria-label="Notifikasi keputusan yang menunggu tindakan"
              tabIndex={-1}
            >
              <div className="top-bar-notif-head">
                <div className="top-bar-notif-heading">
                  <strong className="top-bar-notif-title">Notifikasi</strong>
                  <p className="top-bar-notif-sub">
                    {notifikasi.total > 0
                      ? `${notifikasi.total} keputusan menunggu tindakan`
                      : "Tidak ada keputusan menunggu tindakan"}
                  </p>
                </div>
                <button
                  type="button"
                  className="top-bar-notif-close"
                  onClick={() => {
                    setNotifOpen(false);
                    bellRef.current?.focus();
                  }}
                  aria-label="Tutup notifikasi"
                  title="Tutup"
                >
                  <CloseIcon size={16} />
                </button>
              </div>

              {notifikasi.total === 0 ? (
                <p className="top-bar-notif-empty">
                  Semua keputusan sudah ditindaklanjuti. Permintaan baru muncul di sini.
                </p>
              ) : (
                <ul className="top-bar-notif-list">
                  {notifikasi.shown.map((item, index) => (
                    <li
                      key={item.decision_id ?? `${item.decision_type}-${item.created_at}-${index}`}
                      className="top-bar-notif-item"
                    >
                      <span className="top-bar-notif-item-main">
                        <span className="top-bar-notif-item-label">
                          {DECISION_TYPE_LABELS[item.decision_type ?? ""] ?? "Rekomendasi baru"}
                        </span>
                        <span className="top-bar-notif-item-meta">
                          {formatKg(item.quantity_kg)} · {formatDateTime(item.created_at)}
                        </span>
                      </span>
                      {item.status && <StatusBadge status={item.status} />}
                    </li>
                  ))}
                </ul>
              )}

              {notifikasi.rest > 0 && (
                <p className="top-bar-notif-rest">
                  +{notifikasi.rest} keputusan lain menunggu tindakan
                </p>
              )}

              <button
                type="button"
                className="top-bar-notif-open"
                onClick={() => {
                  setNotifOpen(false);
                  onOpenNotifications();
                }}
              >
                Buka tab Recommendations
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
