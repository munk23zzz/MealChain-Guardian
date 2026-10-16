// @vitest-environment jsdom
//
// Perilaku petunjuk geser (Langkah 4, 16 Okt 2026): komponen harus MENGUKUR tabel
// di sebelahnya, bukan menebak dari lebar layar. Diuji dengan ResizeObserver palsu
// supaya pengukuran ulang saat ukuran berubah ikut terbukti — bukan hanya hasil
// pengukuran pertama.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ScrollHint from "../components/ScrollHint";

let host: HTMLDivElement;
let root: Root;
const pemicuObservasi: Array<() => void> = [];

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  pemicuObservasi.length = 0;
  vi.stubGlobal(
    "ResizeObserver",
    class {
      private cb: () => void;
      constructor(cb: () => void) {
        this.cb = cb;
        pemicuObservasi.push(() => this.cb());
      }
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  );
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

/** Markup seperti aslinya: wadah tabel + petunjuk di dalam kartu yang sama. */
function Papan({ clientWidth, scrollWidth }: { clientWidth: number; scrollWidth: number }) {
  return (
    <div className="card">
      <div
        className="board-table-wrap"
        ref={(el) => {
          if (!el) return;
          Object.defineProperty(el, "clientWidth", { value: clientWidth, configurable: true });
          Object.defineProperty(el, "scrollWidth", { value: scrollWidth, configurable: true });
        }}
      >
        <table />
      </div>
      <ScrollHint />
    </div>
  );
}

function petunjuk(): HTMLElement | null {
  return host.querySelector<HTMLElement>(".board-scroll-hint");
}

describe("ScrollHint — tampil saat tabel benar-benar perlu digeser", () => {
  it("tampil saat tabel meluap, walau layarnya lebar", () => {
    act(() => root.render(<Papan clientWidth={766} scrollWidth={879} />));
    expect(petunjuk()?.getAttribute("data-tampil")).toBe("true");
    expect(petunjuk()?.textContent).toContain("Geser tabel ke samping");
  });

  it("sembunyi saat tabel pas di wadahnya, walau layarnya sempit", () => {
    act(() => root.render(<Papan clientWidth={562} scrollWidth={562} />));
    expect(petunjuk()?.getAttribute("data-tampil")).toBe("false");
  });

  it("mengukur ulang saat ukuran berubah (observasi, bukan sekali jalan)", () => {
    act(() => root.render(<Papan clientWidth={690} scrollWidth={879} />));
    expect(petunjuk()?.getAttribute("data-tampil")).toBe("true");
    act(() => root.render(<Papan clientWidth={1106} scrollWidth={1106} />));
    act(() => pemicuObservasi.forEach((f) => f()));
    expect(petunjuk()?.getAttribute("data-tampil")).toBe("false");
  });

  it("tidak tampil kalau tidak ada wadah tabel di kartunya — bukan menebak", () => {
    act(() => root.render(<ScrollHint />));
    expect(petunjuk()?.getAttribute("data-tampil")).toBe("false");
  });
});
