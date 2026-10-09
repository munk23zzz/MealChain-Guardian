# ADA 2 baris 777! Skrip sebelumnya meninggalkan jejak (DELETE-nya mungkin
# gagal saat skrip error). Berarti data bocor 777 manual lama dengan
# recorded_at 2026-10-05 — dan "ORM latest" dulu = 1400 karena...
# tunggu: kalau ada 777 lama, latest tetap 1400 (10-08 > 10-05). OK itu wajar.
# Bersihkan duplikat lama, lalu cek berapa baris Cianjur telur sebenarnya:
import sqlalchemy
from sqlalchemy import text

DB_SYNC = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
eng = sqlalchemy.create_engine(DB_SYNC)
with eng.begin() as c:
    c.execute(text("DELETE FROM supply_records WHERE source='manual' AND quantity_kg=777"))
rows = c = eng.connect().execute(
    text(
        "SELECT s.recorded_at, s.quantity_kg, s.source, s.id FROM supply_records s "
        "JOIN locations l ON l.id=s.location_id "
        "JOIN commodities c2 ON c2.id=s.commodity_id "
        "WHERE l.name='Cianjur' AND c2.name='telur' ORDER BY s.recorded_at DESC"
    )
).fetchall()
for r in rows:
    print(r)
