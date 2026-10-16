"use client";

// Kolom form dengan pesan validasi MILIK APLIKASI.
//
// WS-G (QA 16 Okt, temuan F7): pada halaman login, klik "Masuk" dengan kolom
// kosong memunculkan "Please fill out this field." — pesan bawaan peramban,
// yang mengikuti LOCALE PERAMBAN, bukan `<html lang="id">`. Di laptop juri
// berperamban en-US, UI berbahasa Indonesia menampilkan validasi berbahasa
// Inggris, dan itu tidak bisa diperbaiki dari sisi aplikasi mana pun kecuali
// dengan memiliki pesannya sendiri.
//
// Yang dipertahankan: `required` + type="email" tetap dipakai, jadi validasi
// native, fokus otomatis ke kolom bermasalah, dan pengumuman pembaca layar
// tetap datang dari peramban. Yang diganti hanya teksnya, lewat
// setCustomValidity.
import type { ChangeEventHandler } from "react";

export type PesanValidasi = {
  /** Kolom dibiarkan kosong. */
  kosong: string;
  /** Terisi tetapi tidak sesuai format (mis. email tanpa "@"). */
  salahFormat: string;
};

export default function ValidatedField({
  label,
  type,
  value,
  onChange,
  autoComplete,
  pesan,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (nilai: string) => void;
  autoComplete?: string;
  pesan: PesanValidasi;
}) {
  const handleChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    // WAJIB: pesan khusus harus dilepas sebelum validasi berikutnya, kalau tidak
    // kolom yang sudah diperbaiki tetap dianggap tidak sah dan pengguna
    // terjebak dengan pesan lama (jebakan klasik setCustomValidity).
    e.currentTarget.setCustomValidity("");
    onChange(e.target.value);
  };

  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        onChange={handleChange}
        autoComplete={autoComplete}
        required
        onInvalid={(e) => {
          const el = e.currentTarget;
          el.setCustomValidity(
            el.validity.valueMissing ? pesan.kosong : pesan.salahFormat
          );
        }}
      />
    </label>
  );
}
