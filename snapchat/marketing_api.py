from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import date, datetime, time as dt_time, timezone
from typing import Any

import requests


API_BASE = "https://adsapi.snapchat.com/v1"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class SnapchatMarketingAPI:
    def __init__(self, access_token: str, pause_seconds: float = 0.35) -> None:
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})
        self.pause_seconds = pause_seconds

    def get(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("http") else f"{API_BASE}{path_or_url}"
        last_error = ""
        for attempt in range(5):
            if attempt:
                time.sleep(min(30, 2**attempt))
            elif self.pause_seconds:
                time.sleep(self.pause_seconds)

            response = self.session.get(url, params=params, timeout=45)
            if response.status_code not in RETRY_STATUSES:
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Snap API GET failed: HTTP {response.status_code}; "
                        f"{response.text[:500]}"
                    )
                return response.json()

            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(int(retry_after))
            last_error = f"HTTP {response.status_code}; {response.text[:300]}"

        raise RuntimeError(f"Snap API GET failed after retries: {last_error}")

    def list_campaigns(self, ad_account_id: str) -> list[dict[str, Any]]:
        payload = self.get(f"/adaccounts/{ad_account_id}/campaigns")
        campaigns: list[dict[str, Any]] = []
        campaigns.extend(_unwrap_collection(payload, "campaigns", "campaign"))

        next_link = _next_link(payload)
        while next_link:
            payload = self.get(next_link)
            campaigns.extend(_unwrap_collection(payload, "campaigns", "campaign"))
            next_link = _next_link(payload)

        return campaigns

    def campaign_stats_daily(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
        fields: Iterable[str],
        attribution_window: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "granularity": "DAY",
            "start_time": _midnight_utc(start_date),
            "end_time": _midnight_utc(end_date),
            "fields": ",".join(dict.fromkeys(fields)),
        }
        if attribution_window:
            params["attribution_window"] = attribution_window

        return self.get(f"/campaigns/{campaign_id}/stats", params=params)


def _midnight_utc(value: date) -> str:
    return datetime.combine(value, dt_time.min, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _unwrap_collection(payload: dict[str, Any], outer_key: str, inner_key: str) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get(outer_key, []):
        if isinstance(item, dict) and inner_key in item:
            rows.append(item[inner_key])
        elif isinstance(item, dict):
            rows.append(item)
    return rows


def _next_link(payload: dict[str, Any]) -> str | None:
    paging = payload.get("paging")
    if isinstance(paging, dict):
        value = paging.get("next_link") or paging.get("next")
        return str(value) if value else None
    return None
