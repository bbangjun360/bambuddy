from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "harness/docker-compose.harness.yml"
ENV_FILE = ROOT / ".env.harness"
EXAMPLE_ENV_FILE = ROOT / ".env.harness.example"
FIXTURE_DIR = ROOT / "harness/fixtures/orca"
PROFILE_DIR = FIXTURE_DIR / "profiles"
MANIFEST = FIXTURE_DIR / "profile-set.json"
ACCEPTED_ORCA_REPOSITORIES = {
    "bbangjun360/orca-slicer-api",
    "maziggy/orca-slicer-api",
}
DIGEST_RE = re.compile(r"[0-9a-f]{64}")
QUALIFIED_ORCA_IMAGE = (
    "ghcr.io/bbangjun360/orca-slicer-api:headless-cli-qualified-20260624"
    "@sha256:1c3e3e6f2ff193d4202bc7284af5d5a8c868e6185a26eeeacf878fe51387f518"
)


def _read_env(path: Path = ENV_FILE) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _orca_image_contract_errors(image: str) -> list[str]:
    errors: list[str] = []
    if not image.startswith("ghcr.io/"):
        errors.append("ORCA_IMAGE must use ghcr.io")

    if "@sha256:" not in image:
        errors.append("ORCA_IMAGE must be pinned with @sha256:")
        reference = image
        digest = ""
    else:
        reference, digest = image.split("@sha256:", 1)
        if not DIGEST_RE.fullmatch(digest):
            errors.append("ORCA_IMAGE sha256 digest must be 64 lowercase hex characters")

    repository_with_tag = reference.removeprefix("ghcr.io/")
    last_path_part = repository_with_tag.rsplit("/", 1)[-1]
    if ":" in last_path_part:
        repository, tag = repository_with_tag.rsplit(":", 1)
    else:
        repository, tag = repository_with_tag, ""

    if repository not in ACCEPTED_ORCA_REPOSITORIES:
        errors.append(f"ORCA_IMAGE repository must be one of {sorted(ACCEPTED_ORCA_REPOSITORIES)}")
    if tag == "latest":
        errors.append("ORCA_IMAGE must not use the latest tag")

    return errors


class OrcaWP010ContractTest(unittest.TestCase):
    def test_fixture_and_approved_profile_manifest_are_deterministic(self) -> None:
        required = {
            "valid_model": FIXTURE_DIR / "fixture-cube-v1.stl",
            "invalid_model": FIXTURE_DIR / "invalid-model-v1.stl",
            "printer_profile": PROFILE_DIR / "p1p-printer.json",
            "process_profile": PROFILE_DIR / "p1p-pla-process.json",
            "filament_profile": PROFILE_DIR / "p1p-pla-filament.json",
            "invalid_profile": PROFILE_DIR / "invalid-profile.json",
        }
        for label, path in required.items():
            self.assertTrue(path.exists(), f"missing {label}: {path}")
            self.assertGreater(path.stat().st_size, 0, f"empty {label}: {path}")

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["profile_set_id"], "p1p-pla-fixture-v1")
        self.assertEqual(manifest["valid_model_sha256"], _sha256(required["valid_model"]))
        self.assertEqual(manifest["invalid_model_sha256"], _sha256(required["invalid_model"]))
        self.assertEqual(manifest["profiles"]["printer"]["sha256"], _sha256(required["printer_profile"]))
        self.assertEqual(manifest["profiles"]["process"]["sha256"], _sha256(required["process_profile"]))
        self.assertEqual(manifest["profiles"]["filament"]["sha256"], _sha256(required["filament_profile"]))

        profile_hash_payload = {
            "printer": manifest["profiles"]["printer"]["sha256"],
            "process": manifest["profiles"]["process"]["sha256"],
            "filaments": [manifest["profiles"]["filament"]["sha256"]],
        }
        expected_set_hash = hashlib.sha256(
            json.dumps(profile_hash_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(manifest["profile_set_sha256"], expected_set_hash)

    def test_harness_pins_real_orca_image(self) -> None:
        env_file = ENV_FILE if ENV_FILE.exists() else EXAMPLE_ENV_FILE
        image = _read_env(env_file)["ORCA_IMAGE"]

        self.assertNotIn("placeholder", image)
        self.assertEqual([], _orca_image_contract_errors(image))

    def test_harness_example_uses_qualified_forked_orca_image(self) -> None:
        image = _read_env(EXAMPLE_ENV_FILE)["ORCA_IMAGE"]

        self.assertEqual(QUALIFIED_ORCA_IMAGE, image)
        self.assertEqual([], _orca_image_contract_errors(image))

    def test_orca_image_contract_accepts_qualified_repositories(self) -> None:
        digest = "a" * 64

        for repository in sorted(ACCEPTED_ORCA_REPOSITORIES):
            with self.subTest(repository=repository):
                image = f"ghcr.io/{repository}:qualified@sha256:{digest}"
                self.assertEqual([], _orca_image_contract_errors(image))

    def test_orca_image_contract_rejects_latest_and_unpinned_tags(self) -> None:
        digest = "a" * 64
        invalid_images = {
            "latest": f"ghcr.io/bbangjun360/orca-slicer-api:latest@sha256:{digest}",
            "unpinned": "ghcr.io/bbangjun360/orca-slicer-api:headless-cli-qualified-20260624",
            "not_ghcr": f"docker.io/bbangjun360/orca-slicer-api:qualified@sha256:{digest}",
            "unknown_owner": f"ghcr.io/someone/orca-slicer-api:qualified@sha256:{digest}",
        }

        for label, image in invalid_images.items():
            with self.subTest(label=label):
                self.assertTrue(_orca_image_contract_errors(image), image)

    def test_harness_services_have_explicit_dns_aliases(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")

        for alias in ("postgres", "mock-services", "orca-slicer-api"):
            self.assertIn(f"- {alias}", text)

    def test_orca_sidecar_has_healthcheck_and_no_printer_credentials(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("orca-slicer-api:", text)
        self.assertIn("healthcheck:", text)
        self.assertIn("http://localhost:3000/health", text)
        self.assertIn('profiles: ["slicer"]', text)
        self.assertIn('127.0.0.1:${ORCA_API_PORT:-13003}:3000', text)
        self.assertIn("harness_orca_data", text)
        self.assertNotIn("network_mode: host", text)
        self.assertNotIn("printer_vlan", text)
        self.assertNotIn("BAMBU_ACCESS_CODE", text)
        self.assertNotIn("PRINTER_SERIAL", text)
        self.assertNotIn("MQTT_PASSWORD", text)


if __name__ == "__main__":
    unittest.main()
