from __future__ import annotations

import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import erp_readonly as erp_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.erp_readonly import ErpProductionRequest
from backend.app.models.library import LibraryFile
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services.erp_readonly import (
    BLOCKED_INVALID_PROFILE,
    BLOCKED_MISSING_ARTIFACT,
    ERP_AUTH_FAILED,
    ERP_INVALID_PAYLOAD,
    ERP_RATE_LIMITED,
    ERP_TIMEOUT,
    ERP_UPSTREAM_ERROR,
    IMPORT_FAILED,
    REVIEW_REQUIRED,
    ErpReadOnlyError,
)


def work_order(**overrides):
    payload = {
        "name": "WO-FAKE-0001",
        "production_item": "SKU-FAKE-001",
        "qty": 1,
        "status": "Submitted",
        "custom_artifact_reference": "fixture-cube-v1",
        "custom_profile_set_id": "p1p-pla-fixture-v1",
        "customer": "Customer FAKE",
    }
    payload.update(overrides)
    return payload


class FakeErpClient:
    def __init__(self, payload=None, error: ErpReadOnlyError | None = None):
        self.payload = payload if payload is not None else work_order()
        self.error = error
        self.fetches: list[str] = []

    async def fetch_work_order(self, work_order_id: str) -> dict:
        self.fetches.append(work_order_id)
        if self.error is not None:
            raise self.error
        return self.payload


class ErpReadOnlyApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Import all models needed by relationships before create_all.
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
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

        self.previous_enabled = erp_route.settings.farm_erp_import_enabled
        erp_route.settings.farm_erp_import_enabled = False
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        erp_route.settings.farm_erp_import_enabled = self.previous_enabled
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def seed_artifact(self, reference: str = "fixture-cube-v1") -> LibraryFile:
        async with self.sessionmaker() as session:
            file = LibraryFile(
                filename="fixture-cube-v1.3mf",
                file_path="/synthetic/fixture-cube-v1.3mf",
                file_type="3mf",
                file_size=1234,
                source_type="erp_artifact",
                source_url=f"erp://artifact/{reference}",
            )
            session.add(file)
            await session.commit()
            await session.refresh(file)
            return file

    def enable_erp(self, fake_client: FakeErpClient) -> None:
        erp_route.settings.farm_erp_import_enabled = True
        app.dependency_overrides[erp_route.get_erp_client] = lambda: fake_client

    async def count_rows(self, model) -> int:
        async with self.sessionmaker() as session:
            return (await session.execute(select(func.count(model.id)))).scalar_one()

    async def all_requests(self) -> list[ErpProductionRequest]:
        async with self.sessionmaker() as session:
            return list((await session.execute(select(ErpProductionRequest))).scalars())

    async def test_import_disabled_by_default(self) -> None:
        response = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())

    async def test_valid_import_creates_one_review_only_request(self) -> None:
        artifact = await self.seed_artifact()
        self.enable_erp(FakeErpClient(work_order()))

        response = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["external_work_order_id"], "WO-FAKE-0001")
        self.assertEqual(body["status"], REVIEW_REQUIRED)
        self.assertEqual(body["library_file_id"], artifact.id)
        self.assertIs(body["executable"], False)
        self.assertEqual(await self.count_rows(ErpProductionRequest), 1)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_duplicate_import_preserves_same_local_request(self) -> None:
        await self.seed_artifact()
        self.enable_erp(FakeErpClient(work_order()))

        first = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")
        second = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["id"], first.json()["id"])
        self.assertEqual(await self.count_rows(ErpProductionRequest), 1)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)

    async def test_missing_artifact_mapping_blocks_request(self) -> None:
        self.enable_erp(FakeErpClient(work_order(custom_artifact_reference="missing-artifact-v1")))

        response = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], BLOCKED_MISSING_ARTIFACT)
        self.assertIsNone(body["library_file_id"])
        self.assertIs(body["executable"], False)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)

    async def test_missing_profile_set_blocks_request(self) -> None:
        await self.seed_artifact()
        self.enable_erp(FakeErpClient(work_order(custom_profile_set_id=None)))

        response = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], BLOCKED_INVALID_PROFILE)
        self.assertIs(body["executable"], False)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)

    async def test_invalid_erp_payload_records_import_failed_without_queue(self) -> None:
        self.enable_erp(FakeErpClient({"production_item": "SKU-FAKE-001", "qty": 1}))

        response = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], ERP_INVALID_PAYLOAD)
        self.assertIs(detail["retryable"], False)
        self.assertIsNotNone(detail["request_id"])
        rows = await self.all_requests()
        self.assertEqual(rows[0].status, IMPORT_FAILED)
        self.assertIs(rows[0].retryable, False)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_erp_error_cases_are_recorded_retryably_without_queue(self) -> None:
        cases = [
            (ErpReadOnlyError(ERP_AUTH_FAILED, "ERP authentication failed", http_status=401, retryable=False), 401, False),
            (ErpReadOnlyError(ERP_RATE_LIMITED, "ERP rate limited request", http_status=503, retryable=True), 503, True),
            (ErpReadOnlyError(ERP_UPSTREAM_ERROR, "ERP server error", http_status=502, retryable=True), 502, True),
            (ErpReadOnlyError(ERP_TIMEOUT, "ERP request timed out", http_status=504, retryable=True), 504, True),
        ]
        for error, http_status, retryable in cases:
            with self.subTest(code=error.code):
                await self.asyncTearDown()
                await self.asyncSetUp()
                self.enable_erp(FakeErpClient(error=error))

                response = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")

                self.assertEqual(response.status_code, http_status)
                detail = response.json()["detail"]
                self.assertEqual(detail["code"], error.code)
                self.assertIs(detail["retryable"], retryable)
                self.assertNotIn("fake-token", str(detail))
                rows = await self.all_requests()
                self.assertEqual(rows[0].status, IMPORT_FAILED)
                self.assertIs(rows[0].retryable, retryable)
                self.assertEqual(await self.count_rows(PrintQueueItem), 0)
                self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_imported_requests_are_visible_by_api(self) -> None:
        await self.seed_artifact()
        self.enable_erp(FakeErpClient(work_order()))
        imported = await self.client.post("/api/v1/erp-readonly/work-orders/WO-FAKE-0001/import")

        listed = await self.client.get("/api/v1/erp-readonly/production-requests?external_work_order_id=WO-FAKE-0001")
        fetched = await self.client.get(f"/api/v1/erp-readonly/production-requests/{imported.json()['id']}")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["id"] for row in listed.json()], [imported.json()["id"]])
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["external_work_order_id"], "WO-FAKE-0001")


if __name__ == "__main__":
    unittest.main()
