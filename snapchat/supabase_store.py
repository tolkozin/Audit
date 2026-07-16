from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from supabase import Client, create_client

from .config import require_secret


def get_supabase() -> Client:
    return create_client(
        require_secret("SUPABASE_URL"),
        require_secret("SUPABASE_SERVICE_ROLE_KEY"),
    )


class SupabaseStore:
    def __init__(self, client: Client | None = None) -> None:
        self.client = client or get_supabase()

    def active_accounts(self, client_slug: str | None = None) -> list[dict[str, Any]]:
        query = (
            self.client.table("ad_accounts")
            .select("*, clients!inner(slug,name)")
            .eq("is_active", True)
            .eq("clients.is_active", True)
        )
        if client_slug:
            query = query.eq("clients.slug", client_slug)
        return query.execute().data or []

    def upsert_campaigns(self, ad_account_id: str, campaigns: list[dict[str, Any]]) -> dict[str, str]:
        rows = []
        for campaign in campaigns:
            snap_id = str(campaign.get("id") or "")
            if not snap_id:
                continue
            rows.append(
                {
                    "ad_account_id": ad_account_id,
                    "snapchat_campaign_id": snap_id,
                    "name": campaign.get("name") or snap_id,
                    "status": campaign.get("status"),
                    "objective": campaign.get("objective"),
                    "delivery_type": _delivery_type(campaign),
                    "optimization_goal": campaign.get("optimization_goal"),
                    "raw": campaign,
                    "updated_at": _now_iso(),
                }
            )

        if rows:
            self.client.table("campaigns").upsert(
                rows, on_conflict="ad_account_id,snapchat_campaign_id"
            ).execute()

        existing = (
            self.client.table("campaigns")
            .select("id,snapchat_campaign_id")
            .eq("ad_account_id", ad_account_id)
            .execute()
            .data
            or []
        )
        return {row["snapchat_campaign_id"]: row["id"] for row in existing}

    def replace_campaign_stats(
        self,
        ad_account_id: str,
        start_date: date,
        end_date: date,
        rows: list[dict[str, Any]],
    ) -> int:
        self.client.table("campaign_stats_daily").delete().eq("ad_account_id", ad_account_id).gte(
            "stat_date", start_date.isoformat()
        ).lt("stat_date", end_date.isoformat()).execute()

        if not rows:
            return 0

        self.client.table("campaign_stats_daily").upsert(
            rows,
            on_conflict="ad_account_id,snapchat_campaign_id,stat_date,attribution_window",
        ).execute()
        return len(rows)

    def prune_old_stats(self, ad_account_id: str, keep_from: date) -> None:
        self.client.table("campaign_stats_daily").delete().eq("ad_account_id", ad_account_id).lt(
            "stat_date", keep_from.isoformat()
        ).execute()

    def create_sync_run(
        self,
        client_slug: str,
        ad_account_id: str,
        start_date: date,
        end_date: date,
        refresh_days: int,
    ) -> str:
        data = (
            self.client.table("sync_runs")
            .insert(
                {
                    "status": "running",
                    "client_slug": client_slug,
                    "ad_account_id": ad_account_id,
                    "date_start": start_date.isoformat(),
                    "date_end": end_date.isoformat(),
                    "refresh_days": refresh_days,
                }
            )
            .execute()
            .data
        )
        return data[0]["id"]

    def finish_sync_run(
        self,
        sync_run_id: str,
        status: str,
        rows_upserted: int = 0,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.client.table("sync_runs").update(
            {
                "status": status,
                "rows_upserted": rows_upserted,
                "error_message": error_message,
                "metadata": metadata or {},
                "finished_at": _now_iso(),
            }
        ).eq("id", sync_run_id).execute()

    def dashboard_rows(
        self,
        client_slug: str | None,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        query = (
            self.client.table("campaign_dashboard")
            .select("*")
            .gte("stat_date", start_date.isoformat())
            .lte("stat_date", end_date.isoformat())
            .order("stat_date")
        )
        if client_slug:
            query = query.eq("client_slug", client_slug)
        return query.execute().data or []

    def dashboard_clients(self) -> list[dict[str, Any]]:
        return (
            self.client.table("ad_accounts")
            .select("id,account_name,currency,attribution_window,default_delivery_type,clients!inner(slug,name)")
            .eq("is_active", True)
            .eq("clients.is_active", True)
            .order("account_name")
            .execute()
            .data
            or []
        )


def _delivery_type(campaign: dict[str, Any]) -> str:
    text = " ".join(
        str(campaign.get(key) or "").lower()
        for key in ("name", "objective", "optimization_goal", "ad_product")
    )
    has_app = any(token in text for token in ("app", "install", "ios", "android"))
    has_web = any(token in text for token in ("web", "site", "purchase", "lead"))
    if has_app and has_web:
        return "mixed"
    if has_app:
        return "app"
    if has_web:
        return "web"
    return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
