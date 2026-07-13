#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _require_safe_target(base_url: str) -> None:
    host = (urlparse(base_url).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("ERP_ALLOW_NON_LOOPBACK") != "true":
        raise RuntimeError("ERP live contract only allows loopback targets unless ERP_ALLOW_NON_LOOPBACK=true")


async def _run() -> dict[str, object]:
    from backend.app.services.erp_draft_write import ErpDraftWriteClient, format_frappe_datetime
    from backend.app.services.erp_readonly import ErpReadOnlyClient, validate_work_order

    base_url = _required_env("ERP_BASE_URL").rstrip("/")
    api_token = _required_env("ERP_API_TOKEN")
    work_order_id = _required_env("ERP_WORK_ORDER_ID")
    event_id = os.environ.get("ERP_EVENT_ID", "wp111-live-contract-event-0001")
    expected_artifact = os.environ.get("ERP_EXPECTED_ARTIFACT", "fixture-cube-v1")
    expected_profile = os.environ.get("ERP_EXPECTED_PROFILE", "p1p-pla-fixture-v1")
    _require_safe_target(base_url)

    read_client = ErpReadOnlyClient(base_url, api_token, api_prefix="/api", timeout=15.0)
    draft_client = ErpDraftWriteClient(base_url, api_token, api_prefix="/api", timeout=15.0)
    try:
        work_order_payload = await read_client.fetch_work_order(work_order_id)
        work_order = validate_work_order(work_order_payload, work_order_id)
        if work_order.artifact_reference != expected_artifact:
            raise RuntimeError("ERP Work Order artifact reference did not match the synthetic fixture")
        if work_order.profile_set_id != expected_profile:
            raise RuntimeError("ERP Work Order profile set did not match the synthetic fixture")

        draft_payload = {
            "farm_event_id": event_id,
            "production_request_id": 111,
            "external_work_order_id": work_order.name,
            "production_item": work_order.production_item,
            "quantity_completed": work_order.quantity,
            "completed_at": format_frappe_datetime(
                datetime(2026, 7, 10, 0, 0, 0, tzinfo=timezone.utc),
                timezone_name="Asia/Seoul",
            ),
        }
        first = await draft_client.create_or_lookup_draft_result(draft_payload, idempotency_key=event_id)
        second = await draft_client.create_or_lookup_draft_result(draft_payload, idempotency_key=event_id)
        reconciled = await draft_client.lookup_draft_result(event_id)

        if first.document.name != second.document.name or second.document.name != reconciled.name:
            raise RuntimeError("ERP idempotency contract returned different Draft document names")
        if reconciled.docstatus != 0:
            raise RuntimeError("ERP live contract produced a non-Draft document")

        return {
            "status": "ok",
            "erp_api_prefix": "/api",
            "work_order_id": work_order.name,
            "production_item": work_order.production_item,
            "draft_document": reconciled.name,
            "draft_docstatus": reconciled.docstatus,
            "first_created": first.created,
            "second_created": second.created,
            "idempotent": True,
        }
    finally:
        await read_client.close()
        await draft_client.close()


def main() -> None:
    print(json.dumps(asyncio.run(_run()), sort_keys=True))


if __name__ == "__main__":
    main()
