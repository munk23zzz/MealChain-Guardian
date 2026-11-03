// @vitest-environment jsdom
// (Perlu DOM: bagian pesan gestur mengganti teks elemen buatan MapLibre.)
import { describe, expect, it } from "vitest";
import {
  MAP_GESTURE_HINT_MOBILE,
  MAP_RESET_LABEL,
  lokalkanPesanGesture,
  mapCooperativeGestures,
  mapResetTitle,
} from "../lib/map-view";

/**
 * Tombol "kembalikan tampilan" (langkah 7b-1, riset peta §5 C4).
 *
 * Tombol ini memanggil `fitBounds` ulang — kalau judulnya salah sebut, pengguna
 * menekan tombol yang menjanjikan sesuatu yang berbeda dari yang terjadi. Karena
 * itu judulnya dibuat fungsi murni dan diuji di sini, seperti sakelar lapisan.
 */
describe("judul tombol kembalikan tampilan peta", () => {
  it("menyebut jumlah lokasi supaya pengguna tahu apa yang akan tampil lagi", () => {
    expect(mapResetTitle(9, false)).toBe("Kembalikan tampilan ke semua 9 lokasi");
  });

  it("menyebut jalur kiriman hanya kalau lapisan jalur memang ikut dikembalikan", () => {
    expect(mapResetTitle(9, true)).toBe(
      "Kembalikan tampilan ke semua 9 lokasi dan jalur kiriman"
    );
    expect(mapResetTitle(9, false)).not.toContain("jalur");
  });

  it("tidak mengarang angka nol: tanpa lokasi, 'semua lokasi' saja tanpa '0 lokasi'", () => {
    const judul = mapResetTitle(0, false);
    expect(judul).not.toContain("0 lokasi");
    expect(judul).toContain("semua lokasi");
  });

  it("jumlah tidak wajar (negatif/NaN) diperlakukan seperti nol, bukan dipaksa jadi angka", () => {
    expect(mapResetTitle(-3, false)).not.toContain("-3");
    expect(mapResetTitle(Number.NaN, false)).not.toContain("NaN");
    expect(mapResetTitle(Number.NaN, false)).toBe(mapResetTitle(0, false));
  });

  it("jumlah pecahan dibulatkan ke bawah (jumlah lokasi selalu bilangan bulat)", () => {
    expect(mapResetTitle(8.7, false)).toContain("8 lokasi");
  });

  it("label tombol tetap singkat, bermakna, dan tanpa jargon bahasa Inggris", () => {
    expect(MAP_RESET_LABEL.length).toBeGreaterThan(3);
    expect(MAP_RESET_LABEL.toLowerCase()).not.toContain("reset");
    expect(MAP_RESET_LABEL.toLowerCase()).not.toContain("zoom");
    expect(MAP_RESET_LABEL.toLowerCase()).not.toContain("fit");
  });
});

/**
 * Gestur kooperatif di peta (celah C9, langkah 7b-2; riset §5).
 *
 * Latar: di ponsel, geser satu jari di atas peta "mencuri" gulir halaman — peta
 * tidak bisa dilewati untuk sampai ke kartu di bawahnya. MapLibre punya mode
 * *cooperative gestures*: satu jari = gulir HALAMAN, dua jari = geser peta.
 * Mode itu juga mengubah desktop (roda tetikus butuh Ctrl), jadi ia hanya boleh
 * menyala untuk perangkat sentuh UTAMA — dan diskriminasi itu diuji di sini,
 * bukan diwariskan dari lebar jendela.
 */
describe("gestur kooperatif peta (kebijakan perangkat)", () => {
  /** Media query tiruan: satu perangkat, satu jawaban per pertanyaan. */
  function perangkat(jenis: "sentuh" | "tetikus"): (q: string) => boolean {
    return (q) => q.includes("pointer: coarse") && jenis === "sentuh";
  }

  it("perangkat sentuh utama (pointer: coarse): gestur kooperatif MENYALA", () => {
    expect(mapCooperativeGestures(perangkat("sentuh"))).toBe(true);
  });

  it("desktop (pointer: fine): tetap seperti sekarang — roda tetikus = zoom", () => {
    expect(mapCooperativeGestures(perangkat("tetikus"))).toBe(false);
  });

  it("jendela desktop yang disempitkan TIDAK ikut dianggap sentuh", () => {
    // Yang diperiksa hanya media pointer, bukan lebar layar: mencabut zoom roda
    // tetikus hanya karena jendelanya sempit akan mengejutkan pengguna desktop.
    const query = (q: string) => q.includes("max-width");
    expect(mapCooperativeGestures(query)).toBe(false);
  });
});

describe("pesan gestur peta dalam bahasa Indonesia", () => {
  function layar(pesan: string): HTMLElement {
    const root = document.createElement("div");
    root.innerHTML = `<div class="maplibregl-cooperative-gesture-screen">
      <span class="maplibregl-desktop-message">${pesan}</span>
      <span class="maplibregl-mobile-message">${pesan}</span>
    </div>`;
    return root;
  }

  it("mengganti pesan bawaan MapLibre (Inggris) dengan kalimat Indonesia", () => {
    const root = layar("Use two fingers to move the map");
    lokalkanPesanGesture(root);
    expect(root.querySelector(".maplibregl-mobile-message")?.textContent).toBe(
      MAP_GESTURE_HINT_MOBILE
    );
    expect(root.textContent).not.toContain("two fingers");
  });

  it("kalimatnya menyebut kedua sisi aturannya: satu jari vs dua jari", () => {
    expect(MAP_GESTURE_HINT_MOBILE).toContain("Satu jari");
    expect(MAP_GESTURE_HINT_MOBILE).toContain("dua jari");
  });

  it("tidak meledak kalau layar pesannya tidak ada (MapLibre lain versi)", () => {
    const root = document.createElement("div");
    expect(() => lokalkanPesanGesture(root)).not.toThrow();
  });
});
