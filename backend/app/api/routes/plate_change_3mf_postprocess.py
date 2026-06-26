from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.permissions import Permission
from backend.app.models.printer import Printer
from backend.app.models.user import User
from backend.app.schemas.plate_change_3mf_postprocess import (
    PlateChange3mfCanaryStartRequest,
    PlateChange3mfCanaryUploadRequest,
    PlateChange3mfPostprocessPlanRequest,
)
from backend.app.services.plate_change_3mf_postprocess import (
    PlateChange3mfPostprocessError,
    default_controlled_roots,
    default_real_sample_output_root,
    default_real_sample_root,
    plate_change_3mf_physical_canary_service,
    plate_change_3mf_postprocess_service,
)

router = APIRouter(prefix="/plate-change-3mf", tags=["plate-change-3mf"])


class PlateChange3mfPhysicalCanaryPrinterOps:
    def bind_printer(self, printer: Printer) -> "_BoundPlateChange3mfPhysicalCanaryPrinterOps":
        return _BoundPlateChange3mfPhysicalCanaryPrinterOps(printer)


class _BoundPlateChange3mfPhysicalCanaryPrinterOps:
    def __init__(self, printer: Printer) -> None:
        self.printer = printer

    def is_connected(self, printer_id: str) -> bool:
        from backend.app.services.printer_manager import printer_manager

        return printer_manager.is_connected(int(printer_id))

    def get_state(self, printer_id: str):
        from backend.app.services.printer_manager import printer_manager

        return printer_manager.get_status(int(printer_id))

    async def upload_artifact(self, printer_id: str, artifact_path: Path) -> str:
        from backend.app.services.bambu_ftp import upload_file_async
        from backend.app.utils.filename import derive_remote_filename

        remote_filename = derive_remote_filename(artifact_path.name)
        remote_path = f"/{remote_filename}"
        uploaded = await upload_file_async(
            self.printer.ip_address,
            self.printer.access_code,
            artifact_path,
            remote_path,
            printer_model=self.printer.model,
        )
        if not uploaded:
            return ""
        return remote_filename

    async def start_print(self, printer_id: str, remote_path: str) -> bool:
        from backend.app.services.printer_manager import printer_manager

        return printer_manager.start_print(int(printer_id), remote_path)


plate_change_3mf_physical_canary_ops = PlateChange3mfPhysicalCanaryPrinterOps()


def _require_enabled() -> None:
    if not settings.farm_plate_change_3mf_postprocess_enabled:
        raise HTTPException(status_code=404, detail="Plate-change 3MF post-processing prototype is disabled")


def _require_safe_dry_run_runtime() -> None:
    if not settings.farm_plate_change_3mf_postprocess_dry_run:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "dry_run_required",
                "message": "Plate-change 3MF post-processing prototype is dry-run only",
            },
        )


def _physical_canary_flags() -> dict[str, object]:
    return {
        "physical_canary_enabled": settings.farm_plate_change_3mf_physical_canary_enabled,
        "allow_printer_upload": settings.farm_plate_change_3mf_allow_printer_upload,
        "allow_print_start": settings.farm_plate_change_3mf_allow_print_start,
        "single_printer_only": settings.farm_plate_change_3mf_canary_single_printer_only,
        "require_human_confirmation": settings.farm_plate_change_3mf_canary_require_human_confirmation,
        "disable_auto_retry": settings.farm_plate_change_3mf_canary_disable_auto_retry,
        "max_starts": settings.farm_plate_change_3mf_canary_max_starts,
        "output_roots": [settings.farm_plate_change_3mf_output_root or default_real_sample_output_root()],
    }


def _require_physical_canary_enabled() -> None:
    if not settings.farm_plate_change_3mf_physical_canary_enabled:
        raise HTTPException(status_code=404, detail="Supervised physical 3MF canary is disabled")


async def _canary_printer_ops_for_body(
    target_printer_ids: list[str],
    db: AsyncSession,
):
    if len(target_printer_ids) != 1:
        return plate_change_3mf_physical_canary_ops
    try:
        printer_pk = int(target_printer_ids[0])
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_printer_id", "message": "Canary printer id must be a Bambuddy printer id"},
        ) from exc
    printer = await db.scalar(select(Printer).where(Printer.id == printer_pk))
    if printer is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "printer_not_found", "message": "Canary printer was not found"},
        )
    ops = plate_change_3mf_physical_canary_ops
    if hasattr(ops, "bind_printer"):
        ops = ops.bind_printer(printer)
    if hasattr(ops, "is_connected") and not ops.is_connected(str(printer_pk)):
        raise HTTPException(
            status_code=400,
            detail={"code": "printer_not_connected", "message": "Canary printer is not connected"},
        )
    return ops


def _error_detail(exc: PlateChange3mfPostprocessError) -> dict[str, str]:
    return {"code": exc.code, "message": exc.message}


@router.post("/postprocess-plans", status_code=202)
async def create_postprocess_plan(
    body: PlateChange3mfPostprocessPlanRequest,
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    _require_safe_dry_run_runtime()
    try:
        return plate_change_3mf_postprocess_service.create_plan(
            source_path=body.source_path,
            enabled=settings.farm_plate_change_3mf_postprocess_enabled,
            dry_run=settings.farm_plate_change_3mf_postprocess_dry_run,
            request_dry_run=body.dry_run,
            allow_output_artifact=settings.farm_plate_change_3mf_allow_output_artifact,
            allow_real_sample_output=settings.farm_plate_change_3mf_allow_real_sample_output,
            create_output_artifact=body.create_output_artifact,
            real_sample_output_review=body.real_sample_output_review,
            output_dir=body.output_dir,
            allowed_roots=default_controlled_roots(settings.base_dir),
            real_sample_roots=[settings.farm_plate_change_3mf_real_sample_root or default_real_sample_root()],
            output_roots=[settings.farm_plate_change_3mf_output_root or default_real_sample_output_root()],
        )
    except PlateChange3mfPostprocessError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(exc)) from exc


@router.get("/status")
async def get_postprocess_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return plate_change_3mf_postprocess_service.status_snapshot(
        enabled=settings.farm_plate_change_3mf_postprocess_enabled,
        dry_run=settings.farm_plate_change_3mf_postprocess_dry_run,
        allow_output_artifact=settings.farm_plate_change_3mf_allow_output_artifact,
        allow_real_sample_output=settings.farm_plate_change_3mf_allow_real_sample_output,
    )

@router.get("/canary-status")
async def get_physical_canary_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return plate_change_3mf_physical_canary_service.canary_status(**_physical_canary_flags())


@router.post("/canary-upload", status_code=202)
async def create_physical_canary_upload(
    body: PlateChange3mfCanaryUploadRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_physical_canary_enabled()
    try:
        ops = await _canary_printer_ops_for_body(body.target_printer_ids, db)
        return await plate_change_3mf_physical_canary_service.canary_upload(
            body.model_dump(),
            printer_ops=ops,
            **_physical_canary_flags(),
        )
    except PlateChange3mfPostprocessError as exc:
        status_code = 404 if exc.code == "physical_canary_disabled" else 400
        raise HTTPException(status_code=status_code, detail=_error_detail(exc)) from exc


@router.post("/canary-start", status_code=202)
async def create_physical_canary_start(
    body: PlateChange3mfCanaryStartRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_physical_canary_enabled()
    try:
        ops = await _canary_printer_ops_for_body(body.target_printer_ids, db)
        printer_state = ops.get_state(body.target_printer_ids[0]) if hasattr(ops, "get_state") else None
        return await plate_change_3mf_physical_canary_service.canary_start(
            body.model_dump(),
            printer_ops=ops,
            printer_state=printer_state,
            **_physical_canary_flags(),
        )
    except PlateChange3mfPostprocessError as exc:
        status_code = 404 if exc.code == "physical_canary_disabled" else 400
        raise HTTPException(status_code=status_code, detail=_error_detail(exc)) from exc
