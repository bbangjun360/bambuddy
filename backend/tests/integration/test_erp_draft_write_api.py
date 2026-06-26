from __future__ import annotations

import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import erp_draft_write as draft_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.erp_readonly import ErpProductionRequest
from backend.app.models.library import LibraryFile
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services.erp_draft_write import (
    DRAFT_ALREADY_EXISTS,
    DRAFT_CREATED,
    DRAFT_WRITE_BLOCKED,
    DRAFT_WRITE_FAILED,
    DRAFT_WRITE_RETRYABLE_FAILURE,
    ERP_DRAFT_AUTH_FAILED,
    ERP_DRAFT_INVALID_PAYLOAD,
    ERP_DRAFT_RATE_LIMITED,
    ERP_DRAFT_TIMEOUT,
    ERP_DRAFT_UPSTREAM_ERROR,
    RECONCILIATION_MATCHED,
    RECONCILIATION_MISMATCH,
    DraftDocument,
    DraftWriteClientResult,
    ErpDraftWriteError,
)
from backend.app.services.erp_readonly import BLOCKED_MISSING_ARTIFACT, REVIEW_REQUIRED


class FakeDraftClient:
    def __init__(self, error: ErpDraftWriteError | None = None, *, mismatch: bool = False):
        self.error = error
        self.mismatch = mismatch
        self.calls: list[dict] = []
        self.lookups: list[str] = []
        self.documents: dict[str, DraftDocument] = {}

    async def create_or_lookup_draft_result(self, payload: dict, *, idempotency_key: str) -> DraftWriteClientResult:
        self.calls.append({"payload": payload, "idempotency_key": idempotency_key})
        if self.error is not None:
            raise self.error
        existing = self.documents.get(idempotency_key)
        if existing is not None:
            return DraftWriteClientResult(document=existing, created=False, recovered_after_timeout=False)
        document = DraftDocument(
            name=f"FDR-FAKE-{len(self.documents) + 1:04d}",
            farm_event_id=idempotency_key,
            docstatus=0,
            status="Draft",
            production_request_id=payload["production_request_id"],
            external_work_order_id=payload["external_work_order_id"],
            production_item=payload["production_item"],
            quantity_completed=payload["quantity_completed"],
            payload={**payload, "docstatus": 0},
        )
        self.documents[idempotency_key] = document
        return DraftWriteClientResult(document=document, created=True, recovered_after_timeout=False)

    async def lookup_draft_result(self, farm_event_id: str) -> DraftDocument:
        self.lookups.append(farm_event_id)
        document = self.documents[farm_event_id]
        if not self.mismatch:
            return document
        return DraftDocument(
            name=document.name,
            farm_event_id=document.farm_event_id,
            docstatus=document.docstatus,
            status=document.status,
            production_request_id=document.production_request_id,
            external_work_order_id=document.external_work_order_id,
            production_item=document.production_item,
            quantity_completed=int(document.quantity_completed or 0) + 1,
            payload={**document.payload, "quantity_completed": int(document.quantity_completed or 0) + 1},
        )


class ErpDraftWriteApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            bed_automation,
            erp_draft_write,
            erp_readonly,
            group,
            library,
            notification_template,
            print_log,
            print_queue,
            settings,
            user,
        )

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_get_db():
            async with self.sessionmaker() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.patches = [
            patch("backend.app.core.database.async_session", self.sessionmaker),
            patch("backend.app.core.auth.async_session", self.sessionmaker),
            patch("backend.app.main.async_session", self.sessionmaker),
        ]
        for patcher in self.patches:
            patcher.start()

        self.previous_enabled = draft_route.settings.farm_erp_draft_posting_enabled
        draft_route.settings.farm_erp_draft_posting_enabled = False
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        draft_route.settings.farm_erp_draft_posting_enabled = self.previous_enabled
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def seed_source_request(self, *, status: str = REVIEW_REQUIRED, executable: bool = False) -> ErpProductionRequest:
        async with self.sessionmaker() as session:
            file = LibraryFile(
                filename="fixture-cube-v1.3mf",
                file_path="/synthetic/fixture-cube-v1.3mf",
                file_type="3mf",
                file_size=1234,
                source_type="erp_artifact",
                source_url="erp://artifact/fixture-cube-v1",
            )
            session.add(file)
            await session.flush()
            request = ErpProductionRequest(
                source_system="erpnext",
                external_work_order_id="WO-FAKE-0001",
                production_item="SKU-FAKE-001",
                quantity=1,
                erp_status="Submitted",
                artifact_reference="fixture-cube-v1",
                profile_set_id="p1p-pla-fixture-v1",
                customer="Customer FAKE",
                library_file_id=file.id,
                status=status,
                review_reason="synthetic review state",
                executable=executable,
                retryable=False,
                import_attempts=1,
                erp_payload={"name": "WO-FAKE-0001"},
            )
            session.add(request)
            await session.commit()
            await session.refresh(request)
            return request

    def enable_draft_write(self, fake_client: FakeDraftClient) -> None:
        draft_route.settings.farm_erp_draft_posting_enabled = True
        app.dependency_overrides[draft_route.get_erp_draft_client] = lambda: fake_client

    async def count_rows(self, model) -> int:
        async with self.sessionmaker() as session:
            return (await session.execute(select(func.count(model.id)))).scalar_one()

    async def all_draft_records(self) -> list[ErpDraftWriteRecord]:
        async with self.sessionmaker() as session:
            return list((await session.execute(select(ErpDraftWriteRecord).order_by(ErpDraftWriteRecord.id))).scalars())

    def draft_body(self, event_uuid: str = "evt-api-0001") -> dict:
        return {
            "event_uuid": event_uuid,
            "print_run_id": "run-synthetic-0001",
            "quantity_completed": 1,
            "completed_at": "2026-06-24T12:00:00Z",
        }

    async def test_draft_write_disabled_by_default(self) -> None:
        response = await self.client.post("/api/v1/erp-draft-write/production-requests/1/drafts", json=self.draft_body())

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())

    async def test_valid_draft_write_creates_synthetic_draft_only(self) -> None:
        source = await self.seed_source_request()
        fake = FakeDraftClient()
        self.enable_draft_write(fake)

        response = await self.client.post(f"/api/v1/erp-draft-write/production-requests/{source.id}/drafts", json=self.draft_body())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], DRAFT_CREATED)
        self.assertEqual(body["erp_document_name"], "FDR-FAKE-0001")
        self.assertEqual(body["erp_docstatus"], 0)
        self.assertFalse(body["dead_letter"])
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 1)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)

    async def test_duplicate_draft_write_is_idempotent(self) -> None:
        source = await self.seed_source_request()
        fake = FakeDraftClient()
        self.enable_draft_write(fake)

        first = await self.client.post(f"/api/v1/erp-draft-write/production-requests/{source.id}/drafts", json=self.draft_body())
        second = await self.client.post(f"/api/v1/erp-draft-write/production-requests/{source.id}/drafts", json=self.draft_body())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["id"], first.json()["id"])
        self.assertEqual(second.json()["status"], DRAFT_ALREADY_EXISTS)
        self.assertEqual(second.json()["erp_document_name"], first.json()["erp_document_name"])
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 1)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)

    async def test_draft_write_is_blocked_when_source_request_is_not_review_safe(self) -> None:
        source = await self.seed_source_request(status=BLOCKED_MISSING_ARTIFACT)
        fake = FakeDraftClient()
        self.enable_draft_write(fake)

        response = await self.client.post(f"/api/v1/erp-draft-write/production-requests/{source.id}/drafts", json=self.draft_body())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], DRAFT_WRITE_BLOCKED)
        self.assertTrue(body["dead_letter"])
        self.assertEqual(len(fake.calls), 0)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)

    async def test_erp_error_cases_are_recorded_safely_without_side_effects(self) -> None:
        cases = [
            (ErpDraftWriteError(ERP_DRAFT_RATE_LIMITED, "ERP draft rate limited", http_status=503, retryable=True), 503, DRAFT_WRITE_RETRYABLE_FAILURE, False),
            (ErpDraftWriteError(ERP_DRAFT_UPSTREAM_ERROR, "ERP draft server error", http_status=502, retryable=True), 502, DRAFT_WRITE_RETRYABLE_FAILURE, False),
            (ErpDraftWriteError(ERP_DRAFT_TIMEOUT, "ERP draft request timed out", http_status=504, retryable=True), 504, DRAFT_WRITE_RETRYABLE_FAILURE, False),
            (ErpDraftWriteError(ERP_DRAFT_AUTH_FAILED, "ERP draft authentication failed", http_status=401, retryable=False), 401, DRAFT_WRITE_FAILED, True),
            (ErpDraftWriteError(ERP_DRAFT_INVALID_PAYLOAD, "ERP draft payload invalid", http_status=422, retryable=False), 422, DRAFT_WRITE_FAILED, True),
        ]
        for error, http_status, expected_status, dead_letter in cases:
            with self.subTest(code=error.code):
                await self.asyncTearDown()
                await self.asyncSetUp()
                source = await self.seed_source_request()
                self.enable_draft_write(FakeDraftClient(error=error))

                response = await self.client.post(
                    f"/api/v1/erp-draft-write/production-requests/{source.id}/drafts",
                    json=self.draft_body(f"evt-{error.code.lower()}"),
                )

                self.assertEqual(response.status_code, http_status)
                detail = response.json()["detail"]
                self.assertEqual(detail["code"], error.code)
                self.assertIs(detail["retryable"], error.retryable)
                self.assertNotIn("synthetic-secret-token", str(detail))
                rows = await self.all_draft_records()
                self.assertEqual(rows[0].status, expected_status)
                self.assertIs(rows[0].retryable, error.retryable)
                self.assertIs(rows[0].dead_letter, dead_letter)
                self.assertEqual(await self.count_rows(PrintQueueItem), 0)
                self.assertEqual(await self.count_rows(PrintLogEntry), 0)
                self.assertEqual(await self.count_rows(BedAutomationCycle), 0)

    async def test_logs_do_not_leak_synthetic_secret(self) -> None:
        source = await self.seed_source_request()
        error = ErpDraftWriteError(
            ERP_DRAFT_AUTH_FAILED,
            "ERP draft authentication failed",
            http_status=401,
            retryable=False,
        )
        self.enable_draft_write(FakeDraftClient(error=error))

        with self.assertLogs("backend.app.services.erp_draft_write", level="INFO") as captured:
            response = await self.client.post(
                f"/api/v1/erp-draft-write/production-requests/{source.id}/drafts",
                json=self.draft_body("evt-log-scrub-0001"),
            )

        self.assertEqual(response.status_code, 401)
        combined_logs = "\n".join(captured.output)
        self.assertNotIn("synthetic-secret-token", combined_logs)
        self.assertNotIn("synthetic-secret-token", str(response.json()))

    async def test_reconciliation_detects_injected_mismatch(self) -> None:
        source = await self.seed_source_request()
        fake = FakeDraftClient(mismatch=True)
        self.enable_draft_write(fake)
        created = await self.client.post(f"/api/v1/erp-draft-write/production-requests/{source.id}/drafts", json=self.draft_body())

        response = await self.client.post(f"/api/v1/erp-draft-write/drafts/{created.json()['event_uuid']}/reconcile")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], RECONCILIATION_MISMATCH)
        self.assertFalse(body["matched"])
        self.assertIn("quantity_completed", body["mismatches"])
        rows = await self.all_draft_records()
        self.assertEqual(rows[0].reconciliation_status, RECONCILIATION_MISMATCH)

    async def test_reconciliation_matches_clean_draft(self) -> None:
        source = await self.seed_source_request()
        fake = FakeDraftClient()
        self.enable_draft_write(fake)
        created = await self.client.post(f"/api/v1/erp-draft-write/production-requests/{source.id}/drafts", json=self.draft_body())

        response = await self.client.post(f"/api/v1/erp-draft-write/drafts/{created.json()['event_uuid']}/reconcile")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], RECONCILIATION_MATCHED)
        self.assertTrue(body["matched"])
        self.assertEqual(body["mismatches"], [])


if __name__ == "__main__":
    unittest.main()
