"""GET /receipts/riwayat — riwayat penerimaan per pemasok (Dok 05 §8.5).

Kenapa endpoint ini diuji terpisah: `GET /receipts` hanya menjawab per BATCH dan
`GET /receipts/menunggu` hanya memuat catatan yang belum diputuskan, sehingga
tidak ada satu pun balasan server yang bisa dipakai layar audit pemasok. Yang
dikunci di sini:

- kg DIPESAN (`ordered_kg`) dan kg DITERIMA (`received_kg`) dua kolom terpisah,
  dan `received_kg` KOSONG selama catatan belum disetujui — barang yang belum
  masuk stok tidak boleh terbaca sebagai sudah diterima;
- nilai rupiah hanya dari harga satuan invoice PO; batch tanpa ikatan bukti
  dinyatakan `null` ("tidak tercatat"), BUKAN Rp 0;
- `ringkasan` dihitung dari SELURUH baris dalam cakupan walau `limit` memotong
  daftarnya — angka kepala tabel tidak berubah saat pengguna pindah halaman;
- cakupan lokasi sama dengan antrean `menunggu` (SPPG = lokasinya, pemantau
  nasional = seluruh jaringan);
- penyaring `supplier_id` dan `status`.

Asersi memakai baris milik tes ini sendiri (supplier + lokasi bersuffix acak)
dan meminta `supplier_id` itu, supaya basis data uji yang dipakai bersama suite
lain tidak membuat angka mutlak apa pun rapuh.

Jalankan: docker compose exec -T backend pytest tests/test_receipts_riwayat.py
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

KOMODITAS = "telur"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _db():
    return create_engine(DSN_SYNC)


def _token(user_id, role, loc_id=None) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(user_id),
        "role": role,
        "loc": str(loc_id) if loc_id else None,
        "iat": now,
        "exp": now + 15 * 60,
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


class _Fx:
    """Baris milik tes ini saja; semuanya dihapus di `tutup()`."""

    def __init__(self):
        self.suffix = uuid.uuid4().hex[:8]
        self.po_numbers: list[str] = []
        eng = _db()
        with eng.begin() as conn:
            self.loc = str(
                conn.execute(
                    text(
                        "INSERT INTO locations (name, region, latitude, longitude) "
                        "VALUES (:n,'test',-6.9,107.6) RETURNING id"
                    ),
                    {"n": f"RWY-loc-{self.suffix}"},
                ).fetchone()[0]
            )
            self.loc_lain = str(
                conn.execute(
                    text(
                        "INSERT INTO locations (name, region, latitude, longitude) "
                        "VALUES (:n,'test',-6.2,106.8) RETURNING id"
                    ),
                    {"n": f"RWY-lain-{self.suffix}"},
                ).fetchone()[0]
            )
            self.sup = str(
                conn.execute(
                    text(
                        "INSERT INTO suppliers (name, location_id, reliability_score) "
                        "VALUES (:n,:l,0.8) RETURNING id"
                    ),
                    {"n": f"RWY-sup-{self.suffix}", "l": self.loc},
                ).fetchone()[0]
            )
            self.komoditas = str(
                conn.execute(
                    text("SELECT id FROM commodities WHERE name=:k"), {"k": KOMODITAS}
                ).fetchone()[0]
            )
            self.head = self._user(conn, "sppg_head", self.loc)
            self.monitor = self._user(conn, "bgn_monitor", None)
        eng.dispose()

    def _user(self, conn, role, loc):
        uid = uuid.uuid4()
        conn.execute(
            text(
                "INSERT INTO users (id, email, name, role, location_id, password_hash) "
                "VALUES (:id,:e,:n,:r,:l,:p)"
            ),
            {
                "id": str(uid),
                "e": f"rwy-{role}-{uid.hex[:10]}@test.local",
                "n": f"RWY {role}",
                "r": role,
                "l": loc,
                "p": bcrypt.hashpw(b"rwy-test-pw", bcrypt.gensalt()).decode(),
            },
        )
        return str(uid)

    def batch(self, loc, kg="100") -> str:
        bid = uuid.uuid4()
        panen = datetime.now(timezone.utc) - timedelta(hours=3)
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO batches (id, supplier_id, location_id, commodity_id, "
                    "quantity_kg, harvested_at, usable_until, safety_status, "
                    "quarantine_status) "
                    "VALUES (:id,:sup,:loc,:k,:q,:h,:u,'pass','none')"
                ),
                {
                    "id": str(bid),
                    "sup": self.sup,
                    "loc": loc,
                    "k": self.komoditas,
                    "q": Decimal(kg),
                    "h": panen,
                    "u": datetime.now(timezone.utc) + timedelta(days=3),
                },
            )
        eng.dispose()
        return str(bid)

    def ikat_po(self, batch_id: str, price="25000.00") -> str:
        """PO + bukti `human_inspection` yang mengikat batch ini ke PO itu.

        Jalur atribusi harga di repo ini hanya satu (lihat
        `app.services.receipt_value`): bukti `human_inspection` terbaru yang
        memuat `batch_ids`. Tanpa baris ini harga memang TIDAK ADA, dan itu
        yang diuji di kasus "tidak tercatat".
        """
        nomor = f"RWY-{self.suffix}-{len(self.po_numbers)}"
        self.po_numbers.append(nomor)
        did = uuid.uuid4()
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO decisions (id, decision_type, status, commodity_id, "
                    "quantity_kg, target_location_id, proposed_by, expires_at) "
                    "VALUES (:id,'supplier_procurement','executed',:k,:q,:l,"
                    "'supervisor_agent',:exp)"
                ),
                {
                    "id": str(did),
                    "k": self.komoditas,
                    "q": Decimal("300"),
                    "l": self.loc,
                    "exp": datetime.now(timezone.utc) + timedelta(hours=6),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO sap_mock_purchase_orders (po_number, supplier_id, "
                    "material_number, ordered_quantity, price, decision_id, status) "
                    "VALUES (:po,:sup,'MAT-TELUR',:q,:p,:d,'submitted')"
                ),
                {
                    "po": nomor,
                    "sup": self.sup,
                    "q": Decimal("300"),
                    "p": Decimal(price),
                    "d": str(did),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
                    "VALUES (:d,'human_inspection',:p)"
                ),
                {
                    "d": str(did),
                    "p": f'{{"batch_ids": ["{batch_id}"]}}',
                },
            )
        eng.dispose()
        return nomor

    def receipt(
        self,
        batch_id: str,
        status="menunggu",
        recorded_at=None,
        note=None,
    ) -> str:
        rid = uuid.uuid4()
        kapan = recorded_at or datetime.now(timezone.utc)
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO batch_receipts (id, batch_id, checked, recorded_by, "
                    "recorded_at, status, reviewed_by, reviewed_at, review_note) "
                    "VALUES (:id,:b,:c,:u,:t,:s,:v,:r,:n)"
                ),
                {
                    "id": str(rid),
                    "b": batch_id,
                    "c": '{"suhu": true, "kemasan": true, "jumlah": true}',
                    "u": self.head,
                    "t": kapan,
                    "s": status,
                    "v": self.head if status != "menunggu" else None,
                    "r": kapan if status != "menunggu" else None,
                    "n": note,
                },
            )
        eng.dispose()
        return str(rid)

    def tutup(self):
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text("DELETE FROM sap_mock_purchase_orders WHERE po_number LIKE :p"),
                {"p": f"RWY-{self.suffix}%"},
            )
            ids = [
                r[0]
                for r in conn.execute(
                    text("SELECT id FROM decisions WHERE target_location_id IN (:a,:b)"),
                    {"a": self.loc, "b": self.loc_lain},
                ).fetchall()
            ]
            if ids:
                conn.execute(
                    text("DELETE FROM agent_traces WHERE decision_id = ANY(:i)"),
                    {"i": ids},
                )
                conn.execute(
                    text("DELETE FROM decision_evidence WHERE decision_id = ANY(:i)"),
                    {"i": ids},
                )
                conn.execute(
                    text("DELETE FROM decisions WHERE id = ANY(:i)"), {"i": ids}
                )
            conn.execute(
                text("DELETE FROM batches WHERE location_id IN (:a,:b)"),
                {"a": self.loc, "b": self.loc_lain},
            )
            conn.execute(text("DELETE FROM suppliers WHERE id = :s"), {"s": self.sup})
            conn.execute(
                text("DELETE FROM users WHERE location_id IN (:a,:b)"),
                {"a": self.loc, "b": self.loc_lain},
            )
            conn.execute(
                text("DELETE FROM locations WHERE id IN (:a,:b)"),
                {"a": self.loc, "b": self.loc_lain},
            )
        eng.dispose()


@pytest.fixture()
def fx():
    f = _Fx()
    try:
        yield f
    finally:
        f.tutup()


def _get(client, fx, **params):
    qs = {"supplier_id": fx.sup, **params}
    return client.get(
        "/receipts/riwayat",
        params=qs,
        headers={"Authorization": f"Bearer {_token(fx.head, 'sppg_head', fx.loc)}"},
    )


def test_menunggu_dua_kolom_kg_dan_nilai_perkiraan(client, fx):
    batch = fx.batch(fx.loc, kg="120")
    fx.ikat_po(batch, price="25000.00")
    fx.receipt(batch, status="menunggu")

    r = _get(client, fx)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ringkasan"]["total"] == 1
    row = data["items"][0]

    # §8.2 — dua angka kg berdiri sendiri; diterima KOSONG sebelum disetujui.
    assert row["ordered_kg"] == 120.0
    assert row["received_kg"] is None
    assert row["batch_quantity_kg"] == 120.0
    # §8.3 — asal harga bisa diucapkan: kg × Rp/kg dari PO …
    assert row["unit_price_idr"] == 25000.0
    assert row["po_number"] == f"RWY-{fx.suffix}-0"
    # Nilai pembukuan belum ada; perkiraan ada.
    assert row["accepted_value_idr"] is None
    assert row["estimated_value_idr"] == 3000000.0
    # Konteks pemasok & batch untuk tabel halaman Pemasok.
    assert row["supplier_id"] == fx.sup
    assert row["supplier"] == f"RWY-sup-{fx.suffix}"
    assert row["commodity"] == KOMODITAS
    assert row["batch_ref"] == batch[:8]
    assert row["checked_count"] == 3

    assert data["ringkasan"]["menunggu"] == 1
    assert data["ringkasan"]["nilai_diterima_idr"] == 0.0
    assert data["ringkasan"]["nilai_menunggu_idr"] == 3000000.0
    assert data["ringkasan"]["kg_diterima"] == 0.0


def test_disetujui_membawa_kg_diterima_dan_nilai_pembukuan(client, fx):
    batch = fx.batch(fx.loc, kg="80")
    fx.ikat_po(batch, price="30000.00")
    fx.receipt(batch, status="disetujui")

    data = _get(client, fx).json()
    row = data["items"][0]
    assert row["status"] == "disetujui"
    assert row["received_kg"] == 80.0
    assert row["accepted_value_idr"] == 2400000.0
    assert data["ringkasan"]["disetujui"] == 1
    assert data["ringkasan"]["nilai_diterima_idr"] == 2400000.0
    assert data["ringkasan"]["kg_diterima"] == 80.0


def test_ditolak_tidak_pernah_membawa_kg_diterima(client, fx):
    batch = fx.batch(fx.loc, kg="60")
    fx.ikat_po(batch, price="20000.00")
    fx.receipt(batch, status="ditolak", note="kemasan bocor")

    data = _get(client, fx).json()
    row = data["items"][0]
    assert row["status"] == "ditolak"
    assert row["received_kg"] is None
    assert row["accepted_value_idr"] is None
    assert row["review_note"] == "kemasan bocor"
    assert data["ringkasan"]["ditolak"] == 1
    assert data["ringkasan"]["nilai_diterima_idr"] == 0.0
    # Barang yang sudah ditolak BUKAN "nilai menunggu": perkiraannya tidak
    # boleh masuk angka kepala tabel bersama catatan yang masih diputuskan.
    assert data["ringkasan"]["nilai_menunggu_idr"] == 0.0


def test_tanpa_ikatan_po_nilai_tidak_tercatat_bukan_nol(client, fx):
    batch = fx.batch(fx.loc, kg="40")
    fx.receipt(batch, status="disetujui")

    data = _get(client, fx).json()
    row = data["items"][0]
    assert row["unit_price_idr"] is None
    assert row["po_number"] is None
    assert row["accepted_value_idr"] is None
    assert row["estimated_value_idr"] is None
    assert data["ringkasan"]["tanpa_harga"] == 1


def test_ringkasan_menghitung_semua_baris_walau_limit_memotong_daftar(client, fx):
    for kg in ("10", "20", "30"):
        batch = fx.batch(fx.loc, kg=kg)
        fx.receipt(batch, status="menunggu")

    data = _get(client, fx, limit=2).json()
    assert len(data["items"]) == 2
    # Angka kepala tabel = seluruh baris dalam cakupan, bukan halaman ini.
    assert data["ringkasan"]["total"] == 3
    assert data["ringkasan"]["kg_dipesan"] == 60.0


def test_penyaring_status_dan_urutan_terbaru_dulu(client, fx):
    lama = fx.batch(fx.loc, kg="10")
    baru = fx.batch(fx.loc, kg="20")
    fx.receipt(lama, status="disetujui", recorded_at=datetime.now(timezone.utc) - timedelta(days=2))
    fx.receipt(baru, status="menunggu")

    semua = _get(client, fx).json()["items"]
    assert [r["ordered_kg"] for r in semua] == [20.0, 10.0]

    hanya_menunggu = _get(client, fx, status="menunggu").json()["items"]
    assert len(hanya_menunggu) == 1
    assert hanya_menunggu[0]["ordered_kg"] == 20.0


def test_cakupan_lokasi_sama_dengan_antrean_menunggu(client, fx):
    batch_lain = fx.batch(fx.loc_lain, kg="50")
    fx.receipt(batch_lain, status="menunggu")

    # Kepala SPPG lokasi A tidak melihat penerimaan lokasi B.
    assert _get(client, fx).json()["ringkasan"]["total"] == 0

    # Pemantau tanpa lokasi melihat seluruh jaringan (lokasi mana pun).
    r = client.get(
        "/receipts/riwayat",
        params={"supplier_id": fx.sup},
        headers={"Authorization": f"Bearer {_token(fx.monitor, 'bgn_monitor')}"},
    )
    assert r.status_code == 200
    assert r.json()["ringkasan"]["total"] == 1


def test_supplier_lain_tidak_ikut_terbaca(client, fx):
    batch = fx.batch(fx.loc, kg="70")
    fx.receipt(batch, status="menunggu")

    siapa_pun = uuid.uuid4()
    r = client.get(
        "/receipts/riwayat",
        params={"supplier_id": str(siapa_pun)},
        headers={"Authorization": f"Bearer {_token(fx.monitor, 'bgn_monitor')}"},
    )
    assert r.status_code == 200
    assert r.json()["ringkasan"]["total"] == 0
