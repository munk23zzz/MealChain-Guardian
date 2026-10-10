// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SupplierExclusionView } from "../components/SupplierExclusionPanel";
import type { SupplierContext, SupplierExclusion } from "../lib/supplier-exclusions";

const exclusion: SupplierExclusion = {
  id: "ex1", supplier_id: "sup", scope_location_id: "loc", status: "active",
  reason: "Old issue", evidence_refs: [{ type: "batch", id: "old" }],
  source_decision_id: "source", restoration_decision_id: null,
  activated_at: null, revoked_at: null, revocation_reason: null,
};
const context: SupplierContext = {
  scope_location_id: "loc", can_propose: true, reason_unavailable: null,
  suppliers: [{ id: "sup", name: "Supplier A", batch_ids: ["old", "new"],
    evidence_refs: [{ type: "batch", id: "old" }, { type: "batch", id: "new" }],
    batches: [{ id: "old", safety_status: "FAIL" }] }],
  exclusions: [exclusion],
};
let root: Root;
let host: HTMLDivElement;
function mount(ctx = context, role = "sppg_head", onCreated = vi.fn()) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div"); document.body.append(host);
  root = createRoot(host);
  act(() => root.render(<SupplierExclusionView context={ctx} role={role} token="t" onCreated={onCreated} />));
  return onCreated;
}
function button(text: string) {
  const found = Array.from(host.querySelectorAll("button")).find(item => item.textContent === text);
  if (!found) throw new Error(`Missing button ${text}`);
  return found;
}
function input(label: string, value: string) {
  const field = Array.from(host.querySelectorAll("label")).find(item => item.textContent?.includes(label))?.querySelector("textarea, input, select");
  if (!(field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement || field instanceof HTMLSelectElement)) throw new Error(`Missing field ${label}`);
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(field), "value")?.set;
  act(() => { setter?.call(field, value); field.dispatchEvent(new Event("input", { bubbles: true })); field.dispatchEvent(new Event("change", { bubbles: true })); });
}
afterEach(() => { act(() => root?.unmount()); host?.remove(); vi.unstubAllGlobals(); });

describe("SupplierExclusionView", () => {
  it.each(["bgn_monitor", "admin", "nutritionist"])("keeps %s read-only and preserves FAIL", role => {
    mount(context, role);
    expect(host.querySelector("form")).toBeNull();
    expect(host.textContent).toContain("FAIL");
    expect(host.textContent).toContain("Supplier A");
  });
  it.each([false, true])("requires both server permission and a receiving scope (permission=%s)", allowed => {
    mount({ ...context, can_propose: allowed, scope_location_id: allowed ? null : "loc" });
    expect(host.querySelector("form")).toBeNull();
  });
  it("does not offer restoration for another SPPG or an unlinked supplier", () => {
    mount({ ...context, exclusions: [{ ...exclusion, scope_location_id: "other" }, { ...exclusion, id: "ex2", supplier_id: "unknown" }] });
    expect(host.querySelectorAll('form[aria-label^="Pemulihan"]')).toHaveLength(0);
  });
  it("keeps restoration reasons isolated per exclusion", () => {
    mount({ ...context, exclusions: [exclusion, { ...exclusion, id: "ex2" }] });
    input("Alasan pemulihan", "Only first exclusion");
    const fields = host.querySelectorAll('form[aria-label^="Pemulihan"] textarea');
    expect(fields.item(0)).toHaveProperty("value", "Only first exclusion");
    expect(fields.item(1)).toHaveProperty("value", "");
  });
  it("blocks duplicate submissions synchronously while a proposal is pending", async () => {
    let resolve!: (value: Response) => void;
    const response = new Promise<Response>(done => { resolve = done; });
    const fetchMock = vi.fn().mockReturnValue(response);
    vi.stubGlobal("fetch", fetchMock);
    const onCreated = mount(context, "sppg_nutritionist");
    input("Alasan exclusion", "Measured issue");
    const form = host.querySelector('form[aria-label="Usulan exclusion"]');
    act(() => {
      form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(button("Ajukan exclusion").disabled).toBe(true);
    expect(button("Ajukan pemulihan").disabled).toBe(true);
    await act(async () => resolve(new Response(JSON.stringify({ ...exclusion, source_decision_id: "proposal-new" }))));
    expect(onCreated).toHaveBeenCalledWith("proposal-new");
    expect(fetchMock.mock.calls[0][0]).toContain("/supplier-exclusions/proposals");
  });
  it("rejects old evidence even when entered using a different reference type", () => {
    const old = "11111111-1111-4111-8111-111111111111";
    mount({ ...context, exclusions: [{ ...exclusion, evidence_refs: [{ type: "batch", id: old }] }] });
    input("Alasan pemulihan", "New reason");
    input("Jenis bukti tersimpan", "decision");
    input("ID bukti tersimpan", old);
    expect(button("Ajukan pemulihan").disabled).toBe(true);
    expect(host.textContent).toContain("Bukti exclusion lama tidak dapat digunakan kembali.");
  });
  it("does not infer a supplier from location alone", () => {
    mount({ ...context, suppliers: [], can_propose: false, reason_unavailable: "Supplier belum teridentifikasi" });
    expect(host.querySelector("form")).toBeNull();
    expect(host.textContent).toContain("Supplier belum teridentifikasi");
  });

  it("accepts a persisted reference ID for server validation and shows the server rejection", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "evidence batch tidak ada atau supplier tidak cocok" }), { status: 422 }));
    vi.stubGlobal("fetch", fetchMock);
    const onCreated = mount();
    input("Alasan pemulihan", "Fresh evidence");
    input("ID bukti tersimpan", "not-a-uuid");
    expect(button("Ajukan pemulihan").disabled).toBe(true);
    input("ID bukti tersimpan", "11111111-1111-4111-8111-111111111111");
    await act(async () => button("Ajukan pemulihan").click());
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("evidence batch tidak ada atau supplier tidak cocok");
    expect(onCreated).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).evidence_refs).toEqual([{ type: "batch", id: "11111111-1111-4111-8111-111111111111" }]);
  });
  it("requires explicitly selected new persisted evidence, then opens the new approval decision", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...exclusion, restoration_decision_id: "restore-new" })));
    vi.stubGlobal("fetch", fetchMock);
    const onCreated = mount();
    input("Alasan pemulihan", "New inspection reviewed");
    expect(button("Ajukan pemulihan").disabled).toBe(true);
    const check = host.querySelector('input[type="checkbox"]');
    expect(check).not.toBeNull();
    expect(host.textContent).toContain("FAIL");
    act(() => { if (check instanceof HTMLInputElement) check.click(); });
    await act(async () => button("Ajukan pemulihan").click());
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ reason: "New inspection reviewed", evidence_refs: [{ type: "batch", id: "new" }] });
    expect(onCreated).toHaveBeenCalledWith("restore-new");
    expect(host.textContent).toContain("approval baru");
    expect(host.textContent).toContain("FAIL");
  });
});
