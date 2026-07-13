from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.scripts.erpnext_live_contract import _require_safe_target
from harness.scripts.erpnext_sandbox_bootstrap import _require_loopback, _write_token

ROOT = Path(__file__).resolve().parents[2]


class ErpNextLiveContractSafetyTest(unittest.TestCase):
    def test_erp_flags_remain_off_with_real_api_defaults(self) -> None:
        config = (ROOT / "backend/app/core/config.py").read_text(encoding="utf-8")
        self.assertIn("farm_erp_import_enabled: bool = False", config)
        self.assertIn("farm_erp_draft_posting_enabled: bool = False", config)
        self.assertIn('farm_erp_api_prefix: str = "/api"', config)
        self.assertIn('farm_erp_timezone: str = "Asia/Seoul"', config)

    def test_live_contract_rejects_non_loopback_without_explicit_override(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                _require_safe_target("https://erp.invalid")

    def test_live_contract_allows_non_loopback_only_with_explicit_override(self) -> None:
        with patch.dict(os.environ, {"ERP_ALLOW_NON_LOOPBACK": "true"}, clear=True):
            _require_safe_target("https://erp.invalid")

    def test_bootstrap_always_rejects_non_loopback(self) -> None:
        with self.assertRaises(RuntimeError):
            _require_loopback("https://erp.invalid")

    def test_bootstrap_token_file_is_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "sandbox-token"

            _write_token(token_path, "synthetic-key:synthetic-secret")

            self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(token_path.read_text(encoding="utf-8"), "synthetic-key:synthetic-secret\n")


    def test_bootstrap_token_writer_refuses_symlink(self) -> None:
        if not hasattr(os, "O_NOFOLLOW"):
            self.skipTest("O_NOFOLLOW is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.write_text("unchanged\n", encoding="utf-8")
            token_path = Path(directory) / "sandbox-token"
            token_path.symlink_to(target)

            with self.assertRaises(OSError):
                _write_token(token_path, "synthetic-key:synthetic-secret")
            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged\n")


if __name__ == "__main__":
    unittest.main()
