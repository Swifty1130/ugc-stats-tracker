"""Fetch today's public stats for every configured account and upsert them
into the Supabase `daily_stats` table.

This is the "fetch -> store" entry point the GitHub Action runs:
    python src/store.py

Needs SUPABASE_URL and SUPABASE_KEY (plus the fetchers' YOUTUBE_API_KEY
and APIFY_TOKEN) as environment variables.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client

from fetch_apify import fetch_instagram_rows, fetch_tiktok_rows
from fetch_youtube import fetch_youtube_rows

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "accounts.json"


def load_accounts():
    """Read config/accounts.json and return the per-platform handle lists."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    for platform in ("youtube", "tiktok", "instagram"):
        if not isinstance(config.get(platform), list):
            raise ValueError(f"config/accounts.json must have a {platform!r} list of handles")
    return config


def main():
    accounts = load_accounts()

    rows = (
        fetch_youtube_rows(accounts["youtube"])
        + fetch_tiktok_rows(accounts["tiktok"])
        + fetch_instagram_rows(accounts["instagram"])
    )

    # Stamp every row with today's UTC date. Combined with the table's
    # UNIQUE (captured_at, platform, account) constraint, re-running on the
    # same day overwrites that day's rows instead of duplicating them.
    today = datetime.now(timezone.utc).date().isoformat()
    for row in rows:
        row["captured_at"] = today

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    client.table("daily_stats").upsert(
        rows, on_conflict="captured_at,platform,account"
    ).execute()
    print(f"Upserted {len(rows)} rows into daily_stats for {today}")


if __name__ == "__main__":
    main()
