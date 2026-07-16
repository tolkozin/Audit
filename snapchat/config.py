from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCAL_CREDS_PATH = ROOT / "snapchat" / "credentials.json"


def get_secret(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass

    return default


def require_secret(name: str) -> str:
    value = get_secret(name)
    if not value:
        raise RuntimeError(f"Missing required secret: {name}")
    return value


def load_snapchat_credentials() -> dict[str, str]:
    env_creds = {
        "client_id": get_secret("SNAP_CLIENT_ID"),
        "client_secret": get_secret("SNAP_CLIENT_SECRET"),
        "refresh_token": get_secret("SNAP_REFRESH_TOKEN"),
    }
    if all(env_creds.values()):
        return {k: str(v) for k, v in env_creds.items()}

    if LOCAL_CREDS_PATH.exists():
        with LOCAL_CREDS_PATH.open() as fh:
            payload: dict[str, Any] = json.load(fh)
        return {
            "client_id": payload["client_id"],
            "client_secret": payload["client_secret"],
            "refresh_token": payload["refresh_token"],
        }

    raise RuntimeError(
        "Snapchat credentials not found. Set SNAP_CLIENT_ID, "
        "SNAP_CLIENT_SECRET, SNAP_REFRESH_TOKEN or create local "
        "snapchat/credentials.json."
    )
