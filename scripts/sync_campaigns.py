from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from snapchat.sync_campaigns import sync_campaign_stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Snapchat campaign-level daily stats.")
    parser.add_argument("--client", help="Optional client slug, e.g. space307")
    parser.add_argument("--refresh-days", type=int, default=3)
    parser.add_argument("--keep-days", type=int, default=90)
    args = parser.parse_args()

    result = sync_campaign_stats(
        client_slug=args.client,
        refresh_days=args.refresh_days,
        keep_days=args.keep_days,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
