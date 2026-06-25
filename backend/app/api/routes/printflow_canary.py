from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.schemas.printflow_canary import PrintFlowCanaryReadinessRequest, PrintFlowRealCanaryRunRequest
from backend.app.services.printflow_canary import (
    MockPrintFlowCanaryReadinessAdapter,
    PrintFlowCanaryError,
    RealPrintFlowCanaryAdapter,
    printflow_canary_service,
)

router = APIRouter(prefix="/printflow-canary", tags=["printflow-canary"])


def _require_enabled() -> None:
    if not settings.farm_printflow_canary_readiness_enabled:
        raise HTTPException(status_code=404, detail="PrintFlow canary readiness is disabled")


def printflow_real_canary_adapter_factory(*, base_url: str, api_token: str) -> RealPrintFlowCanaryAdapter:
    return RealPrintFlowCanaryAdapter(base_url=base_url, api_token=api_token)


def _require_real_canary_enabled() -> None:
    if not settings.farm_printflow_canary_readiness_enabled:
        raise HTTPException(status_code=404, detail="real PrintFlow canary is disabled")


def _error_detail(exc: PrintFlowCanaryError) -> dict[str, str]:
    return {"code": exc.code, "message": exc.message}


@router.post("/readiness-checks", status_code=202)
async def create_readiness_check(
    body: PrintFlowCanaryReadinessRequest,
    _: User | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_UPDATE),
):
    _require_enabled()
    if not settings.farm_printflow_canary_dry_run:
        raise HTTPException(
            status_code=400,
            detail={"code": "dry_run_required", "message": "PrintFlow canary readiness is dry-run only"},
        )
    try:
        adapter = MockPrintFlowCanaryReadinessAdapter(scenario=body.mock_scenario)
        return printflow_canary_service.create_check(
            body.model_dump(),
            adapter=adapter,
            human_approval_required=settings.farm_printflow_canary_human_approval_required,
        )
    except PrintFlowCanaryError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_mock_scenario", "message": str(exc)}) from exc


@router.post("/real-canary-runs", status_code=202)
async def create_real_canary_run(
    body: PrintFlowRealCanaryRunRequest,
    _: User | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_UPDATE),
):
    _require_real_canary_enabled()
    try:
        return printflow_canary_service.create_real_canary(
            body.model_dump(),
            adapter_factory=printflow_real_canary_adapter_factory,
            real_adapter_enabled=settings.farm_printflow_real_adapter_enabled,
            global_dry_run=settings.farm_printflow_canary_dry_run,
            human_approval_required=settings.farm_printflow_canary_human_approval_required,
            single_printer_only=settings.farm_printflow_canary_single_printer_only,
            base_url=settings.farm_printflow_base_url,
            api_token=settings.farm_printflow_api_token,
        )
    except PrintFlowCanaryError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(exc)) from exc


@router.get("/status")
async def get_readiness_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_READ),
):
    _require_enabled()
    return printflow_canary_service.status_snapshot()


@router.get("/metrics", response_class=Response)
async def get_readiness_metrics(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_READ),
):
    _require_enabled()
    return Response(
        content=printflow_canary_service.render_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
