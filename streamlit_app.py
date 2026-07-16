from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from snapchat.supabase_store import SupabaseStore
from snapchat.sync_campaigns import sync_campaign_stats


st.set_page_config(page_title="Snapchat Ops Dashboard", layout="wide")


def money(value: float | int | None, currency: str | None = None) -> str:
    if value is None or pd.isna(value):
        return "-"
    prefix = {"EUR": "€", "USD": "$"}.get(currency or "", "")
    return f"{prefix}{float(value):,.2f}"


def number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.0f}"


@st.cache_resource(show_spinner=False)
def store() -> SupabaseStore:
    return SupabaseStore()


@st.cache_data(ttl=120, show_spinner=False)
def load_accounts() -> list[dict]:
    return store().dashboard_clients()


@st.cache_data(ttl=120, show_spinner=False)
def load_dashboard(client_slug: str, start_date: date, end_date: date) -> pd.DataFrame:
    rows = store().dashboard_rows(client_slug, start_date, end_date)
    return pd.DataFrame(rows)


@st.cache_data(ttl=120, show_spinner=False)
def load_latest_data_date(client_slug: str) -> date | None:
    return store().latest_dashboard_stat_date(client_slug)


st.title("Snapchat Campaign Dashboard")

accounts = load_accounts()
if not accounts:
    st.warning("No active ad accounts found in Supabase.")
    st.stop()

options = []
for account in accounts:
    client = account["clients"]
    label = account["account_name"]
    options.append((label, client["slug"], account))

with st.sidebar:
    st.header("Filters")
    selected_label = st.selectbox("Client / account", [item[0] for item in options])
    selected = next(item for item in options if item[0] == selected_label)
    client_slug = selected[1]
    account = selected[2]

    latest_data_date = load_latest_data_date(client_slug)
    period_label = st.segmented_control(
        "Date range",
        options=["7 days", "14 days", "30 days", "90 days"],
        default="30 days",
    )
    period_days = {"7 days": 7, "14 days": 14, "30 days": 30, "90 days": 90}[period_label]
    end_date = latest_data_date or date.today()
    start_date = end_date - timedelta(days=period_days - 1)

    if latest_data_date:
        st.caption(f"Data through: `{latest_data_date.isoformat()}`")
    st.caption(f"Attribution window: `{account.get('attribution_window') or 'not set'}`")
    st.caption(f"Default type: `{account.get('default_delivery_type') or 'unknown'}`")

    st.divider()
    if st.button("Refresh table data"):
        st.cache_data.clear()
        st.rerun()

    with st.expander("Admin sync"):
        st.caption("Runs campaign-level sync for the selected client. Use sparingly.")
        refresh_days = st.number_input("Refresh days", min_value=1, max_value=14, value=3)
        if st.button("Run Snapchat sync"):
            with st.spinner("Syncing from Snapchat..."):
                try:
                    result = sync_campaign_stats(client_slug=client_slug, refresh_days=int(refresh_days))
                    st.success("Sync finished")
                    st.json(result)
                    st.cache_data.clear()
                except Exception as exc:
                    st.error(str(exc))

df = load_dashboard(client_slug, start_date, end_date)

if df.empty:
    st.info("No campaign stats in the database for this selection yet.")
    st.stop()

st.caption(
    f"Loaded {len(df):,} campaign-day rows from "
    f"{pd.to_datetime(df['stat_date']).min().date()} to "
    f"{pd.to_datetime(df['stat_date']).max().date()}."
)

numeric_cols = [
    "amount_spent",
    "app_installs",
    "sign_ups_total",
    "purchases_total",
    "cost_per_install",
    "cost_per_sign_up",
    "cost_per_purchase",
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

currency = df["currency"].dropna().iloc[0] if "currency" in df and df["currency"].notna().any() else None

total_spend = df["amount_spent"].sum()
total_installs = df["app_installs"].sum()
total_signups = df["sign_ups_total"].sum()
total_purchases = df["purchases_total"].sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Amount Spent", money(total_spend, currency))
col2.metric("App Installs", number(total_installs))
col3.metric("Sign Ups Total", number(total_signups))
col4.metric("Purchases Total", number(total_purchases))

col5, col6, col7 = st.columns(3)
col5.metric("Cost Per Install", money(total_spend / total_installs if total_installs else None, currency))
col6.metric("Cost Per Sign Up", money(total_spend / total_signups if total_signups else None, currency))
col7.metric("Cost Per Purchase", money(total_spend / total_purchases if total_purchases else None, currency))

daily = (
    df.groupby("stat_date", as_index=False)[["amount_spent", "app_installs", "sign_ups_total", "purchases_total"]]
    .sum()
    .sort_values("stat_date")
)
daily["stat_date"] = pd.to_datetime(daily["stat_date"]).dt.date
all_dates = pd.DataFrame({"stat_date": pd.date_range(start_date, end_date).date})
daily = all_dates.merge(daily, on="stat_date", how="left").fillna(
    {
        "amount_spent": 0,
        "app_installs": 0,
        "sign_ups_total": 0,
        "purchases_total": 0,
    }
)

st.subheader("Daily Trend")
spend_fig = px.bar(daily, x="stat_date", y="amount_spent", labels={"amount_spent": "Amount Spent"})
spend_fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
st.plotly_chart(spend_fig, use_container_width=True)

events_daily = daily.melt(
    id_vars="stat_date",
    value_vars=["app_installs", "sign_ups_total", "purchases_total"],
    var_name="metric",
    value_name="value",
)
events_daily["metric"] = events_daily["metric"].map(
    {
        "app_installs": "App Installs",
        "sign_ups_total": "Sign Ups Total",
        "purchases_total": "Purchases Total",
    }
)
events_fig = px.line(events_daily, x="stat_date", y="value", color="metric", markers=True)
events_fig.update_layout(height=340, margin=dict(l=10, r=10, t=20, b=10), legend_title_text="")
st.plotly_chart(events_fig, use_container_width=True)

st.subheader("Campaigns")
campaign_table = (
    df.groupby(["name", "status", "objective", "delivery_type", "attribution_window", "currency"], dropna=False)
    .agg(
        amount_spent=("amount_spent", "sum"),
        app_installs=("app_installs", "sum"),
        sign_ups_total=("sign_ups_total", "sum"),
        purchases_total=("purchases_total", "sum"),
    )
    .reset_index()
)
campaign_table["cost_per_install"] = campaign_table.apply(
    lambda row: row["amount_spent"] / row["app_installs"] if row["app_installs"] else None,
    axis=1,
)
campaign_table["cost_per_sign_up"] = campaign_table.apply(
    lambda row: row["amount_spent"] / row["sign_ups_total"] if row["sign_ups_total"] else None,
    axis=1,
)
campaign_table["cost_per_purchase"] = campaign_table.apply(
    lambda row: row["amount_spent"] / row["purchases_total"] if row["purchases_total"] else None,
    axis=1,
)

display = campaign_table.rename(
    columns={
        "name": "Name",
        "status": "Status",
        "objective": "Objective",
        "amount_spent": "Amount Spent",
        "app_installs": "App Installs",
        "cost_per_install": "Cost Per Install",
        "sign_ups_total": "Sign Ups Total",
        "cost_per_sign_up": "Cost Per Sign Up",
        "purchases_total": "Purchases Total",
        "cost_per_purchase": "Cost Per Purchase",
        "attribution_window": "Attribution Window",
        "delivery_type": "Type",
    }
)
display = display[
    [
        "Name",
        "Status",
        "Objective",
        "Type",
        "Attribution Window",
        "Amount Spent",
        "App Installs",
        "Cost Per Install",
        "Sign Ups Total",
        "Cost Per Sign Up",
        "Purchases Total",
        "Cost Per Purchase",
    ]
].sort_values("Amount Spent", ascending=False)

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Amount Spent": st.column_config.NumberColumn(format="%.2f"),
        "Cost Per Install": st.column_config.NumberColumn(format="%.2f"),
        "Cost Per Sign Up": st.column_config.NumberColumn(format="%.2f"),
        "Cost Per Purchase": st.column_config.NumberColumn(format="%.2f"),
    },
)
