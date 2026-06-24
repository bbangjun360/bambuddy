from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class ErpProductionRequest(Base):
    """Read-only ERP Work Order import for human review.

    Rows in this table are deliberately not queue items and do not represent
    executable printer work. They preserve the external Work Order mapping and
    import status so operators can inspect or retry the read-only import later.
    """

    __tablename__ = "erp_production_requests"
    __table_args__ = (UniqueConstraint("source_system", "external_work_order_id", name="uq_erp_request_source_work_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_system: Mapped[str] = mapped_column(String(32), default="erpnext", nullable=False)
    external_work_order_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    production_item: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erp_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_set_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    library_file_id: Mapped[int | None] = mapped_column(ForeignKey("library_files.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    erp_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    library_file: Mapped["LibraryFile | None"] = relationship()


from backend.app.models.library import LibraryFile  # noqa: E402
