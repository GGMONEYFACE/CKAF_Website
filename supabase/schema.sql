-- Member accounts. The website uses the anon key.
-- Rank and instructor access live here, not in user metadata, because members can edit that.
-- A new account is always white belt. An instructor changes the belt from the admin page.
-- Instructors can also grant or remove instructor status from that page.
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

revoke all on function private.is_admin() from public, anon;
grant usage on schema private to authenticated;
grant execute on function private.is_admin() to authenticated;

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

-- Accounts can sign in as soon as they are created. No confirmation link.
-- Also turn off Authentication → Sign In / Providers → Email → Confirm email
-- in the Supabase dashboard so a confirmation message is not sent.
create or replace function private.confirm_email_on_signup()
returns trigger
language plpgsql
security definer
set search_path = auth
as $$
begin
    if new.email_confirmed_at is null then
        new.email_confirmed_at = now();
    end if;
    return new;
end;
$$;

revoke all on function private.confirm_email_on_signup() from public, anon, authenticated;

drop trigger if exists confirm_email_on_signup on auth.users;
create trigger confirm_email_on_signup
    before insert on auth.users
    for each row execute function private.confirm_email_on_signup();

update auth.users
set email_confirmed_at = now()
where email_confirmed_at is null;

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

grant update (display_name) on table public.profiles to authenticated;
grant update (is_admin) on table public.profiles to authenticated;

create or replace function public.set_my_name(new_name text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    caller uuid := auth.uid();
    cleaned text := left(btrim(coalesce(new_name, '')), 80);
begin
    if caller is null or cleaned = '' then
        return null;
    end if;
    update public.profiles
    set display_name = cleaned
    where id = caller;
    return cleaned;
end;
$$;

revoke all on function public.set_my_name(text) from public, anon;
grant execute on function public.set_my_name(text) to authenticated;

insert into public.profiles (id, display_name, email, rank)
select id, left(split_part(email, '@', 1), 80), left(email, 254), 'white'
from auth.users
where id not in (select id from public.profiles)
on conflict (id) do nothing;

-- Notes from the Suggestions page. Anyone can leave one. Instructors read them.
create table if not exists public.suggestions (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    author_name text not null default '' check (char_length(author_name) <= 80),
    message text not null check (char_length(btrim(message)) between 1 and 2000),
    member_id uuid references auth.users (id) on delete set null
);

create index if not exists suggestions_created_at_idx
    on public.suggestions (created_at desc);

alter table public.suggestions enable row level security;

revoke all on table public.suggestions from public, anon, authenticated;
grant insert (author_name, message) on table public.suggestions to anon, authenticated;
grant select on table public.suggestions to authenticated;
revoke select (member_id) on table public.suggestions from authenticated;

create or replace function private.stamp_suggestion()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    new.member_id := auth.uid();
    new.author_name := left(btrim(coalesce(new.author_name, '')), 80);
    new.message := left(btrim(coalesce(new.message, '')), 2000);
    if new.message = '' then
        raise exception 'empty suggestion';
    end if;
    return new;
end;
$$;

revoke all on function private.stamp_suggestion() from public, anon, authenticated;

drop trigger if exists stamp_suggestion on public.suggestions;
create trigger stamp_suggestion
    before insert on public.suggestions
    for each row execute function private.stamp_suggestion();

drop policy if exists "Anyone can leave a suggestion" on public.suggestions;
create policy "Anyone can leave a suggestion"
    on public.suggestions
    for insert
    to anon, authenticated
    with check (
        char_length(btrim(message)) between 1 and 2000
        and char_length(author_name) <= 80
    );

drop policy if exists "Instructors read suggestions" on public.suggestions;
create policy "Instructors read suggestions"
    on public.suggestions
    for select
    to authenticated
    using ((select private.is_admin()));
