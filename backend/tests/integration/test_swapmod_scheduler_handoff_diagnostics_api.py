from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import swapmod_state_machine as swapmod_route
from backend.app.core.auth import create_access_token, get_password_hash
from backend.app.core.database import Base, get_db
from backend.app.core.permissions import Permission
from backend.app.main import app
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.swapmod_queue_readiness_binding import SwapmodQueueReadinessBinding
from backend.app.services.swapmod_bed_readiness import record_swapmod_bed_readiness
from backend.app.services.swapmod_scheduler_handoff_diagnostics import _diagnostics_summary
from backend.app.services.swapmod_queue_readiness_binding import bind_swapmod_queue_readiness
from backend.app.services.swapmod_scheduler_next_print_gate import scheduler_print_run_key
from backend.app.services.swapmod_state_machine import (
    LOAD_NEXT_PLATE,
    PRINT_FINISHED,
    RELEASE_PLATE,
    START_STEP,
    STEP_MOCK_SUCCEEDED,
    VERIFY_PASSED,
    VERIFY_PLATE_READY,
    VERIFY_PLATE_RELEASED,
    apply_swapmod_event,
    create_swapmod_cycle,
)
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient


class SwapmodSchedulerHandoffDiagnosticsApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        asyncio.get_running_loop().slow_callback_duration = 1.0
        from backend.app.models import (  # noqa: F401
            api_key,
            archive,
            auth_ephemeral,
            bed_automation,
            erp_draft_write,
            group,
            library,
            print_log,
            print_queue,
            printer,
            settings,
            swapmod_queue_readiness_binding,
            swapmod_state_machine,
            user,
        )

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_get_db():
            async with self.sessionmaker() as session:
                try:
                    yield session
                    await session.commit()
                except BaseException:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        self.patches = [
            patch("backend.app.core.database.async_session", self.sessionmaker),
            patch("backend.app.core.auth.async_session", self.sessionmaker),
            patch("backend.app.main.async_session", self.sessionmaker),
        ]
        for patcher in self.patches:
            patcher.start()

        self.previous_values = {
            "farm_swapmod_scheduler_next_print_gate_enabled": (
                swapmod_route.settings.farm_swapmod_scheduler_next_print_gate_enabled
            ),
            "farm_swapmod_scheduler_queue_readiness_binding_enabled": (
                swapmod_route.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled
            ),
            "farm_bed_automation_enabled": swapmod_route.settings.farm_bed_automation_enabled,
        }
        swapmod_route.settings.farm_swapmod_scheduler_next_print_gate_enabled = False
        swapmod_route.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = False
        swapmod_route.settings.farm_bed_automation_enabled = False
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        for name, value in self.previous_values.items():
            setattr(swapmod_route.settings, name, value)
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def create_queue_item(self, *, printer_id: int = 101) -> int:
        async with self.sessionmaker() as session:
            item = PrintQueueItem(
                printer_id=printer_id,
                archive_id=808,
                plate_id=1,
                status="pending",
                position=1,
            )
            session.add(item)
            await session.commit()
            return item.id

    async def create_print_log(self, *, printer_id: int = 101) -> int:
        async with self.sessionmaker() as session:
            entry = PrintLogEntry(
                printer_id=printer_id,
                printer_name="A1 Mini API Diagnostics",
                print_name="Finished plate",
                status="completed",
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(entry)
            await session.commit()
            return entry.id

    async def create_ready_cycle_and_binding(self, *, queue_item_id: int, print_log_id: int) -> int:
        async with self.sessionmaker() as session:
            cycle = await create_swapmod_cycle(
                session,
                cycle_key=f"api-diagnostics-cycle-{print_log_id}",
                printer_id=101,
                source_print_run_id=scheduler_print_run_key(print_log_id),
            )
            for event, event_id, step, verification_source, verification_result in (
                (PRINT_FINISHED, "event-1", None, None, None),
                (START_STEP, "event-2", RELEASE_PLATE, None, None),
                (STEP_MOCK_SUCCEEDED, "event-3", RELEASE_PLATE, None, None),
                (VERIFY_PASSED, "event-4", VERIFY_PLATE_RELEASED, "manual", "pass"),
                (START_STEP, "event-5", LOAD_NEXT_PLATE, None, None),
                (STEP_MOCK_SUCCEEDED, "event-6", LOAD_NEXT_PLATE, None, None),
                (VERIFY_PASSED, "event-7", VERIFY_PLATE_READY, "manual", "pass"),
            ):
                cycle = await apply_swapmod_event(
                    session,
                    cycle,
                    event,
                    event_id=f"{cycle.cycle_key}:{event_id}",
                    step=step,
                    verification_source=verification_source,
                    verification_result=verification_result,
                )
            await record_swapmod_bed_readiness(
                session,
                cycle,
                handoff_key=f"{cycle.cycle_key}-bed-ready",
                printer_id=cycle.printer_id,
                enabled=True,
                bed_automation_enabled=True,
                bed_automation_dry_run=True,
            )
            binding = await bind_swapmod_queue_readiness(
                session,
                cycle,
                binding_key=f"{cycle.cycle_key}-queue-binding",
                queue_item_id=queue_item_id,
                printer_id=101,
                enabled=True,
                bed_automation_enabled=True,
            )
            await session.commit()
            return int(binding["binding_id"])

    async def consume_binding(self, binding_id: int) -> datetime:
        consumed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        async with self.sessionmaker() as session:
            binding = await session.get(SwapmodQueueReadinessBinding, binding_id)
            self.assertIsNotNone(binding)
            binding.consumed_at = consumed_at
            await session.commit()
        return consumed_at

    async def queue_item_snapshot(self, queue_item_id: int) -> tuple[str, object]:
        async with self.sessionmaker() as session:
            item = await session.get(PrintQueueItem, queue_item_id)
            self.assertIsNotNone(item)
            return item.status, item.started_at

    async def binding_consumed_at(self, binding_id: int) -> datetime | None:
        async with self.sessionmaker() as session:
            binding = await session.get(SwapmodQueueReadinessBinding, binding_id)
            self.assertIsNotNone(binding)
            return binding.consumed_at

    async def enable_auth_and_create_token(self, *, username: str, permissions: list[str]) -> str:
        from backend.app.models.group import Group
        from backend.app.models.settings import Settings
        from backend.app.models.user import User

        async with self.sessionmaker() as session:
            session.add(Settings(key="auth_enabled", value="true"))
            group = Group(
                name=f"wp087-{username}",
                description="WP-087 diagnostics auth fixture",
                permissions=permissions,
            )
            user = User(
                username=username,
                password_hash=get_password_hash("local-test-only"),
                role="user",
                is_active=True,
            )
            user.groups.append(group)
            session.add_all([group, user])
            await session.commit()
        return create_access_token(data={"sub": username})

    async def test_handoff_diagnostics_api_reports_safe_default_off_status(self) -> None:
        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics",
            params={"queue_item_id": 123, "printer_id": 456},
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["mode"], "SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS")
        self.assertEqual(body["gate_status"], "allowed")
        self.assertTrue(body["scheduler_start_allowed"])
        self.assertEqual(body["blocked_reasons"], [])
        self.assertFalse(body["scheduler_next_print_gate"]["enforced"])
        self.assertFalse(body["scheduler_queue_readiness_binding_gate"]["enforced"])
        self.assertEqual(body["diagnostics_summary"]["enforced_gates"], [])
        self.assertEqual(body["diagnostics_summary"]["handoff_identity_status"], "not_enforced")
        self.assertFalse(body["diagnostics_summary"]["real_command_sent"])
        self.assertFalse(body["real_command_sent"])
        self.assertFalse(body["printer_command_sent"])
        self.assertFalse(body["queue_dispatch_supported"])
        self.assertFalse(body["scheduler_dispatch_supported"])

    async def test_handoff_diagnostics_status_api_reports_safe_defaults(self) -> None:
        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status",
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["mode"], "SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_API_STATUS")
        self.assertTrue(body["api_enabled"])
        self.assertTrue(body["read_only"])
        self.assertEqual(body["required_query_parameters"], ["queue_item_id", "printer_id"])
        self.assertEqual(body["required_permission"], Permission.PRINTERS_READ.value)
        self.assertEqual(body["response_contract_version"], 1)
        self.assertEqual(body["diagnostics_summary_contract_version"], 1)
        self.assertFalse(body["mutates_state"])
        example_summary = _diagnostics_summary(
            gate_status="allowed",
            scheduler_start_allowed=True,
            blocked_reasons=[],
            next_print_gate={"enforced": False, "blocked_reasons": []},
            queue_readiness_binding_gate={"enforced": False, "blocked_reasons": []},
            handoff_identity_blocked_reasons=[],
        )
        self.assertEqual(body["supported_summary_fields"], list(example_summary.keys()))
        self.assertEqual(
            body["supported_handoff_identity_statuses"],
            ["not_enforced", "not_available", "matched", "mismatch"],
        )
        self.assertEqual(
            body["supported_blocked_reason_sources"],
            [
                "scheduler_next_print_gate",
                "scheduler_queue_readiness_binding_gate",
                "handoff_identity",
            ],
        )
        self.assertFalse(body["scheduler_next_print_gate_enabled"])
        self.assertFalse(body["scheduler_queue_readiness_binding_enabled"])
        self.assertFalse(body["bed_automation_enabled"])
        self.assertFalse(body["real_command_sent"])
        self.assertFalse(body["printer_command_sent"])
        self.assertFalse(body["queue_dispatch_supported"])
        self.assertFalse(body["scheduler_dispatch_supported"])

    async def test_handoff_diagnostics_api_requires_printer_id(self) -> None:
        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics",
            params={"queue_item_id": 123},
        )

        self.assertEqual(response.status_code, 422)

    async def test_handoff_diagnostics_status_requires_auth_when_enabled(self) -> None:
        await self.enable_auth_and_create_token(
            username="wp087-read-status-denied",
            permissions=[Permission.PRINTERS_READ.value],
        )

        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status",
        )

        self.assertEqual(response.status_code, 401)

    async def test_handoff_diagnostics_evaluation_requires_auth_when_enabled(self) -> None:
        await self.enable_auth_and_create_token(
            username="wp087-read-evaluation-denied",
            permissions=[Permission.PRINTERS_READ.value],
        )

        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics",
            params={"queue_item_id": 123, "printer_id": 456},
        )

        self.assertEqual(response.status_code, 401)

    async def test_handoff_diagnostics_status_allows_printers_read_token(self) -> None:
        token = await self.enable_auth_and_create_token(
            username="wp087-read-status-allowed",
            permissions=[Permission.PRINTERS_READ.value],
        )

        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["mode"], "SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_API_STATUS")
        self.assertFalse(body["printer_command_sent"])
        self.assertFalse(body["scheduler_dispatch_supported"])

    async def test_handoff_diagnostics_status_rejects_token_without_printers_read(self) -> None:
        token = await self.enable_auth_and_create_token(
            username="wp087-no-read-status-denied",
            permissions=[],
        )

        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)

    async def test_handoff_diagnostics_evaluation_allows_printers_read_token(self) -> None:
        token = await self.enable_auth_and_create_token(
            username="wp087-read-evaluation-allowed",
            permissions=[Permission.PRINTERS_READ.value],
        )

        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics",
            params={"queue_item_id": 123, "printer_id": 456},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["mode"], "SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS")
        self.assertFalse(body["printer_command_sent"])
        self.assertFalse(body["scheduler_dispatch_supported"])

    async def test_handoff_diagnostics_evaluation_rejects_token_without_printers_read(self) -> None:
        token = await self.enable_auth_and_create_token(
            username="wp087-no-read-denied",
            permissions=[],
        )

        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics",
            params={"queue_item_id": 123, "printer_id": 456},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 403)

    async def test_consumed_binding_api_blocks_without_mutating_queue_or_binding(self) -> None:
        queue_item_id = await self.create_queue_item()
        print_log_id = await self.create_print_log()
        binding_id = await self.create_ready_cycle_and_binding(
            queue_item_id=queue_item_id,
            print_log_id=print_log_id,
        )
        consumed_at = await self.consume_binding(binding_id)
        swapmod_route.settings.farm_swapmod_scheduler_next_print_gate_enabled = True
        swapmod_route.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = True
        swapmod_route.settings.farm_bed_automation_enabled = True

        response = await self.client.get(
            "/api/v1/swapmod-state-machine/scheduler-handoff-diagnostics",
            params={"queue_item_id": queue_item_id, "printer_id": 101},
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["gate_status"], "blocked")
        self.assertFalse(body["scheduler_start_allowed"])
        self.assertIn("queue_readiness_binding_consumed", body["blocked_reasons"])
        self.assertTrue(body["queue_readiness_binding_consumed"])
        self.assertEqual(body["diagnostics_summary"]["primary_blocker"], "queue_readiness_binding_consumed")
        self.assertEqual(
            body["diagnostics_summary"]["blocked_reason_sources"]["scheduler_queue_readiness_binding_gate"],
            ["queue_readiness_binding_consumed"],
        )
        self.assertFalse(body["diagnostics_summary"]["printer_command_sent"])
        self.assertFalse(body["printer_command_sent"])
        self.assertFalse(body["scheduler_dispatch_supported"])
        self.assertEqual(await self.binding_consumed_at(binding_id), consumed_at)
        self.assertEqual(await self.queue_item_snapshot(queue_item_id), ("pending", None))


if __name__ == "__main__":
    unittest.main()
