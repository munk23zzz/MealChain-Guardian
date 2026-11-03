// @vitest-environment jsdom
// WS-D (QA 16 Okt): nav sidebar punya 10 tombol, dan tab yang sedang terbuka
// HANYA ditandai kelas CSS (`.side-tab-active`). Kelas CSS tidak terlihat oleh
// pembaca layar, jadi tidak ada satu pun sinyal bahwa "bagian ini yang sedang
// kamu lihat". Ditambahkan `aria-current="page"` — nilai standar untuk item
// navigasi yang sedang terbuka.
//
// Nav ini dulu ditulis inline di app/page.tsx (1305 baris). Dipindahkan ke
// components/SideNav.tsx supaya bisa diuji sebagai komponen sungguhan, bukan
// lewat pencocokan teks sumber seperti tes lain yang mengawasi page.tsx.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";

import SideNav, { type NavItem } from "../components/SideNav";
import type { NavId } from "../components/NavIcon";

const ITEMS: NavItem[] = [
  { id: "today", label: "Hari Ini" },
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Decision & Evidence", title: "Bukti & keputusan" },
];

let root: Root;
let host: HTMLDivElement;

function mount(active: NavId = "overview", collapsed = false, onSelect = vi.fn()) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() =>
    root.render(
      <SideNav items={ITEMS} active={active} collapsed={collapsed} onSelect={onSelect} />
    )
  );
  return onSelect;
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
});

describe("SideNav — tab mana yang sedang terbuka", () => {
  it("tab aktif ditandai aria-current='page'", () => {
    mount("overview");
    const current = host.querySelectorAll('[aria-current="page"]');
    expect(current).toHaveLength(1);
    expect(current[0].textContent).toContain("Overview");
  });

  it("tab lain TIDAK ditandai — satu sinyal, bukan sepuluh", () => {
    mount("overview");
    const tab = Array.from(host.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Hari Ini")
    );
    expect(tab?.hasAttribute("aria-current")).toBe(false);
  });

  it("berpindah tab memindahkan tandanya, tidak menumpuk", () => {
    mount("evidence");
    const current = host.querySelectorAll('[aria-current="page"]');
    expect(current).toHaveLength(1);
    expect(current[0].textContent).toContain("Decision & Evidence");
    expect(current[0].getAttribute("aria-current")).toBe("page");
  });

  it("penanda visual lama tetap ada (jangan menukar sinyal, tambahkan)", () => {
    mount("overview");
    const aktif = host.querySelectorAll(".side-tab-active");
    expect(aktif).toHaveLength(1);
    // Kelas dan aria-current harus menunjuk tab yang SAMA — dua penanda yang
    // menyimpang lebih buruk daripada satu.
    expect(aktif[0].getAttribute("aria-current")).toBe("page");
  });
});

describe("SideNav — perilaku yang tidak boleh berubah", () => {
  it("mengklik tab memanggil onSelect dengan id tab itu", () => {
    const onSelect = mount("overview");
    const tab = Array.from(host.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Decision & Evidence")
    ) as HTMLButtonElement;
    act(() => tab.click());
    expect(onSelect).toHaveBeenCalledWith("evidence");
  });

  it("nav masih bernama, dan tombolnya bertipe button", () => {
    mount();
    const nav = host.querySelector("nav");
    expect(nav?.getAttribute("aria-label")).toBe("Bagian konsol");
    const tabs = host.querySelectorAll("button");
    expect(tabs).toHaveLength(3);
    tabs.forEach((t) => expect(t.getAttribute("type")).toBe("button"));
  });

  it("rail diciutkan → label dipakai sebagai title; terbuka → title khusus", () => {
    mount("overview", true);
    const ciut = Array.from(host.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Hari Ini")
    );
    expect(ciut?.getAttribute("title")).toBe("Hari Ini");
    act(() => root.unmount());
    host.remove();

    mount("overview", false);
    const terbuka = Array.from(host.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Decision & Evidence")
    );
    expect(terbuka?.getAttribute("title")).toBe("Bukti & keputusan");
  });
});
