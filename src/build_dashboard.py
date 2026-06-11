"""Read the latest snapshot from Supabase and render docs/index.html.

This is the "build" entry point the GitHub Action runs after store.py:
    python src/build_dashboard.py

The page is a self-contained static "spec sheet" styled to match the
portfolio design system. Needs SUPABASE_URL and SUPABASE_KEY.
"""

import os
from pathlib import Path

from supabase import create_client

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "index.html"

PLATFORM_ORDER = ["youtube", "tiktok", "instagram"]
PLATFORM_LABELS = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}


# ---------------------------------------------------------------- formatting

def compact(n):
    """Compact form for hero numbers: 1240000 -> '1.2M', 340000 -> '340K'."""
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(n)


def grouped(n):
    """Full grouped form for table numbers: 1240000 -> '1,240,000'."""
    return "—" if n is None else f"{n:,}"


def sum_nullable(values):
    """Sum, ignoring Nones. Returns None if every value is None."""
    present = [v for v in values if v is not None]
    return sum(present) if present else None


# ------------------------------------------------------------------ querying

def fetch_latest_rows(client):
    """Return all daily_stats rows from the most recent captured_at date."""
    latest = (
        client.table("daily_stats")
        .select("captured_at")
        .order("captured_at", desc=True)
        .limit(1)
        .execute()
    )
    if not latest.data:
        raise RuntimeError("daily_stats is empty — run store.py first")
    latest_date = latest.data[0]["captured_at"]

    result = (
        client.table("daily_stats")
        .select("*")
        .eq("captured_at", latest_date)
        .execute()
    )
    return latest_date, result.data


# ----------------------------------------------------------------- rendering

def render_html(latest_date, rows):
    """Render the full dashboard page from one day's stat rows."""

    # Collapse rows to one summary per platform (sums across accounts).
    platforms = []
    for platform in PLATFORM_ORDER:
        platform_rows = [r for r in rows if r["platform"] == platform]
        if not platform_rows:
            continue
        platforms.append({
            "label": PLATFORM_LABELS[platform],
            "views": sum_nullable([r["total_views"] for r in platform_rows]),
            "likes": sum_nullable([r["total_likes"] for r in platform_rows]),
            "shares": sum_nullable([r["total_shares"] for r in platform_rows]),
            "comments": sum_nullable([r["total_comments"] for r in platform_rows]),
            "followers": sum_nullable([r["followers"] for r in platform_rows]),
        })

    # Grand totals for the hero row.
    total_views = sum_nullable([p["views"] for p in platforms])
    total_likes = sum_nullable([p["likes"] for p in platforms])
    total_shares = sum_nullable([p["shares"] for p in platforms])
    total_followers = sum_nullable([p["followers"] for p in platforms])

    # Hero stat blocks: label, value, whether it's a key (green) total.
    hero_blocks = [
        ("Total Views", compact(total_views), True),
        ("Total Likes", compact(total_likes), False),
        ("Total Shares", compact(total_shares), False),
        ("Total Followers", compact(total_followers), True),
    ]
    hero_html = "\n".join(
        f'''        <div class="stat">
          <p class="stat-label">{label}</p>
          <p class="stat-value{' green' if key else ''}">{value}</p>
        </div>'''
        for label, value, key in hero_blocks
    )

    table_rows_html = "\n".join(
        f'''          <tr>
            <td><span class="pill">{p["label"]}</span></td>
            <td class="num">{grouped(p["views"])}</td>
            <td class="num">{grouped(p["likes"])}</td>
            <td class="num">{grouped(p["shares"])}</td>
            <td class="num">{grouped(p["comments"])}</td>
            <td class="num">{grouped(p["followers"])}</td>
          </tr>'''
        for p in platforms
    )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Performance — Ryan Benjamine</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500&family=EB+Garamond:ital,wght@1,500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    /* Dark "final page" palette: ink background, cream type. The signature
       green is brightened for contrast against black; the original deep
       green (#1F4D38) is kept for fills. */
    --bg: #1A1A1A;
    --bg-alt: #242420;
    --ink: #F5F1EB;
    --body: #C8C3B8;
    --muted: #8E8A80;
    --hairline: rgba(245, 241, 235, .16);
    --green: #54B585;
    --green-deep: #1F4D38;
    --tan: #A38963;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: var(--bg);
    color: var(--body);
    font-family: "Bricolage Grotesque", sans-serif;
  }}

  .mono {{
    font-family: "IBM Plex Mono", monospace;
    text-transform: uppercase;
    letter-spacing: .13em;
  }}

  .page {{
    max-width: 1240px;
    margin: 0 auto;
    padding: 96px 32px 112px;
  }}

  /* ---- header ---- */
  .masthead {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 32px;
    flex-wrap: wrap;
    padding-bottom: 56px;
  }}

  .eyebrow {{
    font-family: "IBM Plex Mono", monospace;
    text-transform: uppercase;
    letter-spacing: .14em;
    font-size: 13px;
    color: var(--tan);
    margin-bottom: 20px;
  }}

  h1 {{
    font-weight: 500;
    letter-spacing: -0.03em;
    font-size: clamp(40px, 5.5vw, 68px);
    line-height: 1.05;
    color: var(--ink);
  }}

  h1 em {{
    font-family: "EB Garamond", serif;
    font-style: italic;
    font-weight: 500;
    color: var(--green);
  }}

  .status {{
    font-family: "IBM Plex Mono", monospace;
    text-transform: uppercase;
    letter-spacing: .12em;
    font-size: 12px;
    color: var(--muted);
    text-align: right;
    white-space: nowrap;
    padding-bottom: 10px;
  }}

  /* ---- aggregate stat blocks (1px hairline grid motif) ---- */
  .totals {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: var(--hairline);
    border-top: 1px solid var(--hairline);
    border-bottom: 1px solid var(--hairline);
  }}

  .stat {{
    background: var(--bg);
    padding: 44px 36px 48px;
  }}

  .stat-label {{
    font-family: "IBM Plex Mono", monospace;
    text-transform: uppercase;
    letter-spacing: .13em;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 18px;
  }}

  .stat-value {{
    font-weight: 500;
    letter-spacing: -0.03em;
    font-size: clamp(48px, 4.8vw, 64px);
    line-height: 1;
    color: var(--ink);
  }}

  .stat-value.green {{ color: var(--green); }}

  /* ---- platform breakdown (spec-sheet table) ---- */
  .breakdown {{ padding-top: 88px; }}

  .breakdown .eyebrow {{ margin-bottom: 28px; }}

  .table-wrap {{ overflow-x: auto; }}

  table {{
    width: 100%;
    border-collapse: collapse;
  }}

  th {{
    font-family: "IBM Plex Mono", monospace;
    font-weight: 400;
    text-transform: uppercase;
    letter-spacing: .13em;
    font-size: 11px;
    color: var(--muted);
    text-align: right;
    padding: 0 20px 14px;
    border-bottom: 1px solid var(--hairline);
  }}

  th:first-child {{ text-align: left; padding-left: 0; }}
  th:last-child {{ padding-right: 0; }}

  td {{
    padding: 26px 20px;
    border-bottom: 1px solid var(--hairline);
    text-align: right;
  }}

  td:first-child {{ text-align: left; padding-left: 0; }}
  td:last-child {{ padding-right: 0; }}

  td.num {{
    font-family: "IBM Plex Mono", monospace;
    font-size: 15px;
    color: var(--body);
  }}

  .pill {{
    display: inline-block;
    font-family: "IBM Plex Mono", monospace;
    text-transform: uppercase;
    letter-spacing: .13em;
    font-size: 11px;
    color: var(--ink);
    background: var(--green-deep);
    border: 1px solid var(--hairline);
    border-radius: 999px;
    padding: 7px 16px;
  }}

  /* ---- footer ---- */
  footer {{
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px 32px;
    max-width: 1240px;
    margin: 0 auto;
    border-top: 1px solid var(--hairline);
    color: var(--muted);
    font-family: "IBM Plex Mono", monospace;
    text-transform: uppercase;
    letter-spacing: .13em;
    font-size: 12px;
    padding: 40px 32px 48px;
  }}

  @media (max-width: 880px) {{
    .totals {{ grid-template-columns: repeat(2, 1fr); }}
    .stat {{ padding: 32px 24px 36px; }}
  }}
</style>
</head>
<body>
  <main class="page">
    <header class="masthead">
      <div>
        <p class="eyebrow">&sect; 08 &mdash; Performance</p>
        <h1>The numbers, <em>refreshed weekly</em></h1>
      </div>
      <p class="status">Last updated &middot; {latest_date}</p>
    </header>

    <section class="totals">
{hero_html}
    </section>

    <section class="breakdown">
      <p class="eyebrow">Platform breakdown</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Platform</th>
              <th>Views</th>
              <th>Likes</th>
              <th>Shares</th>
              <th>Comments</th>
              <th>Followers</th>
            </tr>
          </thead>
          <tbody>
{table_rows_html}
          </tbody>
        </table>
      </div>
    </section>
  </main>

  <footer>
    <span>Ryan Benjamine &middot; UGC &middot; 2026</span>
    <span>&sect; 08 &mdash; Performance</span>
  </footer>
</body>
</html>
'''


def main():
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    latest_date, rows = fetch_latest_rows(client)
    OUTPUT_PATH.write_text(render_html(latest_date, rows), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} from {len(rows)} rows captured {latest_date}")


if __name__ == "__main__":
    main()
