"""Model RoadRoute — cache geometri rute JALAN (OSRM).

Kenapa tabel, bukan panggilan saat peta dibuka (keputusan pemilik 2026-10-16):
demo tidak boleh bergantung pada koneksi internet, hasil harus sama setiap kali
diperlihatkan, dan server OSRM demo publik tidak boleh dibanjiri permintaan dari
peramban pengunjung. Jadi rute diambil sekali saat seeding/sync
(`app/seed/road_routes.py`) dan disimpan di sini.

Baris tabel ini adalah **data pihak ketiga** (routing OpenStreetMap), bukan
hitungan kita sendiri. Karena itu `source` disimpan dan ditampilkan di UI —
supaya klaim "jarak tempuh" tidak pernah menyamar sebagai angka milik sistem.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RoadRoute(Base):
    __tablename__ = "road_routes"
    __table_args__ = (
        CheckConstraint("distance_m >= 0", name="road_routes_distance_check"),
        CheckConstraint("duration_s >= 0", name="road_routes_duration_check"),
        CheckConstraint("source IN ('osrm')", name="check_road_routes_source_vocab"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # Kunci ternormalisasi `profil:lat_a,lon_a>lat_b,lon_b` (4 desimal, lihat
    # app/core/road_route.py:route_key). Unik supaya sinkronisasi idempoten.
    route_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    profile: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'driving'")
    )
    origin_lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    origin_lon: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    destination_lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    destination_lon: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    # GeoJSON LineString apa adanya dari OSRM (`[lon, lat]`).
    geometry: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
