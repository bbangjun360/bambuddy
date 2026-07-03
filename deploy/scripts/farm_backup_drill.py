#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT / "deploy/.env.farm"
DEFAULT_BACKUP_DIR = Path("/srv/bambuddy/backups")
RESTORE_CONFIRMATION = "CONFIRM_FARM_PRODUCTION_RESTORE"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def compose_command(env_file: Path, *args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-directory",
        ".",
        "--env-file",
        str(env_file),
        "-f",
        "docker-compose.yml",
        "-f",
        "deploy/docker-compose.farm.yml",
        "--profile",
        "farm-observability",
        *args,
    ]


def backup_command(env_file: Path) -> list[str]:
    inline = "\n".join(
        [
            "import asyncio",
            "import json",
            "from pathlib import Path",
            "from backend.app.api.routes.settings import create_backup_zip",
            "async def main():",
            "    zip_path, filename = await create_backup_zip(output_path=Path('/app/data/backups'))",
            "    print(json.dumps({'backup': str(zip_path), 'filename': filename}))",
            "asyncio.run(main())",
        ]
    )
    return compose_command(env_file, "exec", "-T", "bambuddy", "python", "-c", inline)


def resolve_backup_dir(env_file: Path) -> Path:
    values = read_env(env_file)
    return Path(values.get("FARM_BACKUP_DIR") or DEFAULT_BACKUP_DIR).expanduser().resolve()


def validate_restore_request(backup_file: Path, *, backup_dir: Path, confirmation: str | None) -> Path:
    if confirmation != RESTORE_CONFIRMATION:
        raise ValueError(f"restore drill requires exact confirmation: {RESTORE_CONFIRMATION}")

    resolved_dir = backup_dir.expanduser().resolve()
    resolved_file = backup_file.expanduser().resolve()

    if not resolved_file.exists():
        raise ValueError(f"backup file does not exist: {resolved_file}")
    if resolved_dir not in resolved_file.parents:
        raise ValueError(f"backup file must be under backup directory: {resolved_dir}")
    if not resolved_file.name.startswith("bambuddy-backup-") or resolved_file.suffix != ".zip":
        raise ValueError("backup file must match bambuddy-backup-*.zip")
    return resolved_file


def restore_drill_report(backup_file: Path, *, backup_dir: Path, confirmation: str | None) -> dict[str, object]:
    resolved = validate_restore_request(backup_file, backup_dir=backup_dir, confirmation=confirmation)
    return {
        "restore_drill": "validated",
        "backup_file": str(resolved),
        "manual_steps": [
            "Start an isolated restore drill host or VM, not the live farm host.",
            "Copy deploy/.env.farm and the selected backup ZIP to the drill host.",
            "Start Bambuddy with a separate COMPOSE_PROJECT_NAME and empty data volume.",
            "Use Bambuddy local-backup restore for the selected backup ZIP.",
            "Verify /health, login, library/archive visibility, printer list, and metrics scrape.",
            "Destroy the isolated drill stack only after recording evidence.",
        ],
    }


def print_dry_run(command: list[str]) -> None:
    print("DRY RUN: no production container or data was modified")
    print(" ".join(command))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Farm production backup and restore drill helper")
    parser.add_argument("mode", choices=("backup", "restore-check"))
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--execute", action="store_true", help="execute the non-destructive backup command")
    parser.add_argument("--backup-file", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)

    if args.mode == "backup":
        command = backup_command(args.env_file)
        if not args.execute:
            print_dry_run(command)
            return 0
        completed = subprocess.run(command, cwd=ROOT, check=False)
        return completed.returncode

    backup_dir = args.backup_dir or resolve_backup_dir(args.env_file)
    if args.backup_file is None:
        raise SystemExit("restore-check requires --backup-file")
    report = restore_drill_report(args.backup_file, backup_dir=backup_dir, confirmation=args.confirm)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
