from __future__ import annotations

import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import obico_shadow as obico_shadow_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem


class ObicoShadowApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            group,
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

        self.previous_enabled = obico_shadow_route.settings.farm_obico_shadow_enabled
        obico_shadow_route.settings.farm_obico_shadow_enabled = False
        obico_shadow_route.obico_shadow_service.clear()
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        obico_shadow_route.settings.farm_obico_shadow_enabled = self.previous_enabled
        obico_shadow_route.obico_shadow_service.clear()
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def count_rows(self, model) -> int:
        async with self.sessionmaker() as session:
            return (await session.execute(select(func.count(model.id)))).scalar_one()

    def enable_shadow_mode(self) -> None:
        obico_shadow_route.settings.farm_obico_shadow_enabled = True

    async def test_ingest_disabled_by_default(self) -> None:
        response = await self.client.post("/api/v1/obico-shadow/events", json={"event_id": "e1"})

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_valid_event_ingests_without_queue_or_print_log_rows(self) -> None:
        self.enable_shadow_mode()

        response = await self.client.post(
            "/api/v1/obico-shadow/events",
            json={
                "event_id": "shadow-api-event-0001",
                "event_type": "POSSIBLE_LAYER_SHIFT",
                "printer_id": "printer-fixture-001",
                "print_id": "print-fixture-cube-001",
                "observed_at": "2026-06-24T10:00:00Z",
                "confidence": 0.88,
            },
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "REVIEW_RECOMMENDED")
        self.assertEqual(body["mode"], "SHADOW_ONLY")
        self.assertIsNone(body["printer_action"])
        self.assertIsNone(body["queue_action"])
        self.assertIsNone(body["bed_action"])
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_status_and_metrics_do_not_expose_secret_metadata(self) -> None:
        self.enable_shadow_mode()
        secret = "wp070-api-secret-not-for-output"

        response = await self.client.post(
            "/api/v1/obico-shadow/events",
            json={
                "event_id": "shadow-api-secret-0001",
                "event_type": "POSSIBLE_DETACHMENT",
                "printer_id": "printer-fixture-001",
                "metadata": {"access_token": secret},
            },
        )
        self.assertEqual(response.status_code, 202)

        status = await self.client.get("/api/v1/obico-shadow/status")
        metrics = await self.client.get("/api/v1/obico-shadow/metrics")
        exposed = status.text + "\n" + metrics.text

        self.assertEqual(status.status_code, 200)
        self.assertEqual(metrics.status_code, 200)
        self.assertIn("bambuddy_obico_shadow_events_total", metrics.text)
        self.assertNotIn(secret, exposed)


if __name__ == "__main__":
    unittest.main()
