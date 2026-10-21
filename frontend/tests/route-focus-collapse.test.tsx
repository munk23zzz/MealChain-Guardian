// @vitest-environment jsdom
// "Pilih kiriman:" bisa DILIPAT (permintaan pemilik 20 Okt 2026).
// Keputusan melipat diambil dari TATA LETAK (anak-anak probe punya offsetTop
// berbeda = lebih dari satu baris), bukan dari jumlah pil — satu baris
// bergantung lebar panel.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RouteFocusPicker from "../components/RouteFocusPicker";
import { focusOptions } from "../lib/route-focus";
import { jumlahBaris, perluTombolTutup } from "../lib/route-focus-lines";

const payload = (n: number) => ({
  routes: Array.from({ length: n }, (_, i) => ({
    batch_id: `b-${i}`,
    supplier_id: `s-${i}`,
    supplier_name: `Pemasok ${i}`,
    origin: { latitude: -6.8 - i * 0.01, longitude: 107.1 },
    destination_id: "L1",
    destination_name: "Jakarta",
    destination: { latitude: -6.2, longitude: 106.8 },
    quantity_kg: 100,
    commodity: "telur",
    journey: {
      dispatched_at: "2026-10-16T12:24:00+00:00",
      eta_at: "2026-10-16T13:00:00+00:00",
      state: "di_jalan",
      state_label: "Di jalan",
      remaining_min: 20,
      progress: 0.5,
    },
  })),
});

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

/** Tiru tata letak: baris ke-`perBaris` berpindah offsetTop. */
function pasangTataLetak(perBaris: number) {
  const probe = host.querySelector(".route-focus-probe") as HTMLElement | null;
  expect(probe).not.toBeNull();
  Array.from(probe!.children).forEach((anak, i) => {
    Object.defineProperty(anak, "offsetTop", {
      configurable: true,
      value: Math.floor(i / perBaris) * 32,
    });
  });
}

describe("jumlahBaris / perluTombolTutup", () => {
  it("menghitung baris dari offsetTop dan hanya melipat bila > 1 baris", () => {
    expect(jumlahBaris([])).toBe(0);
    expect(jumlahBaris([0, 0, 0])).toBe(1);
    expect(jumlahBaris([0, 0, 32, 32])).toBe(2);
    expect(perluTombolTutup([0, 0, 0])).toBe(false);
    expect(perluTombolTutup([0, 32])).toBe(true);
  });
});

describe("RouteFocusPicker — lipat buka", () => {
  it("satu baris: tidak ada segitiga, semua pil tampil", () => {
    const options = focusOptions(payload(2));
    act(() =>
      root.render(
        <RouteFocusPicker options={options} focused={null} total={3} onFocus={() => {}} />
      )
    );
    pasangTataLetak(9); // semuanya di baris 0
    act(() => {
      window.dispatchEvent(new Event("resize"));
    });
    expect(host.querySelector(".route-focus-toggle")).toBeNull();
    expect(host.querySelectorAll("button.route-focus-pill").length).toBeGreaterThan(1);
  });

  it("lebih dari satu baris: ada segitiga, daftar terlipat, dan bisa dibuka", () => {
    const options = focusOptions(payload(6));
    act(() =>
      root.render(
        <RouteFocusPicker options={options} focused={null} total={7} onFocus={() => {}} />
      )
    );
    pasangTataLetak(2); // tiap 2 pil pindah baris

    // Ukur ulang seperti ResizeObserver sungguhan.
    const probe = host.querySelector(".route-focus-probe") as HTMLElement;
    act(() => {
      probe.dispatchEvent(new Event("resize"));
      window.dispatchEvent(new Event("resize"));
    });
    // Pemicu utama di jsdom: tombol ada setelah pengukuran pertama pada mount,
    // jadi paksa satu render ulang dengan mengubah pilihan.
    act(() =>
      root.render(
        <RouteFocusPicker options={[...options]} focused={null} total={7} onFocus={() => {}} />
      )
    );
    const toggle = host.querySelector<HTMLButtonElement>(".route-focus-toggle");
    expect(toggle).not.toBeNull();
    expect(toggle!.getAttribute("aria-expanded")).toBe("false");
    // Terlipat: daftar disembunyikan (bukan sekadar dipotong CSS).
    expect(host.querySelector(".route-focus-list")!.className).toContain("is-collapsed");

    act(() => toggle!.click());
    expect(toggle!.getAttribute("aria-expanded")).toBe("true");
    expect(host.querySelector(".route-focus-list")!.className).not.toContain("is-collapsed");
    expect(toggle!.textContent).toContain("Ringkas");
  });
});
