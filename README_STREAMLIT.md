# Snapchat Ops Dashboard

First MVP: campaign-level Snapchat reporting in Streamlit.

## Data Flow

1. A scheduled sync refreshes the last 3 days per active ad account.
2. Sync writes normalized campaign stats to Supabase.
3. Streamlit reads only Supabase and renders charts/tables.

Streamlit does not call Snapchat automatically on every page load.

## Required Secrets

Set these in Streamlit Cloud secrets, GitHub Actions secrets, or local
`.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "..."

SNAP_CLIENT_ID = "..."
SNAP_CLIENT_SECRET = "..."
SNAP_REFRESH_TOKEN = "..."
```

Never commit real secrets.

## Run Locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Sync Campaign Stats

For one client:

```bash
python scripts/sync_campaigns.py --client space307 --refresh-days 3
```

For all active accounts:

```bash
python scripts/sync_campaigns.py --refresh-days 3
```

The database stores attribution window on the ad account and copies it into every
stats row. If attribution is not configured yet, the sync omits that parameter.

Supported attribution preset for Space307:

```text
7_DAY_SWIPE_0_DAY_VIEW
```

This is sent to Snapchat as:

```text
swipe_up_attribution_window=7_DAY
view_attribution_window=none
```

## GitHub Actions Schedule

The workflow `.github/workflows/sync_campaigns.yml` runs daily at `05:15 UTC` and
refreshes the latest 3 days. It can also be run manually from GitHub Actions.

Add these repository secrets before enabling it:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SNAP_CLIENT_ID`
- `SNAP_CLIENT_SECRET`
- `SNAP_REFRESH_TOKEN`

## Streamlit Cloud

Set the same Supabase secrets in Streamlit Cloud:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Snapchat secrets are only needed in Streamlit if you plan to use the manual
`Admin sync` button from the sidebar.
