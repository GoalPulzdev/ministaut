-- Ministaut push alerts (web push). Run once in GoalPulz Sql.
-- Only the Edge Functions (service role) read or write these tables; RLS without
-- policies keeps them closed to the public publishable key.

create table if not exists ministaut_push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  endpoint text not null check (length(endpoint) between 20 and 800),
  p256dh text not null,
  auth text not null,
  match_id uuid not null,
  venue_id text not null check (venue_id in ('lerkendal', 'koteng_arena')),
  kind text not null check (kind in ('release', 'section')),
  -- '' for release alerts, so the unique key below also covers them.
  section_code text not null default '' check (length(section_code) <= 12),
  threshold integer check (threshold between 1 and 500),
  created_at timestamptz not null default now(),
  last_notified_at timestamptz,
  unique (endpoint, match_id, kind, section_code)
);
create index if not exists ministaut_push_subscriptions_match on ministaut_push_subscriptions (match_id);
alter table ministaut_push_subscriptions enable row level security;

-- Last scan the notifier has handled per match, so each scan triggers alerts once.
create table if not exists ministaut_push_state (
  match_id uuid primary key,
  venue_id text not null,
  last_scan_id uuid not null,
  checked_at timestamptz not null default now()
);
alter table ministaut_push_state enable row level security;

-- Schedule: every 10 minutes. The shared secret lives in Vault, never in Git:
--   select vault.create_secret('<samme verdi som PUSH_CRON_SECRET>', 'ministaut_push_cron');
create extension if not exists pg_cron;
create extension if not exists pg_net;
select cron.schedule('ministaut-push-notify', '*/10 * * * *', $$
  select net.http_post(
    url := 'https://khetbokxbcujwcurvviu.supabase.co/functions/v1/ministaut-push-notify',
    headers := jsonb_build_object('Content-Type', 'application/json',
      'x-cron-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'ministaut_push_cron')),
    body := '{}'::jsonb,
    timeout_milliseconds := 20000)
$$);
