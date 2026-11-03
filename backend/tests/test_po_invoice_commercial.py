"""Fase 5 butir 2/4: PO dan dokumen penerimaan memakai harga KOMERSIAL.

Butir 2 (rencana): "RED: PO memakai `sdc / qty`. Setelah resolver digunakan,
`price == invoice_unit_price` dan penalti tidak masuk."

Butir 4: "`sap_mock_purchase_orders.price` memakai invoice unit price.
`accepted_value_idr` memakai harga komersial PO. PDF menampilkan bahan,
transportasi, handling, total PO, serta SDC secara terpisah bila tersedia."

**Perubahan 29 Okt 2026 (permintaan pemilik):** blok SDC dihapus dari PDF dan
komponen bahan/transportasi/handling pindah ke tabel "Rincian pesanan"
(template PO korporat). Asersi lama yang menuntut "Safe Delivered Cost" dan
angka SDC tercetak diganti asersi sebaliknya: angka analitis itu TIDAK boleh
muncul, sedangkan tiga komponen tagihan tetap wajib tercetak dan berjumlah
sama dengan total PO.

Kenapa ini penting secara uang: PO adalah dokumen yang dibayar pemasok.
Menagihkan `expected_loss`/`freshness_risk`/`safety_penalty` ke pemasok berarti
menagih kerugian internal yang tidak pernah ia sebabkan — dan angka itu
sebelumnya benar-benar tertulis di `sap_mock_purchase_orders.price` karena
`actions.py` membagi SDC (enam komponen) dengan kuantitas.

Berkas ini memaku tiga lapis:
1. jalur TULIS (`POST /actions/execute`) → `price == invoice_unit_price`;
2. bentuk BACA (`GET /sap/purchase-orders`) → `invoice_unit_price` disebut
   namanya, `price_per_kg` tetap ada sebagai alias bahan historis;
3. PDF → bahan/transportasi/handling/total PO dan SDC tampil terpisah.

Baris dipilih dari DB saat tes berjalan (bukan id yang dipaku) supaya dataset
demo boleh dibangun ulang tanpa memerahkan tes.
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

import bcrypt
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine, text

from app.core.commercial_cost import commercial_cost
from app.main import app
from app.services import po_document
from tests.dsn import DSN_SYNC

DB_URL = DSN_SYNC
PW = "TestPass#2026"
TWO_DP = Decimal("0.01")


# ── Pembantu (aritmetika ditulis ulang, bukan diimpor dari modul yang diuji) ──


def _q(nilai: Decimal) -> Decimal:
    return nilai.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def _db():
    return create_engine(DB_URL)


def _teks_pdf(isi: bytes) -> str:
    reader = PdfReader(io.BytesIO(isi))
    return "\n".join((halaman.extract_text() or "") for halaman in reader.pages)


def _ribu(nilai: float, desimal: int) -> str:
    utuh, _, pecahan = f"{nilai:.{desimal}f}".partition(".")
    negatif = utuh.startswith("-")
    utuh = utuh.lstrip("-")
    kelompok = []
    while len(utuh) > 3:
        kelompok.insert(0, utuh[-3:])
        utuh = utuh[:-3]
    kelompok.insert(0, utuh)
    hasil = ".".join(kelompok)
    if desimal:
        hasil += "," + pecahan
    return ("-" if negatif else "") + hasil


def _rupiah_tes(nilai: float) -> str:
    return f"Rp {_ribu(nilai, 2)}"


def _mk_user(role: str, location_name: str | None = None) -> dict:
    engine = _db()
    user_id = str(uuid.uuid4())
    email = f"{role}-{uuid.uuid4().hex[:8]}@test.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            loc_id = None
            if location_name:
                loc_id = conn.execute(
                    text("SELECT id FROM locations WHERE name = :n"), {"n": location_name}
                ).scalar_one_or_none()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (:id, :n, :e, :h, :r, :l)"
                ),
                {
                    "id": user_id,
                    "n": f"T {role}",
                    "e": email,
                    "h": digest,
                    "r": role,
                    "l": loc_id,
                },
            )
        return {"id": user_id, "email": email, "password": PW, "role": role}
    finally:
        engine.dispose()


def _drop_user(email: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


def _login(client: TestClient, akun: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": akun["email"], "password": akun["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


#: Breakdown yang MEMUAT keenam komponen: purchase + transport + handling
#: lengkap (syarat resolver menerbitkan invoice) dan tiga penalti positif,
#: supaya perbedaan invoice vs SDC benar-benar terlihat di angka.
BREAKDOWN_KOMERSIAL = {
    "purchase": "5700000.00",
    "transport": "34200.00",
    "handling": "150000.00",
    "expected_loss": "900000.00",
    "freshness_risk": "250000.00",
    "safety_penalty": "400000.00",
    "basis": "uji fase 5: enam komponen eksplisit",
}

QTY = "200"


def _mk_decision(client: TestClient, headers: dict) -> str:
    payload = {
        "recommendation": {
            "candidate": {
                "source_location": "Cianjur",
                "destination_location": "Jakarta",
                "commodity": "telur",
                "quantity_kg": QTY,
            },
            "safe_delivered_cost": "7434200.00",
            "cost_breakdown": BREAKDOWN_KOMERSIAL,
        }
    }
    resp = client.post("/decisions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["decision_id"]


def _ikat_binding(decision_id: str) -> None:
    """Bukti alokasi: batch + pemasok untuk komoditas keputusan.

    Tanpa ini eksekusi ditolak 409 `binding belum tercatat` — prasyarat produk,
    bukan bagian yang diuji di sini.
    """
    engine = _db()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT d.commodity_id, d.target_location_id, d.source_location_id "
                    "FROM decisions d WHERE d.id = :d"
                ),
                {"d": decision_id},
            ).mappings().one()
            batch = conn.execute(
                text(
                    "SELECT b.id, b.supplier_id FROM batches b "
                    "WHERE b.commodity_id = :c AND b.location_id = :l "
                    "AND b.safety_status = 'pass' AND b.usable_until > now() "
                    "ORDER BY b.quantity_kg DESC, b.id ASC LIMIT 1"
                ),
                {"c": row["commodity_id"], "l": row["source_location_id"]},
            ).mappings().first()
            assert batch is not None, "tidak ada batch pass di lokasi asal"
            conn.execute(
                text(
                    "INSERT INTO decision_evidence (id, decision_id, evidence_type, payload, "
                    "is_consistent, recorded_at) VALUES "
                    "(:id, :d, 'human_inspection', CAST(:p AS jsonb), true, now())"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "d": decision_id,
                    "p": json.dumps(
                        {
                            "allocation_binding": True,
                            "batch_ids": [str(batch["id"])],
                            "supplier_id": str(batch["supplier_id"]),
                        }
                    ),
                },
            )
    finally:
        engine.dispose()


def _verify_decision(decision_id: str) -> None:
    """Verifier harus mencatat verdict sebelum approval boleh diminta.

    Prasyarat produk (409 `decision belum terverifikasi`), bukan bagian yang
    diuji di sini — bentuk barisnya sama dengan penulis verifier di produksi.
    """
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE decisions SET verified_by = 'verifier-agent', "
                    "verifier_note = 'consistent' WHERE id = :d"
                ),
                {"d": decision_id},
            )
    finally:
        engine.dispose()


def _cleanup(decision_id: str | None, emails: list[str]) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d"),
                {"d": decision_id},
            )
            conn.execute(
                text("DELETE FROM price_signals WHERE source_ref LIKE 'po:%' "
                     "AND source_ref NOT IN ("
                     "SELECT 'po:' || po_number FROM sap_mock_purchase_orders)")
            )
            conn.execute(
                text("DELETE FROM decision_evidence WHERE decision_id = :d"),
                {"d": decision_id},
            )
            conn.execute(
                text("DELETE FROM approvals WHERE decision_id = :d"), {"d": decision_id}
            )
            conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id}
            )
    finally:
        engine.dispose()
    for e in emails:
        _drop_user(e)


# ── Butir 2: jalur TULIS — PO memakai harga invoice, bukan SDC/kg ────────────


def test_eksekusi_menulis_harga_invoice_bukan_sdc_per_kg(client):
    """Ini RED yang diminta rencana: `price` dulu `sdc / qty` (37.171,00)."""
    head = _mk_user("sppg_head", "Jakarta")
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = None
    try:
        headers = _login(client, head)
        decision_id = _mk_decision(client, headers)
        _ikat_binding(decision_id)
        assert client.post(
            "/actions/propose", json={"decision_id": decision_id}, headers=headers
        ).status_code == 201
        _verify_decision(decision_id)
        for akun in (head, nutritionist):
            resp = client.post(
                "/actions/approve",
                json={"decision_id": decision_id, "approved": True},
                headers=_login(client, akun),
            )
            assert resp.status_code == 200, resp.text
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        nomor = resp.json()["po_number"]

        # Harga yang SEHARUSNYA: invoice (bahan+angkut+penanganan) ÷ kuantitas.
        invoice = Decimal("5700000.00") + Decimal("34200.00") + Decimal("150000.00")
        harapan = _q(invoice / Decimal(QTY))
        # Harga LAMA (salah secara konsep): SDC enam komponen ÷ kuantitas.
        sdc_lama = _q((invoice + Decimal("1550000.00")) / Decimal(QTY))
        assert harapan == Decimal("29421.00")
        assert sdc_lama == Decimal("37171.00")
        assert harapan != sdc_lama

        engine = _db()
        try:
            with engine.connect() as conn:
                harga = conn.execute(
                    text("SELECT price FROM sap_mock_purchase_orders WHERE po_number = :p"),
                    {"p": nomor},
                ).scalar_one()
        finally:
            engine.dispose()
        assert Decimal(str(harga)) == harapan, (
            f"PO menagih {harga}, seharusnya harga invoice {harapan}"
        )

        # Dan harga itu PERSIS yang dikirim resolver — bukan angka kedua.
        biaya = commercial_cost(Decimal(QTY), BREAKDOWN_KOMERSIAL)
        assert biaya is not None
        assert Decimal(str(harga)) == biaya.invoice_unit_price
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_eksekusi_tidak_menagihkan_penalti_ke_pemasok(client):
    """Selisih total PO terhadap SDC harus PERSIS penalti internal."""
    head = _mk_user("sppg_head", "Jakarta")
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = None
    try:
        headers = _login(client, head)
        decision_id = _mk_decision(client, headers)
        _ikat_binding(decision_id)
        client.post("/actions/propose", json={"decision_id": decision_id}, headers=headers)
        _verify_decision(decision_id)
        for akun in (head, nutritionist):
            client.post(
                "/actions/approve",
                json={"decision_id": decision_id, "approved": True},
                headers=_login(client, akun),
            )
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        nomor = resp.json()["po_number"]

        engine = _db()
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT po.price, po.ordered_quantity, d.safe_delivered_cost "
                        "FROM sap_mock_purchase_orders po "
                        "JOIN decisions d ON d.id = po.decision_id WHERE po.po_number = :p"
                    ),
                    {"p": nomor},
                ).mappings().one()
        finally:
            engine.dispose()

        nilai_po = Decimal(str(row["price"])) * Decimal(str(row["ordered_quantity"]))
        sdc = Decimal(str(row["safe_delivered_cost"]))
        penalti = Decimal("900000.00") + Decimal("250000.00") + Decimal("400000.00")
        # 200 × 29.421 = 5.884.200; SDC 7.434.200; selisih = penalti.
        assert nilai_po == Decimal("5884200.00")
        assert sdc == Decimal("7434200.00")
        assert sdc - nilai_po == penalti
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_keputusan_tanpa_rincian_lengkap_menerbitkan_po_bertanda_legacy(client):
    """Rincian hanya `purchase` (bentuk data lama) → PO tetap terbit, harga =
    harga BAHAN saja, dan barisnya ditandai `legacy_unmigrated`.

    Kenapa tidak menolak (422): menolak eksekusi berarti mengubah kontrak alur
    yang dipakai ~10 berkas tes lain dan menghentikan operator pada data lama
    yang sah. Yang dilarang rencana adalah MENAGIHKAN penalti dan MENGARANG
    komponen — bukan menerbitkan PO dari komponen yang tercatat. Penandaan
    itulah yang memberi tahu pembaca rinciannya belum lengkap.
    """
    head = _mk_user("sppg_head", "Jakarta")
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = None
    try:
        headers = _login(client, head)
        resp = client.post(
            "/decisions",
            json={
                "recommendation": {
                    "candidate": {
                        "source_location": "Cianjur",
                        "destination_location": "Jakarta",
                        "commodity": "telur",
                        "quantity_kg": QTY,
                    },
                    # Hanya bahan: transportasi & penanganan tidak tercatat.
                    "safe_delivered_cost": "15720000.00",
                    "cost_breakdown": {"purchase": "15720000.00"},
                }
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        decision_id = resp.json()["decision_id"]
        _ikat_binding(decision_id)
        client.post("/actions/propose", json={"decision_id": decision_id}, headers=headers)
        _verify_decision(decision_id)
        for akun in (head, nutritionist):
            client.post(
                "/actions/approve",
                json={"decision_id": decision_id, "approved": True},
                headers=_login(client, akun),
            )
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        nomor = resp.json()["po_number"]

        engine = _db()
        try:
            with engine.connect() as conn:
                harga = conn.execute(
                    text("SELECT price FROM sap_mock_purchase_orders WHERE po_number = :p"),
                    {"p": nomor},
                ).scalar_one()
        finally:
            engine.dispose()

        # Harga bahan saja. Harga LAMA yang salah adalah sdc/qty
        # (15.720.000 / 200 = 78.600) — angkanya kebetulan sama di sini karena
        # rincian hanya berisi `purchase`, jadi yang membedakan adalah
        # penandaan legacy di bawah dan ketiadaan penalti.
        assert Decimal(str(harga)) == Decimal("78600.00")

        monitor = _mk_user("bgn_monitor")
        try:
            h = _login(client, monitor)
            rows = client.get("/sap/purchase-orders?limit=200", headers=h).json()["items"]
        finally:
            _drop_user(monitor["email"])
        baris = next(r for r in rows if r["po_number"] == nomor)
        assert baris["cost_legacy"] == "legacy_unmigrated"
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


# ── Butir 4a: bentuk BACA — dua harga dengan nama berbeda ────────────────────


def test_daftar_po_menyebut_invoice_unit_price_secara_eksplisit(client):
    """Klien tidak boleh menebak arti `price_per_kg`."""
    monitor = _mk_user("bgn_monitor")
    try:
        headers = _login(client, monitor)
        resp = client.get("/sap/purchase-orders?limit=5", headers=headers)
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert items, "DB tidak punya PO untuk diuji"
        for row in items:
            assert "invoice_unit_price" in row, "nama harga komersial wajib ada"
            # Alias lama tetap ada supaya panel/tes lama tidak pecah, tetapi
            # artinya sekarang sama: harga yang ditagihkan.
            assert row["price_per_kg"] == pytest.approx(row["invoice_unit_price"])
            assert row["invoice_total"] == pytest.approx(
                row["invoice_unit_price"] * row["ordered_quantity_kg"]
            )
    finally:
        _drop_user(monitor["email"])


def test_daftar_po_menyebut_status_label_legacy(client):
    """Butir 8: PO lama tanpa jejak invoice ditandai, bukan diklaim baru."""
    monitor = _mk_user("bgn_monitor")
    try:
        headers = _login(client, monitor)
        resp = client.get("/sap/purchase-orders?limit=50", headers=headers)
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert items
        nilai = {row["cost_legacy"] for row in items}
        assert nilai <= {"legacy_unmigrated", "migrated", "not_applicable"}, nilai
        # Setiap baris WAJIB punya label — tidak boleh absen (absensi = klaim).
        assert all("cost_legacy" in row for row in items)
    finally:
        _drop_user(monitor["email"])


# ── Butir 4b: PDF menampilkan dua arti biaya secara terpisah ─────────────────


def test_pdf_menampilkan_bahan_transport_handling_dan_total_po():
    """Tanpa DB: PDF dari dokumen ber-rincian komersial mencetak empat angka."""
    isi = po_document.bangun_pdf(
        {
            "po_number": "MC-UJI-F5",
            "status": "submitted",
            "created_at": datetime(2026, 10, 27, 3, 0, tzinfo=UTC),
            "ordered_quantity": 200.0,
            "price": 29421.0,
            "total": 5884200.0,
            "material_number": "MAT-TELUR",
            "commodity_name": "Telur",
            "location_name": "Jakarta",
            "supplier_name": "CV Contoh",
            "commercial_cost": {
                "purchase_total": "5700000.00",
                "transport_total": "34200.00",
                "handling_total": "150000.00",
                "invoice_total": "5884200.00",
                "invoice_unit_price": "29421.00",
                "sdc_total": "7434200.00",
                "sdc_unit_price": "37171.00",
                "expected_loss": "900000.00",
                "freshness_risk": "250000.00",
                "safety_penalty": "400000.00",
                "risk_method": {
                    "kind": "simulated_policy",
                    "source": "app/core/safe_delivered_cost.py:bobot_demo",
                    "version": "sdc-policy-1",
                    "period": None,
                    "baseline": None,
                },
            },
            "keputusan": {
                "id": str(uuid.uuid4()),
                "jenis": "supplier_procurement",
                "status": "executed",
                "iteration": 1,
                "proposed_by": "supervisor_agent",
                "created_at": datetime(2026, 10, 27, 2, 0, tzinfo=UTC),
                "expires_at": datetime(2026, 10, 27, 8, 0, tzinfo=UTC),
            },
            "persetujuan": [],
            "syarat": {},
            "dibuat_pada": datetime(2026, 10, 27, 4, 0, tzinfo=UTC),
        }
    )
    teks = _teks_pdf(isi)
    # Empat komponen komersial, masing-masing dengan labelnya sendiri.
    # Sejak template korporat (29 Okt 2026) transportasi & penanganan duduk di
    # tabel "Rincian pesanan" yang sama dengan bahan — bukan blok terpisah.
    assert "Rincian pesanan" in teks
    assert "Bahan" in teks
    assert _rupiah_tes(5700000) in teks
    assert "Transportasi" in teks
    assert _rupiah_tes(34200) in teks
    assert "Penanganan" in teks
    assert _rupiah_tes(150000) in teks
    assert _rupiah_tes(5884200) in teks
    # Total tagihan = bahan + transportasi + penanganan, bukan SDC.
    assert "Total PO (bahan + transportasi + penanganan)" in teks
    # Blok "Safe Delivered Cost" DIHAPUS atas permintaan pemilik 29 Okt 2026:
    # angka analitisnya (7.434.200) tidak boleh tercetak sama sekali.
    assert "Safe Delivered Cost" not in teks
    assert _rupiah_tes(7434200) not in teks
    assert _rupiah_tes(900000) not in teks
    # Angka risiko analitis tidak tercetak. Klaim "TIDAK ditagihkan" juga tidak
    # lagi dicetak: kalimat itu tinggal di blok "Syarat & ketentuan" yang
    # dihapus 29 Okt 2026 atas permintaan pemilik.
    assert "simulasi" in teks.lower()
    assert "aktual" not in teks.lower()
    assert "TIDAK ditagihkan" not in teks


def test_pdf_tanpa_rincian_komersial_tidak_mengarang_komponen():
    """PO lama (tanpa `commercial_cost`) tetap terbit, tetapi tidak mengarang
    baris bahan/transportasi/penanganan yang tidak ada di data."""
    isi = po_document.bangun_pdf(
        {
            "po_number": "MC-UJI-LEGACY",
            "status": "confirmed",
            "created_at": datetime(2026, 10, 27, 3, 0, tzinfo=UTC),
            "ordered_quantity": 12.5,
            "price": 20000,
            "total": 250000.0,
            "material_number": "MAT-BERA",
            "commodity_name": "Beras",
            "location_name": "Jakarta",
            "supplier_name": "CV Contoh",
            "keputusan": {
                "id": str(uuid.uuid4()),
                "jenis": "regional_balance",
                "status": "executed",
                "iteration": 1,
                "proposed_by": "supervisor_agent",
                "created_at": datetime(2026, 10, 27, 2, 0, tzinfo=UTC),
                "expires_at": datetime(2026, 10, 27, 8, 0, tzinfo=UTC),
            },
            "persetujuan": [],
            "syarat": {},
            "dibuat_pada": datetime(2026, 10, 27, 4, 0, tzinfo=UTC),
        }
    )
    teks = _teks_pdf(isi)
    assert "MC-UJI-LEGACY" in teks
    assert "Rp 250.000,00" in teks
    # Tidak ada klaim komponen yang tidak tercatat.
    assert "Safe Delivered Cost" not in teks
    assert "Transportasi" not in teks


def test_pdf_legacy_ditandai_belum_termigrasi():
    """Butir 8: label `legacy_unmigrated` terbaca pembaca dokumen."""
    isi = po_document.bangun_pdf(
        {
            "po_number": "MC-UJI-LEGACY2",
            "status": "confirmed",
            "created_at": datetime(2026, 10, 27, 3, 0, tzinfo=UTC),
            "ordered_quantity": 10.0,
            "price": 20000,
            "total": 200000.0,
            "material_number": "MAT-BERA",
            "commodity_name": "Beras",
            "location_name": "Jakarta",
            "supplier_name": "CV Contoh",
            "cost_legacy": "legacy_unmigrated",
            "keputusan": {
                "id": str(uuid.uuid4()),
                "jenis": "regional_balance",
                "status": "executed",
                "iteration": 1,
                "proposed_by": "supervisor_agent",
                "created_at": datetime(2026, 10, 27, 2, 0, tzinfo=UTC),
                "expires_at": datetime(2026, 10, 27, 8, 0, tzinfo=UTC),
            },
            "persetujuan": [],
            "syarat": {},
            "dibuat_pada": datetime(2026, 10, 27, 4, 0, tzinfo=UTC),
        }
    )
    teks = _teks_pdf(isi)
    assert "legacy_unmigrated" in teks
    # Dan alasannya jelas bagi pembaca dokumen.
    assert "belum dimigrasi" in teks.lower() or "format biaya lama" in teks.lower()


# ── Butir 1: pembulatan per kg dan selisih rupiah yang harus dijelaskan ─────


def _baris_po(**over: object) -> dict:
    """Satu baris SELECT PO sebagai mapping — bentuk yang dibaca `_baris`."""
    dasar: dict[str, object] = {
        "po_number": "MC-UJI-BULAT",
        "status": "submitted",
        "created_at": datetime(2026, 10, 27, 9, 0, tzinfo=UTC),
        "decision_id": uuid.uuid4(),
        "decision_status": "executed",
        "location_id": uuid.uuid4(),
        "location_name": "Jakarta",
        "supplier_id": uuid.uuid4(),
        "supplier_name": "CV Contoh",
        "material_number": "MAT-TELU",
        "commodity_name": "Telur",
        "ordered_quantity": 3.0,
        "price": 3.67,
        "decision_quantity": 3.0,
        "cost_breakdown": {
            "purchase": "10.00",
            "transport": "1.00",
            "handling": "0.00",
            "expected_loss": "1.00",
            "freshness_risk": "0.00",
            "safety_penalty": "0.00",
        },
    }
    dasar.update(over)
    return dasar


def test_invoice_total_memakai_total_invoice_bukan_harga_kali_kuantitas():
    """Butir 1: selisih `kuantitas × harga satuan` dijelaskan, bukan disembunyikan.

    Invoice 11,00 untuk 3 kg → harga satuan 3,67/kg (HALF_UP). Tagihan baris
    `3 × 3,67 = 11,01` berbeda SATU SEN. Yang dinamai `invoice_total` harus
    total invoice (11,00); `total_value` tetap fakta tabel SAP (11,01).
    """
    from app.api.sap_orders import _baris

    baris = _baris(_baris_po())

    assert baris["invoice_unit_price"] == pytest.approx(3.67)
    assert baris["invoice_total"] == pytest.approx(11.00)
    # Selisihnya pembulatan per kg: harga 2 desimal × kg.
    assert baris["price_per_kg"] * baris["ordered_quantity_kg"] == pytest.approx(11.01)
    assert baris["total_value"] == pytest.approx(11.01)


def test_invoice_total_sama_dengan_harga_kali_kuantitas_bila_tidak_ada_selisih():
    """Kontrol positif: 200 kg × 29.421 = 5.884.200 — dua arti bertemu."""
    from app.api.sap_orders import _baris

    baris = _baris(
        _baris_po(
            ordered_quantity=200.0,
            decision_quantity=200.0,
            price=29421.00,
            cost_breakdown={
                "purchase": "5700000.00",
                "transport": "34200.00",
                "handling": "150000.00",
                "expected_loss": "100000.00",
                "freshness_risk": "0.00",
                "safety_penalty": "0.00",
            },
        )
    )

    assert baris["invoice_total"] == pytest.approx(5884200.00)
    assert baris["invoice_unit_price"] * baris["ordered_quantity_kg"] == pytest.approx(
        5884200.00
    )


def test_invoice_total_baris_legacy_memakai_harga_tersimpan():
    """Rincian tidak lengkap → tidak ada invoice yang bisa diturunkan.

    Satu-satunya angka jujur adalah yang benar-benar tertagih di tabel:
    `harga tersimpan × kuantitas`. Barisnya tetap ditandai legacy.
    """
    from app.api.sap_orders import _baris

    baris = _baris(
        _baris_po(
            ordered_quantity=600.0,
            decision_quantity=600.0,
            price=26200.00,
            cost_breakdown={"purchase": "15720000.00"},
        )
    )

    assert baris["cost_legacy"] == "legacy_unmigrated"
    assert baris["invoice_total"] == pytest.approx(15720000.00)


def test_pdf_menjelaskan_selisih_pembulatan_subtotal_vs_harga_kali_jumlah():
    """Template korporat: dua arti total tidak boleh diam-diam disamakan.

    Invoice 11,00 untuk 3 kg -> harga satuan 3,67/kg, sehingga harga x jumlah =
    11,01. PDF wajib mencetak subtotal (11,00) DAN total PO (11,01) sebagai dua
    baris berbeda — bukan memilih salah satu diam-diam. Kalimat penjelas
    "Selisih Rp ..." dihapus 29 Okt 2026 bersama catatan kaki lainnya; kedua
    angka itu sendiri yang menjadi buktinya.
    """
    isi = po_document.bangun_pdf(
        {
            "po_number": "MC-UJI-BULAT-PDF",
            "status": "submitted",
            "created_at": datetime(2026, 10, 29, 3, 0, tzinfo=UTC),
            "ordered_quantity": 3.0,
            "price": 3.67,
            "total": 11.01,
            "material_number": "MAT-TELU",
            "commodity_name": "Telur",
            "location_name": "Jakarta",
            "supplier_name": "CV Contoh",
            "commercial_cost": {
                "purchase_total": "10.00",
                "transport_total": "1.00",
                "handling_total": "0.00",
                "invoice_total": "11.00",
                "invoice_unit_price": "3.67",
                "sdc_total": None,
                "sdc_unit_price": None,
                "expected_loss": None,
                "freshness_risk": None,
                "safety_penalty": None,
                "risk_method": {"kind": "simulated_policy", "version": "sdc-policy-1"},
            },
            "keputusan": {"id": "kep-2", "status": "executed"},
            "persetujuan": [],
            "dibuat_pada": datetime(2026, 10, 29, 4, 0, tzinfo=UTC),
        }
    )
    teks = _teks_pdf(isi)
    assert "Subtotal (jumlah baris di atas)" in teks
    assert _rupiah_tes(11.00) in teks
    assert "Total PO (harga satuan × jumlah)" in teks
    assert _rupiah_tes(11.01) in teks
    # Kalimat penjelas selisih termasuk catatan kaki yang dihapus 29 Okt 2026.
    assert "Selisih Rp" not in teks
