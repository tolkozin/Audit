# AGENTS.md — Snapchat Ad Audit Automation (Allformance)

## What this is
Tooling to produce Snapchat advertising **audits** for Allformance clients.
Given a client's ad performance data, we generate branded Excel reports (and, for
some clients, PPTX decks) with campaign / creative / demographic / event-score
analysis and an executive summary.

## Layout
- `gen_report.py` — the audit engine. `AuditReport` class builds an Excel workbook
  sheet by sheet (`add_campaign_sheet`, `add_creative_sheet`, `add_demographics_sheet`,
  `add_custom_sheet`, `add_event_score_sheet`, `add_adset_changes_sheet`,
  `add_audit_summary`). It is **not** a CLI — an agent calls the methods with
  already-parsed data. Brand colors + styles live at the top of the file.
- `audit_template.xlsx`, `audit_template_client.docx` — reference output formats.
- `<Client>/` — one folder per client (1xBet, Endel, Space307, Metro Brazil, Kegel,
  StarzPlay, Hula, Sporty, PolicyBazaar, …). Holds raw exports and generated outputs.
  Some clients have their own `generate_presentation.py` (python-pptx deck builder).

**Client data is siloed by folder. Never read one client's data while producing
another client's report, and never write output outside the target client's folder.**

## Current data flow (manual — being replaced)
1. Human exports a CSV from Snapchat Ads Manager.
2. Agent parses it and calls `AuditReport` to build the report.

The CSV schema (target shape for the API export below) is, per ad row:
`Campaign Id, Campaign Name, Ad Set Id, Ad Set Name, Creative Id, Ad Id, Ad Name,
Ad Active Status, Ad Type, Amount Spent, Paid Impressions, Paid eCPM, Clicks, eCPC,
Click Rate, Purchases, Cost per Purchase, 2 Second Video Views (+ View Time Only),
15 Second Video Views, Video Plays at 25/50/75%, Video Completions,
Avg View Time Millis, Purchase Roas, Purchases Value`.

## What to build next: API export
Replace the manual CSV download with a module that pulls the same data from the
**Snapchat Marketing API** (`https://adsapi.snapchat.com/v1/`).

Hierarchy: Organization → Ad Account → Campaign → Ad Squad (ad set) → Ad → Creative.
Stats come from the `/stats` endpoints (granularity + fields + breakdown). Auth is
OAuth 2.0 with a refresh token per grant; access tokens are short-lived.

**Context that shapes the design — respect it, don't design around it:**
- Multiple business organizations **and** standalone client ad accounts that are
  *not* under a business center. Each client authorizes separately → store one
  credential set (refresh token, org id, ad account id) **per client**, keyed to
  the client folder. Do not share tokens across clients.
- **Safety first: do not hammer the API.** Low request volume, sequential where
  possible, exponential backoff on 429/5xx, respect rate-limit headers. This is
  live client data — a mistake is worse than a slow export.
- **Accuracy + isolation.** The export for client X must only ever touch client X's
  account, and land only in `X/`. Verify the ad-account id before writing anything.

Output should match the CSV schema above so `gen_report.py` consumes it unchanged.

## Conventions
- Python 3, `openpyxl` for Excel, `python-pptx` for decks.
- Never commit secrets. Credentials/tokens go in a gitignored store (e.g. `.env` or
  a `secrets/` dir), one entry per client.
- Keep client outputs inside the client folder.

## Deliberately unspecified
Module structure, credential storage format, token-refresh flow, and how far to push
per-client parallelism are left to you — pick sane, safe defaults and note the choices.
