"""Fetch public TikTok and Instagram stats via Apify Actors (REST API).

Actors used (all fetch PUBLIC profile data only — no login, no OAuth):
  - TikTok:    clockworks/tiktok-scraper
  - Instagram: apify/instagram-scraper (profile: followers, post count)
               + apify/instagram-reel-scraper (live per-reel engagement)

Each run: start the Actor, poll until it finishes, then download its dataset.
Needs the APIFY_TOKEN environment variable.
"""

import os
import time

import requests

API_BASE = "https://api.apify.com/v2"

# How many recent TikTok videos to scrape per profile. Engagement totals
# (views/likes/shares/comments) are summed over these videos.
TIKTOK_VIDEOS_PER_PROFILE = 100

# How many recent Instagram reels to scrape per profile. Engagement totals
# (views/likes/comments) are summed over these reels.
INSTAGRAM_REELS_PER_PROFILE = 50

POLL_INTERVAL_SECONDS = 15
MAX_WAIT_SECONDS = 15 * 60  # give a scrape up to 15 minutes


def _run_actor(actor_id, run_input):
    """Run an Apify Actor and return its dataset items as a list of dicts."""
    token = os.environ["APIFY_TOKEN"]

    # 1. Start the run. Actor IDs use ~ instead of / in URLs.
    response = requests.post(
        f"{API_BASE}/acts/{actor_id.replace('/', '~')}/runs",
        params={"token": token},
        json=run_input,
        timeout=30,
    )
    response.raise_for_status()
    run = response.json()["data"]

    # 2. Poll until the run reaches a terminal state.
    deadline = time.time() + MAX_WAIT_SECONDS
    while True:
        time.sleep(POLL_INTERVAL_SECONDS)
        response = requests.get(
            f"{API_BASE}/actor-runs/{run['id']}",
            params={"token": token},
            timeout=30,
        )
        response.raise_for_status()
        run = response.json()["data"]
        if run["status"] == "SUCCEEDED":
            break
        if run["status"] in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run of {actor_id} ended with status {run['status']}")
        if time.time() > deadline:
            raise TimeoutError(f"Apify run of {actor_id} took longer than {MAX_WAIT_SECONDS}s")

    # 3. Download the results.
    response = requests.get(
        f"{API_BASE}/datasets/{run['defaultDatasetId']}/items",
        params={"token": token, "clean": "true"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def fetch_tiktok_rows(accounts):
    """Return one normalized stats row per TikTok handle in `accounts`.

    The scraper returns one item per video, each carrying the profile's
    authorMeta. Followers and total likes come from authorMeta (account-wide
    figures); views, shares and comments are summed over the scraped videos.
    """
    rows = []
    for account in accounts:
        items = _run_actor("clockworks/tiktok-scraper", {
            "profiles": [account.lstrip("@")],
            "resultsPerPage": TIKTOK_VIDEOS_PER_PROFILE,
        })
        if not items:
            raise ValueError(f"TikTok scrape returned nothing for {account!r} — check the handle")

        author = items[0].get("authorMeta", {})
        rows.append({
            "platform": "tiktok",
            "account": account,
            "followers": author.get("fans"),
            "total_views": sum(item.get("playCount", 0) for item in items),
            # authorMeta.heart is TikTok's public account-wide like total.
            "total_likes": author.get("heart", 0),
            "total_shares": sum(item.get("shareCount", 0) for item in items),
            "total_comments": sum(item.get("commentCount", 0) for item in items),
            "video_count": author.get("video"),
        })
        print(f"[tiktok] {account}: {rows[-1]['total_views']:,} views across "
              f"{len(items)} recent videos")
    return rows


def fetch_instagram_rows(accounts):
    """Return one normalized stats row per Instagram handle in `accounts`.

    Two scrapes per account, because no single public source has everything:
      1. apify/instagram-scraper (profile details) -> followers, post count.
         Its embedded latestPosts only carry videoViewCount, which Meta froze
         for public web scrapers — the number stops updating, so it is NOT
         usable for views.
      2. apify/instagram-reel-scraper (recent reels) -> live videoPlayCount
         ("Plays"), likes and comments, summed over the scraped reels.

    Shares are never public on Instagram.
    """
    rows = []
    for account in accounts:
        handle = account.lstrip("@")

        profile_items = _run_actor("apify/instagram-scraper", {
            "directUrls": [f"https://www.instagram.com/{handle}/"],
            "resultsType": "details",
        })
        if not profile_items:
            raise ValueError(f"Instagram scrape returned nothing for {account!r} — check the handle")
        profile = profile_items[0]

        reels = _run_actor("apify/instagram-reel-scraper", {
            "username": [handle],
            "resultsLimit": INSTAGRAM_REELS_PER_PROFILE,
        })
        if not reels:
            # A profile with no reels is legitimate; engagement just sums to 0.
            print(f"[instagram] {account}: no reels returned")

        rows.append({
            "platform": "instagram",
            "account": account,
            "followers": profile.get("followersCount"),
            # videoPlayCount is the live "Plays" metric; fall back to the
            # legacy videoViewCount only for old items that lack it.
            "total_views": sum(reel.get("videoPlayCount") or reel.get("videoViewCount") or 0
                               for reel in reels),
            # likesCount is -1 when the creator hides likes on a post.
            "total_likes": sum(max(reel.get("likesCount") or 0, 0) for reel in reels),
            "total_shares": None,  # Instagram does not expose share counts publicly
            "total_comments": sum(reel.get("commentsCount") or 0 for reel in reels),
            "video_count": profile.get("postsCount"),
        })
        print(f"[instagram] {account}: {rows[-1]['followers']:,} followers, "
              f"{rows[-1]['total_views']:,} views across {len(reels)} recent reels")
    return rows
