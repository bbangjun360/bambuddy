from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class ErpDraftWriteRecord(Base):
    """Local audit state for ERP Draft result writes.

    This table records adapter delivery attempts only. It is not a print queue,
    print history, inventory ledger, or accounting ledger.
    """

    __tablename__ = "erp_draft_write_records"
    __table_args__ = (UniqueConstraint("event_uuid", name="uq_erp_draft_write_event_uuid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_request_id: Mapped[int] = mapped_column(ForeignKey("erp_production_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    event_uuid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    print_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(64), nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dead_letter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    erp_document_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    erp_doctype: Mapped[str | None] = mapped_column(String(128), nullable=True)
    erp_docstatus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erp_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reconciliation_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reconciliation_mismatches: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    source_request: Mapped["ErpProductionRequest"] = relationship()


from backend.app.models.erp_readonly import ErpProductionRequest  # noqa: E402
