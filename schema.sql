-- UGC stats tracker: one row per (day, platform, account).
-- Run this once in the Supabase SQL editor (Dashboard -> SQL Editor -> New query -> paste -> Run).
--
-- The GitHub Action authenticates with the service_role key, which bypasses
-- Row Level Security, so no policies are needed here.

create table if not exists daily_stats (
  captured_at    date   not null,  -- the day the snapshot was taken (UTC)
  platform       text   not null,  -- 'youtube' | 'tiktok' | 'instagram'
  account        text   not null,  -- the handle exactly as written in config/accounts.json
  followers      bigint,           -- subscribers / followers (null if unavailable)
  total_views    bigint not null,
  total_likes    bigint not null,
  total_shares   bigint,           -- only TikTok exposes shares publicly; null elsewhere
  total_comments bigint,           -- engagement fallback where shares aren't public
  video_count    int,              -- videos / posts on the account

  -- One row per account per day. store.py upserts against this constraint,
  -- so re-running on the same day overwrites instead of duplicating.
  unique (captured_at, platform, account)
);

-- With RLS on and no policies defined, the table is inaccessible to the
-- public anon key. The GitHub Action still works because the service_role
-- key bypasses RLS.
alter table daily_stats enable row level security;
