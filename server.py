# CKAF member site.
# Supabase checks the password. The browser keeps those tokens in HttpOnly cookies.
# A signed session token, readable by the page, carries the name, belt, and instructor flag.
# Member pages are read from protected/ and sent only when the rank is high enough.
# Local: python server.py
# Vercel: proxy.py handles the same requests.

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
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
# Kata opens three belts before the rank that must know it, so a student
# can read the form for the next test and the two forms after that.
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
    "giecho-il-bu.html": 1,
    "giecho-yi-bu.html": 1,
    "giecho-sahm-bu.html": 1,
    "pyong-an-cho-dan.html": 2,
    "pyong-an-yi-dan.html": 3,
    "pyong-an-sahm-dan.html": 4,
    "pyong-an-sa-dan.html": 5,
    "nahanchi-sahm-dan.html": 6,
    "pyong-an-oh-dan.html": 7,
    "empi.html": 8,
    "bassai.html": 9,
    "one-steps.html": 1,
}

# Current belt -> the testing page that lists the next test.
NEXT_TEST_FILE = {
    "white": "Testing/white-belts.html",
    "10th": "Testing/10th-gold.html",
    "9th": "Testing/9th-purple.html",
    "8th": "Testing/8th-orange.html",
    "7th": "Testing/7th-blue.html",
    "6th": "Testing/6th-green.html",
    "5th": "Testing/5th-green.html",
    "4th": "Testing/4th-brown.html",
    "3rd": "Testing/3rd-brown.html",
    "2nd": "Testing/2nd-red.html",
    "1st": "Testing/1st-red.html",
}

PUBLIC_HTML = {
    "index.html",
    "locations.html",
    "verses.html",
    "login.html",
    "register.html",
    "forgot.html",
    "reset.html",
    "suggestions.html",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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
SESSION_COOKIE = "ckaf_session"
REMEMBER_SECONDS = 60 * 60 * 24 * 7
SESSION_SECONDS = 60 * 60 * 12
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
SUGGEST_LOCK = threading.Lock()
SUGGESTIONS_SENT = {}
SUGGEST_LIMIT = 5
SUGGESTION_DIR = ROOT / "suggestions"
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
    if 'data-min-rank="white"' not in low or 'data-min-rank="9th"' in low or 'data-min-rank="6th"' in low or 'class="note"' in low:
        raise SystemExit("One-steps sections would leak to a lower belt. Refusing to start.")
    purple = strip_onesteps(steps, rank_level("9th"))
    if 'data-min-rank="9th"' not in purple or 'data-min-rank="6th"' in purple:
        raise SystemExit("A purple belt would see the wrong one-steps. Refusing to start.")
    blue = strip_onesteps(steps, rank_level("7th"))
    if 'data-min-rank="6th"' in blue or 'class="note"' in blue:
        raise SystemExit("A blue belt would see advanced one-steps. Refusing to start.")
    green = strip_onesteps(steps, rank_level("6th"))
    if 'data-min-rank="6th"' not in green or 'class="note"' not in green:
        raise SystemExit("A green belt would not see advanced one-steps. Refusing to start.")
    high = strip_onesteps(steps, rank_level("black"))
    if 'data-min-rank="6th"' not in high or 'class="note"' not in high:
        raise SystemExit("One-steps sections for a black belt were removed. Refusing to start.")
    account = (ROOT / "protected" / "account.html").read_text(encoding="utf-8")

    def next_test_text(page):
        start = page.find('<section id="next-test">')
        end = page.find("</section>", start)
        if start < 0 or end < 0:
            return ""
        return page[start:end]

    white_page, white_code = prepare_html("account.html", account, {"displayName": "Member", "rank": "white", "admin": False})
    white_test = next_test_text(white_page or "")
    if white_code != 200 or "10th Gold Belt Testing Requirements" not in white_test or "Bassai" in white_test:
        raise SystemExit("Account page would show the wrong belt test. Refusing to start.")
    red_page, red_code = prepare_html("account.html", account, {"displayName": "Member", "rank": "1st", "admin": False})
    red_test = next_test_text(red_page or "")
    if red_code != 200 or "1st Black Belt Testing Requirements" not in red_test or "10th Gold" in red_test:
        raise SystemExit("A red belt account would show the wrong test. Refusing to start.")
    black_page, black_code = prepare_html("account.html", account, {"displayName": "Member", "rank": "black", "admin": False})
    black_test = next_test_text(black_page or "")
    if black_code != 200 or "Bassai" in black_test or "Testing Requirements" in black_test:
        raise SystemExit("A black belt account would show another test. Refusing to start.")
    guest_page, guest_code = prepare_html("account.html", account, None)
    if guest_code != 403 or guest_page is None or "Testing Requirements" in guest_page:
        raise SystemExit("Account tests would be visible without signing in. Refusing to start.")
    if "Change password" not in (white_page or "") or 'id="current-password"' not in (white_page or ""):
        raise SystemExit("A signed-in member would not see the password form. Refusing to start.")
    if guest_page and ("Change password" in guest_page or 'id="current-password"' in guest_page):
        raise SystemExit("The password form would be visible without signing in. Refusing to start.")
    if required_level("forgot.html") != 0 or required_level("reset.html") != 0:
        raise SystemExit("Password reset pages would be hidden. Refusing to start.")
    if required_level("suggestions.html") != 0:
        raise SystemExit("The suggestions page would be hidden. Refusing to start.")
    if static_file("/suggestions/note.txt") is not None:
        raise SystemExit("Suggestion notes would be public. Refusing to start.")
    suggestions = (ROOT / "suggestions.html").read_text(encoding="utf-8")
    if 'id="suggestion"' not in suggestions or "/api/suggestions" not in suggestions:
        raise SystemExit("The suggestions page is missing its form. Refusing to start.")
    check_form_window()


def form_visible(page, code):
    return code == 200 and page is not None and "steps-list" in page and "access-gate" not in page


def form_hidden(page, code):
    return code == 403 and page is not None and "steps-list" not in page and "access-gate" in page


def check_form_window():
    # A belt sees the form required at the next test, plus the two after it.
    white = {"displayName": "Member", "rank": "white", "admin": False}
    gold = {"displayName": "Member", "rank": "10th", "admin": False}
    brown = {"displayName": "Member", "rank": "4th", "admin": False}
    third = {"displayName": "Member", "rank": "3rd", "admin": False}
    samples = (
        ("Kata/giecho-sahm-bu.html", white, True),
        ("Kata/pyong-an-cho-dan.html", white, False),
        ("Kata/pyong-an-cho-dan.html", gold, True),
        ("Kata/pyong-an-yi-dan.html", gold, False),
        ("Kata/bassai.html", brown, False),
        ("Kata/bassai.html", third, True),
        ("Kata/giecho-il-bu.html", None, False),
    )
    for relative, session, opened in samples:
        text = (ROOT / "protected" / relative).read_text(encoding="utf-8")
        page, code = prepare_html(relative, text, session)
        if opened and not form_visible(page, code):
            raise SystemExit("A belt cannot see the forms for the next three tests. Refusing to start.")
        if not opened and not form_hidden(page, code):
            raise SystemExit("A form would be visible more than two tests ahead. Refusing to start.")


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
    if level < rank_level("6th"):
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
    if level < rank_level("6th") and 'class="note"' in stripped:
        return None
    return stripped


def instructor_gate(session, relative_path):
    if session:
        message = "This page is for instructors."
        link = "Switch account"
    else:
        message = "This page is for instructors. Sign in to continue."
        link = "Sign in"
    href = login_href(relative_path)
    return (
        '<div class="access-gate"><h2>Instructors only</h2><p>'
        + html.escape(message)
        + '</p><a class="gate-link" href="'
        + html.escape(href, quote=True)
        + '">'
        + html.escape(link)
        + "</a></div>"
    )


def member_gate(relative_path):
    href = login_href(relative_path)
    return (
        '<div class="access-gate"><h2>Members only</h2><p>Sign in to see your member page.</p>'
        '<a class="gate-link" href="'
        + html.escape(href, quote=True)
        + '">Sign in</a></div>'
    )


def next_test_section(rank):
    if rank == "black":
        return (
            '<section id="next-test">'
            '<h3 class="section-heading">Next test</h3>'
            "<p>You have reached black belt. There is no further test on this site.</p>"
            "</section>"
        )
    relative = NEXT_TEST_FILE.get(rank)
    found = page_file(relative) if relative else None
    if found is None:
        return ""
    text = found.read_text(encoding="utf-8")
    heading_at = text.find("Testing Requirements")
    start = text.rfind("<h3", 0, heading_at) if heading_at >= 0 else -1
    end = text.find("</div>", heading_at) if heading_at >= 0 else -1
    if start < 0 or end < 0:
        return ""
    body = text[start:end].replace('href="../', 'href="')
    return '<section id="next-test">' + body + "</section>"


def prepare_html(relative_path, page, session):
    name = relative_path.rsplit("/", 1)[-1]
    if name == "admin.html":
        if session and session.get("admin"):
            return page, 200
        gated = replace_main_content(page, instructor_gate(session, relative_path))
        if gated is None:
            return None, 403
        return gated, 403
    if name == "account.html":
        if session:
            filled = page.replace('<div id="next-test"></div>', next_test_section(session.get("rank")))
            return filled, 200
        gated = replace_main_content(page, member_gate(relative_path))
        if gated is None:
            return None, 403
        return gated, 403
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


def one_cookie(name, value, max_age, secure, http_only=True):
    parts = [name + "=" + urllib.parse.quote(value, safe=""), "Path=/", "SameSite=Lax"]
    if http_only:
        parts.append("HttpOnly")
    if secure:
        parts.append("Secure")
    if max_age is not None:
        parts.append("Max-Age=" + str(int(max_age)))
    return "; ".join(parts)


def jwt_secret():
    secret = os.environ.get("CKAF_JWT_SECRET", "").strip()
    if len(secret) < 32:
        return b""
    return secret.encode("utf-8")


def b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_session(profile, ttl):
    secret = jwt_secret()
    user_id = profile.get("id") if isinstance(profile, dict) else None
    rank = profile.get("rank") if isinstance(profile, dict) else None
    name = profile.get("displayName") if isinstance(profile, dict) else None
    if not secret or not isinstance(user_id, str) or not UUID_RE.match(user_id):
        return ""
    if rank not in RANKS or not isinstance(name, str) or not name.strip():
        return ""
    now = int(time.time())
    header = b64url_encode(b'{"alg":"HS256","typ":"JWT"}')
    body = {
        "sub": user_id.lower(),
        "name": name.strip()[:80],
        "rank": rank,
        "admin": profile.get("admin") is True,
        "iat": now,
        "exp": now + int(ttl),
    }
    payload = b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signing = header + "." + payload
    signature = b64url_encode(hmac.new(secret, signing.encode("ascii"), hashlib.sha256).digest())
    return signing + "." + signature


def read_session_token(token):
    secret = jwt_secret()
    if not secret or not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        return None
    try:
        expected = hmac.new(secret, (parts[0] + "." + parts[1]).encode("ascii"), hashlib.sha256).digest()
        actual = b64url_decode(parts[2])
        payload = json.loads(b64url_decode(parts[1]).decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return None
    if not hmac.compare_digest(expected, actual) or not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    user_id = payload.get("sub")
    name = payload.get("name")
    rank = payload.get("rank")
    if isinstance(exp, float) and exp.is_integer():
        exp = int(exp)
    if not isinstance(exp, int) or exp < time.time():
        return None
    if not isinstance(user_id, str) or not UUID_RE.match(user_id):
        return None
    if not isinstance(name, str) or not name.strip() or rank not in RANKS:
        return None
    issued = payload.get("iat")
    if isinstance(issued, float) and issued.is_integer():
        issued = int(issued)
    return {
        "id": user_id.lower(),
        "displayName": name.strip()[:80],
        "rank": rank,
        "admin": payload.get("admin") is True,
        "iat": issued if isinstance(issued, int) else 0,
    }


def jwt_payload_unverified(token):
    if not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(b64url_decode(parts[1]).decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def access_expired(token):
    payload = jwt_payload_unverified(token)
    exp = payload.get("exp") if isinstance(payload, dict) else None
    if isinstance(exp, float) and exp.is_integer():
        exp = int(exp)
    if not isinstance(exp, int):
        return True
    return exp < time.time() + 30


def auth_cookies(access, refresh, expires_in, remember, headers, clear=False, profile=None):
    secure = cookies_are_secure(headers)
    refresh_age = 0 if clear else (REMEMBER_SECONDS if remember else None)
    access_age = 0 if clear else (int(expires_in or 3600) if remember else None)
    remember_age = 0 if clear else refresh_age
    ttl = REMEMBER_SECONDS if remember else SESSION_SECONDS
    session = "" if clear or not profile else sign_session(profile, ttl)
    session_age = 0 if clear or not session else (ttl if remember else None)
    return [
        one_cookie(ACCESS_COOKIE, "" if clear else access, access_age, secure),
        one_cookie(REFRESH_COOKIE, "" if clear else refresh, refresh_age, secure),
        one_cookie(REMEMBER_COOKIE, "" if clear else ("1" if remember else "0"), remember_age, secure),
        one_cookie(SESSION_COOKIE, session, session_age, secure, http_only=False),
    ]


def with_id(profile, user_id):
    profile = dict(profile)
    profile["id"] = user_id
    return profile


def session_cookies(headers, access, refresh, expires_in, remember, profile):
    return auth_cookies(access, refresh, expires_in, remember, headers, profile=profile)


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


def supabase_call(method, path, body=None, token=None, extra_headers=None):
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
    for name, value in (extra_headers or {}).items():
        request.add_header(name, value)
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


def empty_profile(user):
    fallback = user["email"].split("@")[0] if user["email"] else "Member"
    return {"displayName": fallback[:80], "rank": None, "admin": False}


def flag_true(value):
    return value is True or (isinstance(value, str) and value.lower() in ("true", "t"))


def profile_from_row(row, user):
    profile = empty_profile(user)
    name = row.get("display_name") if isinstance(row, dict) else None
    if isinstance(name, str) and name.strip():
        profile["displayName"] = name.strip()[:80]
    rank = row.get("rank") if isinstance(row, dict) else None
    profile["rank"] = rank if rank in RANKS else None
    profile["admin"] = isinstance(row, dict) and flag_true(row.get("is_admin"))
    return profile


def read_profile(access_token, user):
    global PROFILE_WARNED
    for columns in ("display_name,rank,is_admin", "display_name,rank"):
        status, payload = supabase_call(
            "GET",
            "/rest/v1/profiles?id=eq." + user["id"] + "&select=" + columns,
            token=access_token,
        )
        if status == 200 and isinstance(payload, list):
            if not payload or not isinstance(payload[0], dict):
                return empty_profile(user)
            return profile_from_row(payload[0], user)
    if not PROFILE_WARNED:
        PROFILE_WARNED = True
        print("Could not read member profiles. Run supabase/schema.sql in the Supabase SQL editor.", file=sys.stderr)
    return empty_profile(user)


def fetch_profile(access_token, user):
    profile = read_profile(access_token, user)
    if profile.get("admin"):
        return profile
    status, payload = supabase_call("POST", "/rest/v1/rpc/claim_instructor", {}, token=access_token)
    if status == 200 and payload is True:
        claimed = read_profile(access_token, user)
        claimed["admin"] = True
        if claimed.get("displayName"):
            return claimed
        profile["admin"] = True
    return profile


def authorize(cookie_header, headers, fresh=False):
    cookies = parse_cookies(cookie_header)
    access = cookies.get(ACCESS_COOKIE) or ""
    refresh = cookies.get(REFRESH_COOKIE) or ""
    remember = cookies.get(REMEMBER_COOKIE) == "1"
    if not configured() or (not access and not refresh):
        return None, [], ""
    session = read_session_token(cookies.get(SESSION_COOKIE))
    if session and access and not fresh and not access_expired(access):
        return session, [], access
    if access and not access_expired(access):
        status, payload = supabase_call("GET", "/auth/v1/user", token=access)
        if status == 0:
            return None, [], ""
        user = user_from_token_payload(payload) if status == 200 else None
        if user:
            profile = with_id(fetch_profile(access, user), user["id"])
            return profile, session_cookies(headers, access, refresh, 3600, remember, profile), access
    if not refresh:
        return None, [], ""
    status, payload = supabase_call(
        "POST",
        "/auth/v1/token?grant_type=refresh_token",
        {"refresh_token": refresh},
    )
    if status == 0:
        return None, [], ""
    user = user_from_token_payload(payload)
    if status != 200 or not user or "access_token" not in payload or "refresh_token" not in payload:
        return None, auth_cookies("", "", 0, False, headers, clear=True), ""
    access = payload["access_token"]
    profile = with_id(fetch_profile(access, user), user["id"])
    return profile, session_cookies(
        headers,
        access,
        payload["refresh_token"],
        payload.get("expires_in") or 3600,
        remember,
        profile,
    ), access


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


def suggestion_wait(ip, record):
    now = time.time()
    with SUGGEST_LOCK:
        recent = [stamp for stamp in SUGGESTIONS_SENT.get(ip, []) if now - stamp < ATTEMPT_WINDOW]
        if len(recent) >= SUGGEST_LIMIT:
            SUGGESTIONS_SENT[ip] = recent
            return int(ATTEMPT_WINDOW - (now - recent[0])) + 1
        if record:
            recent.append(now)
        SUGGESTIONS_SENT[ip] = recent
    return 0


def login_failure_message(payload):
    text = json.dumps(payload).lower() if isinstance(payload, dict) else ""
    if "confirm" in text:
        return "This account is not ready to sign in. Ask an instructor."
    return "Invalid email or password."


def site_origin(headers):
    forwarded = headers.get("X-Forwarded-Host") or headers.get("Host") or ""
    host = forwarded.split(",")[0].strip()
    if not host or any(ch in host for ch in " /@\\"):
        return ""
    proto = (headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower()
    if proto not in ("http", "https"):
        proto = "https" if cookies_are_secure(headers) else "http"
    return proto + "://" + host


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
    access = payload["access_token"]
    profile = with_id(fetch_profile(access, user), user["id"])
    cookies = session_cookies(
        headers,
        access,
        payload["refresh_token"],
        payload.get("expires_in") or 3600,
        remember,
        profile,
    )
    return json_result(200, {"redirect": destination}, cookies)


def handle_logout(headers):
    cookies = parse_cookies(headers.get("Cookie"))
    access = cookies.get(ACCESS_COOKIE)
    if access and configured():
        supabase_call("POST", "/auth/v1/logout", {}, token=access)
    return json_result(200, {"ok": True}, auth_cookies("", "", 0, False, headers, clear=True))


def handle_me(headers):
    profile, cookies, _token = authorize(headers.get("Cookie"), headers, fresh=True)
    if not profile:
        return json_result(401, {"message": "Sign in."}, cookies)
    return json_result(200, {
        "displayName": profile["displayName"],
        "rank": profile["rank"],
        "isAdmin": profile.get("admin") is True,
    }, cookies)


def clean_name(value):
    if not isinstance(value, str):
        return ""
    cleaned = "".join(ch for ch in value if ch >= " " and ch != "\x7f")
    return " ".join(cleaned.split())[:80]


def read_json(raw, headers):
    ctype = headers.get("Content-Type") or ""
    if raw is None or "application/json" not in ctype:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def signup_message(status, payload):
    text = ""
    if isinstance(payload, dict):
        text = " ".join(
            str(payload.get(key) or "")
            for key in ("msg", "message", "error_description", "error", "error_code")
        ).lower()
    if "already" in text or "registered" in text or "exists" in text:
        return "That email is already registered. Sign in instead."
    if "password" in text:
        return "Use a password of at least 8 characters."
    if status == 0:
        return "Registration is unavailable right now."
    return "Registration was rejected. Check the name, email, and password."


def handle_register(headers, raw, ip):
    wait = attempt_wait(ip)
    if wait > 0:
        return json_result(429, {"message": "Too many attempts. Try again in " + str(wait) + " seconds."})
    data = read_json(raw, headers)
    if data is None:
        return json_result(400, {"message": "Registration was rejected."})
    name = clean_name(data.get("name"))
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        record_failure(ip)
        return json_result(400, {"message": "Enter your name, email, and a password of at least 8 characters."})
    email = email.strip().lower()
    if not name or not EMAIL_RE.match(email) or len(email) > 254 or len(password) < 8 or len(password) > 72:
        record_failure(ip)
        return json_result(400, {"message": "Enter your name, email, and a password of at least 8 characters."})
    if not configured():
        return json_result(503, {"message": "Registration is unavailable right now."})
    record_failure(ip)
    status, payload = supabase_call(
        "POST",
        "/auth/v1/signup",
        {"email": email, "password": password, "data": {"display_name": name}},
    )
    if status == 0:
        return json_result(503, {"message": "Registration is unavailable right now."})
    if not isinstance(payload, dict):
        return json_result(400, {"message": signup_message(status, payload)})
    user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
    identities = user.get("identities") if isinstance(user, dict) else None
    if isinstance(identities, list) and not identities:
        return json_result(400, {"message": "That email is already registered. Sign in instead."})
    created = status == 200 and isinstance(user, dict) and isinstance(user.get("id"), str) and user.get("id")
    if created:
        clear_failures(ip)
        return json_result(200, {"redirect": "login.html"})
    return json_result(400, {"message": signup_message(status, payload)})


def recovery_token(value):
    if not isinstance(value, str) or value.count(".") != 2 or len(value) > 8192:
        return ""
    parts = value.split(".")
    if any(not part or len(part) > 4096 for part in parts):
        return ""
    payload = jwt_payload_unverified(value)
    methods = []
    amr = payload.get("amr") if isinstance(payload, dict) else None
    if isinstance(amr, list):
        for entry in amr:
            method = entry.get("method") if isinstance(entry, dict) else entry
            if isinstance(method, str):
                methods.append(method)
    if "otp" not in methods and "recovery" not in methods:
        return ""
    return value


def forgot_message():
    return "If that email belongs to a member, a reset link is on its way."


def handle_forgot(headers, raw, ip):
    wait = attempt_wait(ip)
    if wait > 0:
        return json_result(429, {"message": "Too many attempts. Try again in " + str(wait) + " seconds."})
    data = read_json(raw, headers)
    if data is None:
        return json_result(400, {"message": "Enter the email for your member account."})
    email = data.get("email")
    if not isinstance(email, str):
        return json_result(400, {"message": "Enter the email for your member account."})
    email = email.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        return json_result(400, {"message": "Enter the email for your member account."})
    if not configured():
        return json_result(503, {"message": "Password reset is unavailable right now."})
    origin = site_origin(headers)
    if not origin:
        return json_result(503, {"message": "Password reset is unavailable right now."})
    record_failure(ip)
    status, payload = supabase_call(
        "POST",
        "/auth/v1/recover?redirect_to=" + urllib.parse.quote(origin + "/reset.html", safe=""),
        {"email": email},
    )
    if status == 0:
        return json_result(503, {"message": "Password reset is unavailable right now."})
    if status in (200, 201):
        return json_result(200, {"ok": True, "message": forgot_message()})
    text = json.dumps(payload).lower() if isinstance(payload, dict) else ""
    if "not found" in text or "user" in text:
        return json_result(200, {"ok": True, "message": forgot_message()})
    return json_result(503, {"message": "Password reset is unavailable right now."})


def handle_reset(headers, raw, ip):
    wait = attempt_wait(ip)
    if wait > 0:
        return json_result(429, {"message": "Too many attempts. Try again in " + str(wait) + " seconds."})
    data = read_json(raw, headers)
    if data is None:
        return json_result(400, {"message": "Choose a new password."})
    token = recovery_token(data.get("token"))
    password = data.get("password")
    confirm = data.get("confirm")
    if not token:
        return json_result(400, {"message": "This reset link has expired. Request a new one."})
    if not isinstance(password, str) or not isinstance(confirm, str):
        return json_result(400, {"message": "Choose a new password."})
    if password != confirm:
        return json_result(400, {"message": "Those passwords do not match."})
    if len(password) < 8 or len(password) > 72:
        return json_result(400, {"message": "Use a password of at least 8 characters."})
    if not configured():
        return json_result(503, {"message": "Password reset is unavailable right now."})
    record_failure(ip)
    status, payload = supabase_call(
        "PUT",
        "/auth/v1/user",
        {"password": password},
        token=token,
    )
    if status == 200:
        clear_failures(ip)
        return json_result(200, {"ok": True, "redirect": "login.html"})
    if status in (401, 403):
        return json_result(400, {"message": "This reset link has expired. Request a new one."})
    detail = json.dumps(payload).lower() if isinstance(payload, dict) else ""
    if "password" in detail:
        return json_result(400, {"message": "Use a password of at least 8 characters."})
    return json_result(503, {"message": "Password reset is unavailable right now."})


def require_admin(headers):
    profile, cookies, token = authorize(headers.get("Cookie"), headers)
    if not profile or not profile.get("admin") or not token:
        return None, cookies, ""
    return profile, cookies, token


def handle_admin_members(headers):
    _profile, cookies, token = require_admin(headers)
    if not token:
        return json_result(403, {"message": "Instructors only."}, cookies)
    status, payload = supabase_call(
        "GET",
        "/rest/v1/profiles?select=id,display_name,email,rank,is_admin&order=display_name.asc",
        token=token,
    )
    if status != 200 or not isinstance(payload, list):
        return json_result(503, {"message": "The member list is unavailable."}, cookies)
    members = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        user_id = row.get("id")
        rank = row.get("rank")
        if not isinstance(user_id, str) or not UUID_RE.match(user_id) or rank not in RANKS:
            continue
        name = row.get("display_name") if isinstance(row.get("display_name"), str) else "Member"
        email = row.get("email") if isinstance(row.get("email"), str) else ""
        members.append({
            "id": user_id.lower(),
            "displayName": name.strip()[:80] or "Member",
            "email": email[:254],
            "rank": rank,
            "admin": flag_true(row.get("is_admin")),
        })
    return json_result(200, {"members": members}, cookies)


def handle_admin_rank(headers, raw):
    _profile, cookies, token = require_admin(headers)
    if not token:
        return json_result(403, {"message": "Instructors only."}, cookies)
    data = read_json(raw, headers)
    if data is None:
        return json_result(400, {"message": "Choose a member and a belt."}, cookies)
    user_id = data.get("id")
    rank = data.get("rank")
    name = clean_name(data.get("name")) if "name" in data else ""
    instructor = data.get("admin") if isinstance(data, dict) else None
    if not isinstance(user_id, str) or not UUID_RE.match(user_id) or rank not in RANKS or not name:
        return json_result(400, {"message": "Enter the member's name and choose a belt."}, cookies)
    if not isinstance(instructor, bool):
        return json_result(400, {"message": "Choose whether this member is an instructor."}, cookies)
    path = "/rest/v1/profiles?id=eq." + user_id.lower()
    prefer = {"Prefer": "return=representation"}

    def row_saved(payload, expect_admin):
        if not (isinstance(payload, list) and payload and isinstance(payload[0], dict)):
            return False
        row = payload[0]
        if row.get("rank") != rank or row.get("display_name") != name:
            return False
        if expect_admin is None:
            return True
        return flag_true(row.get("is_admin")) is expect_admin

    def cookies_for_self(include_admin):
        if not (_profile.get("id") and user_id.lower() == _profile["id"]):
            return cookies
        stored = parse_cookies(headers.get("Cookie"))
        _profile["displayName"] = name
        _profile["rank"] = rank
        if include_admin:
            _profile["admin"] = instructor
        return session_cookies(
            headers,
            token,
            stored.get(REFRESH_COOKIE) or "",
            3600,
            stored.get(REMEMBER_COOKIE) == "1",
            _profile,
        )

    status, payload = supabase_call(
        "PATCH",
        path,
        {"rank": rank, "display_name": name, "is_admin": instructor},
        token=token,
        extra_headers=prefer,
    )
    if status == 200 and row_saved(payload, instructor):
        return json_result(
            200,
            {"ok": True, "rank": rank, "displayName": name, "admin": instructor},
            cookies_for_self(True),
        )
    detail = payload.get("message") if isinstance(payload, dict) else ""
    denied = isinstance(detail, str) and ("is_admin" in detail or "permission" in detail.lower())
    if denied:
        status, payload = supabase_call(
            "PATCH",
            path,
            {"rank": rank, "display_name": name},
            token=token,
            extra_headers=prefer,
        )
        if status == 200 and row_saved(payload, None):
            return json_result(
                403,
                {"message": "The name and belt were saved. Instructor status was not. Run the latest supabase/schema.sql in the Supabase SQL editor."},
                cookies_for_self(False),
            )
    return json_result(403, {"message": "That member was not saved."}, cookies)


def handle_account_name(headers, raw):
    profile, cookies, token = authorize(headers.get("Cookie"), headers)
    if not profile or not token:
        return json_result(401, {"message": "Sign in."}, cookies)
    data = read_json(raw, headers)
    if data is None:
        return json_result(400, {"message": "Enter your name."}, cookies)
    name = clean_name(data.get("name"))
    if not name:
        return json_result(400, {"message": "Enter your name."}, cookies)
    status, payload = supabase_call(
        "POST",
        "/rest/v1/rpc/set_my_name",
        {"new_name": name},
        token=token,
    )
    saved = payload.strip() if isinstance(payload, str) else ""
    if status != 200 or saved != name:
        return json_result(403, {"message": "That name was not saved."}, cookies)
    profile["displayName"] = name
    stored = parse_cookies(headers.get("Cookie"))
    cookies = session_cookies(
        headers,
        token,
        stored.get(REFRESH_COOKIE) or "",
        3600,
        stored.get(REMEMBER_COOKIE) == "1",
        profile,
    )
    return json_result(200, {"ok": True, "displayName": name}, cookies)


def account_email(token):
    status, payload = supabase_call("GET", "/auth/v1/user", token=token)
    user = payload.get("user") if isinstance(payload, dict) and isinstance(payload.get("user"), dict) else payload
    email = user.get("email") if isinstance(user, dict) else ""
    if status != 200 or not isinstance(email, str):
        return ""
    return email.strip().lower()


def handle_account_password(headers, raw, ip):
    wait = attempt_wait(ip)
    if wait > 0:
        return json_result(429, {"message": "Too many attempts. Try again in " + str(wait) + " seconds."})
    profile, cookies, token = authorize(headers.get("Cookie"), headers)
    if not profile or not token:
        return json_result(401, {"message": "Sign in."}, cookies)
    data = read_json(raw, headers)
    if data is None:
        return json_result(400, {"message": "Enter your current password and a new password."}, cookies)
    current = data.get("current")
    password = data.get("password")
    confirm = data.get("confirm")
    if not isinstance(current, str) or not isinstance(password, str) or not isinstance(confirm, str):
        return json_result(400, {"message": "Enter your current password and a new password."}, cookies)
    if password != confirm:
        return json_result(400, {"message": "Those passwords do not match."}, cookies)
    if len(password) < 8 or len(password) > 72 or len(current) < 1 or len(current) > 72:
        return json_result(400, {"message": "Use a password of at least 8 characters."}, cookies)
    if current == password:
        return json_result(400, {"message": "Choose a different password."}, cookies)
    email = account_email(token)
    if not email:
        return json_result(503, {"message": "Password changes are unavailable right now."}, cookies)
    status, payload = supabase_call(
        "POST",
        "/auth/v1/token?grant_type=password",
        {"email": email, "password": current},
    )
    if status == 0:
        return json_result(503, {"message": "Password changes are unavailable right now."}, cookies)
    fresh = payload.get("access_token") if isinstance(payload, dict) else ""
    fresh_refresh = payload.get("refresh_token") if isinstance(payload, dict) else ""
    checked = user_from_token_payload(payload)
    if status != 200 or not isinstance(fresh, str) or not fresh:
        record_failure(ip)
        return json_result(400, {"message": "That current password is not right."}, cookies)
    if checked and isinstance(fresh_refresh, str) and fresh_refresh:
        stored = parse_cookies(headers.get("Cookie"))
        cookies = session_cookies(
            headers,
            fresh,
            fresh_refresh,
            payload.get("expires_in") or 3600,
            stored.get(REMEMBER_COOKIE) == "1",
            with_id(fetch_profile(fresh, checked), checked["id"]),
        )
    status, updated = supabase_call(
        "PUT",
        "/auth/v1/user",
        {"password": password},
        token=fresh,
    )
    if status != 200:
        detail = ""
        if isinstance(updated, dict):
            detail = " ".join(
                str(updated.get(key) or "")
                for key in ("msg", "message", "error_description", "error")
            ).lower()
        if "password" in detail:
            return json_result(400, {"message": "Use a password of at least 8 characters."}, cookies)
        return json_result(403, {"message": "That password was not changed."}, cookies)
    status, signed_in = supabase_call(
        "POST",
        "/auth/v1/token?grant_type=password",
        {"email": email, "password": password},
    )
    user = user_from_token_payload(signed_in)
    access = signed_in.get("access_token") if isinstance(signed_in, dict) else ""
    refresh = signed_in.get("refresh_token") if isinstance(signed_in, dict) else ""
    if status != 200 or not user or not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh:
        clear_failures(ip)
        return json_result(200, {"ok": True, "redirect": "login.html"}, auth_cookies("", "", 0, False, headers, clear=True))
    clear_failures(ip)
    member = with_id(fetch_profile(access, user), user["id"])
    stored = parse_cookies(headers.get("Cookie"))
    cookies = session_cookies(
        headers,
        access,
        refresh,
        signed_in.get("expires_in") or 3600,
        stored.get(REMEMBER_COOKIE) == "1",
        member,
    )
    return json_result(200, {"ok": True}, cookies)


def clean_message(value):
    if not isinstance(value, str):
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    kept = []
    for ch in value:
        if ch in "\n\t" or (" " <= ch and ch != "\x7f"):
            kept.append(ch)
    text = "".join(kept).strip()
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text[:2000]


def save_suggestion_file(name, message):
    folder = SUGGESTION_DIR
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    if not inside_root(folder):
        return False
    filename = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(4) + ".txt"
    path = folder / filename
    if path.suffix != ".txt" or not inside_root(path):
        return False
    sent = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    body = "Name: %s\nSent: %s UTC\n\n%s\n" % (name or "A visitor", sent, message)
    try:
        path.write_text(body, encoding="utf-8")
    except OSError:
        return False
    return True


def store_suggestion(name, message, token):
    saved_file = save_suggestion_file(name, message)
    if not configured():
        return saved_file
    status, _payload = supabase_call(
        "POST",
        "/rest/v1/suggestions",
        {"author_name": name, "message": message},
        token=token or None,
        extra_headers={"Prefer": "return=minimal"},
    )
    return status in (200, 201, 204)


def suggestion_item(row):
    if not isinstance(row, dict):
        return None
    message = row.get("message") if isinstance(row.get("message"), str) else ""
    message = message.strip()[:2000]
    if not message:
        return None
    name = row.get("author_name") if isinstance(row.get("author_name"), str) else ""
    created = row.get("created_at") if isinstance(row.get("created_at"), str) else ""
    item_id = row.get("id") if isinstance(row.get("id"), str) else ""
    return {
        "id": item_id,
        "createdAt": created,
        "name": name.strip()[:80] or "A visitor",
        "message": message,
    }


def handle_suggestion(headers, raw, ip):
    wait = suggestion_wait(ip, False)
    if wait > 0:
        return json_result(429, {"message": "Too many suggestions. Try again in " + str(wait) + " seconds."})
    data = read_json(raw, headers)
    if data is None:
        return json_result(400, {"message": "That suggestion was not saved."})
    decoy = data.get("company")
    if isinstance(decoy, str) and decoy.strip():
        suggestion_wait(ip, True)
        return json_result(200, {"ok": True, "message": "Thanks. An instructor can read that suggestion."})
    name = clean_name(data.get("name"))
    message = clean_message(data.get("message"))
    if not message:
        return json_result(400, {"message": "Write a suggestion first."})
    _session, cookies, token = authorize(headers.get("Cookie"), headers)
    suggestion_wait(ip, True)
    if store_suggestion(name, message, token):
        return json_result(200, {"ok": True, "message": "Thanks. An instructor can read that suggestion."}, cookies)
    return json_result(503, {"message": "Suggestions are unavailable right now."}, cookies)


def handle_admin_suggestions(headers):
    _profile, cookies, token = require_admin(headers)
    if not token:
        return json_result(403, {"message": "Instructors only."}, cookies)
    status, payload = supabase_call(
        "GET",
        "/rest/v1/suggestions?select=id,created_at,author_name,message&order=created_at.desc&limit=200",
        token=token,
    )
    if status != 200 or not isinstance(payload, list):
        return json_result(503, {"message": "Suggestions are unavailable right now."}, cookies)
    notes = []
    for row in payload:
        item = suggestion_item(row)
        if item:
            notes.append(item)
    return json_result(200, {"suggestions": notes}, cookies)


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
        session, cookies, _token = authorize(headers.get("Cookie"), headers)
        page, status = prepare_html(relative, body.decode("utf-8"), session)
        if page is None:
            return 403, "text/plain; charset=utf-8", b"That page is not available.\n", cookies
        body = page.encode("utf-8")
    return status, content_type, body, cookies


def handle_request(method, path, headers, body, ip):
    try:
        if method == "POST":
            if path not in (
                "/api/login",
                "/api/logout",
                "/api/register",
                "/api/forgot",
                "/api/reset",
                "/api/admin/rank",
                "/api/account/name",
                "/api/account/password",
                "/api/suggestions",
            ):
                return json_result(404, {"message": "Not found."})
            if not same_origin(headers):
                return json_result(403, {"message": "That request was rejected."})
            if path == "/api/login":
                return handle_login(headers, body, ip)
            if path == "/api/register":
                return handle_register(headers, body, ip)
            if path == "/api/forgot":
                return handle_forgot(headers, body, ip)
            if path == "/api/reset":
                return handle_reset(headers, body, ip)
            if path == "/api/admin/rank":
                return handle_admin_rank(headers, body)
            if path == "/api/account/name":
                return handle_account_name(headers, body)
            if path == "/api/account/password":
                return handle_account_password(headers, body, ip)
            if path == "/api/suggestions":
                return handle_suggestion(headers, body, ip)
            return handle_logout(headers)
        if method != "GET":
            return json_result(405, {"message": "Not found."})
        if path == "/api/me":
            return handle_me(headers)
        if path == "/api/admin/members":
            return handle_admin_members(headers)
        if path == "/api/admin/suggestions":
            return handle_admin_suggestions(headers)
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
        raw = read_body(self, 16384)
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
