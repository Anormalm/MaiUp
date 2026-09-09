from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class Settings:
    database_url: str
    dxrating_url: str
    current_intl_version: str
    intl_config_path: Path
    intl_overrides_path: Path
    raw_catalog_dir: Path
    import_asset_dir: Path


def get_settings() -> Settings:
    config_path = DATA_ROOT / "config" / "international.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    default_db = (PROJECT_ROOT / "apps" / "api" / "maiup.db").as_posix()
    return Settings(
        database_url=os.getenv("MAIUP_DATABASE_URL", f"sqlite:///{default_db}"),
        dxrating_url=os.getenv(
            "MAIUP_DXRATING_URL",
            "https://miruku.dxrating.net/api/v1/dxdata",
        ),
        current_intl_version=os.getenv(
            "MAIUP_CURRENT_INTL_VERSION",
            config["currentVersion"],
        ),
        intl_config_path=config_path,
        intl_overrides_path=DATA_ROOT / "overrides" / "international_chart_constants.json",
        raw_catalog_dir=DATA_ROOT / "catalog" / "raw",
        import_asset_dir=DATA_ROOT / "imports",
    )
