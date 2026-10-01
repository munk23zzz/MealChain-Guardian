"""Model User — 3 role final (Schema.md §1, Architecture.md §2).

Role: sppg_head | sppg_nutritionist | bgn_monitor.
- sppg_head/sppg_nutritionist: WAJIB punya location_id
- bgn_monitor: location_id WAJIB NULL (akses lintas lokasi, read-only)
"""

import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

VALID_ROLES = ("sppg_head", "sppg_nutritionist", "bgn_monitor")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('sppg_head','sppg_nutritionist','bgn_monitor')",
            name="check_user_role",
        ),
        # sppg_head/sppg_nutritionist wajib punya lokasi; bgn_monitor wajib NULL
        CheckConstraint(
            "(role IN ('sppg_head','sppg_nutritionist') AND location_id IS NOT NULL)"
            " OR (role = 'bgn_monitor' AND location_id IS NULL)",
            name="check_user_role_location_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
