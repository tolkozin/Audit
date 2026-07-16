from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .auth import refresh_access_token
from .marketing_api import SnapchatMarketingAPI
from .supabase_store import SupabaseStore


DEFAULT_FIELD_MAP = {
    "amount_spent": "spend",
    "app_installs": "total_installs",
    "sign_ups_total": "conversion_sign_ups",
    "purchases_total": "conversion_purchases",
}


def sync_campaign_stats(
    client_slug: str | None = None,
    refresh_days: int = 3,
    keep_days: int = 90,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    store = SupabaseStore()
    accounts = store.active_accounts(client_slug)
    if not accounts:
        raise RuntimeError(f"No active accounts found for client={client_slug!r}")

    end = end_date or datetime.now(timezone.utc).date()
    start = end - timedelta(days=refresh_days)
    keep_from = end - timedelta(days=keep_days)

    api = SnapchatMarketingAPI(refresh_access_token())
    results = []

    for account in accounts:
        client = account["clients"]
        sync_id = store.create_sync_run(client["slug"], account["id"], start, end, refresh_days)
        rows_upserted = 0
        try:
            campaigns = api.list_campaigns(account["snapchat_ad_account_id"])
            campaign_id_map = store.upsert_campaigns(account["id"], campaigns)

            field_map = dict(DEFAULT_FIELD_MAP)
            field_map.update(account.get("stats_field_map") or {})
            fields = list(field_map.values())

            stat_rows: list[dict[str, Any]] = []
            for campaign in campaigns:
                campaign_snap_id = str(campaign.get("id") or "")
                if not campaign_snap_id:
                    continue
                payload = api.campaign_stats_daily(
                    campaign_snap_id,
                    start,
                    end,
                    fields,
                    account.get("timezone") or "UTC",
                    attribution_params(account.get("attribution_window")),
                )
                stat_rows.extend(
                    _rows_from_stats_payload(
                        payload=payload,
                        account=account,
                        campaign_snap_id=campaign_snap_id,
                        campaign_db_id=campaign_id_map.get(campaign_snap_id),
                        field_map=field_map,
                    )
                )

            rows_upserted = store.replace_campaign_stats(account["id"], start, end, stat_rows)
            store.prune_old_stats(account["id"], keep_from)
            store.finish_sync_run(
                sync_id,
                "success",
                rows_upserted=rows_upserted,
                metadata={"campaigns_seen": len(campaigns), "refresh_days": refresh_days},
            )
            results.append(
                {
                    "client": client["slug"],
                    "account": account["account_name"],
                    "status": "success",
                    "rows": rows_upserted,
                }
            )
        except Exception as exc:
            store.finish_sync_run(sync_id, "failed", rows_upserted=rows_upserted, error_message=str(exc))
            results.append(
                {
                    "client": client["slug"],
                    "account": account["account_name"],
                    "status": "failed",
                    "error": str(exc),
                }
            )

    return results


def attribution_params(attribution_window: str | None) -> dict[str, str]:
    if not attribution_window:
        return {}

    normalized = attribution_window.strip().upper()
    presets = {
        "7_DAY_SWIPE_0_DAY_VIEW": {
            "swipe_up_attribution_window": "7_DAY",
            "view_attribution_window": "none",
        },
        "7_DAY_SWIPE_NONE_VIEW": {
            "swipe_up_attribution_window": "7_DAY",
            "view_attribution_window": "none",
        },
        "7_DAY_CLICK_0_DAY_VIEW": {
            "swipe_up_attribution_window": "7_DAY",
            "view_attribution_window": "none",
        },
        "28_DAY_SWIPE_1_DAY_VIEW": {
            "swipe_up_attribution_window": "28_DAY",
            "view_attribution_window": "1_DAY",
        },
        "7_DAY_SWIPE_1_DAY_VIEW": {
            "swipe_up_attribution_window": "7_DAY",
            "view_attribution_window": "1_DAY",
        },
    }
    if normalized in presets:
        return presets[normalized]

    raise ValueError(
        f"Unsupported attribution_window {attribution_window!r}. "
        "Add it to snapchat.sync_campaigns.attribution_params."
    )


def _rows_from_stats_payload(
    payload: dict[str, Any],
    account: dict[str, Any],
    campaign_snap_id: str,
    campaign_db_id: str | None,
    field_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows = []
    for stat in _iter_stat_blocks(payload):
        start_time = stat.get("start_time")
        if not start_time:
            continue
        stats = stat.get("stats") or {}
        if not isinstance(stats, dict):
            continue

        amount_spent = _metric(stats, field_map["amount_spent"], money=True)
        row = {
            "ad_account_id": account["id"],
            "campaign_id": campaign_db_id,
            "snapchat_campaign_id": campaign_snap_id,
            "stat_date": _date_from_snap_time(str(start_time)).isoformat(),
            "attribution_window": account.get("attribution_window"),
            "currency": account.get("currency"),
            "amount_spent": amount_spent,
            "app_installs": _metric(stats, field_map["app_installs"]),
            "sign_ups_total": _metric(stats, field_map["sign_ups_total"]),
            "purchases_total": _metric(stats, field_map["purchases_total"]),
            "metrics": stats,
            "finalized_data_end_time": payload.get("finalized_data_end_time")
            or stat.get("finalized_data_end_time"),
        }
        rows.append(row)
    return rows


def _iter_stat_blocks(value: Any):
    if isinstance(value, dict):
        if isinstance(value.get("stats"), dict) and value.get("start_time"):
            yield value
        for child in value.values():
            yield from _iter_stat_blocks(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_stat_blocks(child)


def _metric(stats: dict[str, Any], field: str, money: bool = False) -> float:
    raw = stats.get(field, 0) or 0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if money:
        return value / 1_000_000
    return value


def _date_from_snap_time(value: str) -> date:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).date()
