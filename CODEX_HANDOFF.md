# CODEX HANDOFF — Snapchat Audit Automation (Allformance)

Read this together with `AGENTS.md`. This file is the current-state handoff: what
exists, what's done, and the exact next task. Prior setup was done in a separate
assistant session; you are continuing it.

## Goal (phased)
This project is now broader than audits: build a Snapchat Ads operations and
intelligence foundation first, then automate reports, audits, media plans, QBRs,
and later safe write operations.

1. **Data export + visualization** — campaign-level Snapchat data sync into
   Supabase and Streamlit dashboard. ← we are here.
2. Reporting automation — match account data into tables/templates.
3. External client data ingestion — AppsFlyer/Adjust/BI/other client exports.
4. Analysis outputs — campaign analysis, audits, media plans, QBRs.
5. Later: guarded write ops — upload creatives, create campaigns/ad sets, change
   bids/budgets/statuses with dry-run and approval.

Managed connectors (Windsor/Supermetrics) were rejected: they are read-only and
can't do phase 3. Everything goes through the Snapchat Marketing API directly.

## Current status
- ✅ OAuth app `AF_AUT` created, working. Login `anatolii.k@allformance.com`,
  redirect `https://allformance.com`, scope `snapchat-marketing-api`.
- ✅ Access verified: 7 organizations, 85 ad accounts.
- ✅ Credentials saved to `snapchat/credentials.json` (**gitignored** — contains
  `client_id`, `client_secret`, `refresh_token`). Read tokens from there; never
  hardcode or print them.
- ✅ Non-secret account inventory in `snapchat/accounts.json` (org → ad accounts with
  id/name/currency/status). **This is the source of truth for client isolation.**
- ✅ Supabase project `Snap_Aut_Main` connected and schema created for campaign
  dashboard MVP: `clients`, `ad_accounts`, `campaigns`,
  `campaign_stats_daily`, `sync_runs`, and `campaign_dashboard` view.
- ✅ Streamlit/GitHub Actions foundation added in code.
- ⏳ Next: add real secrets to Streamlit/GitHub Actions, set attribution windows
  per ad account, then run first campaign sync for Space307.

## Repo layout
- `gen_report.py` — `AuditReport` class, builds branded Excel audits. Not a CLI; call
  its methods with parsed data. Consumes the manual-CSV schema (below).
- `<Client>/` — one folder per client (Metro Brazil, Space307, Endel, StarzPlay,
  PolicyBazaar, Sporty, Kegel, Hula, 1xBet). Raw exports + outputs live here. Some
  have their own `generate_presentation.py` (python-pptx decks).
- `snapchat/credentials.json` — secrets (gitignored).
- `snapchat/accounts.json` — account inventory.
- `streamlit_app.py` — campaign-level dashboard reading Supabase only.
- `snapchat/` — API/auth/sync modules. JSON credential/inventory files remain
  gitignored; Python files are tracked.
- `scripts/sync_campaigns.py` — CLI for campaign-level sync.
- `.github/workflows/sync_campaigns.yml` — daily free GitHub Actions sync.

## Client → ad_account_id (verified; full list in accounts.json)
| Client folder | Ad account name | ad_account_id | Currency |
|---|---|---|---|
| Metro Brazil | METRO BRAZIL | 7138c910-c3e2-4063-9d0a-98ea4f6edd7c | USD |
| Space307 | Space307 | 2d3c9d73-3182-46ed-b4b7-8b54bd834fb5 | EUR |
| Space307 | Space307 MENA | 14260f4f-6a19-4fae-95be-dfb8b08f04ef | EUR |
| Endel | Endel | 69621057-348d-4ef7-b3e5-b875b27149fd | USD |
| StarzPlay | STARZ PLAY Self Service | fa990d8a-6c25-44a1-9975-ff1508aa468a | USD |
| StarzPlay | Starzplay iOS 14 | fec051fb-183f-4418-ad82-51776c0bcc7e | USD |
| PolicyBazaar | POLICYBAZAAR MIDDLE EAST | 10cbfbd3-ea0d-44ee-9280-62a1ae1f55c0 | USD |
| Sporty | SportyGroup | 222a11fc-9523-47f5-9360-f91d0bde70ed | USD |
| Kegel | Kegel Quiz | 8ce8b6ae-8725-4ec6-9604-6734e6b8b930 | EUR |

1xBet and Hula ad accounts not yet identified by name — ask the user for the exact
account name before exporting those.

## Hard constraints (do not violate)
- **Never mix client data.** Resolve `ad_account_id` by client name from
  `accounts.json`, and verify it before any read/write. Output only into that
  client's folder.
- **Don't hammer the API.** Sequential requests, low volume, exponential backoff on
  429/5xx, respect rate-limit headers. This is live client data — slow is fine, wrong
  is not.
- **Accuracy first.** Validate row counts and spend totals against a known-good
  manual CSV when possible.

## Snapchat Marketing API reference
- API base `https://adsapi.snapchat.com/v1/`.
- Token refresh (no browser): POST `https://accounts.snapchat.com/login/oauth2/access_token`
  with `grant_type=refresh_token`, `client_id`, `client_secret`, `refresh_token`.
  Access token lives ~1h; refresh token is durable. Do this before each run.
- Hierarchy: Organization → Ad Account → Campaign → Ad Squad (ad set) → Ad → Creative.
- Stats: `/adaccounts/{id}/stats`, or per-entity `/campaigns/{id}/stats` etc., with
  `granularity`, `fields`, and optional `breakdown`. Confirm exact field names against
  https://developers.snap.com/api/marketing-api/Ads-API — don't guess metric names.

## Current Streamlit MVP metrics
Campaign-level only:

`Name, Status, Objective, Type, Attribution Window, Amount Spent, App Installs,
Cost Per Install, Sign Ups Total, Cost Per Sign Up, Purchases Total,
Cost Per Purchase`.

Attribution window is stored on `ad_accounts.attribution_window` and copied into
each stats row. If it is unset, sync omits the attribution parameter.

## Legacy audit CSV schema (later export must match this so gen_report.py is unchanged)
Per ad row:
`Campaign Id, Campaign Name, Ad Set Id, Ad Set Name, Creative Id, Ad Id, Ad Name,
Ad Active Status, Ad Type, Amount Spent, Paid Impressions, Paid eCPM, Clicks, eCPC,
Click Rate, Purchases, Cost per Purchase, 2 Second Video Views,
2 Second Video Views (View Time Only), 15 Second Video Views, Video Plays at 25%,
Video Plays at 50%, Video Plays at 75%, Video Completions, Avg View Time Millis,
Purchase Roas, Purchases Value`

Reference sample: `Metro Brazil/*.csv` (real manual export — use it to verify the API
export reproduces the same columns and comparable numbers).

## Your next task
Write `snapchat/export.py`:
1. Load creds from `credentials.json`, refresh the access token.
2. Given a client name (and date range), look up its `ad_account_id` in
   `accounts.json` (fail loudly if ambiguous/missing).
3. Pull ad-level stats + entity names/ids, map to the CSV schema above.
4. Write `<Client>/snapchat_export_<start>_<end>.csv`.
5. Backoff + rate limiting; no secrets in logs.

Design choices (module structure, pagination, how names are joined to stats) are
yours — pick safe defaults and leave short comments explaining them. Start with
**Metro Brazil** since a reference CSV exists to validate accuracy.
