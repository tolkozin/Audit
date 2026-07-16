from __future__ import annotations

import requests

from .config import load_snapchat_credentials


TOKEN_URL = "https://accounts.snapchat.com/login/oauth2/access_token"


def refresh_access_token() -> str:
    creds = load_snapchat_credentials()
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Snap token refresh failed: HTTP {response.status_code}")

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Snap token refresh response did not include access_token")
    return str(access_token)
