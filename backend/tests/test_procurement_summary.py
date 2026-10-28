"""GET /procurement/summary — angka pengadaan nyata untuk tile Overview.

Kenapa endpoint ini ada (laporan pemilik 27 Okt 2026: "setelah pengadaan
dieksekusi, Overview tidak berubah"): tiga kartu Overview yang ada hanya
membaca pasokan/kebutuhan (yang memang TIDAK berubah saat execute — stok baru
bertambah setelah penerimaan disetujui) dan satu antrean keputusan. Tidak ada
satu pun angka di Overview yang berasal dari PO yang terbit, jejak ACT, atau
batch yang berangkat, sehingga eksekusi pengadaan tidak terlihat di layar
 walau ia benar-benar mengubah tiga tabel.

Kontrak yang dikunci di sini:
- periode DIHITUNG SERVER (hari kalender Asia/Jakarta), sama dengan `GET /kpi`;
- cakupan lokasi mengikuti peran (SPPG = lokasinya, bgn_monitor = nasional);
- angka berasal dari `sap_mock_purchase_orders`, `agent_traces` (step ACT), dan
  `batches.dispatched_at` — bukan proksi;
- nilai komitmen = Σ(price × ordered_quantity) pada periode itu;
- PO di lokasi lain dan PO di luar periode TIDAK boleh ikut.

Asersi memakai DELTA (sebelum vs sesudah menyisipkan baris uji), bukan
`count(*)` mutlak: basis data uji dipakai bersama suite lain, jadi angka
mutlak apa pun akan rapuh.
"""

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
    import os

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
                    {"n": f"OPS-loc-{self.suffix}"},
                ).fetchone()[0]
            )
            self.loc_lain = str(
                conn.execute(
                    text(
                        "INSERT INTO locations (name, region, latitude, longitude) "
                        "VALUES (:n,'test',-6.2,106.8) RETURNING id"
                    ),
                    {"n": f"OPS-lain-{self.suffix}"},
                ).fetchone()[0]
            )
            self.sup = str(
                conn.execute(
                    text(
                        "INSERT INTO suppliers (name, location_id, reliability_score) "
                        "VALUES (:n,:l,0.8) RETURNING id"
                    ),
                    {"n": f"OPS-sup-{self.suffix}", "l": self.loc},
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
                "e": f"ops-{role}-{uid.hex[:10]}@test.local",
                "n": f"OPS {role}",
                "r": role,
                "l": loc,
                "p": bcrypt.hashpw(b"ops-test-pw", bcrypt.gensalt()).decode(),
            },
        )
        return str(uid)

    def decision(self, loc, status="executed", created_at=None) -> str:
        """Keputusan operasional (bukan tipe administrasi) di lokasi tertentu."""
        did = uuid.uuid4()
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO decisions (id, decision_type, status, commodity_id, "
                    "quantity_kg, target_location_id, proposed_by, expires_at, created_at) "
                    "VALUES (:id,'supplier_procurement',:s,:k,:q,:l,'supervisor_agent',"
                    ":exp,:c)"
                ),
                {
                    "id": str(did),
                    "s": status,
                    "k": self.komoditas,
                    "q": Decimal("300"),
                    "l": loc,
                    "exp": datetime.now(timezone.utc) + timedelta(hours=6),
                    "c": created_at or datetime.now(timezone.utc),
                },
            )
        eng.dispose()
        return str(did)

    def po(self, loc, price="32500.00", qty="300.00", created_at=None) -> str:
        nomor = f"OPS-{self.suffix}-{len(self.po_numbers)}"
        self.po_numbers.append(nomor)
        did = self.decision(loc, created_at=created_at)
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO sap_mock_purchase_orders (po_number, supplier_id, "
                    "material_number, ordered_quantity, price, decision_id, status, created_at) "
                    "VALUES (:po,:sup,:mat,:q,:p,:d,'submitted',:c)"
                ),
                {
                    "po": nomor,
                    "sup": self.sup,
                    "mat": "MAT-TELUR",
                    "q": Decimal(qty),
                    "p": Decimal(price),
                    "d": did,
                    "c": created_at or datetime.now(timezone.utc),
                },
            )
        eng.dispose()
        return nomor

    def act(self, loc, step_at=None) -> str:
        did = self.decision(loc)
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agent_traces (decision_id, step_name, tool_called, step_at) "
                    "VALUES (:d,'ACT','sap_mock.create_purchase_order',:t)"
                ),
                {"d": did, "t": step_at or datetime.now(timezone.utc)},
            )
        eng.dispose()
        return did

    def batch(self, loc, dispatched_at=None, harvested_at=None) -> str:
        bid = uuid.uuid4()
        panen = harvested_at or (datetime.now(timezone.utc) - timedelta(hours=2))
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO batches (id, supplier_id, location_id, commodity_id, "
                    "quantity_kg, harvested_at, usable_until, safety_status, "
                    "quarantine_status, dispatched_at) "
                    "VALUES (:id,:sup,:loc,:k,:q,:h,:u,'pass','none',:d)"
                ),
                {
                    "id": str(bid),
                    "sup": self.sup,
                    "loc": loc,
                    "k": self.komoditas,
                    "q": Decimal("100"),
                    "h": panen,
                    "u": datetime.now(timezone.utc) + timedelta(days=3),
                    "d": dispatched_at,
                },
            )
        eng.dispose()
        return str(bid)

    def receipt(self, loc, kg="100", reviewed_at=None, status="disetujui") -> str:
        """Penerimaan atas satu batch; kg yang "diterima" = batches.quantity_kg."""
        bid = uuid.uuid4()
        panen = datetime.now(timezone.utc) - timedelta(hours=2)
        kapan = reviewed_at or datetime.now(timezone.utc)
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
            conn.execute(
                text(
                    "INSERT INTO batch_receipts (batch_id, recorded_by, recorded_at, "
                    "status, reviewed_by, reviewed_at) "
                    "VALUES (:b,:u,:t,:s,:u,:r)"
                ),
                {
                    "b": str(bid),
                    "u": self.head,
                    "t": panen,
                    "s": status,
                    "r": kapan if status == "disetujui" else None,
                },
            )
        eng.dispose()
        return str(bid)

    def tutup(self):
        eng = _db()
        with eng.begin() as conn:
            conn.execute(
                text("DELETE FROM sap_mock_purchase_orders WHERE po_number LIKE :p"),
                {"p": f"OPS-{self.suffix}%"},
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
                    text("DELETE FROM decisions WHERE id = ANY(:i)"), {"i": ids}
                )
            conn.execute(
                text("DELETE FROM batches WHERE location_id IN (:a,:b)"),
                {"a": self.loc, "b": self.loc_lain},
            )
            conn.execute(
                text("DELETE FROM suppliers WHERE id = :s"), {"s": self.sup}
            )
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


def _ringkas(client, tok, **params):
    r = client.get(
        "/procurement/summary", params=params, headers={"Authorization": f"Bearer {tok}"}
    )
    return r


def _nilai(bagian) -> Decimal:
    return Decimal(str(bagian["total_value"]))


# --------------------------------------------------------------------- RED


def test_endpoint_ada_dan_mengirim_periode_server(client, fx):
    tok = _token(fx.head, "sppg_head", fx.loc)
    r = _ringkas(client, tok, periode="today")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["period"]["key"] == "today"
    assert body["period"]["label"] == "Hari ini"
    assert body["period"]["timezone"] == "Asia/Jakarta"
    assert body["period"]["start"] and body["period"]["end"]
    assert body["data_source"] == "live_aggregate"
    assert body["scope"]["location_id"] == fx.loc


def test_po_act_dan_truk_pada_periode_bertambah_tepat_satu(client, fx):
    """Delta, bukan count(*) mutlak: suite lain memakai basis data yang sama."""
    tok = _token(fx.head, "sppg_head", fx.loc)
    awal = _ringkas(client, tok, periode="today").json()

    nomor = fx.po(fx.loc, price="32500.00", qty="300.00")  # 9.750.000
    fx.act(fx.loc)
    fx.batch(fx.loc, dispatched_at=datetime.now(timezone.utc))

    akhir = _ringkas(client, tok, periode="today").json()

    po_a, po_b = awal["purchase_orders"], akhir["purchase_orders"]
    assert po_b["state"] == "available"
    assert po_b["currency"] == "IDR"
    assert po_b["count"] == po_a["count"] + 1
    assert _nilai(po_b) - _nilai(po_a) == Decimal("9750000.00")
    assert po_b["last"]["po_number"] == nomor
    assert po_b["last"]["status"] == "submitted"

    assert akhir["decisions_executed"]["count"] == awal["decisions_executed"]["count"] + 1
    assert (
        akhir["batches_dispatched"]["count"]
        == awal["batches_dispatched"]["count"] + 1
    )


def test_po_lokasi_lain_dan_di_luar_periode_tidak_dihitung(client, fx):
    tok = _token(fx.head, "sppg_head", fx.loc)
    awal = _ringkas(client, tok, periode="today").json()

    fx.po(fx.loc_lain)  # lokasi lain
    fx.act(fx.loc_lain)
    fx.batch(fx.loc_lain, dispatched_at=datetime.now(timezone.utc))
    fx.po(fx.loc, created_at=datetime.now(timezone.utc) - timedelta(days=40))  # lampau
    fx.act(fx.loc, step_at=datetime.now(timezone.utc) - timedelta(days=40))
    fx.batch(fx.loc, dispatched_at=datetime.now(timezone.utc) - timedelta(days=40),
             harvested_at=datetime.now(timezone.utc) - timedelta(days=41))

    akhir = _ringkas(client, tok, periode="today").json()
    assert akhir["purchase_orders"]["count"] == awal["purchase_orders"]["count"]
    assert _nilai(akhir["purchase_orders"]) == _nilai(awal["purchase_orders"])
    assert (
        akhir["decisions_executed"]["count"]
        == awal["decisions_executed"]["count"]
    )
    assert (
        akhir["batches_dispatched"]["count"]
        == awal["batches_dispatched"]["count"]
    )


def test_monitor_melihat_nasional_dan_bisa_pilih_lokasi(client, fx):
    fx.po(fx.loc)
    fx.po(fx.loc_lain)
    tok = _token(fx.monitor, "bgn_monitor")
    nasional = _ringkas(client, tok, periode="today")
    assert nasional.status_code == 200, nasional.text
    hanya = _ringkas(client, tok, periode="today", location_id=fx.loc_lain)
    assert hanya.status_code == 200, hanya.text
    assert hanya.json()["purchase_orders"]["count"] <= nasional.json()["purchase_orders"]["count"]
    assert hanya.json()["scope"]["location_id"] == fx.loc_lain


def test_scope_lokasi_asing_ditolak_dan_periode_ngawur_422(client, fx):
    tok = _token(fx.head, "sppg_head", fx.loc)
    asing = _ringkas(client, tok, periode="today", location_id=fx.loc_lain)
    assert asing.status_code == 403, asing.text
    ngawur = _ringkas(client, tok, periode="kemarin")
    assert ngawur.status_code == 422, ngawur.text


# ------------------------------------------------- kg diterima (permintaan pemilik)


def test_penerimaan_disetujui_menambah_kg_diterima_pada_periode(client, fx):
    """Eksekusi tidak menambah stok; penerimaan disetujui yang menambah.

    Kg "diterima" = `batches.quantity_kg` milik penerimaan berstatus `disetujui`
    dengan `reviewed_at` di dalam periode. Angka ini yang membuat Overview
    bergerak setelah barang benar-benar masuk, bukan hanya setelah PO terbit.
    """
    tok = _token(fx.head, "sppg_head", fx.loc)
    awal = _ringkas(client, tok, periode="today").json()
    assert "receipts" in awal, "kontrak kg diterima belum ada di respons"

    fx.receipt(fx.loc, kg="125.50")

    akhir = _ringkas(client, tok, periode="today").json()
    masuk = akhir["receipts"]
    assert masuk["state"] == "available"
    assert masuk["count"] == awal["receipts"]["count"] + 1
    assert Decimal(str(masuk["kg"])) - Decimal(str(awal["receipts"]["kg"])) == Decimal(
        "125.50"
    )
    assert masuk["last"]["kg"] == "125.50"
    assert masuk["last"]["reviewed_at"]


def test_penerimaan_menunggu_atau_lokasi_lain_tidak_dihitung(client, fx):
    """Yang belum disetujui bukan barang diterima; lokasi lain bukan cakupan saya."""
    tok = _token(fx.head, "sppg_head", fx.loc)
    awal = _ringkas(client, tok, periode="today").json()

    fx.receipt(fx.loc, kg="50", status="menunggu")
    fx.receipt(fx.loc_lain, kg="75", status="disetujui")
    fx.receipt(fx.loc, kg="40", reviewed_at=datetime.now(timezone.utc) - timedelta(days=40))

    akhir = _ringkas(client, tok, periode="today").json()
    assert akhir["receipts"]["count"] == awal["receipts"]["count"]
    assert Decimal(str(akhir["receipts"]["kg"])) == Decimal(str(awal["receipts"]["kg"]))
