"""Fetch public TikTok and Instagram stats via Apify Actors (REST API).

Actors used (both fetch PUBLIC profile data only — no login, no OAuth):
  - TikTok:    clockworks/tiktok-scraper
  - Instagram: apify/instagram-reel-scraper

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


def fetch_instagram_rows(accounts):
    """Return one normalized stats row per Instagram handle in `accounts`.

    The apify/instagram-reel-scraper returns a flat list of individual post items.
    Follower counts and total posts are pulled from the owner profile metadata attached
    to the first item, while videoPlayCount, likes, and comments are summed across all items.
    """
    rows = []
    for account in accounts:
        clean_handle = account.lstrip("@")
        
        # 1. Fixed input keys to match the Reel Scraper schema requirements
        items = _run_actor("apify/instagram-reel-scraper", {
            "username": [clean_handle],
            "resultsLimit": 20,  # Limits how many recent reels it scans to save compute
        })
        if not items:
            raise ValueError(f"Instagram scrape returned nothing for {account!r} — check the handle")

        # 2. Extract profile-wide metrics from the owner object meta of the first post
        first_post_owner = items[0].get("owner", {})
        followers = first_post_owner.get("followersCount") or 0
        posts_count = first_post_owner.get("postsCount") or 0

        # 3. Sum the active fields directly across the flat items array
        total_views = sum(post.get("videoPlayCount") or 0 for post in items)
        total_likes = sum(max(post.get("likesCount") or 0, 0) for post in items)
        total_comments = sum(post.get("commentsCount") or 0 for post in items)

        rows.append({
            "platform": "instagram",
            "account": account,
            "followers": followers,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_shares": None,  # Instagram does not expose share counts publicly
            "total_comments": total_comments,
            "video_count": posts_count,
        })
        
        print(f"[instagram] {account}: {followers:,} followers, "
              f"{len(items)} recent reels summed (Total Views: {total_views:,})")
              
    return rows


def fetch_instagram_rows(accounts):
    """Return one normalized stats row per Instagram handle in `accounts`.

    With resultsType "details" the scraper returns one profile item that
    includes the ~12 latest posts Instagram exposes publicly; engagement
    totals are summed over those posts. Shares are never public on Instagram.
    """
    rows = []
    for account in accounts:
        items = _run_actor("apify/instagram-reel-scraper", {
            "directUrls": [f"https://www.instagram.com/{account.lstrip('@')}/"],
            "resultsType": "details",
        })
        if not items:
            raise ValueError(f"Instagram scrape returned nothing for {account!r} — check the handle")

        profile = items[0]
        latest_posts = profile.get("latestPosts", [])
        rows.append({
            "platform": "instagram",
            "account": account,
            "followers": profile.get("followersCount"),
            # Only video posts have a view count; photos contribute 0.
            "total_views": sum(post.get("videoPlayCount") or 0 for post in latest_posts),
            # likesCount is -1 when the creator hides likes on a post.
            "total_likes": sum(max(post.get("likesCount") or 0, 0) for post in latest_posts),
            "total_shares": None,  # Instagram does not expose share counts publicly
            "total_comments": sum(post.get("commentsCount") or 0 for post in latest_posts),
            "video_count": profile.get("postsCount"),
        })
        print(f"[instagram] {account}: {rows[-1]['followers']:,} followers, "
              f"{len(latest_posts)} recent posts summed")
    return rows
