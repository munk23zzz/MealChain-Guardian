// @vitest-environment jsdom
// WS-G (QA 16 Okt, temuan F7): pada halaman login, klik "Masuk" dengan kolom
// kosong memunculkan pesan bawaan peramban — "Please fill out this field."
// Teks itu mengikuti LOCALE PERAMBAN, bukan `<html lang="id">`, jadi di laptop
// juri yang berperamban en-US validasi form berbahasa Inggris di UI Indonesia.
//
// Tidak ada string aplikasi yang bisa "diterjemahkan" untuk memperbaikinya:
// yang harus dilakukan adalah MEMILIKI pesannya sendiri lewat setCustomValidity,
// supaya teksnya sama di peramban mana pun, sementara `required`/type="email"
// tetap dipakai (validasi native, fokus otomatis, dan pengumuman pembaca layar
// tetap dari peramban).
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { useState } from "react";

import ValidatedField, { type PesanValidasi } from "../components/ValidatedField";

const PESAN_EMAIL: PesanValidasi = {
  kosong: "Isi email dulu.",
  salahFormat: "Format email belum benar — contoh: nama@demo.local.",
};

let root: Root;
let host: HTMLDivElement;

function Harness({
  pesan = PESAN_EMAIL,
  tipe = "email",
  awal = "",
}: {
  pesan?: PesanValidasi;
  tipe?: string;
  awal?: string;
}) {
  const [nilai, setNilai] = useState(awal);
  return (
    <ValidatedField
      label="Email"
      type={tipe}
      value={nilai}
      onChange={setNilai}
      autoComplete="username"
      pesan={pesan}
    />
  );
}

function mount(props: Parameters<typeof Harness>[0] = {}) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root.render(<Harness {...props} />));
  const input = host.querySelector("input") as HTMLInputElement;
  if (!input) throw new Error("input tidak dirender");
  return input;
}

/** Peramban memicu `invalid` saat submit ditolak; React memasangnya langsung di elemen. */
function picuInvalid(input: HTMLInputElement) {
  act(() => {
    input.dispatchEvent(new Event("invalid", { cancelable: true }));
  });
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
});

describe("ValidatedField — pesan validasi milik aplikasi, bukan locale peramban", () => {
  it("kolom kosong → pesan Indonesia, bukan 'Please fill out this field.'", () => {
    const input = mount();
    expect(input.validity.valueMissing).toBe(true);
    picuInvalid(input);
    expect(input.validationMessage).toBe("Isi email dulu.");
    expect(input.validationMessage).not.toMatch(/please|field|required/i);
  });

  it("format salah → pesan format, bukan pesan kosong", () => {
    const input = mount({ awal: "bukan-email" });
    expect(input.validity.valueMissing).toBe(false);
    picuInvalid(input);
    expect(input.validationMessage).toBe(
      "Format email belum benar — contoh: nama@demo.local."
    );
  });

  it("pesan password bisa berbeda dari email (satu komponen, dua teks)", () => {
    const input = mount({
      tipe: "password",
      pesan: { kosong: "Isi password dulu.", salahFormat: "Isi password dulu." },
    });
    picuInvalid(input);
    expect(input.validationMessage).toBe("Isi password dulu.");
  });

  it("mulai mengetik → pesan khusus dilepas, validasi kembali ke peramban", () => {
    const input = mount();
    picuInvalid(input);
    expect(input.validationMessage).not.toBe("");

    act(() => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value"
      )?.set;
      setter?.call(input, "a");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    // Kalau pesan lama tidak dilepas, kolom yang sudah diperbaiki tetap
    // dianggap tidak sah dan pengguna terjebak — jebakan klasik setCustomValidity.
    // Yang diperiksa KEADAANNYA, bukan teks: setelah dilepas, teks pesan menjadi
    // milik peramban lagi ("Constraints not satisfied" di jsdom, kalimat lain di
    // Chrome) — memaku teks itu berarti menguji peramban, bukan komponen ini.
    expect(input.validity.customError).toBe(false);
    expect(input.validationMessage).not.toBe("Isi email dulu.");
  });

  it("nilai yang diketik tetap diteruskan ke pemanggil", () => {
    const input = mount();
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value"
      )?.set;
      setter?.call(input, "sppg.head@demo.local");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(input.value).toBe("sppg.head@demo.local");
  });

  it("label, required, dan atribut peramban tetap apa adanya", () => {
    const input = mount();
    expect(host.querySelector("span")?.textContent).toBe("Email");
    expect(input.required).toBe(true);
    expect(input.getAttribute("type")).toBe("email");
    expect(input.getAttribute("autocomplete")).toBe("username");
  });
});
