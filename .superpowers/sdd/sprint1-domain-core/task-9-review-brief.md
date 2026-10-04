# Task 9 Review Brief — SAP Provider Contract & Mock (Sprint 1 MealChain)

Mode: VERIFIKASI SAJA — jangan ubah kode. Kode sudah ada (uncommitted), belum pernah direview.

## Files
- backend/app/sap_integration/provider_interface.py
- backend/app/sap_integration/mock_provider.py
- backend/app/sap_integration/aws_mcp_provider.py
- backend/app/sap_integration/factory.py
- backend/app/sap_integration/mock_service.py (pendukung mock-sap service)
- backend/tests/test_sap_integration_contract.py
- backend/tests/test_mock_sap_health.py

## Matriks wajib (plan Task 9)
1. Kontrak SAPDataProvider mendefinisikan 5 methods: get_material_stock, get_purchase_orders,
   create_purchase_order, get_business_partner, get_product_master.
2. Factory default = mock (tanpa env config eksplisit → MockSAPProvider).
3. Response field memakai nama kontrak SAP di Skill.md §6: MaterialNumber, Plant,
   StorageLocation, Batch, MatlStkQty, BaseUnit (stock); PurchaseOrder/PO fields sesuai §6.
4. Data source = MOCK: provider mock mengidentifikasi data sebagai simulasi
   (header X-Data-Source: MOCK pada service / flag source pada contract).
5. Unknown material/plant → list kosong, bukan crash.
6. AWS stub: aws_mcp_provider.py raise NotImplementedError eksplisit, tanpa akses eksternal,
   tidak pernah dipilih tanpa config eksplisit (factory tidak mengembalikannya by default).
7. Setiap kapabilitas switch independen (env SAP_*_MODE per kapabilitas).
8. Tidak ada credential nyata di kode.
9. create_purchase_order TIDAK dipanggil oleh endpoint Sprint 1 dan tidak auto-execute.

## Cara kerja
1. Baca keenam file. Cocokkan setiap baris matriks → COVERED/MISSING/WEAK dengan file:line.
2. Jalankan: docker compose exec -T backend pytest tests/test_sap_integration_contract.py tests/test_mock_sap_health.py -q
3. Jalankan: docker compose exec -T backend ruff check app/sap_integration/
4. Grep kontrak: pastikan tidak ada boto3/requests/httpx call keluar di mock provider;
   factory tidak instantiate AWS provider tanpa env.
5. Tulis laporan ke .superpowers/sdd/sprint1-domain-core/task-9-review-report.md:
   verdict PASS/FAIL spec, matriks per baris, temuan Critical/Important/Minor + file:line,
   output pytest + ruff.

Return HANYA: status CLEAN/FINDINGS, ringkasan pytest, ruff, temuan Critical/Important.
