import logging
import os
import re as _re
from pathlib import Path

from pydantic_settings import BaseSettings

# Application version - single source of truth
APP_VERSION = "0.2.4.7"
GITHUB_REPO = "maziggy/bambuddy"
BUG_REPORT_RELAY_URL = os.environ.get("BUG_REPORT_RELAY_URL", "https://bambuddy.cool/api/bug-report")

# App directory - where the application is installed (for static files)
_app_dir = Path(__file__).resolve().parent.parent.parent.parent

# Data directory - for persistent data (database, archives)
# Use DATA_DIR env var if set (Docker), otherwise use project root (local dev)
_data_dir_env = os.environ.get("DATA_DIR")
_data_dir = Path(_data_dir_env) if _data_dir_env else _app_dir

# Plate calibration directory - special handling to maintain backwards compatibility
# Docker: DATA_DIR/plate_calibration (e.g., /data/plate_calibration)
# Local dev: project_root/data/plate_calibration (original location)
_plate_cal_dir = Path(_data_dir_env) / "plate_calibration" if _data_dir_env else _app_dir / "data" / "plate_calibration"

# Log directory - use LOG_DIR env var if set, otherwise use app_dir/logs
_log_dir_env = os.environ.get("LOG_DIR")
_log_dir = Path(_log_dir_env) if _log_dir_env else _app_dir / "logs"


def _migrate_database() -> Path:
    """Migrate database from old name to new name if needed."""
    old_db = _data_dir / "bambutrack.db"
    new_db = _data_dir / "bambuddy.db"

    # If old database exists and new one doesn't, rename it
    if old_db.exists() and not new_db.exists():
        try:
            old_db.rename(new_db)
            logging.info("Migrated database: %s -> %s", old_db, new_db)
        except Exception as e:
            logging.warning("Could not migrate database: %s. Using old location.", e)
            return old_db

    # If old database exists (and new one now exists too), it was migrated
    # If only new exists, use new
    # If neither exists, use new (will be created)
    return new_db if new_db.exists() or not old_db.exists() else old_db


# External DATABASE_URL takes priority (PostgreSQL support)
_external_db_url = os.environ.get("DATABASE_URL")

# Determine database path (handles migration) — only used for SQLite
_db_path = _migrate_database() if not _external_db_url else None


class Settings(BaseSettings):
    app_name: str = "Bambuddy"
    debug: bool = False  # Default to production mode

    # Paths
    base_dir: Path = _data_dir  # For backwards compatibility
    # `app_dir` is where the source code is checked out — distinct from `base_dir`
    # on native installs where DATA_DIR is set to a sibling like INSTALL_PATH/data.
    # Use this when you need the working tree (requirements.txt, frontend/, etc.)
    # rather than the data dir. On Docker / local dev where DATA_DIR is unset,
    # app_dir == base_dir.
    app_dir: Path = _app_dir
    archive_dir: Path = _data_dir / "archive"
    plate_calibration_dir: Path = _plate_cal_dir  # Plate detection references
    static_dir: Path = _app_dir / "static"  # Static files are part of app, not data
    log_dir: Path = _log_dir
    database_url: str = _external_db_url or f"sqlite+aiosqlite:///{_db_path}"

    # Logging
    log_level: str = "INFO"  # Override with LOG_LEVEL env var or DEBUG=true
    log_to_file: bool = True  # Set to false to disable file logging

    # API
    api_prefix: str = "/api/v1"

    # Slicer API sidecars. Defaults match the docker-compose.yml ports in the
    # orca-slicer-api fork (https://github.com/maziggy/orca-slicer-api):
    #   OrcaSlicer  → port 3003 (default profile)
    #   BambuStudio → port 3001 (built locally via Dockerfile.bambu-studio)
    # The slice route picks which one based on the user's preferred_slicer
    # setting.
    slicer_api_url: str = "http://localhost:3003"
    bambu_studio_api_url: str = "http://localhost:3001"

    # WP-030 ERP read-only import. Disabled by default; tests and harness
    # scenarios opt in explicitly. This integration reads Work Orders only.
    farm_erp_import_enabled: bool = False
    farm_erp_base_url: str = "http://mock-services:9099"
    farm_erp_api_token: str | None = None
    farm_erp_timeout_seconds: float = 5.0

    # WP-040 ERP draft write. Disabled by default; creates Draft-only
    # synthetic ERP output documents through the mock/sandbox adapter.
    farm_erp_draft_posting_enabled: bool = False

    # WP-050 bed automation simulator. Disabled by default and dry-run only.
    farm_bed_automation_enabled: bool = False
    farm_bed_automation_dry_run: bool = True

    # WP-070 Obico Shadow Mode. Disabled by default and records observations only.
    farm_obico_shadow_enabled: bool = False

    # WP-060 PrintFlow canary readiness. Disabled by default; dry-run,
    # human-gated, mock-readiness checks only. The previous server-adapter
    # model is deprecated/pending redesign because PrintFlow/SwapMod are 3MF
    # post-processing workflows, not remote control servers for live operation.
    farm_printflow_canary_readiness_enabled: bool = False
    farm_printflow_real_adapter_enabled: bool = False
    farm_printflow_canary_dry_run: bool = True
    farm_printflow_canary_human_approval_required: bool = True
    farm_printflow_canary_single_printer_only: bool = True
    farm_printflow_base_url: str | None = None
    farm_printflow_api_token: str | None = None

    # WP-063 Bambuddy-native plate-change command research. Disabled by
    # default and dry-run only. Real command execution is intentionally not
    # implemented in this Work Package.
    farm_plate_change_command_enabled: bool = False
    farm_plate_change_command_dry_run: bool = True
    farm_plate_change_human_approval_required: bool = True
    farm_plate_change_single_printer_only: bool = True
    farm_plate_change_allow_real_commands: bool = False
    farm_plate_change_transport_enabled: bool = False
    farm_plate_change_allow_real_transport: bool = False
    farm_plate_change_transport_dry_run: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Don't reject unknown env vars — MFA_ENCRYPTION_KEY (#1219) and other
        # operational env vars are read directly by their owning modules and
        # never declared as Settings fields.
        extra = "ignore"


settings = Settings()

# S6: Warn on unknown MFA_*/BAMBUDDY_* env vars so typos like MFA_ENCYPTION_KEY
# are not silently swallowed by ``extra = "ignore"``. The original Pydantic
# behaviour rejected them outright and broke startup (#1219); we now accept
# them but log every unrecognised one at INFO so operators can spot mistakes.
_INTENTIONAL_UNSETTINGS = {
    "MFA_ENCRYPTION_KEY",  # encryption.py reads this directly
    "DATA_DIR",  # paths.py / config.py
    "DATABASE_URL",  # config.py (above)
    "LOG_DIR",  # config.py (above)
    "LOG_LEVEL",  # main.py logging setup
    "BUG_REPORT_RELAY_URL",  # config.py (above)
}

_known_settings_fields = {f.upper() for f in settings.model_fields}

for _env_key in os.environ:
    if _re.match(r"^(MFA_|BAMBUDDY_)", _env_key, _re.IGNORECASE):
        _norm = _env_key.upper()
        if _norm not in _known_settings_fields and _norm not in _INTENTIONAL_UNSETTINGS:
            logging.info(
                "Unknown env var %r — not a declared Settings field. Possible typo? Recognised operational vars: %s",
                _env_key,
                sorted(_INTENTIONAL_UNSETTINGS),
            )

# Ensure directories exist
settings.archive_dir.mkdir(parents=True, exist_ok=True)
settings.plate_calibration_dir.mkdir(parents=True, exist_ok=True)
settings.static_dir.mkdir(exist_ok=True)
if settings.log_to_file:
    settings.log_dir.mkdir(exist_ok=True)
