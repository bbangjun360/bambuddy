#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _resolve_harness_env_file() -> Path:
    selected = Path(os.environ.get("HARNESS_ENV", ".env.harness"))
    return selected if selected.is_absolute() else ROOT / selected


HARNESS_ENV_FILE = _resolve_harness_env_file()
FIXTURE_DIR = ROOT / "harness/fixtures/orca"
PROFILE_DIR = FIXTURE_DIR / "profiles"
ARTIFACT_DIR = ROOT / "harness/artifacts/orca"


def _read_harness_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not HARNESS_ENV_FILE.exists():
        return values
    for line in HARNESS_ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


_HARNESS_ENV = _read_harness_env()
ORCA_BASE_URL = os.environ.get(
    "ORCA_BASE_URL",
    f"http://127.0.0.1:{_HARNESS_ENV.get('ORCA_API_PORT', '13003')}",
).rstrip("/")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _part(boundary: str, name: str, content: bytes, filename: str | None = None, content_type: str | None = None) -> bytes:
    disposition = f'Content-Disposition: form-data; name="{name}"'
    if filename is not None:
        disposition += f'; filename="{filename}"'
    headers = [f"--{boundary}", disposition]
    if content_type is not None:
        headers.append(f"Content-Type: {content_type}")
    return ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + content + b"\r\n"


def _multipart_body() -> tuple[bytes, str, dict]:
    boundary = f"wp010-{uuid.uuid4().hex}"
    model = (FIXTURE_DIR / "fixture-cube-v1.stl").read_bytes()
    printer = (PROFILE_DIR / "p1p-printer.json").read_bytes()
    process = (PROFILE_DIR / "p1p-pla-process.json").read_bytes()
    filament = (PROFILE_DIR / "p1p-pla-filament.json").read_bytes()
    body = b"".join(
        [
            _part(boundary, "file", model, "fixture-cube-v1.stl", "model/stl"),
            _part(boundary, "printerProfile", printer, "p1p-printer.json", "application/json"),
            _part(boundary, "presetProfile", process, "p1p-pla-process.json", "application/json"),
            _part(boundary, "filamentProfile", filament, "p1p-pla-filament.json", "application/json"),
            _part(boundary, "exportType", b"3mf"),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    hashes = {
        "source_sha256": _sha256(model),
        "profile_sha256": {
            "printer": _sha256(printer),
            "process": _sha256(process),
            "filaments": [_sha256(filament)],
        },
    }
    payload = {
        "printer": hashes["profile_sha256"]["printer"],
        "process": hashes["profile_sha256"]["process"],
        "filaments": hashes["profile_sha256"]["filaments"],
    }
    hashes["profile_set_sha256"] = _sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return body, boundary, hashes


def wait_for_health(timeout: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{ORCA_BASE_URL}/health", timeout=5) as result:
                body = result.read(8192).decode("utf-8", errors="replace")
                if 200 <= result.status < 400:
                    try:
                        return json.loads(body)
                    except json.JSONDecodeError:
                        return {"raw": body[:500]}
                last_error = f"HTTP {result.status}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Orca sidecar did not become healthy: {last_error}")


def main() -> int:
    health = wait_for_health()
    body, boundary, hashes = _multipart_body()
    request = urllib.request.Request(
        f"{ORCA_BASE_URL}/slice",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as result:
            output = result.read()
            headers = dict(result.headers.items())
    except urllib.error.HTTPError as exc:
        error_body = exc.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"Orca slice failed with HTTP {exc.code}: {error_body}") from exc

    if not output.startswith(b"PK\x03\x04"):
        raise RuntimeError("Orca slice did not return a 3MF zip payload")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARTIFACT_DIR / "fixture-cube-v1.gcode.3mf"
    output_path.write_bytes(output)
    hashes["output_sha256"] = _sha256(output)

    evidence = {
        "healthy": True,
        "health": health,
        "artifact": str(output_path.relative_to(ROOT)),
        "artifact_size": len(output),
        "headers": {
            "x-print-time-seconds": headers.get("X-Print-Time-Seconds"),
            "x-filament-used-g": headers.get("X-Filament-Used-G"),
            "x-filament-used-mm": headers.get("X-Filament-Used-Mm"),
        },
        "hashes": hashes,
    }
    (ARTIFACT_DIR / "fixture-cube-v1.evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"healthy": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
