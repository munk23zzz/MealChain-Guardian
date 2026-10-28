// @vitest-environment jsdom
//
// Kontrak drawer "Detail Keputusan" terhadap dokumen `01-detail-keputusan.md`.
// Yang dipin adalah HAL YANG DIBACA PENGGUNA, bukan hiasan:
//   §1  panel samping (dialog modal) dengan kepala = label + judul + status + id;
//   §2  urutan dua belas bagian (di sini: fakta dasar → biaya → PO → approval →
//       aksi → usulan → bukti), plus strip alur di paling atas;
//   §6.1 rumus di bawah angka turunan;
//   §6.2 tiga lapis biaya, bukan tabel datar;
//   §6.4 status PO sebagai langkah;
//   §6.5 bagian kosong tetap tampil dengan penjelasan, dan keputusan
//       administratif TIDAK menampilkan biaya/PO palsu.
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

const ADMINISTRATIF = {
  decision_id: "2ae7e0f9-1834-5baf-bb3d-e2e935b4f6e1",
  decision_type: "supplier_exclusion_restoration",
  status: "pending_approval",
  quantity_kg: null,
  safe_delivered_cost: null,
  supplier_name: "CV Ayam Kampung Cugenang",
  target_location: "Jakarta",
  expires_at: "2026-10-29T02:52:36Z",
};

const RINGKASAN_ADMIN = {
  decision_id: ADMINISTRATIF.decision_id,
  decision_type: ADMINISTRATIF.decision_type,
  status: "pending_approval",
  purchase_order: null,
  approval_requirement: { verdict: "consistent", min_approvals: 1, required_roles: [["sppg_head", "sppg_nutritionist"]] },
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
    chain: [],
    traces: [
      { step_at: "2026-10-28T07:50:00Z", step_name: "cek_kuota_sppg", tool_called: "check_quota", output_summary: "kuota tersisa 420 kg" },
    ],
    supplierContext: null,
    role: "sppg_head",
    // token null: tidak ada permintaan jaringan dari dalam drawer.
    token: null,
    now: NOW,
    ...over,
  };
  act(() => root!.render(<DecisionDrawer {...props} />));
  return props;
}

/**
 * Render ulang pada root yang SAMA — meniru halaman yang membuka popup untuk
 * keputusan berbeda atau dengan tombol berbeda tanpa melepas komponennya.
 * Tes "mount segar" tidak bisa menangkap bug panel yang tertinggal dari
 * pembukaan sebelumnya.
 */
function renderUlang(over: Record<string, unknown> = {}) {
  const props: any = {
    open: true,
    onClose: vi.fn(),
    decision: PEMBELIAN,
    summary: RINGKASAN_PEMBELIAN,
    chain: [],
    traces: [{ step_at: "2026-10-28T07:50:00Z", step_name: "cek_kuota_sppg", tool_called: "check_quota", output_summary: "kuota tersisa 420 kg" }],
    supplierContext: null,
    role: "sppg_head",
    token: null,
    now: NOW,
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

describe("kepala drawer (§1 & §2 butir 1)", () => {
  it("memakai panel samping: dialog modal berlabel, label kecil + judul + status + id", () => {
    mount();
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.className).toContain("popup-keputusan");
    expect(dialog?.getAttribute("aria-modal")).toBe("true");
    // label kecil
    expect(document.querySelector(".popup-eyebrow")?.textContent).toBe("Detail Keputusan");
    // judul dalam bahasa pengguna (bukan slug mentah)
    const judul = document.getElementById("popup-keputusan-judul")?.textContent ?? "";
    expect(judul).toContain("Pengadaan");
    expect(judul).not.toContain("_");
    // pil status + potongan id 8 karakter
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

describe("strip alur (§2 butir 2)", () => {
  it("keputusan pembelian memakai empat langkah", () => {
    mount();
    const label = Array.from(document.querySelectorAll(".detail-alur .detail-step-label")).map(
      (e) => e.textContent
    );
    expect(label).toEqual(["Usulan", "Verifikasi", "Approval", "Dibeli"]);
  });

  it("keputusan administratif memakai tiga langkah", () => {
    mount({ decision: ADMINISTRATIF, summary: RINGKASAN_ADMIN });
    const label = Array.from(document.querySelectorAll(".detail-alur .detail-step-label")).map(
      (e) => e.textContent
    );
    expect(label).toEqual(["Usulan", "Persetujuan", "Diberlakukan"]);
  });
});

describe("urutan bagian (§2)", () => {
  it("fakta dasar → biaya → PO → approval → usulan → bukti", () => {
    mount();
    const bagian = judulBagian();
    const posisi = (judul: string) => bagian.findIndex((b) => (b ?? "").startsWith(judul));
    expect(posisi("Fakta dasar")).toBeGreaterThanOrEqual(0);
    expect(posisi("Fakta dasar")).toBeLessThan(posisi("Biaya"));
    expect(posisi("Biaya")).toBeLessThan(posisi("Pesanan pembelian"));
    expect(posisi("Pesanan pembelian")).toBeLessThan(posisi("Kewajiban persetujuan"));
    expect(posisi("Kewajiban persetujuan")).toBeLessThan(posisi("Usulan"));
    expect(posisi("Usulan")).toBeLessThan(posisi("Bukti"));
  });
});

describe("biaya: tiga lapis + rumus (§6.1 & §6.2)", () => {
  it("menampilkan tiga lapis dengan nilai dan rumus per kg", () => {
    mount();
    const judul = Array.from(document.querySelectorAll(".detail-layer dt")).map((e) => e.textContent);
    expect(judul).toEqual([
      "Dibayar ke pemasok",
      "Tambahan sampai barang tiba",
      "Tambahan karena risiko",
    ]);
    const teks = document.body.textContent ?? "";
    expect(teks).toContain("Rp7.358.754");
    expect(teks).toContain("Rp7.358.754 ÷ 600 kg");
    expect(teks).toContain("Rp159.593");
    expect(teks).toContain("Rp88.305");
    expect(teks).toContain("Rp7.606.652");
  });

  it("menampilkan perbandingan harga setempat", () => {
    mount();
    const teks = document.body.textContent ?? "";
    expect(teks).toContain("Lebih murah");
    expect(teks).toContain("7,2%");
  });

  it("keputusan administratif tidak merender biaya maupun PO sama sekali", () => {
    mount({ decision: ADMINISTRATIF, summary: RINGKASAN_ADMIN });
    // Dok 01 §4: bagian ini TIDAK dirender, bukan dirender lalu dijelaskan.
    const teks = document.body.textContent ?? "";
    expect(teks).not.toContain("Biaya, harga & penerimaan");
    expect(teks).not.toContain("Pesanan pembelian");
    expect(document.querySelectorAll(".detail-layer").length).toBe(0);
    expect(document.querySelectorAll(".detail-po").length).toBe(0);
  });
});

describe("PO sebagai langkah (§6.4)", () => {
  it("menampilkan tiga titik dengan tahap 'Terkirim' aktif untuk status submitted", () => {
    mount();
    const langkah = Array.from(document.querySelectorAll(".detail-po-step")).map((e) => ({
      label: e.textContent?.trim(),
      state: e.className,
    }));
    expect(langkah.map((l) => l.label)).toEqual(["Terbit", "Terkirim", "Diterima SAP"]);
    expect(langkah[0].state).toContain("selesai");
    expect(langkah[1].state).toContain("kini");
  });

  it("mencetak status PO dalam bahasa Indonesia, bukan status mentah", () => {
    mount();
    // Dibatasi ke seksi PO: bagian lain (ApprovalOverview) masih mencetak status
    // mentah dan itu di luar lingkup drawer ini.
    const seksi = document.querySelector(".detail-po")?.closest(".detail-sec");
    expect(seksi).not.toBeNull();
    const teks = seksi?.textContent ?? "";
    expect(teks).toContain("Status PO");
    expect(teks).toContain("Terkirim ke SAP");
    expect(teks).not.toContain("submitted");
  });

  it("menyebut nomor PO dan bahwa harga satuan = harga terkirim", () => {
    mount();
    const teks = document.body.textContent ?? "";
    expect(teks).toContain("MC-B5B391FE89E1");
    expect(teks).toContain("bukan harga beli");
  });
});

describe("tampilan awal dipilih dari kartu, bukan dari tab di popup", () => {
  it("bawaan: popup dibuka pada rincian", () => {
    mount();
    expect(document.querySelectorAll(".detail-layers").length).toBeGreaterThan(0);
    expect(document.querySelectorAll(".agent-console").length).toBe(0);
    // Tidak ada tab di dalam popup: pemilihan dilakukan di kartu feed.
    expect(document.querySelector(".popup-tabs")).toBeNull();
    expect(document.querySelectorAll(".popup-tab").length).toBe(0);
    // Panel persetujuan belum terbuka — tombol pemicunya saja yang tampil.
    expect(document.querySelector(".aksi-panel")).toBeNull();
  });
});

// Jejak agen dulu tombol kedua di kartu feed. Sekarang ia tautan tenang di
// kepala popup: kartu hanya menawarkan dua pekerjaan (Rincian & Persetujuan).
describe("tautan jejak agen di kepala popup", () => {
  it("menulis 'Jejak agen (N)' di kepala popup, bukan di badan", () => {
    mount();
    const tautan = document.querySelector(".detail-tautan") as HTMLButtonElement;
    expect(tautan).not.toBeNull();
    expect(tautan.textContent).toBe("Jejak agen (1)");
    // Kepala popup (meta), bukan isi: nav ini tidak ikut tergulir bersama isi.
    expect(tautan.closest(".popup-meta")).not.toBeNull();
    expect(tautan.closest(".popup-body")).toBeNull();
    // Navigasi, bukan tombol tekan: tidak ada status terpilih.
    expect(tautan.getAttribute("aria-pressed")).toBeNull();
  });

  it("mengalihkan ke jejak agen lalu kembali ke rincian", () => {
    mount();
    act(() => (document.querySelector(".detail-tautan") as HTMLButtonElement).click());
    expect(document.querySelectorAll(".agent-console").length).toBe(1);
    expect(document.querySelectorAll(".detail-layers").length).toBe(0);
    const kembali = document.querySelector(".detail-tautan") as HTMLButtonElement;
    expect(kembali.textContent).toBe("Kembali ke rincian");
    // Satu elemen untuk dua arah: label berganti di tempat, jadi fokus keyboard
    // tidak hilang ke <body> saat berpindah tampilan.
    expect(document.querySelectorAll(".detail-tautan").length).toBe(1);
    act(() => kembali.click());
    expect(document.querySelectorAll(".agent-console").length).toBe(0);
    expect(document.querySelectorAll(".detail-layers").length).toBeGreaterThan(0);
  });

  it("tanpa jejak tercatat: tidak ada tautan yang menjanjikan halaman kosong", () => {
    mount({ traces: [] });
    expect(document.querySelector(".detail-tautan")).toBeNull();
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
    // Satu jendela saja: satu backdrop, satu dialog.
    expect(document.querySelectorAll(".popup-backdrop").length).toBe(1);
    expect(document.querySelectorAll('[role="dialog"]').length).toBe(1);
    expect(document.querySelector(".popup-governance")).toBeNull();
  });

  it("panel terbuka tanpa tombol pemicu ganda, dan angka tetap terbaca", () => {
    mount({ tampilanAwal: "persetujuan" });
    // Panel punya "Tutup panel" sendiri; pemicu yang sama tidak dirender dua kali.
    expect(document.querySelector(".decision-actions > button")).toBeNull();
    const panel = document.querySelector("#aksi-panel");
    expect(panel).not.toBeNull();
    expect(panel!.getAttribute("aria-label")).toContain("persetujuan");
    // Pita angka & rincian tidak diganti: panel adalah bagiannya.
    expect(document.querySelectorAll(".detail-kpi").length).toBe(1);
    expect(document.querySelectorAll(".detail-layers").length).toBeGreaterThan(0);
  });

  it("kembali dari jejak agen tidak membuka panel itu lagi", () => {
    mount({ tampilanAwal: "persetujuan" });
    act(() => (document.querySelector(".detail-tautan") as HTMLButtonElement).click());
    expect(document.querySelectorAll(".agent-console").length).toBe(1);
    act(() => (document.querySelector(".detail-tautan") as HTMLButtonElement).click());
    expect(document.querySelectorAll(".agent-console").length).toBe(0);
    // Panel tidak membuka dirinya sendiri di atas isi yang sedang dibaca.
    expect(document.querySelector(".aksi-panel")).toBeNull();
  });
});

describe("persetujuan tanpa popup di dalam popup", () => {
  it("membuka konfirmasi sebagai panel di dalam popup yang sama", () => {
    mount();
    const pemicu = document.querySelector(".decision-actions > button") as HTMLButtonElement;
    expect(pemicu).not.toBeNull();
    act(() => pemicu.click());
    // Tidak ada jendela kedua: satu backdrop, satu dialog.
    expect(document.querySelectorAll(".popup-backdrop").length).toBe(1);
    expect(document.querySelectorAll('[role="dialog"]').length).toBe(1);
    const panel = document.querySelector(".aksi-panel");
    expect(panel).not.toBeNull();
    // Panel itu hidup di dalam badan popup detail, bukan di atasnya.
    expect(panel!.closest(".popup-body")).not.toBeNull();
    expect(document.querySelector(".popup-governance")).toBeNull();
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

  it("isi dua kolom, dengan bagian lebar penuh untuk alur/aksi/usulan/bukti", () => {
    expect(css).toContain(".popup-keputusan .popup-body {");
    expect(css).toMatch(/\.popup-keputusan \.popup-body \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
    expect(css).toMatch(/\.detail-sec--full \{ grid-column: 1 \/ -1; \}/);
  });
});

// Wiring halaman: klik kartu membuka drawer, bukan pindah tab.
describe("wiring app/page.tsx", () => {
  const sumber = readFileSync(join(__dirname, "..", "app", "page.tsx"), "utf8");
  const kartuFeed = sumber.slice(sumber.indexOf('className="feed"'), sumber.indexOf("<Pager"));

  it("memasang DecisionDrawer dengan summary keputusan", () => {
    expect(sumber).toContain('import DecisionDrawer from "../components/DecisionDrawer"');
    expect(sumber).toMatch(/<DecisionDrawer[\s\S]*summary=\{approvalSummary\}/);
    expect(sumber).toContain("returnFocusRef={popupTriggerRef}");
  });

  it("kartu feed membuka drawer, tidak memindahkan tab", () => {
    expect(kartuFeed).toContain("bukaPopupKeputusan(");
    expect(kartuFeed).not.toContain('setTab("evidence")');
  });

  it("kartu feed memberi dua tombol: rincian dan persetujuan", () => {
    // Pembungkus <div>: tombol tidak boleh bersarang di dalam tombol.
    expect(kartuFeed).toContain('className="rec-baris"');
    expect(kartuFeed).not.toContain('className="link-button"');
    expect(kartuFeed).toContain("onBuka={(tampilan, pemicu) =>");
    expect(kartuFeed).toContain("tampilan");
    // Jejak agen bukan pilihan tombol kartu lagi.
    expect(kartuFeed).not.toContain('"jejak"');
  });

  it("tombol Persetujuan hanya tampil bagi yang berwenang menyetujui", () => {
    // Aturannya SATU: visibleActions, bukan daftar peran kedua di halaman
    // (daftar duplikat = dua kebenaran yang cepat menyimpang).
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
    expect(sumber).toMatch(/bukaPopupKeputusan\(\s*[\s\S]{0,120}tampilan\s*\)/);
  });
});

describe("panel persetujuan mengikuti pilihan pembukaan terakhir", () => {
  it('buka via "Persetujuan" menampilkan panel; buka ulang via "Rincian" menutupnya', () => {
    mount({ tampilanAwal: "persetujuan" });
    expect(document.querySelectorAll(".aksi-panel").length).toBe(1);

    // tutup popup (komponen tetap terpasang di halaman)
    renderUlang({ open: false, tampilanAwal: "persetujuan" });
    expect(document.querySelector(".popup-keputusan")).toBeNull();

    // buka lagi lewat tombol "Rincian" pada keputusan/komponen yang sama
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
    expect(teks).toContain("Tutup panel ini untuk kembali membaca rincian.");
  });
});

describe("dokumen PO (PDF)", () => {
  it("keputusan yang sudah disetujui menawarkan unduhan dokumen PO", () => {
    mount({
      decision: { ...PEMBELIAN, status: "approved" },
      summary: { ...RINGKASAN_PEMBELIAN, status: "approved" },
      token: "token-uji",
    });
    const tombol = Array.from(document.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Unduh dokumen PO")
    );
    expect(tombol).not.toBeUndefined();
  });

  it("keputusan yang masih menunggu persetujuan tidak menawarkan tombol itu", () => {
    mount({ token: "token-uji" });
    const tombol = Array.from(document.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Unduh dokumen PO")
    );
    expect(tombol).toBeUndefined();
  });

  it("tanpa sesi tulis tombolnya juga tidak ditawarkan (tidak ada token)", () => {
    mount({
      decision: { ...PEMBELIAN, status: "executed" },
      summary: { ...RINGKASAN_PEMBELIAN, status: "executed" },
      token: null,
    });
    const tombol = Array.from(document.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Unduh dokumen PO")
    );
    expect(tombol).toBeUndefined();
  });
});
