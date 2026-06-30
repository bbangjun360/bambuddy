from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class SwapmodQueueReadinessBinding(Base):
    """Durable binding between a READY SwapMod bed proof and one queue item."""

    __tablename__ = "swapmod_queue_readiness_bindings"
    __table_args__ = (
        UniqueConstraint("binding_key", name="uq_swapmod_queue_readiness_binding_key"),
        UniqueConstraint("queue_item_id", name="uq_swapmod_queue_readiness_queue_item_id"),
        UniqueConstraint("bed_cycle_key", name="uq_swapmod_queue_readiness_bed_cycle_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    binding_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    queue_item_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    printer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    source_cycle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_print_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bed_cycle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    queue_archive_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_library_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_plate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_fingerprint: Mapped[str] = mapped_column(String(256), nullable=False)

    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
