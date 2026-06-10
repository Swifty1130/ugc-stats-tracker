"""Fetch public stats for YouTube channels via the YouTube Data API v3.

Uses a plain API key (no OAuth) and only reads PUBLIC data:
  - channel statistics  -> subscribers, lifetime views, video count
  - per-video statistics -> likes and comments, summed across all uploads

Needs the YOUTUBE_API_KEY environment variable.
"""

import os

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"


def _get(endpoint, **params):
    """Call one YouTube API endpoint and return the parsed JSON."""
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    response = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _lookup_channel(account):
    """Return the API's channel object for a channel ID or an @handle."""
    if account.startswith("UC"):
        params = {"id": account}
    else:
        # The API accepts handles with or without the leading @.
        params = {"forHandle": account}
    data = _get("channels", part="statistics,contentDetails", **params)
    items = data.get("items", [])
    if not items:
        raise ValueError(f"YouTube channel not found: {account!r} — check config/accounts.json")
    return items[0]


def _list_upload_video_ids(uploads_playlist_id):
    """Page through the channel's uploads playlist and collect every video ID."""
    video_ids = []
    page_token = None
    while True:
        params = {"playlistId": uploads_playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        data = _get("playlistItems", part="contentDetails", **params)
        for item in data.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        page_token = data.get("nextPageToken")
        if not page_token:
            return video_ids


def _sum_video_likes_and_comments(video_ids):
    """Sum likeCount and commentCount across videos (50 per API call)."""
    total_likes = 0
    total_comments = 0
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]
        data = _get("videos", part="statistics", id=",".join(batch))
        for item in data.get("items", []):
            stats = item["statistics"]
            # likeCount/commentCount are missing when the creator hides them.
            total_likes += int(stats.get("likeCount", 0))
            total_comments += int(stats.get("commentCount", 0))
    return total_likes, total_comments


def fetch_youtube_rows(accounts):
    """Return one normalized stats row (dict) per channel in `accounts`."""
    rows = []
    for account in accounts:
        channel = _lookup_channel(account)
        channel_stats = channel["statistics"]
        uploads_playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]

        video_ids = _list_upload_video_ids(uploads_playlist_id)
        total_likes, total_comments = _sum_video_likes_and_comments(video_ids)

        rows.append({
            "platform": "youtube",
            "account": account,
            "followers": int(channel_stats.get("subscriberCount", 0)),
            "total_views": int(channel_stats.get("viewCount", 0)),
            "total_likes": total_likes,
            "total_shares": None,  # YouTube does not expose share counts publicly
            "total_comments": total_comments,
            "video_count": int(channel_stats.get("videoCount", 0)),
        })
        print(f"[youtube] {account}: {rows[-1]['total_views']:,} views, "
              f"{rows[-1]['followers']:,} subscribers")
    return rows
