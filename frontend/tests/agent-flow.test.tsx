import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import {
  ApiError,
  login,
  fetchDecisions,
  fetchDecisionTraces,
  approveAction,
  executeAction,
} from "../lib/api";
import { decodeRole, formatIDR } from "../lib/auth";
import StatusBadge from "../components/StatusBadge";
import RecommendationCard from "../components/RecommendationCard";
import AgentTraceViewer from "../components/AgentTraceViewer";
import ApprovalModal from "../components/ApprovalModal";
import DecisionActions from "../components/DecisionActions";

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("api client (kontrak backend aktual)", () => {
  it("login POST /auth/login dan mengembalikan token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ access_token: "jwt-abc" }), text: () => Promise.resolve(JSON.stringify({ access_token: "jwt-abc" })),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await login("sppg.head@demo.local", "pw");
    expect(result.access_token).toBe("jwt-abc");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/auth/login");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      email: "sppg.head@demo.local",
      password: "pw",
    });
  });

  it("fetchDecisions GET /decisions dengan Bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [] }), text: () => Promise.resolve(JSON.stringify({ items: [] })),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchDecisions("jwt-abc");
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/decisions");
    expect(init.headers.Authorization).toBe("Bearer jwt-abc");
  });

  it("fetchDecisionTraces GET /decisions/{id}/traces", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ decision_id: "d1", steps: [] }), text: () => Promise.resolve(JSON.stringify({ decision_id: "d1", steps: [] })),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchDecisionTraces("d1", "jwt-abc");
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/decisions/d1/traces"
    );
  });

  it("approve/execute POST dengan body dan Bearer", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}), text: () => Promise.resolve(JSON.stringify({})),
    });
    vi.stubGlobal("fetch", fetchMock);

    await approveAction("d1", true, "jwt-abc");
    const [approveUrl, approveInit] = fetchMock.mock.calls[0];
    expect(String(approveUrl)).toContain("/actions/approve");
    expect(JSON.parse(approveInit.body)).toEqual({
      decision_id: "d1",
      approved: true,
    });
    expect(approveInit.headers.Authorization).toBe("Bearer jwt-abc");

    await executeAction("d1", "jwt-abc");
    const [execUrl] = fetchMock.mock.calls[1];
    expect(String(execUrl)).toContain("/actions/execute");
  });

  it("HTTP error dilempar dengan status, bukan diam", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: "unauthorized" }), text: () => Promise.resolve(JSON.stringify({ detail: "unauthorized" })),
      })
    );
    // Audit M9: pesan galat = alasan server; status tetap terbaca dari properti.
    const galat = (await login("x", "y").catch((err) => err)) as ApiError;
    expect(galat).toBeInstanceOf(ApiError);
    expect(galat.status).toBe(401);
    expect(galat.message).toBe("unauthorized");
  });
});

describe("auth helper", () => {
  it("decodeRole membaca payload JWT (display-only)", () => {
    const payload = Buffer.from(
      JSON.stringify({ role: "bgn_monitor" })
    ).toString("base64url");
    const token = `h.${payload}.s`;
    expect(decodeRole(token)).toBe("bgn_monitor");
  });

  it("token rusak → null (bukan crash)", () => {
    expect(decodeRole("bukan-jwt")).toBeNull();
  });
});

describe("formatIDR", () => {
  it("menampilkan rupiah gaya Indonesia", () => {
    expect(formatIDR("16206000.00")).toBe("Rp16.206.000");
  });

  it("nilai kosong ditulis '—', bukan '-' (aturan repo)", () => {
    expect(formatIDR(null)).toBe("—");
    expect(formatIDR(undefined)).toBe("—");
    expect(formatIDR("bukan-angka")).toBe("—");
    // nol yang NYATA tetap Rp0 — nol bukan "tidak diketahui".
    expect(formatIDR(0)).toBe("Rp0");
  });
});

describe("StatusBadge (status tidak boleh ambigu)", () => {
  it("FAIL merah + label eksplisit", () => {
    const html = renderToStaticMarkup(<StatusBadge status="FAIL" />);
    expect(html).toContain("FAIL");
    expect(html).toContain("status-danger");
  });
  it("PASS hijau", () => {
    const html = renderToStaticMarkup(<StatusBadge status="PASS" />);
    expect(html).toContain("PASS");
    expect(html).toContain("status-safe");
  });
});

describe("RecommendationCard", () => {
  const decision = {
    decision_id: "d1",
    status: "pending_approval",
    quantity_kg: 600,
    safe_delivered_cost: 16206000,
    expires_at: "2026-10-06T13:00:00+00:00",
    valid: true,
  };

  it("menampilkan judul, SDC, status, expiry, dan badge mock", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={decision} mockSourced />
    );
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("Menunggu persetujuan");
    expect(html).toContain("Data Simulasi");
    expect(html).toContain("600");
  });

  it("mock badge hanya bila bersumber mock", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={decision} mockSourced={false} />
    );
    expect(html).not.toContain("Data Simulasi");
  });
});

describe("AgentTraceViewer (activity log aktual)", () => {
  const steps = [
    {
      step_name: "DETECT",
      tool_called: "supply.get+demand.get",
      input_summary: { commodity: "telur" },
      output_summary: { shortage: { location: "Jakarta" } },
      step_at: "2026-10-06T12:00:00+00:00",
    },
    {
      step_name: "VERIFY",
      tool_called: "verifier.rest",
      input_summary: {},
      output_summary: { verdict: "UNAVAILABLE" },
      step_at: "2026-10-06T12:00:01+00:00",
    },
  ];

  it("render langkah terurut + sebutan alat + timestamp", () => {
    const html = renderToStaticMarkup(<AgentTraceViewer steps={steps} />);
    expect(html.indexOf("DETECT")).toBeLessThan(html.indexOf("VERIFY"));
    // Slug internal tidak boleh tampil; yang dibaca pengguna adalah sebutannya.
    expect(html).not.toContain("supply.get+demand.get");
    expect(html).not.toContain("verifier.rest");
    expect(html).toContain("Ambil pasokan &amp; permintaan");
    expect(html).toContain("Layanan verifikator");
    expect(html).toContain("12:00:01");
  });

  it("slug alat yang dikenal diganti sebutan; yang tidak dikenal tidak ditampilkan", () => {
    const dikenal = renderToStaticMarkup(
      <AgentTraceViewer steps={[{ step_name: "VERIFY", tool_called: "evaluate_safety" }]} />
    );
    expect(dikenal).toContain("Periksa keamanan");
    expect(dikenal).not.toContain("evaluate_safety");

    // Slug teknis tanpa padanan manusia: baris alatnya tidak dirender sama sekali.
    const asing = renderToStaticMarkup(
      <AgentTraceViewer steps={[{ step_name: "ACT", tool_called: "sap_mock.create_purchase_order" }]} />
    );
    expect(asing).not.toContain("sap_mock.create_purchase_order");
    expect(asing).not.toContain("trace-tool");
  });

  it("belum memilih keputusan → dikatakan apa adanya, bukan 'tidak ada langkah'", () => {
    // WS-C (QA 16 Okt): dulu satu pesan untuk DUA keadaan berbeda — sebelum
    // pengguna memilih apa pun, layar sudah mengklaim "belum ada langkah agent
    // yang tercatat untuk keputusan ini", padahal keputusannya belum dipilih.
    // Pesan yang salah membuat orang mencari bug yang tidak ada.
    const html = renderToStaticMarkup(<AgentTraceViewer steps={[]} />);
    expect(html).toContain("Pilih keputusan");
    expect(html).not.toContain("Belum ada langkah agent");
  });

  it("keputusan dipilih tetapi kosong → empty state jelas, bukan blank", () => {
    const html = renderToStaticMarkup(
      <AgentTraceViewer steps={[]} decisionId="766366cf-3c19-404d-a846-cb3e4c1ac913" />
    );
    expect(html).toContain("Belum ada langkah agent");
  });
});

describe("ApprovalModal (friksi disengaja)", () => {
  it("menampilkan ringkasan sebelum tombol approve", () => {
    // S4-04: fixture memakai shape kanonik — verdict verifier hidup di
    // `verifier.verdict` (read model server), bukan field top-level feed.
    const html = renderToStaticMarkup(
      <ApprovalModal
        summary={{
          quantity_kg: 600,
          safe_delivered_cost: 16206000,
          verifier: { verdict: "consistent", verified_by: "verifier_agent" },
        }}
      />
    );
    expect(html).toContain("600");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("consistent");
    expect(html).toContain("Konfirmasi Approval");
  });

  it("tanpa approve-all massal", () => {
    const html = renderToStaticMarkup(
      <ApprovalModal summary={null} />
    );
    expect(html.toLowerCase()).not.toContain("approve all");
  });
});

describe("DecisionActions (role scope)", () => {
  it("approver melihat pemicu popup persetujuan (bukan tombol telanjang di kartu)", () => {
    // 2026-10-14: pilihan tindakan pindah ke popup — markup statis (popup
    // tertutup, dirender lewat portal) hanya memuat pemicunya. Isi menunya
    // diuji di tests/approval-menu.test.tsx.
    const html = renderToStaticMarkup(
      <DecisionActions decisionId="d1" role="sppg_head" status="pending_approval" token="t" />
    );
    expect(html).toContain("Kelola persetujuan");
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).not.toContain("read-only");
  });

  it("bgn_monitor read-only: tanpa pemicu approve/execute sama sekali", () => {
    const html = renderToStaticMarkup(
      <DecisionActions decisionId="d1" role="bgn_monitor" status="pending_approval" token="t" />
    );
    expect(html).not.toContain("Kelola persetujuan");
    expect(html).not.toContain('aria-haspopup="dialog"');
    expect(html).toContain("read-only");
  });
});
