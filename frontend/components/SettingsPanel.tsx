"use client";

// Panel Pengaturan (S4-11): kelola pengguna & lokasi SPPG.
//
// Hanya peran `bgn_monitor` yang melihat tab ini (rail menyaring lewat
// `MANAGE_ROLES`); backend juga menegakkan hal yang sama (`/admin/*` → 403),
// jadi UI bukan satu-satunya penjaga.
//
// Aturan yang dipegang: perubahan hanya dikirim untuk field yang benar berubah
// (`draftUserUpdate`), lokasi tidak dikirim saat peran baru = monitor, dan
// angka/teks yang tidak ada datanya ditulis apa adanya (bukan dikarang).

import { useCallback, useEffect, useState } from "react";

import {
  fetchAdminLocations,
  fetchAdminUsers,
  updateAdminLocation,
  updateAdminUser,
} from "../lib/api";
import { draftUserUpdate, roleLabel } from "../lib/settings";
import ScrollHint from "./ScrollHint";

type AdminUser = {
  id: string;
  name: string;
  email: string;
  role: string;
  locationId: string | null;
  locationName: string | null;
};

type AdminLocation = {
  id: string;
  name: string;
  region: string;
  latitude: number;
  longitude: number;
};

const ROLE_OPTIONS = ["sppg_head", "sppg_nutritionist", "bgn_monitor"];

export default function SettingsPanel({ token }: { token: string }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [locations, setLocations] = useState<AdminLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, l] = await Promise.all([
        fetchAdminUsers(token),
        fetchAdminLocations(token),
      ]);
      setUsers(u);
      setLocations(l);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "gagal memuat data pengaturan",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const simpanPengguna = useCallback(
    async (user: AdminUser, role: string, locationId: string | null) => {
      const payload = draftUserUpdate(user, role, locationId);
      if (Object.keys(payload).length === 0) {
        setNotice("Tidak ada perubahan untuk disimpan.");
        return;
      }
      try {
        const hasil = await updateAdminUser(user.id, payload, token);
        setUsers((prev) => prev.map((u) => (u.id === hasil.id ? hasil : u)));
        setNotice(`Perubahan untuk ${hasil.email} tersimpan.`);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "gagal menyimpan");
      }
    },
    [token],
  );

  const simpanLokasi = useCallback(
    async (
      loc: AdminLocation,
      nama: string,
      wilayah: string,
      lat: number,
      lon: number,
    ) => {
      const payload: Record<string, string | number> = {};
      if (nama !== loc.name) payload.name = nama;
      if (wilayah !== loc.region) payload.region = wilayah;
      if (lat !== loc.latitude) payload.latitude = lat;
      if (lon !== loc.longitude) payload.longitude = lon;
      if (Object.keys(payload).length === 0) {
        setNotice("Tidak ada perubahan untuk disimpan.");
        return;
      }
      try {
        const hasil = await updateAdminLocation(loc.id, payload, token);
        setLocations((prev) => prev.map((l) => (l.id === hasil.id ? hasil : l)));
        setNotice(`Lokasi ${hasil.name} tersimpan.`);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "gagal menyimpan");
      }
    },
    [token],
  );

  return (
    <div className="settings">
      <div className="settings-head">
        <div>
          <h1 className="settings-title">Pengaturan</h1>
          <p className="settings-sub">
            Kelola pengguna SPPG dan daftar lokasi. Perubahan berlaku untuk
            keputusan BERIKUTNYA — keputusan lama tidak diubah.
          </p>
        </div>
        <button type="button" className="settings-refresh" onClick={() => void load()}>
          Muat ulang
        </button>
      </div>

      {notice && (
        <p className="settings-notice" role="status" aria-live="polite">
          {notice}
        </p>
      )}
      {error && (
        <p className="settings-error" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p className="settings-sub">Memuat pengguna & lokasi…</p>
      ) : (
        <>
          <section className="settings-card" aria-labelledby="settings-users">
            <h2 id="settings-users" className="settings-card-title">
              Pengguna ({users.length})
            </h2>
            <div className="settings-table-wrap">
              <table className="settings-table">
                <thead>
                  <tr>
                    <th scope="col">Nama</th>
                    <th scope="col">Peran</th>
                    <th scope="col">Lokasi</th>
                    <th scope="col">Simpan</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <UserRow
                      key={user.id}
                      user={user}
                      locations={locations}
                      onSave={simpanPengguna}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <ScrollHint />
          </section>

          <section className="settings-card" aria-labelledby="settings-locations">
            <h2 id="settings-locations" className="settings-card-title">
              Lokasi ({locations.length})
            </h2>
            <p className="settings-sub">
              Lokasi tidak bisa dihapus: keputusan & batch historis merujuknya.
            </p>
            <div className="settings-table-wrap">
              <table className="settings-table">
                <thead>
                  <tr>
                    <th scope="col">Nama</th>
                    <th scope="col">Wilayah</th>
                    <th scope="col">Koordinat</th>
                    <th scope="col">Simpan</th>
                  </tr>
                </thead>
                <tbody>
                  {locations.map((loc) => (
                    <LocationRow key={loc.id} location={loc} onSave={simpanLokasi} />
                  ))}
                </tbody>
              </table>
            </div>
            <ScrollHint />
          </section>
        </>
      )}
    </div>
  );
}

function UserRow({
  user,
  locations,
  onSave,
}: {
  user: AdminUser;
  locations: AdminLocation[];
  onSave: (user: AdminUser, role: string, locationId: string | null) => void;
}) {
  const [role, setRole] = useState(user.role);
  const [locationId, setLocationId] = useState<string | null>(user.locationId);

  useEffect(() => {
    setRole(user.role);
    setLocationId(user.locationId);
  }, [user.role, user.locationId]);

  const butuhLokasi = role !== "bgn_monitor";
  const berubah = Object.keys(draftUserUpdate(user, role, locationId)).length > 0;

  return (
    <tr>
      <td>
        <span className="settings-name">{user.name}</span>
        <span className="settings-email">{user.email}</span>
      </td>
      <td>
        <label className="settings-sr" htmlFor={`peran-${user.id}`}>
          Peran {user.name}
        </label>
        <select
          id={`peran-${user.id}`}
          className="settings-select"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          {ROLE_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {roleLabel(r)}
            </option>
          ))}
        </select>
      </td>
      <td>
        {butuhLokasi ? (
          <>
            <label className="settings-sr" htmlFor={`lokasi-${user.id}`}>
              Lokasi {user.name}
            </label>
            <select
              id={`lokasi-${user.id}`}
              className="settings-select"
              value={locationId ?? ""}
              onChange={(e) => setLocationId(e.target.value || null)}
            >
              <option value="">— pilih lokasi —</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </>
        ) : (
          <span className="settings-muted">
            Tidak terikat lokasi (monitor nasional)
          </span>
        )}
      </td>
      <td>
        <div className="settings-save-cell">
          {/* Chip ini hanya muncul kalau draft MEMANG berbeda dari yang
              tersimpan — bukan hiasan yang selalu tampil. */}
          {berubah ? <span className="settings-dirty">belum disimpan</span> : null}
          <button
            type="button"
            className="settings-save"
            disabled={!berubah}
            onClick={() => onSave(user, role, locationId)}
          >
            Simpan
          </button>
        </div>
      </td>
    </tr>
  );
}

function LocationRow({
  location,
  onSave,
}: {
  location: AdminLocation;
  onSave: (
    loc: AdminLocation,
    nama: string,
    wilayah: string,
    lat: number,
    lon: number,
  ) => void;
}) {
  const [nama, setNama] = useState(location.name);
  const [wilayah, setWilayah] = useState(location.region);

  useEffect(() => {
    setNama(location.name);
    setWilayah(location.region);
  }, [location.name, location.region]);

  const berubah = nama !== location.name || wilayah !== location.region;

  return (
    <tr>
      <td>
        <label className="settings-sr" htmlFor={`nama-${location.id}`}>
          Nama lokasi {location.name}
        </label>
        <input
          id={`nama-${location.id}`}
          className="settings-input"
          value={nama}
          onChange={(e) => setNama(e.target.value)}
        />
      </td>
      <td>
        <label className="settings-sr" htmlFor={`wilayah-${location.id}`}>
          Wilayah {location.name}
        </label>
        <input
          id={`wilayah-${location.id}`}
          className="settings-input"
          value={wilayah}
          onChange={(e) => setWilayah(e.target.value)}
        />
      </td>
      <td className="settings-coord">
        {location.latitude.toFixed(4)}, {location.longitude.toFixed(4)}
      </td>
      <td>
        <div className="settings-save-cell">
          {berubah ? <span className="settings-dirty">belum disimpan</span> : null}
          <button
            type="button"
            className="settings-save"
            disabled={!berubah}
            onClick={() =>
              onSave(location, nama, wilayah, location.latitude, location.longitude)
            }
          >
            Simpan
          </button>
        </div>
      </td>
    </tr>
  );
}
