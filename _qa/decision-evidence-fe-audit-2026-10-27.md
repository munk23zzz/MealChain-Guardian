# Frontend audit — "Decision & Evidence" page (MealChain Guardian)

Date: 2026-10-27 · Scope: `frontend/` (read-only) · Auditor: subagent run
Trigger: decision `943e662c…` (`supplier_procurement`, `source_location_id` NULL) is `approved` but
`POST /actions/execute` answers `409 binding batch/supplier berubah`; the frontend must show that honestly.

> **Note on concurrent work (checked at the end of this audit, 08:1xZ).** The backend working tree is
> being edited by another session: `backend/app/services/supplier_eligibility.py`,
> `backend/app/services/approval_summary.py` and `backend/app/api/actions.py` are modified but **not
> committed** (a `lokasi_batch_acuan()` helper that compares procurement bindings against
> `target_location_id`). The backend container runs with `uvicorn --reload` and has restarted, so the
> running API may already contain that fix. Everything below about the **frontend** is unaffected (no
> file under `frontend/` is modified — `git status` confirms). §6 states which of the two readings
> (committed vs working tree) each claim comes from.

---

## 0. Method & constraints (what was actually executed)

| Did | Command / evidence |
|---|---|
| Read | `frontend/app/page.tsx`, `lib/api.ts`, `lib/evidence.ts`, `lib/governance.ts`, `lib/bahasa.ts`, `lib/query.ts`, `lib/refresh.ts`, `lib/export.ts`, `lib/supplier-exclusions.ts`, `lib/decision-picker.ts`, `lib/topbar.ts`, `lib/hooks/useDecisionDetail.ts`, `useDecisions.ts`, `usePurchaseOrders.ts`, `useActiveSection.ts`, `components/DecisionEvidence.tsx`, `DecisionActions.tsx`, `ApprovalMenu.tsx`, `ApprovalModal.tsx`, `DecisionAudit.tsx`, `DecisionChain.tsx`, `DecisionPicker.tsx`, `Popup.tsx`, `FactList.tsx`, `SectionJump.tsx`, `GovernanceStatus.tsx`, `IntegrityPanel.tsx`, `ComplianceEvidencePanel.tsx`, `SupplierExclusionPanel.tsx`, `PurchaseOrderList.tsx`, `next.config.js` |
| Typecheck | `npx tsc --noEmit` in `frontend/` → exit 0, no output |
| Unit tests | `npx vitest run tests/decision-evidence.test.tsx tests/approval-menu.test.tsx tests/decision-actions-trigger-label.test.tsx tests/evidence-rapi.test.tsx` → **74 passed / 4 files** |
| Read-only SQL | `docker compose exec -T postgres psql -U mealchain -d mealchain -c "select …"` (see §7) |
| Read-only logs | `docker compose logs --tail 400 backend` (see §4) |
| Not done | No `POST/PUT/PATCH/DELETE` against the backend (no login, no `/actions/*`), no pytest, no source edits |

---

## 1. What the page actually is (render map)

`tab === "evidence"` in `app/page.tsx:1843-1891` renders three things:

```
page.tsx:1848  <p className="board-alert" role="status">  ← partial-fetch banner (detail.errors)
page.tsx:1854  <DecisionEvidence …/>                      ← the whole page body
page.tsx:1880  <PurchaseOrderList …/>                     ← PO panel under it (same tab, not part of DecisionEvidence)
```

Inside `DecisionEvidence` (`components/DecisionEvidence.tsx`):

| Region | Anchor id | Rendered by |
|---|---|---|
| Header + decision picker | — | `DecisionEvidence.tsx:254-294` → `DecisionPicker` |
| Section jump nav | — | `DecisionEvidence.tsx:300` → `SectionJump` |
| (empty / loading state) | — | `DecisionEvidence.tsx:302-352` |
| A. Decision hero | `#ringkasan` | `DecisionEvidence.tsx:356-488` |
| B. Approval route | `#rute` | `DecisionEvidence.tsx:494-517` |
| C. Governance & approval (action trigger) | `#zona-keputusan` | `DecisionEvidence.tsx:519-540` → `DecisionActions` + `GovernanceStatus` + `FactList` |
| D. Evidence cards (cost / safety+supplier / identity) | `#bukti` | `DecisionEvidence.tsx:544-573` → `FactList` |
| Supplier-exclusion form (conditional) | — | `DecisionEvidence.tsx:576-584` → `SupplierExclusionView` |
| E. Audit trail + integrity | `#jejak` | `DecisionEvidence.tsx:587-595` (`DecisionAudit`), `599` (`IntegrityPanel`) |
| Sticky action shortcut bar | — | `DecisionEvidence.tsx:608-631` |

`ComplianceEvidencePanel` is only reachable through `IntegrityPanel.tsx:224-233` (`<details>` "Rincian pengukuran & ekspor bukti").
`DecisionChain.tsx` is **imported but never used** on this page (`app/page.tsx:114`, no `<DecisionChain` anywhere — grep returns nothing). Dead import; `tsconfig.json` has no `noUnusedLocals`, so nothing fails.

---

## 2. Interaction table (every interactive element, in DOM order)

Legend: **S** = shown on success, **F** = shown exactly on failure. Copy is verbatim from JSX.

### 2.1 Page header / picker (`DecisionEvidence.tsx:254-294`)

| # | Element (label) | Component:line | Handler | API fn:line | HTTP | Success | Failure |
|---|---|---|---|---|---|---|---|
| 1 | Picker trigger (shows current decision, placeholder `Pilih keputusan`) | `DecisionPicker.tsx:196-226` (used `DecisionEvidence.tsx:264-281`) | `onClick={() => setTerbuka(!kembali)}` (`:204`) | none — selection only; triggers `useDecisionDetail` | — | panel opens, focus to search box | n/a |
| 2 | Search box (`Cari jenis, status, atau nomor…`) | `DecisionPicker.tsx:237-253` | `setKueri` + `setSorot(0)` (`:248-251`) | — | — | filters; no hit → `Tidak ada keputusan yang cocok dengan “{kueri}”.` (`:269-272`) | n/a |
| 3 | Clear-search `×` (`aria-label="Hapus pencarian"`) | `DecisionPicker.tsx:255-266` | clears query, refocuses input | — | — | — | n/a |
| 4 | Option row (`role="option"`, `data-value=<id>`) | `DecisionPicker.tsx:289-312` | `onClick={() => pilih(option)}` (`:298`) → `onChange(option.value)` (`:133-137`) | `fetchDecisionTraces/Chain/ApprovalSummary/SupplierContext` via `useDecisionDetail` | 4× GET (see §3) | page re-renders for new decision (`page.tsx:1859` `setSelectedId`) | partial-fetch banner if any of the 4 fails (`page.tsx:1848-1853`) |
| 5 | Keyboard: ↑ ↓ Home End Enter Esc Tab | `DecisionPicker.tsx:150-182` | `geser/pilih/tutup` | — | — | Esc closes without changing selection | — |
| 6 | `Tampilkan yang lewat tenggat ({N})` checkbox | `DecisionEvidence.tsx:282-291` | `onChange={setShowExpired(checked)}` (`:287`) | — | — | adds expired rows to picker groups | n/a |
| 7 | Picker hint line | `DecisionEvidence.tsx:270-280` | none | — | — | `{n} menunggu tindakan · {x} lewat tenggat (disembunyikan|ditampilkan) · {n} keputusan tersedia` | **renders `0 … 0` while the feed is still loading** (finding F5) |

### 2.2 Section nav + empty state (`DecisionEvidence.tsx:300-352`)

| # | Element | Component:line | Handler | API | Success | Failure |
|---|---|---|---|---|---|---|
| 8 | Jump links `Ringkasan` `Jalur persetujuan` `Keputusan` `Bukti` `Jejak & integritas` | `SectionJump.tsx:33-50` (`items` from `lib/section-jump.ts:37-45`) | native `<a href="#id">`; active marker from `useActiveSection` (`lib/hooks/useActiveSection.ts:21-77`) | — | scrolls + `aria-current="true"` | dead anchor if the target block is absent (e.g. `#rute` block only when `selected`) |
| 9 | Suggestion card (`{decision_type} / {status} · {id8}`) | `DecisionEvidence.tsx:331-342` | `onClick={() => onSelect(id)}` (`:334`) | as #4 | decision opens | — |
| 10 | `Buka Recommendation Feed` | `DecisionEvidence.tsx:348-350` | `onOpenRecommendations` → `page.tsx:1870` `setTab("recommendations")` | — | tab switch | — |

### 2.3 Hero (`DecisionEvidence.tsx:356-488`)

| # | Element | Component:line | Handler | API fn:line | HTTP | Success | Failure |
|---|---|---|---|---|---|---|---|
| 11 | `Unduh bukti (JSON)` (label while running: `Menyiapkan bukti…`) | `DecisionEvidence.tsx:388-395` | `eksporBukti` (`:137-146`) | `downloadDossier` `lib/export.ts:108-113` → `fetchDossier` `lib/api.ts:847` | `GET /decisions/{id}/dossier` | `Bukti terunduh sebagai {nama}.` (`:402-406`, `role="status"`) + browser download | `Gagal mengunduh bukti — coba lagi; kalau tetap gagal, unduh dari bagian “Bukti tersimpan” di bawah.` (`:407-412`) — **cause swallowed** (`catch {}` at `:143`) |
| 12 | `Ke zona keputusan ↓` | `DecisionEvidence.tsx:396-399` | anchor `#zona-keputusan` | — | — | scroll | — |
| 13 | `<summary> Akibat tiap pilihan / disetujui / ditolak` | `DecisionEvidence.tsx:459-474` | native `<details>` | — | — | shows `Kalau disetujui` / `Kalau ditolak` rows | — |
| 14 | `Buka jejak agen →` | `DecisionEvidence.tsx:478-481` | `onOpenTraces` → `page.tsx:1871` `setTab("agent-log")` | — | — | tab switch | — |

### 2.4 Governance — the only mutation surface (`DecisionActions.tsx` → popup)

The popup is the single gate for all 6 mutations. **Every handler returns `null` on success and the raw error string on failure** (`DecisionActions.tsx:135-224`). `run()` in `ApprovalMenu.tsx:61-75` closes the popup on `null` and prints the string into `.action-error` on failure.

| # | Element (label) | Component:line | Handler | API fn:line | HTTP body | Success copy (card, `.action-message`) | Failure copy (popup, `.action-error role=alert`) |
|---|---|---|---|---|---|---|---|
| 15 | Trigger `Kelola persetujuan…` / `Menunggu rekan…` / `Lihat hasil…` | `DecisionActions.tsx:228-239` (labels `:112-117`) | `setOpened(true)` (`:232`) | — | — | popup opens; focus trapped (`Popup.tsx:63-111`) | — |
| 16 | Popup close `×` (`aria-label="Tutup jendela"`), `Tutup`, Esc, backdrop | `Popup.tsx:139-155`, `ApprovalMenu.tsx:368-370`, `Popup.tsx:77-82`, `:120-122` | `onClose` | — | — | closes, focus returns to trigger (`Popup.tsx:104-110`) | — |
| 17 | **`Setuju`** | `ApprovalModal.tsx:227-247` (only rendered when `actions.approve && canApprove`, `ApprovalMenu.tsx:121`) | `run("approve", onApprove)` (`:119`) → `DecisionActions.approve` (`:137-146`) | `approveAction` `lib/api.ts:185` | `POST /actions/approve {"decision_id":…,"approved":true}` | `Approval tercatat` (`:141`) | raw `err.message`; `.action-error` (e.g. `approval sudah tercatat`, `decision expired`, `decision belum terverifikasi`, `HTTP 409: /actions/approve`) |
| 18 | **`Tolak`** → reason box | `ApprovalMenu.tsx:139-148` → `:320-356` | `openReject()` (`:77-80`) | — | — | textarea `Alasan penolakan (wajib — jadi bahan learning agent)` + `Kirim penolakan` / `Batal menolak` | — |
| 19 | **`Kirim penolakan`** | `ApprovalMenu.tsx:334-341` | `run("reject", () => onReject(reason))` → `DecisionActions.reject` (`:148-160`) | `approveAction` `lib/api.ts:185` | `POST /actions/approve {"approved":false,"comment":reason}` | `Keputusan ditolak — agent bisa re-propose dengan iterasi baru.` | empty reason → `Alasan penolakan wajib diisi — ini bahan learning agent.` (client-side, `:149-151`); server error → raw message |
| 20 | **`Verifikasi`** | `ApprovalMenu.tsx:186-194` | `run("verify", onVerify)` → `DecisionActions.verify` (`:203-224`) | `verifyAction` `lib/api.ts:212` | `POST /actions/verify {"decision_id":…}` | `Verifier ({provider}): {verdict} — verdict tercatat, keputusan siap dieksekusi setelah approval terpenuhi.` — or, when `recorded===false`: `Verifier (…): UNAVAILABLE — tidak ada verdict hasil audit, jadi belum dihitung sebagai verifikasi. Setuju tetap terkunci sampai verifier memberi hasil.` (`:211-219`) | raw message |
| 21 | **`Ajukan`** | `ApprovalMenu.tsx:220-228` (only `!administrative && !expired`) | `run("propose", onPropose)` → `DecisionActions.ajukan` (`:162-173`) | `proposeAction` `lib/api.ts:453` | `POST /actions/propose {"decision_id":…}` | `Keputusan diajukan — menunggu persetujuan Ahli Gizi dan Kepala SPPG.` | raw message |
| 22 | **`Eksekusi`** ← the bug path | `ApprovalMenu.tsx:254-262` (only `actions.execute && summary.can_execute === true`, `:96`,`:244`) | `run("execute", onExecute)` → `DecisionActions.execute` (`:188-201`) | `executeAction` `lib/api.ts:201` | `POST /actions/execute {"decision_id":…}` | `PO {po_number} dibuat (mock)` (e.g. `PO MC-E7150DA4CB4B dibuat (mock)`), or administrative variant `Status administratif supplier tercatat: {status}. Safety batch tidak diubah.` | **`binding batch/supplier berubah`** — bare clause, no prefix, red box inside popup; `ApiError.message` = FastAPI `detail` verbatim (`lib/api.ts:19-24`) |
| 23 | `Eksekusi` *blocked* note | `ApprovalMenu.tsx:266-276` | none (not a button) | — | — | `Eksekusi ke SAP (mock)` + `Belum tersedia — server belum mengizinkan[: {blocking_reasons[0]}]` | *(renders raw English `blocking_reasons[0]`, finding F7)* |
| 24 | **`Minta re-propose`** | `ApprovalMenu.tsx:287-295` | `run("repropose", onRepropose)` → `DecisionActions.repropose` (`:175-186`) | `reproposeAction` `lib/api.ts:225` | `POST /actions/repropose` | `Iterasi v{n} dibuat — menunggu verifikasi & approval.` | raw message |
| 25 | Nav-guard notes (`Penolakan belum tersedia`, `Setuju belum tersedia`, `Belum tersedia — keputusan sudah lewat tenggat…`) | `ApprovalMenu.tsx:152-162`, `:164-175`, `:198-208`, `:232-242`, `:299-309` | none | — | — | static explanation | — |

Sticky shortcut bar (only when `butuhTindakan(...)` and the zone is off-screen, `DecisionEvidence.tsx:608-631`): anchor `Ke zona keputusan ↓` / `Kembali ke zona keputusan ↑` (`lib/evidence.ts:337-346`). Not a second mutation path.

### 2.5 Integrity panel (`IntegrityPanel.tsx`) — `#jejak`

| # | Element | Component:line | Handler | API fn:line | HTTP | Success | Failure |
|---|---|---|---|---|---|---|---|
| 26 | `Verifikasi ulang` (label `memeriksa…` while busy) | `IntegrityPanel.tsx:172-180` | `refresh()` (`:88-105`) | `verifyLedger` `lib/api.ts:838` then `fetchDossier` `lib/api.ts:847` | `GET /ledger/verify`, then `GET /decisions/{id}/dossier` | chips → `Rantai valid` / `tersegel & terverifikasi` (`:56-74`), block count, head prefix, coverage note | `e.message` in `.integrity-error` (`:235`) — **and chips stay at `memeriksa rantai…` / `memuat dossier…` forever** (F4) |
| 27 | `<summary> Rincian pengukuran & ekspor bukti` | `IntegrityPanel.tsx:224-233` | native `<details>` (only if `dossier !== null`) | — | — | reveals `ComplianceEvidencePanel` + export buttons | hidden while dossier is null |
| 28 | `Export JSON dossier` | `IntegrityPanel.tsx:229` | `downloadText(dossierToJson(dossier))` (`lib/export.ts:16-18`) | **none** (client-side only) | — | file download, **no feedback at all** | — |
| 29 | `Export CSV bukti` | `IntegrityPanel.tsx:230` | `downloadText(dossierToCsv(dossier))` | none | — | file download, no feedback | — |

### 2.6 Supplier governance form (conditional, `DecisionEvidence.tsx:576-584`)

Rendered only when `fetchSupplierContext` succeeded. `canMutate = approver && context.can_propose && scope_location_id && token` (`SupplierExclusionPanel.tsx:77`).

| # | Element | Component:line | Handler | API fn:line | HTTP | Success | Failure |
|---|---|---|---|---|---|---|---|
| 30 | `<select> Supplier`, `Alasan exclusion` textarea, `Ajukan exclusion` | `SupplierExclusionPanel.tsx:121-131` (`:128` button) | `submitExclusion` (`:94-103`) → `submit` (`:80-93`) | `proposeSupplierExclusion` `lib/supplier-exclusions.ts:49` | `POST /supplier-exclusions/proposals` | `Usulan exclusion dibuat dan menunggu verifikasi serta approval manusia.` (`role="status"`), `onCreated(id)` → refetch feed + select new decision (`page.tsx:1866-1869`) | `role="alert"` with `error.message`, fallback `Usulan tidak dapat dibuat.` (`:88`) |
| 31 | `Lihat keputusan exclusion` / `Lihat keputusan pemulihan` | `SupplierExclusionPanel.tsx:139-140` | `onCreated(decision_id)` | — | — | switches decision | — |
| 32 | Restoration form: `Alasan pemulihan`, evidence checkboxes, `Jenis bukti tersimpan` select, `ID bukti tersimpan` input, `Ajukan pemulihan` | `SupplierExclusionPanel.tsx:47-67` (`:65` button) | `restore` (`:37-46`) | `proposeSupplierRestoration` `lib/supplier-exclusions.ts:56` | `POST /supplier-exclusions/{id}/restore` | `Usulan pemulihan dibuat; verifikasi dan approval baru tetap wajib. Exclusion masih aktif.` | `Bukti exclusion lama tidak dapat digunakan kembali.` / `ID bukti harus berupa UUID yang valid.`; server error raw; missing id → `Respons tidak memuat ID keputusan pemulihan. Muat ulang sebelum mencoba kembali.` (`:42`) |

### 2.7 Purchase order panel (`PurchaseOrderList.tsx`, same tab, `page.tsx:1880-1889`)

| # | Element | Component:line | Handler | API fn:line | HTTP | Success | Failure |
|---|---|---|---|---|---|---|---|
| 33 | `Muat ulang` (label `Memuat…`) | `PurchaseOrderList.tsx:315-319` | `onRetry` → `page.tsx:1888` `purchaseOrders.refetch()` | `fetchPurchaseOrders` `lib/api.ts:116` + `fetchPurchaseOrderSummary` `:130` | `GET /sap/purchase-orders?limit=200`, `GET /sap/purchase-orders/summary` | list re-renders | `Purchase order tidak bisa dimuat: {error}` (`role="alert"`, `:322-326`) |
| 34 | `Lihat keputusan` / `Buka keputusan` (`<a href="?keputusan=…">`) | `PurchaseOrderList.tsx:383-398` | `onClick` → `onOpenDecision` → `bukaKeputusanDariPO` (`page.tsx:390-402`) | — | — | switches decision + scrolls to `#ringkasan` | — |
| 35 | `Unduh PDF` (`aria-label="Unduh dokumen PDF untuk PO {po}"`, label `Menyiapkan PDF…`) | `PurchaseOrderList.tsx:405-440` | `unduhDokumen` (`:276-289`) | `downloadPoPdf` `lib/export.ts:88-93` → `fetchPurchaseOrderPdf` `lib/api.ts:141` | `GET /sap/purchase-orders/{po}/pdf` | `Dokumen terunduh sebagai {nama}.` (`role="status"`, `:442-459`) | `Dokumen tidak bisa diunduh: {pesan}` (`role="alert"`, `:461-465`) — uses `detail` first, good |

---

## 3. Fetch / polling behaviour

| Data | Hook | Interval | Key | When disabled |
|---|---|---|---|---|
| Decision feed `GET /decisions` | `useDecisions` (`lib/hooks/useDecisions.ts:37-51`) | **5 000 ms** (`:14`) | `["decisions", scope, window]` | `!token` |
| Detail bundle: `GET /decisions/{id}/traces`, `/chain`, `/approval-summary`, `GET /supplier-exclusions/context/{id}` | `useDecisionDetail` (`lib/hooks/useDecisionDetail.ts:45-84`) | **5 000 ms** (`:19`, `:82`) — 4 requests per tick | `["decision-detail", id, scope]` | `!token \|\| !decisionId` |
| Ledger + dossier | `IntegrityPanel.refresh` (`:88-109`) | **none** (effect on mount / decision change / manual button) | — | — |
| Purchase orders (list + summary) | `usePurchaseOrders` (`lib/hooks/usePurchaseOrders.ts:20-50`) | **none** (`refetchInterval: false`, `retry: false`) | `["purchase-orders", scope]`, `["purchase-order-summary", scope]` | `!token` |
| Everything else (map, today, KPI…) | `lib/query.ts:12-26` | default **60 000 ms**; `staleTime` 30 000 ms; `retry: 1`; `refetchOnWindowFocus: false` | — | — |
| Clock used by the page (`dueLabel`, `windowUsage`) | `app/page.tsx:743-747` | `setInterval(…, 30000)` on `now` | — | — |

**Refetch after a write:** every successful non-GET inside `request()` calls `segarkanSetelahTulis()` (`lib/api.ts:79`) → `client.invalidateQueries()` with no key (`app/providers.tsx:19-24`) → **all** queries invalidate + refetch. So after approve/reject/verify/propose/repropose/execute, feed, detail bundle, dossier/ledger (no — ledger is local state, not a query) and PO panel all refresh. `IntegrityPanel` is *not* a React Query consumer, so its ledger/dossier do **not** refresh after an action (only on decision change or the manual button).

Observed in backend logs (`docker compose logs backend`): `GET /decisions/f0ac8333…/approval-summary` repeating every ~5 s, and one `GET /decisions/64ce3369…/approval-summary → 403 Forbidden` (out-of-scope decision, the `detail.errors` path firing in production-like use).

---

## 4. Loading / empty / error states as implemented

| Surface | Loading | Empty | Error |
|---|---|---|---|
| Page body, nothing selected | `Memuat keputusan…` + explanation (`DecisionEvidence.tsx:302-309`, gated by `loading={decisionsQuery.isPending}`, `page.tsx:1858`) | `Belum ada keputusan dipilih` / `Keputusan itu tidak ada di cakupan akun ini` (`:314-321`) + suggestions | — |
| Picker hint | **none** — renders `0 menunggu tindakan · 0 keputusan tersedia` (F5) | `Tidak ada keputusan yang cocok…` (search) | — |
| Hero metrics / facts | facts render with `—` for missing values (`lib/evidence.ts` `DASH`) | `—` | — |
| Flags `Perlu diperhatikan` | suppressed until `summary` arrives (`DecisionEvidence.tsx:157-159`, deliberate) | not rendered | — |
| Governance card | **none** — renders `Menunggu persetujuan` from an empty summary (F2) | `—` in facts | **none inline**; only tab-top banner `Sebagian bukti gagal dibaca: {errors}. Panel di bawah hanya menampilkan bagian yang berhasil dimuat.` (`page.tsx:1848-1853`, `role="status"`) |
| Audit trail | — | `Belum ada jejak yang bisa dibaca untuk keputusan ini.` (`DecisionAudit.tsx:28`) | — |
| Integrity panel | chip `memeriksa rantai…` / `memuat dossier…` + `Memuat dossier…` (`IntegrityPanel.tsx:56-74`, `:196`) | `Pilih keputusan untuk melihat dossier.` (`:195`) | `.integrity-error` (`:235`) — chips never leave the "loading" label (F4) |
| Compliance rows | — | `Belum ada bukti pengukuran untuk keputusan ini.` (`ComplianceEvidencePanel.tsx:25`) | — |
| PO panel | `Memuat purchase order…` (`PurchaseOrderList.tsx:328-330`) | `Belum ada purchase order untuk SPPG Anda.` / `…tercatat.` (`:226-229`) | `Purchase order tidak bisa dimuat: {error}` (`:322-326`) |
| Supplier form | `Mengirim usulan…` (`SupplierExclusionPanel.tsx:145`) | `Belum ada bukti baru pada keputusan ini. …` (`:56`) | `role="alert"` (`:146`) |

There is **no error boundary anywhere**: `frontend/app/` contains no `error.tsx` / `global-error.tsx`, and `grep -rn "ErrorBoundary\|componentDidCatch"` returns nothing. Any throw in any panel blanks the whole SPA (Next's "Application error: a client-side exception has occurred"). Plausible throw sites are listed in F10.

---

## 5. Findings

Severity: **P0** blocks the demo story · **P1** user sees something wrong/misleading · **P2** polish / hygiene.

### F1 — P0 · The execute 409 is displayed, but as an unattributed raw server clause, while the screen still claims the action is available
- Path: `DecisionActions.execute` (`components/DecisionActions.tsx:188-201`) → returns `String(err.message)` → `ApprovalMenu.run` (`:65-70`) → `<p className="action-error" role="alert">{error}</p>` (`components/ApprovalMenu.tsx:360-364`).
- `ApiError` sets `message = detail` when FastAPI sent a string (`lib/api.ts:19-24`), so the alert body is exactly:
  `binding batch/supplier berubah`
  — lowercase, no subject, no verb for the user, no "what to do", and no indication *which* action failed (the popup still lists Setuju/Tolak/Eksekusi around it).
- `humanizeBlocker` is applied to the **success** message only (`DecisionActions.tsx:248`), never to `error`, and it has no mapping for this string anyway (`lib/bahasa.ts:25-37`).
- Contradiction on screen: `GovernanceStatus` renders `Siap dieksekusi` (from `summary.can_execute`, `lib/governance.ts:117`) and the facts row `Boleh dieksekusi: Ya` / `Alasan tertahan: —` (`lib/evidence.ts:1167-1169`) while the button that is offered cannot succeed. `can_execute` does not model the binding check (backend `approval_summary._supplier_for` has a procurement branch at `:88-95` that skips `resolve_binding`, `:357-375` never adds a binding blocker).
- Effect for a demo operator: the modal closes on every *other* success, but here it stays open with a red box and the card keeps saying "Siap dieksekusi". Nothing on the page (hero, route, facts) changes.
- Minimum frontend fix: prefix + humanize in `DecisionActions.execute`'s catch (e.g. `Eksekusi tidak dijalankan: ${humanizeBlocker(detail) ?? detail}`), add `binding batch/supplier berubah` / `binding ambigu…` / `binding tidak valid` to `BLOCKER_ID`, and render `.action-error` with a heading that names the action. Real fix belongs in `can_execute`.

### F2 — P1 · Missing `approval-summary` is rendered as a plausible, wrong governance state
- `DecisionEvidence.tsx:532` calls `GovernanceStatus view={governanceView(summary)}`; with `summary === null` (`useDecisionDetail` returns `KOSONG` while loading **or** after all-4-failed, `useDecisionDetail.ts:37-43`, `:84`) `governanceView` falls to `status = "menunggu"` (`lib/governance.ts:114-120`) → chip `Menunggu persetujuan`, `Tidak ada … peran syarat` progress hidden.
- Meanwhile the hero badge renders the true feed status (`DecisionEvidence.tsx:362` → `statusWord`), e.g. `disetujui`. Two contradictory statuses, same card stack.
- All mutations silently vanish: `showActions={actions.approve && canApprove}` (`ApprovalMenu.tsx:121`) drops the Setuju button, and the explanation that appears is `Setuju belum tersedia — Verifikasi belum menghasilkan verdict…` (`:164-175`) — **misattributes the cause** (the real cause is that the read model never arrived).
- No inline error and no loading state on the card. Only the tab-top banner (`page.tsx:1848`) mentions `ringkasan persetujuan` among failed parts — far above, and `role="status"` not `alert`.
- Suggested: give `useDecisionDetail` a per-part status, and render on the card `Ringkasan persetujuan belum termuat — status di bawah dari feed, bukan dari read model.` + retry; keep the chip neutral (`—`) instead of `Menunggu persetujuan`.

### F3 — P1 · Success feedback is unstyled and never cleared (and leaks across decisions)
- `.action-message` has **no CSS rule** anywhere (`grep -rn action-message frontend/app frontend/components` → only 5 JSX usages; `.action-error` is styled at `app/globals.css:8956-8966`). So `Approval tercatat`, `PO MC-… dibuat (mock)`, `Iterasi v2 dibuat …` render as a bare paragraph.
- `DecisionEvidence.tsx:524-530` renders `<DecisionActions … />` **without `key`**, and `message` lives in that component's state (`DecisionActions.tsx:100`). Selecting another decision keeps the old success message on the new decision's card (`message` is only ever overwritten or left alone, never reset).
- `unduh` state in `DecisionEvidence.tsx:134-136` has the same problem: `Bukti terunduh sebagai dossier-<OLD-ID>.json.` stays on screen after switching decisions (`:402-406`).

### F4 — P1 · Integrity panel can show a **different decision's** dossier, and one failing call hides the other
- `IntegrityPanel.refresh` (`:88-105`) fetches `verifyLedger` first, then the dossier, in one `try`. If the ledger call fails, the dossier is never fetched; both chips stay at their loading labels (`ledgerState(null)` → `memeriksa rantai…` `:57`; `dossierState(id, null)` → `memuat dossier…` `:69`) even though `busy === false`.
- `dossier` state is **not cleared** when `decisionId` changes (`useEffect` deps `:107-109` only re-run refresh). Until the new fetch resolves, and *permanently* if it fails, the panel shows the previous decision's `Alamat konten`, `Tanda tangan` and measurement rows under the new decision's heading. There is no `key={decisionId}` on the panel (`DecisionEvidence.tsx:599`).
- Fix: two independent `try/catch`es, `setDossier(null)` (and `setLedger(null)`) at the start of a decision change, and a per-box error label instead of the sticky "loading" chips.

### F5 — P2 · Picker counts show `0` during load
`DecisionEvidence.tsx:270-280` derives `countActionable(...)`/`decisions.length` from an empty array; `loading` is only used for the body (`:302`). On first paint the header reads `0 menunggu tindakan · 0 keputusan tersedia`, then jumps. Suggest `Memuat daftar keputusan…` while `loading`.

### F6 — P2 · Approved-but-expired decisions disappear from the picker (procurement TTL is ~30 min)
`APPROVED` is in `ACTIONABLE_STATUSES` (`lib/topbar.ts:39-45`), so `isExpiredAction` (`:154-161`) classifies an expired `approved` decision as "lewat tenggat" and `decisionGroups` filters it out unless `keep` (`lib/decision-picker.ts:122-131`), i.e. unless it is already the selected one. The only hint is `· {x} lewat tenggat disembunyikan` (`DecisionEvidence.tsx:273-277`) and the checkbox label.
Live example: `943e662c` (created 07:27:58Z, expires 07:58:02Z) and `f0ac8333` (created 07:53Z, expires 08:23Z) are `approved` procurement decisions with a ~30-minute window; after that they are unselectable from the picker, which is precisely the "I need to execute this" case. Also note `decisionGroups` is called **without `role`** (`DecisionEvidence.tsx:176-179`), so `isExpiredAction` can never mark `proposed` drafts expired there.

### F7 — P2 · Execute-blocked note prints raw server English
`ApprovalMenu.tsx:110-112` takes `summary.blocking_reasons[0]` **verbatim** and interpolates it (`:266-276`):
`Belum tersedia — server belum mengizinkan: approval belum memenuhi requirement (missing/rejected).`
`GovernanceStatus` next to it *does* humanize the same list (`lib/governance.ts:129` → `lib/bahasa.ts:69-80`). Should use `blockingReasons(summary)[0]`.

### F8 — P2 · `Unduh bukti (JSON)` discards the reason
`DecisionEvidence.tsx:143-145` is `catch { setUnduh({state:"gagal"}) }` — no `err` binding, so a 403 (`dossier` of an out-of-scope decision), a 404, or a proxy HTML error all produce the same `Gagal mengunduh bukti — coba lagi…`. Compare `PurchaseOrderList.tsx:282-288`, which does it right (`detail || message || fallback`).

### F9 — P2 · Read-only note prints the raw role code
`DecisionActions.tsx:122-124`: `Peran bgn_monitor bersifat read-only.` — should be `roleLabel(role)` like everywhere else (`lib/settings.ts` via `lib/bahasa.ts`).

### F10 — P2 · No error boundary; three unguarded dereferences can blank the whole app
`frontend/app/` has no `error.tsx`; a render throw kills the single-page console.
- `IntegrityPanel.tsx:70` — `dossier.signature.state` (throws if a 200 body lacks `signature`).
- `IntegrityPanel.tsx:202` — `dossier.content_address.slice(0, 24)` (throws if `content_address` is null; the backend always sends it today, `backend/app/api/dossier.py:50-55`, so this is defence-in-depth).
- `ApprovalModal.tsx:89-92` — `(state.missing ?? []).flat()` (throws if `missing` is present but not an array).
Suggested: `dossier?.content_address ? … : "—"`, `dossier?.signature?.state ?? "unsigned"`, `Array.isArray(state.missing) ? … : []`, plus a small boundary around the evidence tab.

### F11 — P2 · PO panel goes stale and stays stale
`usePurchaseOrders.ts:26`/`:36` set `refetchInterval: false`, and the global config disables `refetchOnWindowFocus` (`lib/query.ts:116`). Only a write elsewhere or the manual `Muat ulang` refreshes it. If another operator approves+executes while this tab is open, the PO table (and the `keputusan ini` marker) keep showing the old state indefinitely.

### F12 — P2 · 4 HTTP calls every 5 s regardless of which tab is open
`useDecisionDetail` polls unconditionally on `decisionId` (`useDecisionDetail.ts:80-82`) and `page.tsx:405` never passes the active tab, so traces/chain/approval-summary/supplier-context keep hitting the backend every 5 s while the user is on Overview, Peta, Demo Control, etc. Evidence: repeated `GET /decisions/f0ac8333…/approval-summary` in the backend log at ~5 s cadence. Suggest `enabled: tab === "evidence"` (as `useSuppliers`/`useKpi` already do).

### F13 — P2 · Small copy/correctness nits
- `DecisionActions.tsx:195`: `PO ${result.po_number ?? ""} dibuat (mock)` → `PO  dibuat (mock)` if the field is ever absent.
- `ApprovalModal.tsx:12-15` `Show` renders the English token `unavailable` on an Indonesian page; for procurement this produces `Pemasok → SPPG unavailable → Jakarta` when `supplier` is null (`:160-177`).
- Procurement decisions have no measured evidence, so `ComplianceEvidencePanel` reports the binding row as `Perlu verifikasi 1` (`lib/evidence.ts:100-107` defaults any status-less row to `NEEDS_VERIFICATION`) — reads like an unmet safety gate.
- `app/page.tsx:114` imports `DecisionChain` but never renders it.
- `decisionFacts` correctly shows `Pemasok → SPPG` for procurement (`lib/evidence.ts:962-973`), so the old `Rute —` bug is fixed; the only remaining "empty route" case is `Pemasok → SPPG —` when both supplier name and target are missing.

---

## 6. `supplier_procurement` walk-through (why the page "does not work" for the user)

Data verified read-only (2026-10-27, DB `now()` = 08:00:59Z):

```
id        status    src_null  expires_at (UTC)  valid  verified_by      verifier_note
f0ac8333  approved  t         2026-10-27 08:23    t      verifier_agent   flagged
943e662c  approved  t         2026-10-27 07:58    f      verifier_agent   flagged
26e8bbbf  pending   t         2026-10-27 07:54    f      verifier_agent   flagged
64ce3369  proposed  t         2026-10-27 15:23    t      —                —
```
`943e662c`: `supplier_id=f4bbb1fc`, `commodity=1b4b49fe`, `qty=360 kg`, approvals 2/2.
Binding evidence (`decision_evidence`, `evidence_type=human_inspection`):
`allocation_binding=true`, `supplier_id=f4bbb1fc…`, `batch_ids=["5c05d411…"]`.
`f0ac8333`: approvals 2/2, `qty=15`, `sdc=761399.56`, binding `supplier_id=d4899915…`, `batch_ids=["45204477…"]`.

**Both bindings are internally consistent** — the batch supplier, the batch commodity and the batch
location all match the decision row and the decision's target (`275d1be7…` = Jakarta):

| decision | dec supplier | batch | batch supplier | batch commodity | batch location |
|---|---|---|---|---|---|
| `943e662c` | `f4bbb1fc` | `5c05d411` | `f4bbb1fc` ✔ | `1b4b49fe` ✔ | `275d1be7` = target ✔ |
| `f0ac8333` | `d4899915` | `45204477` | `d4899915` ✔ | `e7cb3007` ✔ | `275d1be7` = target ✔ |

So the *only* failing predicate in the committed backend is `batch.location_id != decision.source_location_id`
(`supplier_eligibility.py` `resolve_binding`, committed version line ~113) — i.e. comparing a real
`location_id` with `NULL`. In the working-tree version that comparison became
`batch.location_id != lokasi_batch_acuan(decision)` (`:133`), which for procurement returns
`target_location_id` (`:99-101`), and these two decisions would then satisfy the binding check.

UI sequence, step by step:

1. Feed row arrives; `selected` is the **feed row only** (`page.tsx:880`) — no `summary`, no `source_location`.
2. `decisionHeadline` (`lib/evidence.ts:421-458`) → `Pengadaan 360 kg beras` + second line `{pemasok} → Jakarta` (needs `summary.supplier`, so nothing extra until the summary lands).
3. First paint of the governance card: `governanceView(null)` → **`Menunggu persetujuan`** although the hero says `disetujui` (F2). ~1 fetch later it flips to `Persetujuan lengkap` / `Siap dieksekusi`.
4. Route stepper (`approvalRoute`, `:560-647`) shows `Eksekusi · target Simulasi` and state `current` when `can_execute === true`.
5. `ApprovalMenu` renders the **`Eksekusi` button** because `can_execute === true` (procurement branch of `_supplier_for` never touches the binding; `_safety_view` short-circuits on `source_location_id IS NULL` → `blocked=False`).
6. Click → `POST /actions/execute` → `revalidate_transfer` → `resolve_binding`. With the **committed**
   backend this compares `batch.location_id` against `decision.source_location_id` (**NULL**) for every
   type → `409 binding batch/supplier berubah`. With the **working-tree** backend (`lokasi_batch_acuan`)
   these two decisions pass the binding check; the same frontend path is still reached by the other 409
   branches that survive that fix — `supplier excluded pada SPPG penerima`,
   `safety revalidation gagal: …`, `supplier_unknown: tidak ada batch pemasok di SPPG tujuan`,
   `supplier_unknown: keputusan pengadaan tanpa pemasok/batch tujuan`.
7. Popup stays open; `.action-error` shows exactly `binding batch/supplier berubah` (or whichever of the
   above fired, verbatim). Nothing else on the page changes: chip still `Siap dieksekusi`,
   `Alasan tertahan: —`, no retry hint, no pointer to the evidence row that contradicts the decision.

Other procurement-specific behaviour that is already correct and worth keeping:
- `decisionFacts` label `Pemasok → SPPG` + supplier name (`lib/evidence.ts:962-973`) — no `Rute —`.
- `ApprovalModal` label switches to `Pemasok → SPPG` for this type (`ApprovalModal.tsx:160-177`).
- `decisionHeadline` verb `Pengadaan` (`lib/evidence.ts:384`).
- Expired procurement decisions drop out of the picker (F6) — this is the second half of the demo problem: 30 minutes after the agent ran, the decision is no longer selectable at all.

---

## 7. Texts a browser test can assert (exact strings + selector hints)

All selectors below are taken from the rendered JSX. `page.getByRole(...)` + `getByText` works; `data-action` and `data-testid` are the stable hooks.

### Open the action surface
| Step | Selector | Assert |
|---|---|---|
| Trigger | `button[aria-haspopup="dialog"]` inside `.decision-actions` (`DecisionActions.tsx:228-239`) | text matches `^(Kelola persetujuan\|Menunggu rekan\|Lihat hasil)…$` (`…` is an `aria-hidden` span) |
| Popup | `[role="dialog"][aria-labelledby="approval-popup-title"]` (`Popup.tsx:124-132`) | contains `Governance & persetujuan`, `Konfirmasi Approval`, `#<id8> · v<n>` |
| Summary first | `.approval-modal dl` | contains `Syarat approval`, `Verdict verifier`, `Target eksekusi` |
| Esc / close | `button[aria-label="Tutup jendela"]` (`Popup.tsx:139-155`) | `[role=dialog]` count → 0, focus back on trigger |

### Per action — success assertions
| Action | Click | Assert on success |
|---|---|---|
| Approve | `.approval-modal-actions button` with text `Setuju` (`ApprovalModal.tsx:227-247`) | popup closed **and** `.decision-actions .action-message[role=status]` text `Approval tercatat` |
| Reject | `button[data-action="reject"]` (`ApprovalMenu.tsx:139-148`) → `textarea[placeholder="cth: Kuota SPPG Jakarta penuh minggu ini"]` → button `Kirim penolakan` | `.action-message` = `Keputusan ditolak — agent bisa re-propose dengan iterasi baru.` |
| Verify | `button[data-action="verify"]` (`:186-194`) | `.action-message` **starts with** `Verifier (` and contains `verdict tercatat, keputusan siap dieksekusi setelah approval terpenuhi.` (or, for UNAVAILABLE: `tidak ada verdict hasil audit, jadi belum dihitung sebagai verifikasi.`) |
| Propose | `button[data-action="propose"]` (`:220-228`) | `.action-message` = `Keputusan diajukan — menunggu persetujuan Ahli Gizi dan Kepala SPPG.` |
| Re-propose | `button[data-action="repropose"]` (`:287-295`) | `.action-message` matches `/^Iterasi v\d+ dibuat — menunggu verifikasi & approval\.$/` |
| Execute | `button[data-action="execute"]` (`:254-262`) | `.action-message` matches `/^PO MC-[0-9A-F]{12} dibuat \(mock\)$/` **and** the PO panel gains a row containing the same `MC-…` number (`PurchaseOrderList.tsx:363`) |
| Execute fails (the bug) | same button | `.action-error[role=alert]` exists, popup still open, and its text equals `binding batch/supplier berubah`; plus the card still reads `Siap dieksekusi` (this pair is the regression to lock) |
| Export dossier (hero) | `button.evidence-export` (`DecisionEvidence.tsx:388-395`) | label goes `Menyiapkan bukti…` then `.evidence-note[role=status]` = `Bukti terunduh sebagai dossier-<id>.json.` |
| Ledger refresh | `[data-testid="btn-verify-ledger"]` (`IntegrityPanel.tsx:172-180`) | `[data-testid="ledger-status"]` chip text ∈ {`Rantai valid`, `Rantai putus`}, button label returns to `Verifikasi ulang` |
| Dossier export | `summary` `Rincian pengukuran & ekspor bukti` → `Export JSON dossier` / `Export CSV bukti` (`:225-233`) | both buttons present, `[data-testid="compliance-evidence-panel"]` visible |
| PO PDF | `button[aria-label^="Unduh dokumen PDF untuk PO"]` (`PurchaseOrderList.tsx:406-437`) | `.po-pdf-note[role=status]` = `Dokumen terunduh sebagai PO-<n>.pdf.` |
| PO retry | `button.btn-ghost` (`:315-319`) | label toggles `Memuat…` → `Muat ulang` |
| Pick another decision | `#pilih-keputusan` → `.dpick-search` → `.dpick-option[data-value="<id>"]` (`DecisionPicker.tsx:196-314`) | `#ringkasan h2.evidence-hero-title` changes; URL gains `?keputusan=<id>` (`page.tsx:363-375`) |
| Expired toggle | checkbox in `.evidence-picker-toggle` (`DecisionEvidence.tsx:282-291`) | hint text toggles `… lewat tenggat disembunyikan` ⇄ `… lewat tenggat ditampilkan` |
| Jump links | `.section-jump-link` (`SectionJump.tsx:39-47`) | 5 links: `Ringkasan`, `Jalur persetujuan`, `Keputusan`, `Bukti`, `Jejak & integritas` |
| Read-only role (`bgn_monitor`) | — | `.read-only-note` = `Peran bgn_monitor bersifat read-only.` and no `[aria-haspopup="dialog"]` |
| Partial-fetch banner | — | `.board-alert[role=status]` starts with `Sebagian bukti gagal dibaca: ` |

### Error-path assertions that are currently **impossible** (gaps to fill before writing the test)
- No stable string distinguishes "summary not loaded" from "summary failed" (F2) — you can only assert the absence of `Setuju`.
- No string identifies *which* action failed after a 409 (F1).
- `Export JSON/CSV` produce no DOM feedback at all (nothing to assert).

---

## 8. Recommended minimum fixes (frontend only, ordered)

1. `DecisionActions` catch blocks: `Eksekusi tidak dijalankan: {humanizeBlocker(detail) ?? detail}`; extend `BLOCKER_ID` in `lib/bahasa.ts` with `binding batch/supplier berubah`, `binding ambigu; ajukan keputusan baru`, `binding tidak valid`.
2. `key={selected.decision_id}` on `DecisionActions` (and reset `unduh` in `DecisionEvidence`) so success messages cannot leak across decisions; add `.action-message` CSS (or reuse `.action-error` with an ok tone).
3. Give the governance card a real pending/error state instead of `governanceView(null) → "Menunggu persetujuan"`.
4. Split `IntegrityPanel.refresh` into two independent fetches, clear `dossier` on decision change, and give each proof box an error label.
5. `ApprovalMenu.tsx:110-112` → `blockingReasons(summary)[0]`.
6. `useDecisionDetail(... enabled: tab === "evidence")`.
7. Picker hint: `Memuat daftar keputusan…` while `loading`.
8. `roleLabel(role)` in the read-only note; `dossier?.content_address ?? "—"`, `signature?.state ?? "unsigned"`, `Array.isArray(state.missing)`; add `app/error.tsx`.

---

## 9. Limits of this audit

- No mutation was executed, so every "success copy" above is read from source (and from `tests/approval-menu.test.tsx`, `tests/decision-evidence.test.tsx`, which pass) rather than observed in a browser.
- The 409 for `f0ac8333`/`943e662c` was reproduced by reading `resolve_binding` + the DB rows, not by calling `POST /actions/execute`.
- The backend files cited in §6 were changing during this audit (uncommitted `lokasi_batch_acuan` fix by another session, with `uvicorn --reload` restarting the container). Line numbers for `backend/**` are therefore approximate; every **frontend** citation is against the unmodified working tree.
- `943e662c` is already past `expires_at` at the time of this audit, so the live UI shows the *blocked* note (`Belum tersedia — server belum mengizinkan: jendela berlaku keputusan sudah lewat`) rather than the button; the button reappears for a fresh (<30 min) approved procurement decision such as `f0ac8333`.
