# Verifikasi batas SAP — adopsi Nabil B1–B3

> **Snapshot tahun 2026 (tanggal tidak tertulis)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Tanggal verifikasi: 2026-10-10

## Keputusan boundary

- `backend/app/sap_integration/` adalah **adapter data SAP**. Ia mempertahankan
  dictionary SAP-shaped yang sudah dipakai caller (`Plant`, `MaterialNumber`,
  `PurchaseOrder`, `DataSource`, dan seterusnya).
- `backend/app/ai_providers/forecast_client.py` dan `verifier_client.py` adalah
  **client/provider model SAP AI Core**, bukan adapter material stock atau PO.
  `ForecastResult`, label `SAP-RPT-1.6`, fallback statistik, verdict verifier,
  dan guard safety tetap berada di boundary AI tersebut.
- Tidak ada import `SAPDataProvider` ke client AI, dan tidak ada perubahan pada
  transaksi SQL PO di `backend/app/api/actions.py`.

## Kontrak yang direkonsiliasi

`provider_interface.py` sekarang memberi anotasi `TypedDict` untuk record yang
sudah benar-benar dikembalikan adapter: `MaterialStockRecord`,
`PurchaseOrderRecord`, `BusinessPartnerRecord`, `ProductMasterRecord`, dan
`PurchaseOrderResult`. Anotasi ini tidak mengubah nama key atau payload runtime.

`SAPCapability` mendokumentasikan kemampuan yang bisa dipilih. `MATERIAL_DOCUMENTS`
dinyatakan eksplisit tetapi belum didukung. `get_provider(capability=...)`
melempar `UnsupportedCapabilityError` untuk capability yang tidak tersedia;
tidak ada fallback diam-diam ke mock.

Default tetap `ProviderKind.MOCK`. Semua record mock tetap membawa
`DataSource: "MOCK"`; write PO mock tetap ditolak dengan `PermissionError` karena
memerlukan approval manusia. `aws_mcp` tetap unavailable dan dipilih hanya
melalui mode eksplisit yang saat ini fail-closed.

## Bukti pengujian

Focused tests:

```text
backend/tests/test_sap_integration_contract.py
backend/tests/test_sap_provider_factory.py
```

Acceptance yang dicakup: default mock, mode unknown, AWS unsupported, provenance
mock, stable dictionary fields, human-approval guard, supported capability
selection, unsupported `material_documents`, dan capability inventory provider.

Perintah yang dipakai pada lingkungan kerja:

```bash
python -m pytest tests/test_sap_integration_contract.py tests/test_sap_provider_factory.py -q
ruff check app/sap_integration tests/test_sap_integration_contract.py tests/test_sap_provider_factory.py
```

Jika dependency test/linter hanya tersedia di container, jalankan ekuivalennya
melalui `docker compose exec -T backend`.
