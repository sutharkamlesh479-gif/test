"""Configuration for AURIX Agent. Secrets are stored locally, never in the repo."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / ".aurix-agent"
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "active_provider": "OpenAI-compatible",
    "providers": [
        {
            "name": "OpenAI-compatible",
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
            "api_key": "",
            "enabled": True,
        }
    ],
    "max_tool_rounds": 8,
    "request_timeout_seconds": 90,
}


def load_config() -> dict[str, Any]:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    if isinstance(data, dict):
        merged.update({k: v for k, v in data.items() if k in merged})
        if isinstance(data.get("providers"), list):
            merged["providers"] = data["providers"]
    if not isinstance(merged.get("providers"), list):
        merged["providers"] = []
    return merged


def save_config(config: dict[str, Any]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temp = CONFIG_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, CONFIG_PATH)
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        # Windows ACLs, rather than POSIX mode bits, control access there.
        pass


def enabled_providers(config: dict[str, Any]) -> list[dict[str, Any]]:
    providers = config.get("providers", [])
    active_name = config.get("active_provider")
    enabled = [p for p in providers if isinstance(p, dict) and p.get("enabled", True) and p.get("endpoint") and p.get("model")]
    enabled.sort(key=lambda p: p.get("name") != active_name)
    return enabled
