# Vercel runs this before member pages are sent. It reads the same rules as server.py.

from urllib.parse import urlparse

from vercel.proxy import PlainTextResponse, Proxy, Request, Response

import server

server.load_env_file()
server.load_env_and_check_files()

proxy = Proxy()


def as_response(status, content_type, body, cookies):
    media_type = content_type.split(";", 1)[0]
    response = Response(body, status_code=status, media_type=media_type)
    for cookie in cookies:
        response.headers.append("set-cookie", cookie)
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["referrer-policy"] = "same-origin"
    response.headers["x-frame-options"] = "DENY"
    if media_type in ("text/html", "application/json"):
        response.headers["cache-control"] = "no-store"
    return response


async def dispatch(request: Request) -> Response:
    parsed = urlparse(str(request.url))
    if parsed.path == "/protected" or parsed.path.startswith("/protected/"):
        return PlainTextResponse("That page is not on this site.\n", status_code=404)
    body = await request.body()
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = forwarded.split(",")[0].strip() or "0.0.0.0"
    status, content_type, payload, cookies = server.handle_request(
        request.method,
        parsed.path,
        request.headers,
        body,
        ip,
    )
    return as_response(status, content_type, payload, cookies)


@proxy.route("/api/{path:path}", methods=["GET", "POST"])
async def api(request: Request) -> Response:
    return await dispatch(request)


@proxy.route("/protected/{path:path}")
async def hidden(request: Request) -> Response:
    return PlainTextResponse("That page is not on this site.\n", status_code=404)


@proxy.route("/one-steps.html")
async def one_steps(request: Request) -> Response:
    return await dispatch(request)


@proxy.route("/Kata/{path:path}")
async def kata(request: Request) -> Response:
    return await dispatch(request)


@proxy.route("/Testing/{path:path}")
async def testing(request: Request) -> Response:
    return await dispatch(request)
