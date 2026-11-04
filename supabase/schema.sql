-- Member accounts. The website uses the anon key.
-- Rank and instructor access live here, not in user metadata, because members can edit that.
-- A new account is always white belt. An instructor changes the belt from the admin page.
-- Instructor emails are listed in private.admin_emails. Example:
--   insert into private.admin_emails (email) values ('instructor@example.com');

create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    display_name text not null check (char_length(display_name) between 1 and 80),
    email text,
    rank text not null default 'white' check (rank in (
        'white', '10th', '9th', '8th', '7th', '6th', '5th',
        '4th', '3rd', '2nd', '1st', 'black'
    )),
    is_admin boolean not null default false,
    created_at timestamptz not null default now()
);

alter table public.profiles add column if not exists email text;
alter table public.profiles add column if not exists is_admin boolean not null default false;

alter table public.profiles enable row level security;

revoke all on table public.profiles from public, anon, authenticated;
grant select on table public.profiles to authenticated;
grant update (rank) on table public.profiles to authenticated;

drop policy if exists "Members read their own profile" on public.profiles;
create policy "Members read their own profile"
    on public.profiles
    for select
    to authenticated
    using (auth.uid() = id);

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.admin_emails (
    email text primary key
);
revoke all on table private.admin_emails from public, anon, authenticated;

create or replace function private.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.profiles
        where id = auth.uid()
          and is_admin
    );
$$;

revoke all on function private.is_admin() from public, anon, authenticated;

drop policy if exists "Admins read member profiles" on public.profiles;
create policy "Admins read member profiles"
    on public.profiles
    for select
    to authenticated
    using (private.is_admin());

drop policy if exists "Admins update belt ranks" on public.profiles;
create policy "Admins update belt ranks"
    on public.profiles
    for update
    to authenticated
    using (private.is_admin())
    with check (private.is_admin());

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    chosen_name text;
begin
    chosen_name := left(coalesce(
        nullif(btrim(new.raw_user_meta_data ->> 'display_name'), ''),
        nullif(split_part(new.email, '@', 1), ''),
        'Member'
    ), 80);
    insert into public.profiles (id, display_name, email, rank, is_admin)
    values (new.id, chosen_name, left(coalesce(new.email, ''), 254), 'white', false);
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function private.handle_new_user();

create or replace function public.claim_instructor()
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    caller uuid := auth.uid();
    caller_email text;
begin
    if caller is null then
        return false;
    end if;
    select users.email into caller_email
    from auth.users
    where users.id = caller;
    if caller_email is null or btrim(caller_email) = '' then
        return false;
    end if;
    if not exists (
        select 1
        from private.admin_emails
        where lower(email) = lower(caller_email)
    ) then
        return false;
    end if;
    update public.profiles
    set is_admin = true
    where id = caller
      and is_admin = false;
    return true;
end;
$$;

revoke all on function public.claim_instructor() from public, anon;
grant execute on function public.claim_instructor() to authenticated;

insert into public.profiles (id, display_name, email, rank)
select id, left(split_part(email, '@', 1), 80), left(email, 254), 'white'
from auth.users
where id not in (select id from public.profiles)
on conflict (id) do nothing;
