from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class FarmCostLedgerSnapshot(Base):
    """Immutable estimate and policy context for one actual print-log row."""

    __tablename__ = "farm_cost_ledger_snapshots"
    __table_args__ = (
        UniqueConstraint("print_log_entry_id", name="uq_farm_cost_ledger_print_log_entry"),
        CheckConstraint(
            "attempt_kind IN ('original', 'reprint', 'unlinked')",
            name="ck_farm_cost_ledger_attempt_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    print_log_entry_id: Mapped[int] = mapped_column(
        ForeignKey("print_log_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Deliberately not a foreign key: retain the original identifier if an
    # archive is later removed and PrintLogEntry.archive_id becomes NULL.
    archive_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_kind: Mapped[str] = mapped_column(String(16), nullable=False)

    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    material_rate_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy_rate_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_power_kw: Mapped[float] = mapped_column(Float, nullable=False)
    machine_rate_per_hour: Mapped[float] = mapped_column(Float, nullable=False)

    estimated_filament_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_material_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_energy_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_energy_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_machine_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
