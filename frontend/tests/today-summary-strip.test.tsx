// @vitest-environment jsdom
// Strip ringkasan "Hari Ini" (desain ulang 2026-10-17) — kontrak markup & interaksi.
//
// Kenapa pakai jsdom, bukan renderToStaticMarkup: inti strip ini bukan bentuknya,
// melainkan "lompat ke kartunya". Jadi yang diuji di sini benar-benar diklik.
//
// Kontrak:
// - strip = <nav aria-label> berisi lima tombol (bukan div), supaya bisa
//   dijangkau papan tik dan pembaca layar tanpa perlakuan khusus;
// - tiap tombol membawa `data-today-target` = id kartu tujuan (satu sumber
//   dengan `summaryTiles().target`, bukan daftar id terpisah yang bisa basi);
// - aria-label menyebut label + nilai + catatan, jadi pembaca layar tidak
//   mendengar "tombol" tanpa isi;
// - melompat berarti menggulir ke kartu DAN memindahkan fokus ke kartu itu
//   (tanpa fokus, pengguna papan tik tetap tertinggal di strip);
// - gulir halus dihormati hanya bila pengguna tidak meminta gerak minimal.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";

import TodaySummary, { jumpToSection } from "../components/TodaySummary";
import type { SummaryTile } from "../lib/today";

const TILES: SummaryTile[] = [
  { key: "action", label: "Menunggu tindakan", value: "13", note: "1 sudah lewat tenggat", tone: "danger", target: "today-action" },
  { key: "batches", label: "Batch <48 jam", value: "2", note: "kedaluwarsa 1 batch (450 kg)", tone: "danger", target: "today-batches" },
  { key: "shortage", label: "Lokasi shortage", value: "1", note: "Total kekurangan 780 kg", tone: "warn", target: "today-shortage" },
  { key: "kpi", label: "KPI terisi", value: "5/7", note: "2 metrik belum ada data", tone: "warn", target: "today-kpi" },
  { key: "ledger", label: "Rantai audit", value: "Rantai utuh", note: "3.301 blok", tone: "ok", target: "today-ledger" },
];

let root: Root;
let host: HTMLDivElement;

function mount(tiles: SummaryTile[] = TILES, onJump = () => {}) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => {
    root.render(<TodaySummary tiles={tiles} onJump={onJump} />);
  });
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  vi.unstubAllGlobals();
});

describe("strip ringkasan — markup", () => {
  it("memakai nav berlabel dan lima tombol", () => {
    mount();
    const nav = host.querySelector("nav.today-summary");
    expect(nav).not.toBeNull();
    expect(nav!.getAttribute("aria-label")).toContain("Ringkasan");
    expect(host.querySelectorAll("button.today-tile")).toHaveLength(5);
  });

  it("urutan tile tetap dan setiap tile menunjuk kartu tujuan", () => {
    mount();
    const target = Array.from(host.querySelectorAll("button.today-tile")).map((b) =>
      b.getAttribute("data-today-target"),
    );
    expect(target).toEqual([
      "today-action",
      "today-batches",
      "today-shortage",
      "today-kpi",
      "today-ledger",
    ]);
  });

  it("tiap tombol menulis label, nilai, dan nada dari data", () => {
    mount();
    const pertama = host.querySelector('button[data-today-target="today-action"]')!;
    expect(pertama.textContent).toContain("Menunggu tindakan");
    expect(pertama.textContent).toContain("13");
    expect(pertama.className).toContain("today-tile-danger");
    const rantai = host.querySelector('button[data-today-target="today-ledger"]')!;
    expect(rantai.className).toContain("today-tile-ok");
  });

  it("nilai berupa frasa memakai kelas teks (font UI), angka tetap font data", () => {
    mount();
    const rantai = host.querySelector(
      'button[data-today-target="today-ledger"] .today-tile-value',
    )!;
    expect(rantai.textContent).toBe("Rantai utuh");
    expect(rantai.className).toContain("today-tile-value--teks");
    const angka = host.querySelector(
      'button[data-today-target="today-kpi"] .today-tile-value',
    )!;
    expect(angka.textContent).toBe("5/7");
    expect(angka.className).not.toContain("today-tile-value--teks");
  });

  it("tidak ada nilai karangan: tile '—' tetap tampil apa adanya", () => {
    mount([{ key: "batches", label: "Batch <48 jam", value: "—", note: null, tone: "none", target: "today-batches" }]);
    const tombol = host.querySelector("button.today-tile")!;
    expect(tombol.textContent).toContain("—");
    expect(tombol.className).toContain("today-tile-none");
  });
});

describe("strip ringkasan — interaksi", () => {
  it("klik memanggil onJump dengan id kartu tujuan", () => {
    const onJump = vi.fn();
    mount(TILES, onJump);
    const tombol = host.querySelector('button[data-today-target="today-shortage"]') as HTMLButtonElement;
    act(() => {
      tombol.click();
    });
    expect(onJump).toHaveBeenCalledWith("today-shortage");
  });

  it("jumpToSection menggulir ke kartu DAN memindahkan fokus ke kartu itu", () => {
    const kartu = document.createElement("article");
    kartu.id = "today-batches";
    kartu.tabIndex = -1;
    const gulir = vi.fn();
    (kartu as unknown as { scrollIntoView: unknown }).scrollIntoView = gulir;
    document.body.append(kartu);

    jumpToSection("today-batches");

    expect(gulir).toHaveBeenCalledTimes(1);
    expect(gulir.mock.calls[0][0]).toMatchObject({ block: "start" });
    expect(document.activeElement).toBe(kartu);
    kartu.remove();
  });

  it("gulir halus dimatikan saat pengguna meminta gerak minimal", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: q.includes("reduced-motion"),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    const kartu = document.createElement("article");
    kartu.id = "today-kpi";
    kartu.tabIndex = -1;
    const gulir = vi.fn();
    (kartu as unknown as { scrollIntoView: unknown }).scrollIntoView = gulir;
    document.body.append(kartu);

    jumpToSection("today-kpi");

    expect(gulir.mock.calls[0][0]).toMatchObject({ behavior: "auto" });
    kartu.remove();
  });
});
