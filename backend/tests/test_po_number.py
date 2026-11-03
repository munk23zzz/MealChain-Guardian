"""Satu bentuk nomor PO untuk semua PO yang lahir dari eksekusi.

Audit 18 Okt 2026: `sap_mock_purchase_orders` menyimpan tiga gaya nomor —
`MC-<12 hex>` (dari `POST /actions/execute`), `DEMO-PO-<KOTA>-<KOMODITAS>`
(dari seed aktivitas demo, tetapi barisnya PUNYA `decision_id` sehingga panel
melaporkannya sebagai `origin=execution`), dan nomor SAP asli `4500000001`
(baris impor tanpa keputusan). Dua gaya pertama sama-sama "terbit dari
eksekusi" tetapi tidak bisa dikenali dengan satu aturan.

Aturan sekarang: SETIAP PO yang lahir dari keputusan memakai
`MC-<12 hex pertama id keputusan>`. Baris impor SAP (tanpa `decision_id`) tetap
memakai nomor aslinya — itu memang objek lain, dan panel menandainya
`origin=demo`.
"""

import uuid

import pytest

from app.core.po_number import nomor_po

DECISION = uuid.UUID("f8cd1043-aaaa-bbbb-cccc-1234567890ab")


def test_format_mc_dua_belas_hex():
    nomor = nomor_po(DECISION)
    assert nomor == "MC-F8CD1043AAAA"
    assert len(nomor) == 15
    assert nomor == nomor.upper()


def test_deterministik_untuk_keputusan_yang_sama():
    assert nomor_po(DECISION) == nomor_po(str(DECISION)) == nomor_po(DECISION.hex)


def test_berbeda_untuk_keputusan_berbeda():
    lain = uuid.UUID("40ff4838-1111-2222-3333-444455556666")
    assert nomor_po(DECISION) != nomor_po(lain)


def test_menolak_id_yang_bukan_uuid():
    with pytest.raises(ValueError):
        nomor_po("bukan-uuid")
