-- Run this once in the Supabase SQL editor (Dashboard → SQL → New query).
-- Then add members under Authentication → Users, with Auto Confirm turned on.
-- Set each person's name and belt in Table Editor → profiles.
-- Allowed rank values: white, 10th, 9th, 8th, 7th, 6th, 5th, 4th, 3rd, 2nd, 1st, black
--
-- Do not put the service_role key in this project. The website uses the anon key,
-- and members can only read their own row. Change a belt from the Supabase dashboard.

create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    display_name text not null check (char_length(display_name) between 1 and 80),
    rank text not null default 'white' check (rank in (
        'white', '10th', '9th', '8th', '7th', '6th', '5th',
        '4th', '3rd', '2nd', '1st', 'black'
    )),
    created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

revoke all on table public.profiles from public, anon, authenticated;
grant select on table public.profiles to authenticated;

drop policy if exists "Members read their own profile" on public.profiles;
create policy "Members read their own profile"
    on public.profiles
    for select
    to authenticated
    using (auth.uid() = id);

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, display_name, rank)
    values (
        new.id,
        left(coalesce(nullif(new.raw_user_meta_data->>'display_name', ''), split_part(new.email, '@', 1)), 80),
        'white'
    );
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function private.handle_new_user();

insert into public.profiles (id, display_name, rank)
select id, left(split_part(email, '@', 1), 80), 'white'
from auth.users
where id not in (select id from public.profiles)
on conflict (id) do nothing;
