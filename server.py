# CKAF member site.
# Supabase checks the password. The browser keeps two HttpOnly cookies.
# Member pages are read from protected/ and sent only when the rank is high enough.
# Local: python server.py
# Vercel: proxy.py handles the same requests.

import html
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RANKS = {
    "white": 1,
    "10th": 2,
    "9th": 3,
    "8th": 4,
    "7th": 5,
    "6th": 6,
    "5th": 7,
    "4th": 8,
    "3rd": 9,
    "2nd": 10,
    "1st": 11,
    "black": 12,
}

RANK_LABEL = {
    "white": "White Belt",
    "10th": "10th Gold",
    "9th": "9th Purple",
    "8th": "8th Orange",
    "7th": "7th Blue",
    "6th": "6th Green",
    "5th": "5th Green",
    "4th": "4th Brown",
    "3rd": "3rd Brown",
    "2nd": "2nd Red",
    "1st": "1st Red",
    "black": "Black Belt",
}

# Basename -> minimum rank level. Keep this in step with cookies.js.
# one-steps.html is also trimmed by section inside the page.
PAGE_LEVEL = {
    "white-belts.html": 1,
    "10th-gold.html": 2,
    "9th-purple.html": 3,
    "8th-orange.html": 4,
    "7th-blue.html": 5,
    "6th-green.html": 6,
    "5th-green.html": 7,
    "4th-brown.html": 8,
    "3rd-brown.html": 9,
    "2nd-red.html": 10,
    "1st-red.html": 11,
    "giecho-il-bu.html": 2,
    "giecho-yi-bu.html": 3,
    "giecho-sahm-bu.html": 4,
    "pyong-an-cho-dan.html": 5,
    "pyong-an-yi-dan.html": 6,
    "pyong-an-sahm-dan.html": 7,
    "pyong-an-sa-dan.html": 8,
    "nahanchi-sahm-dan.html": 9,
    "pyong-an-oh-dan.html": 10,
    "empi.html": 11,
    "bassai.html": 12,
    "one-steps.html": 1,
}

PUBLIC_HTML = {
    "index.html",
    "locations.html",
    "verses.html",
    "login.html",
}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

ACCESS_COOKIE = "ckaf_access"
REFRESH_COOKIE = "ckaf_refresh"
REMEMBER_COOKIE = "ckaf_remember"
REMEMBER_SECONDS = 60 * 60 * 24 * 7
MAX_ATTEMPTS = 8
ATTEMPT_WINDOW = 600
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
SECTION_RE = re.compile(
    r"[ \t]*<h3 class=\"section-heading\">[^<]*</h3>\s*"
    r"<div class=\"onesteps-container\" data-min-rank=\"([a-z0-9]+)\" data-section-name=\"([^\"]*)\">",
    re.IGNORECASE,
)
NOTE_RE = re.compile(r"\s*<p class=\"note\">[\s\S]*?</p>", re.IGNORECASE)

ATTEMPT_LOCK = threading.Lock()
ATTEMPTS = {}
PROFILE_WARNED = False


def load_env_file():
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def supabase_settings():
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    local = host in ("127.0.0.1", "localhost")
    placeholder = "YOUR_PROJECT" in url or "your_anon_key" in key
    scheme_ok = parsed.scheme == "https" or (parsed.scheme == "http" and local)
    if scheme_ok and parsed.netloc and len(key) >= 20 and not placeholder:
        return url, key
    return None, None


def configured():
    url, key = supabase_settings()
    return bool(url and key)


def rank_level(rank_id):
    return RANKS.get(rank_id, 0)


def rank_label_for_level(level):
    for rank_id, value in RANKS.items():
        if value == level:
            return RANK_LABEL[rank_id]
    return "Black Belt"


def required_level(relative_path):
    name = relative_path.rsplit("/", 1)[-1]
    if name in PUBLIC_HTML:
        return 0
    if name in PAGE_LEVEL:
        return PAGE_LEVEL[name]
    if name.endswith(".html"):
        return RANKS["black"]
    return 0


def load_env_and_check_files():
    kata = (ROOT / "protected" / "Kata" / "giecho-il-bu.html").read_text(encoding="utf-8")
    gated = replace_main_content(kata, "<p>gated</p>")
    if gated is None or "steps-list" in gated or "Junbi" in gated:
        raise SystemExit("Protected pages would leak content. Refusing to start.")
    steps = (ROOT / "protected" / "one-steps.html").read_text(encoding="utf-8")
    low = strip_onesteps(steps, rank_level("white"))
    if 'data-min-rank="5th"' in low or 'data-min-rank="1st"' in low or 'class="note"' in low:
        raise SystemExit("One-steps sections would leak to a lower belt. Refusing to start.")
    high = strip_onesteps(steps, rank_level("black"))
    if 'data-min-rank="1st"' not in high or 'class="note"' not in high:
        raise SystemExit("One-steps sections for a black belt were removed. Refusing to start.")


def find_div_open(text, start):
    lower = text.lower()
    index = start
    while index < len(lower):
        found = lower.find("<div", index)
        if found < 0:
            return -1
        nxt = lower[found + 4:found + 5]
        if nxt in (" ", ">", "/", "\n", "\t", "\r"):
            return found
        index = found + 4
    return -1


def div_span(text, open_index):
    close_at = text.find(">", open_index)
    if close_at < 0:
        return None
    depth = 1
    index = close_at + 1
    while depth and index < len(text):
        nxt_open = find_div_open(text, index)
        nxt_close = text.lower().find("</div>", index)
        if nxt_close < 0:
            return None
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            index = nxt_open + 4
        else:
            depth -= 1
            if depth == 0:
                return close_at + 1, nxt_close, nxt_close + len("</div>")
            index = nxt_close + len("</div>")
    return None


def replace_main_content(page, inner):
    marker = '<div class="content">'
    start = page.find(marker)
    if start < 0:
        return None
    span = div_span(page, start)
    if span is None:
        return None
    inner_start, inner_end, _tag_end = span
    return page[:inner_start] + inner + page[inner_end:]


def strip_onesteps(page, level):
    pieces = []
    cursor = 0
    for match in SECTION_RE.finditer(page):
        div_at = match.start() + match.group(0).lower().rfind("<div")
        span = div_span(page, div_at)
        if span is None:
            return page
        _inner_start, _inner_end, tag_end = span
        pieces.append(page[cursor:match.start()])
        need = rank_level(match.group(1))
        if level >= need:
            pieces.append(page[match.start():tag_end])
        else:
            name = match.group(2)
            label = RANK_LABEL.get(match.group(1), "a higher belt")
            pieces.append(
                '\n    <p class="rank-note">'
                + html.escape(name)
                + " is available to "
                + html.escape(label)
                + " and above.</p>\n"
            )
        cursor = tag_end
    pieces.append(page[cursor:])
    result = "".join(pieces)
    if level < rank_level("1st"):
        result = NOTE_RE.sub("", result)
    return result


def login_href(relative_path):
    depth = relative_path.count("/")
    prefix = "../" * depth
    return prefix + "login.html?next=" + urllib.parse.quote(relative_path, safe="")


def gate_inner(session, required, relative_path):
    required_label = rank_label_for_level(required)
    if session and session.get("rank"):
        message = (
            "This page is for "
            + required_label
            + " and above. You are signed in as "
            + RANK_LABEL.get(session["rank"], "a member")
            + "."
        )
        link = "Switch account"
    elif session:
        message = "This page is for members with a rank on file. Ask an instructor to set your rank."
        link = "Switch account"
    else:
        message = "This page is for " + required_label + " and above. Sign in to continue."
        link = "Sign in"
    href = login_href(relative_path)
    return (
        '<div class="access-gate"><h2>Members only</h2><p>'
        + html.escape(message)
        + '</p><a class="gate-link" href="'
        + html.escape(href, quote=True)
        + '">'
        + html.escape(link)
        + "</a></div>"
    )


def onesteps_for(page, level):
    stripped = strip_onesteps(page, level)
    if stripped is None:
        return None
    for rank_id, need in RANKS.items():
        if need > level and ('data-min-rank="%s"' % rank_id) in stripped:
            return None
    if level < rank_level("1st") and 'class="note"' in stripped:
        return None
    return stripped


def prepare_html(relative_path, page, session):
    need = required_level(relative_path)
    level = rank_level(session["rank"]) if session and session.get("rank") else 0
    if relative_path.rsplit("/", 1)[-1] == "one-steps.html" and level >= need:
        trimmed = onesteps_for(page, level)
        if trimmed is None:
            level = 0
            need = max(need, 1)
        else:
            return trimmed, 200
    if need > level:
        inner = gate_inner(session, need, relative_path)
        gated = replace_main_content(page, inner)
        if gated is None:
            return None, 403
        return gated, 403
    return page, 200


def safe_relative(value):
    if not isinstance(value, str) or len(value) < 1 or len(value) > 200:
        return "index.html"
    if not re.fullmatch(r"[A-Za-z0-9./_-]+", value):
        return "index.html"
    if value.startswith("/") or value.startswith(".") or ".." in value.split("/"):
        return "index.html"
    if not value.endswith(".html"):
        return "index.html"
    return value


def inside_root(candidate):
    root = ROOT.resolve()
    resolved = candidate.resolve()
    return resolved == root or root in resolved.parents


def page_file(relative):
    if relative == "protected" or relative.startswith("protected/"):
        return None
    for base in (ROOT, ROOT / "protected"):
        candidate = base / relative
        if inside_root(candidate) and candidate.is_file():
            return candidate
    return None


def resolve_existing(relative_path):
    relative_path = safe_relative(relative_path)
    found = page_file(relative_path)
    if found is None or found.suffix.lower() != ".html":
        return "index.html"
    return relative_path


def static_file(url_path):
    if url_path == "/":
        relative = "index.html"
    else:
        relative = urllib.parse.unquote(url_path).lstrip("/")
    relative = relative.replace("\\", "/")
    if relative.endswith("/"):
        relative += "index.html"
    parts = relative.split("/")
    if any(part in ("", ".", "..") or part.startswith(".") for part in parts):
        return None
    if relative == "protected" or relative.startswith("protected/"):
        return None
    found = page_file(relative)
    if found is None or found.suffix.lower() not in CONTENT_TYPES:
        return None
    return found, relative


def cookies_are_secure(headers):
    if os.environ.get("CKAF_COOKIE_SECURE", "").strip() == "1" or os.environ.get("VERCEL") == "1":
        return True
    if headers is None:
        return False
    proto = headers.get("X-Forwarded-Proto") or ""
    return proto.split(",")[0].strip().lower() == "https"


def one_cookie(name, value, max_age, secure):
    parts = [name + "=" + urllib.parse.quote(value, safe=""), "Path=/", "HttpOnly", "SameSite=Lax"]
    if secure:
        parts.append("Secure")
    if max_age is not None:
        parts.append("Max-Age=" + str(int(max_age)))
    return "; ".join(parts)


def auth_cookies(access, refresh, expires_in, remember, headers, clear=False):
    secure = cookies_are_secure(headers)
    refresh_age = 0 if clear else (REMEMBER_SECONDS if remember else None)
    access_age = 0 if clear else (int(expires_in or 3600) if remember else None)
    remember_age = 0 if clear else refresh_age
    return [
        one_cookie(ACCESS_COOKIE, "" if clear else access, access_age, secure),
        one_cookie(REFRESH_COOKIE, "" if clear else refresh, refresh_age, secure),
        one_cookie(REMEMBER_COOKIE, "" if clear else ("1" if remember else "0"), remember_age, secure),
    ]


def parse_cookies(header):
    found = {}
    if not header:
        return found
    for part in header.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        found[name.strip()] = urllib.parse.unquote(value.strip())
    return found


def supabase_call(method, path, body=None, token=None):
    base, key = supabase_settings()
    if not base:
        return 0, {}
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("apikey", key)
    request.add_header("Accept", "application/json")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read()
        status = error.code
    except urllib.error.URLError:
        return 0, {}
    if not raw:
        return status, {}
    try:
        return status, json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return status, {}


def user_from_token_payload(payload):
    user = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user, dict):
        user = payload if isinstance(payload, dict) else {}
    user_id = user.get("id") if isinstance(user, dict) else None
    email = user.get("email") if isinstance(user, dict) else ""
    if not isinstance(user_id, str) or not UUID_RE.match(user_id):
        return None
    if not isinstance(email, str):
        email = ""
    return {"id": user_id, "email": email}


def fetch_profile(access_token, user):
    global PROFILE_WARNED
    status, payload = supabase_call(
        "GET",
        "/rest/v1/profiles?id=eq." + user["id"] + "&select=display_name,rank",
        token=access_token,
    )
    fallback = user["email"].split("@")[0] if user["email"] else "Member"
    if status != 200 or not isinstance(payload, list):
        if not PROFILE_WARNED:
            PROFILE_WARNED = True
            print("Could not read member profiles. Run supabase/schema.sql in the Supabase SQL editor.", file=sys.stderr)
        return {"displayName": fallback[:80], "rank": None}
    if not payload:
        return {"displayName": fallback[:80], "rank": None}
    row = payload[0] if isinstance(payload[0], dict) else {}
    name = row.get("display_name")
    if not isinstance(name, str) or not name.strip():
        name = fallback
    rank = row.get("rank")
    if rank not in RANKS:
        rank = None
    return {"displayName": name.strip()[:80], "rank": rank}


def authorize(cookie_header, headers):
    cookies = parse_cookies(cookie_header)
    access = cookies.get(ACCESS_COOKIE) or ""
    refresh = cookies.get(REFRESH_COOKIE) or ""
    remember = cookies.get(REMEMBER_COOKIE) == "1"
    if not configured() or (not access and not refresh):
        return None, []
    if access:
        status, payload = supabase_call("GET", "/auth/v1/user", token=access)
        if status == 0:
            return None, []
        user = user_from_token_payload(payload) if status == 200 else None
        if user:
            return fetch_profile(access, user), []
    if not refresh:
        return None, []
    status, payload = supabase_call(
        "POST",
        "/auth/v1/token?grant_type=refresh_token",
        {"refresh_token": refresh},
    )
    if status == 0:
        return None, []
    user = user_from_token_payload(payload)
    if status != 200 or not user or "access_token" not in payload or "refresh_token" not in payload:
        return None, auth_cookies("", "", 0, False, headers, clear=True)
    profile = fetch_profile(payload["access_token"], user)
    return profile, auth_cookies(
        payload["access_token"],
        payload["refresh_token"],
        payload.get("expires_in") or 3600,
        remember,
        headers,
    )


def attempt_wait(ip):
    now = time.time()
    with ATTEMPT_LOCK:
        recent = [stamp for stamp in ATTEMPTS.get(ip, []) if now - stamp < ATTEMPT_WINDOW]
        ATTEMPTS[ip] = recent
        if len(recent) >= MAX_ATTEMPTS:
            return int(ATTEMPT_WINDOW - (now - recent[0])) + 1
    return 0


def record_failure(ip):
    with ATTEMPT_LOCK:
        ATTEMPTS.setdefault(ip, []).append(time.time())


def clear_failures(ip):
    with ATTEMPT_LOCK:
        ATTEMPTS.pop(ip, None)


def login_failure_message(payload):
    text = json.dumps(payload).lower() if isinstance(payload, dict) else ""
    if "confirm" in text:
        return "Confirm your email, then sign in."
    return "Invalid email or password."


def same_origin(headers):
    host = headers.get("Host") or ""
    origin = headers.get("Origin")
    if origin:
        return urllib.parse.urlparse(origin).netloc == host
    fetch_site = headers.get("Sec-Fetch-Site") or ""
    return fetch_site in ("same-origin", "none")


def read_body(handler, limit=4096):
    try:
        length = int(handler.headers.get("Content-Length") or "0")
    except ValueError:
        return None
    if length < 0 or length > limit:
        return None
    if length == 0:
        return b""
    return handler.rfile.read(length)


def json_result(status, payload, cookies=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, "application/json; charset=utf-8", body, cookies or []


def handle_login(headers, raw, ip):
    wait = attempt_wait(ip)
    if wait > 0:
        return json_result(429, {"message": "Too many attempts. Try again in " + str(wait) + " seconds."})
    ctype = headers.get("Content-Type") or ""
    if raw is None or "application/json" not in ctype:
        return json_result(400, {"message": "Sign-in was rejected."})
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return json_result(400, {"message": "Sign-in was rejected."})
    if not isinstance(data, dict):
        return json_result(400, {"message": "Sign-in was rejected."})
    email = data.get("email")
    password = data.get("password")
    remember = data.get("remember") is True
    destination = resolve_existing(safe_relative(data.get("next")))
    if not isinstance(email, str) or not isinstance(password, str):
        record_failure(ip)
        return json_result(401, {"message": "Invalid email or password."})
    email = email.strip().lower()
    if not configured():
        return json_result(503, {"message": "Sign-in is unavailable right now."})
    if len(email) < 3 or len(email) > 254 or "@" not in email or len(password) < 1 or len(password) > 72:
        record_failure(ip)
        return json_result(401, {"message": "Invalid email or password."})
    status, payload = supabase_call(
        "POST",
        "/auth/v1/token?grant_type=password",
        {"email": email, "password": password},
    )
    user = user_from_token_payload(payload)
    if status == 0:
        return json_result(503, {"message": "Sign-in is unavailable right now."})
    if status != 200 or not user or "access_token" not in payload or "refresh_token" not in payload:
        record_failure(ip)
        return json_result(401, {"message": login_failure_message(payload)})
    clear_failures(ip)
    cookies = auth_cookies(
        payload["access_token"],
        payload["refresh_token"],
        payload.get("expires_in") or 3600,
        remember,
        headers,
    )
    return json_result(200, {"redirect": destination}, cookies)


def handle_logout(headers):
    cookies = parse_cookies(headers.get("Cookie"))
    access = cookies.get(ACCESS_COOKIE)
    if access and configured():
        supabase_call("POST", "/auth/v1/logout", {}, token=access)
    return json_result(200, {"ok": True}, auth_cookies("", "", 0, False, headers, clear=True))


def handle_me(headers):
    profile, cookies = authorize(headers.get("Cookie"), headers)
    if not profile:
        return json_result(401, {"message": "Sign in."}, cookies)
    return json_result(200, {"displayName": profile["displayName"], "rank": profile["rank"]}, cookies)


def handle_page(path, headers):
    found = static_file(path)
    if found is None:
        return 404, "text/plain; charset=utf-8", b"That page is not on this site.\n", []
    file_path, relative = found
    body = file_path.read_bytes()
    content_type = CONTENT_TYPES[file_path.suffix.lower()]
    cookies = []
    status = 200
    if file_path.suffix.lower() == ".html":
        session, cookies = authorize(headers.get("Cookie"), headers)
        page, status = prepare_html(relative, body.decode("utf-8"), session)
        if page is None:
            return 403, "text/plain; charset=utf-8", b"That page is not available.\n", cookies
        body = page.encode("utf-8")
    return status, content_type, body, cookies


def handle_request(method, path, headers, body, ip):
    try:
        if method == "POST":
            if path not in ("/api/login", "/api/logout"):
                return json_result(404, {"message": "Not found."})
            if not same_origin(headers):
                return json_result(403, {"message": "Sign-in was rejected."})
            if path == "/api/login":
                return handle_login(headers, body, ip)
            return handle_logout(headers)
        if method != "GET":
            return json_result(405, {"message": "Not found."})
        if path == "/api/me":
            return handle_me(headers)
        if path.startswith("/api/") or path == "/protected" or path.startswith("/protected/"):
            return json_result(404, {"message": "Not found."})
        return handle_page(path, headers)
    except Exception:
        traceback.print_exc()
        return json_result(500, {"message": "Something went wrong."})


class Handler(BaseHTTPRequestHandler):
    server_version = "CKAF"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        status, content_type, body, cookies = handle_request(self.command, path, self.headers, b"", self.client_address[0])
        self.send_result(status, content_type, body, cookies)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        raw = read_body(self, 4096)
        status, content_type, body, cookies = handle_request(self.command, path, self.headers, raw, self.client_address[0])
        self.send_result(status, content_type, body, cookies)

    def send_result(self, status, content_type, body, cookies):
        extra = []
        if content_type.startswith("text/html") or content_type.startswith("application/json"):
            extra.append(("Cache-Control", "no-store"))
        for cookie in cookies:
            extra.append(("Set-Cookie", cookie))
        self.send_bytes(status, content_type, body, extra)

    def send_bytes(self, status, content_type, body, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        for name, value in extra or []:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def main():
    load_env_file()
    load_env_and_check_files()
    host = os.environ.get("CKAF_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.environ.get("CKAF_PORT", "8080"))
    except ValueError:
        port = 8080
    server = ThreadingHTTPServer((host, port), Handler)
    shown = "127.0.0.1" if host == "0.0.0.0" else host
    print("CKAF is running at http://%s:%s" % (shown, port), flush=True)
    if configured():
        print("Supabase is configured. Member sign-in uses that project.", flush=True)
    else:
        print("Supabase is not configured. Copy .env.example to .env and add SUPABASE_URL and SUPABASE_ANON_KEY.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
