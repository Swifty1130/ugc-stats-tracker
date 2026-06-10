# UGC Stats Tracker

A daily-refreshed, single-page dashboard of PUBLIC metrics (views, likes,
shares/comments, followers) across YouTube, TikTok, and Instagram. A GitHub
Action fetches stats every day, stores them in Supabase, regenerates a styled
`docs/index.html`, and deploys it to GitHub Pages — nothing ever runs on your
own machine.

**Flow:** GitHub Actions cron → `src/store.py` (fetch + upsert into Supabase)
→ `src/build_dashboard.py` (render `docs/index.html`) → deploy to Pages.

## One-time setup

### 1. Create the Supabase table

1. Create a free project at [supabase.com](https://supabase.com).
2. In the dashboard, open **SQL Editor → New query**, paste the contents of
   [`schema.sql`](schema.sql), and click **Run**. That creates the
   `daily_stats` table.
3. Note two values for step 3:
   - **Project URL** — Settings → API → Project URL (looks like
     `https://abcdefgh.supabase.co`)
   - **service_role key** — Settings → API → Project API keys →
     `service_role` (the secret one, *not* `anon`)

### 2. Get your API keys

- **YouTube** — in [Google Cloud Console](https://console.cloud.google.com),
  create a project, enable the **YouTube Data API v3**, then create an
  **API key** under APIs & Services → Credentials. Free; no OAuth needed.
- **Apify** — sign up at [apify.com](https://apify.com), then copy your API
  token from **Settings → API & Integrations**. TikTok and Instagram are
  scraped through Apify Actors (`clockworks/tiktok-scraper` and
  `apify/instagram-scraper`), public data only.

> **Cost note:** daily Apify pulls of a few accounts cost pennies — each run
> scrapes one profile page plus recent posts, well within Apify's cheapest
> usage tier. Switch the cron to weekly (see below) to shrink it further.

### 3. Add the four repository secrets

In this repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add exactly these four:

| Secret name       | Value                                      |
| ----------------- | ------------------------------------------ |
| `YOUTUBE_API_KEY` | your Google Cloud API key                  |
| `APIFY_TOKEN`     | your Apify API token                       |
| `SUPABASE_URL`    | your Supabase Project URL                  |
| `SUPABASE_KEY`    | your Supabase `service_role` key           |

No secret is ever committed — the code only reads them from environment
variables, which the workflow injects from these secrets.

### 4. Fill in your handles

Edit [`config/accounts.json`](config/accounts.json) and replace the
placeholders with your real public handles:

```json
{
  "youtube": ["@yourchannel"],
  "tiktok": ["@yourtiktok"],
  "instagram": ["yourinsta"]
}
```

- YouTube accepts a channel ID (`UC...`) or an `@handle`.
- TikTok handles keep the `@`; Instagram handles have no `@`.
- Each list can hold several accounts.

### 5. Turn on GitHub Pages

One-time toggle: **Settings → Pages → Source → GitHub Actions**.
After the first deploy, the dashboard lives at
`https://<your-username>.github.io/ugc-stats-tracker/`.

## Running it

The workflow runs automatically **every day at 13:00 UTC**. To run it now,
open the **Actions** tab → *Update UGC dashboard* → **Run workflow**.

To switch to weekly, edit the one cron line in
[`.github/workflows/update.yml`](.github/workflows/update.yml):

```yaml
- cron: "0 13 * * *" # daily at 13:00 UTC — for weekly (Mondays) change to "0 13 * * 1"
```

Re-runs on the same day overwrite that day's rows (no duplicates), thanks to
the table's `UNIQUE (captured_at, platform, account)` constraint.

## Notes on the metrics

- All data is **public** — no OAuth, no private analytics.
- **Shares** are only public on TikTok; YouTube and Instagram show `—` and
  comments serve as the engagement fallback.
- TikTok views/shares/comments are summed over the latest ~100 videos;
  followers and likes are account-wide. Instagram engagement covers the
  ~12 latest posts its public profile exposes.
- The committed `docs/index.html` holds sample placeholder numbers; the first
  workflow run replaces it with your real stats.
