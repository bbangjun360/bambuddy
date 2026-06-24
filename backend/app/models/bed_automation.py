from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class BedAutomationCycle(Base):
    """Durable simulated bed-cycle state owned by Bambuddy."""

    __tablename__ = "bed_automation_cycles"
    __table_args__ = (UniqueConstraint("cycle_key", name="uq_bed_automation_cycle_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    printer_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_print_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    state: Mapped[str] = mapped_column(String(64), nullable=False, default="IDLE")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ready_for_next_print: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    manual_review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    seen_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    transition_log: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    transition_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
