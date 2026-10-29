// @vitest-environment jsdom
//
// Chip "Perlu perhatian" di bilah saring Agent Log (UI-1, 29 Okt 2026).
// Chip ini toggle, bukan pilihan status verifikasi: menekannya menyaring
// keputusan yang ditandai verifikator atau lewat tenggat, dan "Kosongkan
// filter" harus mengembalikannya.
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import ModuleSearch from "../components/ModuleSearch";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let root: Root | null = null;
let host: HTMLDivElement | null = null;

function render(node: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(node));
  return host;
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
});

const dasar = {
  query: "",
  onQuery: () => {},
  commodity: null,
  onCommodity: () => {},
  verification: "all" as const,
  onVerification: () => {},
  commodities: [],
  counts: { all: 17, terverifikasi: 8, menunggu: 9, ditolak: 1 },
  total: 17,
};

describe("chip Perlu perhatian", () => {
  it("menampilkan jumlah dan keadaan tidak aktif", () => {
    const el = render(
      <ModuleSearch {...dasar} attention={false} onAttention={() => {}} attentionCount={3} />
    );
    const chip = el.querySelector<HTMLButtonElement>(".filter-chip-attention");
    expect(chip).not.toBeNull();
    expect(chip!.textContent).toContain("Perlu perhatian");
    expect(chip!.textContent).toContain("3");
    expect(chip!.getAttribute("aria-pressed")).toBe("false");
  });

  it("menekan chip meminta saringan dinyalakan", () => {
    const onAttention = vi.fn();
    const el = render(
      <ModuleSearch {...dasar} attention={false} onAttention={onAttention} attentionCount={3} />
    );
    const chip = el.querySelector<HTMLButtonElement>(".filter-chip-attention")!;
    act(() => chip.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(onAttention).toHaveBeenCalledWith(true);
  });

  it("saat menyala memakai nada peringatan, bukan biru aksi", () => {
    const el = render(
      <ModuleSearch {...dasar} attention onAttention={() => {}} attentionCount={3} />
    );
    const chip = el.querySelector<HTMLButtonElement>(".filter-chip-attention")!;
    expect(chip.getAttribute("aria-pressed")).toBe("true");
    expect(chip.className).toContain("filter-chip-warn");
  });

  it("Kosongkan filter mematikan saringan triage juga", () => {
    const onAttention = vi.fn();
    const onVerification = vi.fn();
    const onQuery = vi.fn();
    const el = render(
      <ModuleSearch
        {...dasar}
        query="beras"
        verification="menunggu"
        onQuery={onQuery}
        onVerification={onVerification}
        attention
        onAttention={onAttention}
        attentionCount={3}
      />
    );
    const reset = el.querySelector<HTMLButtonElement>(".aa-search-reset")!;
    act(() => reset.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(onAttention).toHaveBeenCalledWith(false);
    expect(onVerification).toHaveBeenCalledWith("all");
    expect(onQuery).toHaveBeenCalledWith("");
  });
});
