"""
Supplier model - represents food suppliers.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Supplier(Base):
    """Supplier model for food providers."""
    
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint("reliability_score >= 0 AND reliability_score <= 1", name="check_reliability"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    reliability_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.80)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
