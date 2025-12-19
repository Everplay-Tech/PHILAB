"""Platform configuration helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class PlatformConfig:
    enabled: bool = False
    central_url: str = "https://api.philab.everplay.tech"
    auto_submit: bool = False
    api_key: str | None = None
    contributor_id: str | None = None

    @classmethod
    def from_env(cls) -> "PlatformConfig":
        return cls(
            enabled=os.environ.get("PHILAB_PLATFORM_ENABLED", "false").lower() == "true",
            central_url=os.environ.get("PHILAB_PLATFORM_URL", cls.central_url),
            auto_submit=os.environ.get("PHILAB_PLATFORM_AUTO_SUBMIT", "false").lower() == "true",
            api_key=os.environ.get("PHILAB_API_KEY"),
            contributor_id=os.environ.get("PHILAB_CONTRIBUTOR_ID"),
        )
