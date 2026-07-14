from datetime import datetime

from pydantic import BaseModel


class FarmCostLedgerItem(BaseModel):
    id: int
    print_log_entry_id: int
    archive_id: int | None
    print_name: str | None
    printer_name: str | None
    printer_id: int | None
    status: str
    attempt_number: int | None
    attempt_kind: str
    policy_version: str
    currency: str

    estimated_filament_grams: float | None
    estimated_duration_seconds: int | None
    estimated_material_cost: float | None
    estimated_energy_kwh: float | None
    estimated_energy_cost: float | None
    estimated_machine_cost: float | None
    estimated_total_cost: float | None

    actual_filament_grams: float | None
    actual_duration_seconds: int | None
    actual_material_cost: float | None
    actual_energy_kwh: float | None
    actual_energy_cost: float | None
    actual_machine_cost: float | None
    actual_total_cost: float | None
    variance_cost: float | None
    cost_complete: bool
    missing_actual_components: list[str]

    captured_at: datetime
    run_created_at: datetime


class FarmCostLedgerSummary(BaseModel):
    total_run_count: int
    completed_run_count: int
    failed_run_count: int
    cancelled_run_count: int
    original_run_count: int
    reprint_run_count: int
    incomplete_run_count: int

    estimated_material_cost: float
    estimated_energy_cost: float
    estimated_machine_cost: float
    estimated_total_cost: float
    actual_material_cost: float
    actual_energy_cost: float
    actual_machine_cost: float
    actual_total_cost: float
    variance_cost: float
    failed_actual_total_cost: float
    reprint_actual_total_cost: float


class FarmCostLedgerResponse(BaseModel):
    currency: str
    items: list[FarmCostLedgerItem]
    total: int
    limit: int
    offset: int
    summary: FarmCostLedgerSummary
