// @vitest-environment jsdom
//
// Kontrak popup "Detail Keputusan" dari kartu Recommendation Feed.
//
// 29 Okt 2026 — seleksi blok kembar Recommendations ↔ Decision & Evidence
// ("Paket B"). Popup ini sekarang popup AKSI CEPAT, bukan salinan dossier:
//   - TETAP: kepala (label + judul + status + id), angka ringkas, tombol
//     putuskan, kewajiban persetujuan, satu tautan "Buka halaman lengkap";
//   - DICABUT: strip alur, fakta dasar, rincian biaya, PO, pemasok, jejak agen,
//     jejak iterasi, usulan, unduhan JSON/PDF.
// Alasan pencabutan: blok itu milik halaman Decision & Evidence (satu keputusan,
// satu dossier). Tes di bawah menjaga agar salinan itu tidak tumbuh kembali.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

import DecisionDrawer from "../components/DecisionDrawer";

const NOW = new Date("2026-10-28T08:00:00Z");

const PEMBELIAN = {
  decision_id: "b5b391fe-89e1-5a5c-970a-3314bff2e5dc",
  decision_type: "supplier_procurement",
  status: "pending_approval",
  quantity_kg: 600,
  safe_delivered_cost: 7606651.97,
  commodity: "beras",
  supplier: { id: "s1", name: "UD Rorotan Jaya Beras" },
  target_location: "Jakarta",
  expires_at: "2026-10-29T02:52:36Z",
  demo_case: "shortage-darurat",
  market_reference: { source: "pihps_reference", price_per_kg: 13657.02 },
};

const RINGKASAN_PEMBELIAN = {
  decision_id: PEMBELIAN.decision_id,
  decision_type: "supplier_procurement",
  status: "pending_approval",
  quantity_kg: 600,
  safe_delivered_cost: 7606651.97,
  commercial_cost: {
    purchase_total: "7358754.00",
    transport_total: "9592.92",
    handling_total: "150000.00",
    invoice_total: "7518346.92",
    invoice_unit_price: "12530.58",
    expected_loss: "88305.05",
    freshness_risk: "0.00",
    safety_penalty: "0.00",
    sdc_total: "7606651.97",
    sdc_unit_price: "12677.75",
  },
  purchase_order: { po_number: "MC-B5B391FE89E1", status: "submitted", created_at: "2026-10-28T07:57:22Z" },
  verifier: { verdict: "consistent", verified_by: "verifier_agent" },
  approval_requirement: { verdict: "consistent", min_approvals: 2, required_roles: [["sppg_head"], ["sppg_nutritionist"]] },
  approvals: [],
  can_approve: true,
  can_reject: true,
  can_execute: false,
  blocking_reasons: [],
  approver_roles: ["sppg_head", "sppg_nutritionist"],
};

let root: Root | null = null;
let host: HTMLDivElement | null = null;

function mount(over: Record<string, unknown> = {}) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  const props: any = {
    open: true,
    onClose: vi.fn(),
    decision: PEMBELIAN,
    summary: RINGKASAN_PEMBELIAN,
    role: "sppg_head",
    // token null: tidak ada permintaan jaringan dari dalam popup.
    token: null,
    now: NOW,
    onOpenFullPage: vi.fn(),
    ...over,
  };
  act(() => root!.render(<DecisionDrawer {...props} />));
  return props;
}

/**
 * Render ulang pada root yang SAMA — meniru halaman yang membuka popup untuk
 * keputusan berbeda atau dengan tombol berbeda tanpa melepas komponennya.
 */
function renderUlang(over: Record<string, unknown> = {}) {
  const props: any = {
    open: true,
    onClose: vi.fn(),
    decision: PEMBELIAN,
    summary: RINGKASAN_PEMBELIAN,
    role: "sppg_head",
    token: null,
    now: NOW,
    onOpenFullPage: vi.fn(),
    ...over,
  };
  act(() => root!.render(<DecisionDrawer {...props} />));
  return props;
}

function judulBagian() {
  return Array.from(document.querySelectorAll(".detail-h")).map((e) => e.textContent?.trim());
}

afterEach(() => {
  act(() => root?.unmount());
  root = null;
  host?.remove();
  host = null;
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

describe("kepala popup", () => {
  it("dialog modal berlabel: label kecil + judul + status + potongan id", () => {
    mount();
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.className).toContain("popup-keputusan");
    expect(dialog?.getAttribute("aria-modal")).toBe("true");
    expect(document.querySelector(".popup-eyebrow")?.textContent).toBe("Detail Keputusan");
    const judul = document.getElementById("popup-keputusan-judul")?.textContent ?? "";
    expect(judul).toContain("Pengadaan");
    expect(judul).not.toContain("_");
    expect(document.querySelector(".popup-meta .badge")).not.toBeNull();
    expect(document.querySelector(".detail-id")?.textContent).toBe("#b5b391fe");
  });

  it("menutup lewat Escape dan klik backdrop", () => {
    const props = mount();
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(props.onClose).toHaveBeenCalledTimes(1);
    const backdrop = document.querySelector(".popup-backdrop") as HTMLElement;
    act(() => backdrop.dispatchEvent(new MouseEvent("mousedown", { bubbles: true })));
    expect(props.onClose).toHaveBeenCalledTimes(2);
  });
});

describe("isi popup = aksi cepat, bukan dossier", () => {
  it("hanya memuat tiga bagian: angka ringkas, putuskan, kewajiban persetujuan", () => {
    mount();
    expect(judulBagian()).toEqual([
      "Putuskan sekarang",
      // Judul kewajiban + catatan ringkasnya: "Kewajiban persetujuan 0 dari 2 disetujui"
      "Kewajiban persetujuan 0 dari 2 disetujui",
    ]);
  });

  it("pita angka tetap ada: jumlah, harga terkirim, dan pembanding acuan", () => {
    mount();
    expect(document.querySelectorAll(".detail-kpi").length).toBe(1);
    const teks = document.querySelector(".detail-kpi")?.textContent ?? "";
    expect(teks).toContain("Jumlah");
    expect(teks).toContain("600 kg");
    expect(teks).toContain("Harga terkirim");
    expect(teks).toContain("Rp12.678/kg");
    expect(teks).toContain("Dibanding harga acuan");
  });

  it("blok dossier TIDAK disalin lagi: alur, fakta, biaya, PO, pemasok, jejak, usulan", () => {
    mount();
    const teks = document.body.textContent ?? "";
    // Setiap judul di bawah ini punya rumahnya di halaman Decision & Evidence.
    for (const judul of [
      "Alur keputusan",
      "Fakta dasar",
      "Biaya, harga & penerimaan",
      "Pesanan pembelian",
      "Catatan verifier",
      "Usulan",
      "Jejak iterasi",
      "Jejak agen",
      "Bukti & audit",
      "Pemasok",
      "Konteks angka",
    ]) {
      expect(teks, `"${judul}" tidak boleh dirender di popup`).not.toContain(judul);
    }
    expect(document.querySelector(".detail-alur")).toBeNull();
    expect(document.querySelector(".detail-layers")).toBeNull();
    expect(document.querySelector(".detail-po")).toBeNull();
    expect(document.querySelector(".agent-console")).toBeNull();
    expect(document.querySelector(".detail-tautan")).toBeNull();
  });

  it("tidak menawarkan unduhan dari popup (ekspor milik halaman bukti)", () => {
    mount({ token: "token-uji" });
    const label = Array.from(document.querySelectorAll("button")).map((b) => b.textContent ?? "");
    expect(label.some((t) => t.includes("Unduh bukti"))).toBe(false);
    expect(label.some((t) => t.includes("Unduh dokumen PO"))).toBe(false);
  });

  it("satu tautan keluar: 'Buka halaman lengkap' memanggil onOpenFullPage", () => {
    const props = mount();
    const tombol = Array.from(document.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Buka halaman lengkap")
    );
    expect(tombol).not.toBeUndefined();
    act(() => tombol!.click());
    expect(props.onOpenFullPage).toHaveBeenCalledWith(PEMBELIAN.decision_id);
    expect(document.body.textContent).toContain("Decision & Evidence");
  });

  it("tanpa onOpenFullPage, tautan keluar tidak dirender", () => {
    mount({ onOpenFullPage: undefined });
    const label = Array.from(document.querySelectorAll("button")).map((b) => b.textContent ?? "");
    expect(label.some((t) => t.includes("Buka halaman lengkap"))).toBe(false);
  });

  it("menyebut akibat persetujuan dalam satu kalimat (bukan tabel)", () => {
    mount();
    const teks = document.querySelector(".detail-setelah")?.textContent ?? "";
    expect(teks.length).toBeGreaterThan(10);
    expect(teks).toContain("PO MC-B5B391FE89E1 sudah terbit");
  });
});

// Tombol "Persetujuan" di kartu harus mendaratkan pengguna pada panelnya, bukan
// pada kepala popup dengan panel tersembunyi jauh di bawah.
describe('tampilanAwal="persetujuan": panel langsung terbuka', () => {
  it("panel persetujuan sudah terbuka di dalam popup yang sama", () => {
    mount({ tampilanAwal: "persetujuan" });
    const panel = document.querySelector(".aksi-panel");
    expect(panel).not.toBeNull();
    expect(panel!.closest(".popup-body")).not.toBeNull();
    expect(document.querySelectorAll(".popup-backdrop").length).toBe(1);
    expect(document.querySelectorAll('[role="dialog"]').length).toBe(1);
  });

  it("panel terbuka tanpa tombol pemicu ganda, dan angka tetap terbaca", () => {
    mount({ tampilanAwal: "persetujuan" });
    expect(document.querySelector(".decision-actions > button")).toBeNull();
    const panel = document.querySelector("#aksi-panel");
    expect(panel).not.toBeNull();
    expect(panel!.getAttribute("aria-label")).toContain("persetujuan");
    // Pita angka tidak diganti: panel adalah bagiannya.
    expect(document.querySelectorAll(".detail-kpi").length).toBe(1);
  });
});

describe("persetujuan tanpa popup di dalam popup", () => {
  it("membuka konfirmasi sebagai panel di dalam popup yang sama", () => {
    mount();
    const pemicu = document.querySelector(".decision-actions > button") as HTMLButtonElement;
    expect(pemicu).not.toBeNull();
    act(() => pemicu.click());
    expect(document.querySelectorAll(".popup-backdrop").length).toBe(1);
    expect(document.querySelectorAll('[role="dialog"]').length).toBe(1);
    const panel = document.querySelector(".aksi-panel");
    expect(panel).not.toBeNull();
    expect(panel!.closest(".popup-body")).not.toBeNull();
    expect(pemicu.getAttribute("aria-controls")).toBe("aksi-panel");
  });
});

// Bentuk panel: POPUP DI TENGAH (permintaan pemilik), bukan panel samping.
describe("bentuk: popup di tengah, bukan drawer samping", () => {
  const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");
  const mulai = css.indexOf(".popup-keputusan {");
  const aturan = css.slice(mulai, css.indexOf("}", mulai));

  it("panel dibatasi lebar 920 px dan tidak menempel ke tepi kanan layar", () => {
    expect(aturan).toContain("width: min(920px, 100%)");
    expect(aturan).toContain("max-height: min(90vh, 880px)");
    expect(css).not.toContain(".popup-backdrop:has(> .popup-keputusan)");
    expect(css).not.toMatch(/\.popup-keputusan\s*\{[^}]*100dvh/);
  });

  it("isi dua kolom, dengan bagian lebar penuh", () => {
    expect(css).toContain(".popup-keputusan .popup-body {");
    expect(css).toMatch(
      /\.popup-keputusan \.popup-body \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/
    );
    expect(css).toMatch(/\.detail-sec--full \{ grid-column: 1 \/ -1; \}/);
  });
});

// Wiring halaman: klik kartu membuka popup, bukan pindah tab.
describe("wiring app/page.tsx", () => {
  const sumber = readFileSync(join(__dirname, "..", "app", "page.tsx"), "utf8");
  const kartuFeed = sumber.slice(sumber.indexOf('className="feed"'), sumber.indexOf("<Pager"));

  it("memasang DecisionDrawer dengan summary keputusan", () => {
    expect(sumber).toContain('import DecisionDrawer from "../components/DecisionDrawer"');
    expect(sumber).toMatch(/<DecisionDrawer[\s\S]*summary=\{approvalSummary\}/);
    expect(sumber).toContain("returnFocusRef={popupTriggerRef}");
  });

  it("tidak lagi mengoper data dossier ke popup", () => {
    // Seleksi 29 Okt 2026: chain/traces/supplierContext milik halaman bukti.
    const blok = sumber.slice(sumber.indexOf("<DecisionDrawer"), sumber.indexOf("/>", sumber.indexOf("<DecisionDrawer")));
    expect(blok).not.toContain("chain={");
    expect(blok).not.toContain("traces={");
    expect(blok).not.toContain("supplierContext={");
    expect(blok).toContain("onOpenFullPage=");
  });

  it("kartu feed membuka popup, tidak memindahkan tab", () => {
    expect(kartuFeed).toContain("bukaPopupKeputusan(");
    expect(kartuFeed).not.toContain('setTab("evidence")');
  });

  it("kartu feed memberi dua tombol: rincian dan persetujuan", () => {
    expect(kartuFeed).toContain('className="rec-baris"');
    expect(kartuFeed).toContain("onBuka={(tampilan, pemicu) =>");
    // Jejak agen bukan pilihan tombol kartu.
    expect(kartuFeed).not.toContain('"jejak"');
  });

  it("tombol Persetujuan hanya tampil bagi yang berwenang menyetujui", () => {
    expect(sumber).toContain('import { visibleActions } from "../components/DecisionActions"');
    expect(kartuFeed).toContain('visibleActions(role ?? "", String(d.status ?? ""))');
    expect(kartuFeed).toContain("const bolehSetujui = !aksi.readOnly && aksi.approve");
    expect(kartuFeed).toContain("tampilPersetujuan={bolehSetujui}");
  });

  it("popup menerima tampilan pilihan kartu", () => {
    expect(sumber).toContain(
      'const [popupTampilan, setPopupTampilan] = useState<"rincian" | "persetujuan">("rincian")'
    );
    expect(sumber).toContain("tampilanAwal={popupTampilan}");
    expect(sumber).toMatch(/bukaPopupKeputusan\(\s*[\s\S]{0,140}tampilan\s*\)/);
  });
});

describe("panel persetujuan mengikuti pilihan pembukaan terakhir", () => {
  it('buka via "Persetujuan" menampilkan panel; buka ulang via "Rincian" menutupnya', () => {
    mount({ tampilanAwal: "persetujuan" });
    expect(document.querySelectorAll(".aksi-panel").length).toBe(1);

    renderUlang({ open: false, tampilanAwal: "persetujuan" });
    expect(document.querySelector(".popup-keputusan")).toBeNull();

    renderUlang({ open: true, tampilanAwal: "rincian" });
    expect(document.querySelectorAll(".popup-keputusan").length).toBe(1);
    expect(document.querySelectorAll(".aksi-panel").length).toBe(0);
  });

  it('sesudah membaca rincian, buka via "Persetujuan" tetap membuka panel', () => {
    mount({ tampilanAwal: "rincian" });
    expect(document.querySelectorAll(".aksi-panel").length).toBe(0);

    renderUlang({ open: false, tampilanAwal: "rincian" });
    renderUlang({ open: true, tampilanAwal: "persetujuan" });
    expect(document.querySelectorAll(".aksi-panel").length).toBe(1);
    expect(document.querySelectorAll(".popup-backdrop").length).toBe(1);
    expect(document.querySelectorAll('[role="dialog"]').length).toBe(1);
  });

  it("panel inline tidak lagi menyuruh menekan Esc untuk menutup jendela", () => {
    mount({ tampilanAwal: "persetujuan" });
    const teks = document.querySelector(".aksi-panel")?.textContent ?? "";
    expect(teks).not.toContain("Tekan Esc");
  });
});
