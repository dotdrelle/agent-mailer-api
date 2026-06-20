#!/usr/bin/env python3
"""MailerSend MCP Server — Streamable HTTP transport for container deployment."""

import asyncio
import contextlib
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from typing import Any

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send
import uvicorn


app = Server("agent-mailer-api")

_AGENT_VERSION = "0.6.8"
_MCP_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
_MAILERSEND_API_KEY = os.environ.get("MAILERSEND_API_KEY", "")
_MAILERSEND_FROM_EMAIL = os.environ.get("MAILERSEND_FROM_EMAIL", "no-reply@example.com")
_MAILERSEND_FROM_NAME = os.environ.get("MAILERSEND_FROM_NAME", "Mailer Agent")
_MAILERSEND_API_URL = os.environ.get("MAILERSEND_API_URL", "https://api.mailersend.com/v1/email")
_MAILERSEND_USER_AGENT = os.environ.get("MAILERSEND_USER_AGENT", "curl/8.7.1")
_MAILERSEND_VERIFY_SSL = os.environ.get("MAILERSEND_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
_REQUIRE_CONFIRMATION = os.environ.get("MAILER_REQUIRE_CONFIRMATION", "true").lower() not in {"0", "false", "no"}
_DEFAULT_DRY_RUN = os.environ.get("MAILER_DRY_RUN", "false").lower() in {"1", "true", "yes"}

if not _MCP_TOKEN:
    print("[mailer-mcp] Warning: MCP_AUTH_TOKEN is not configured; the endpoint accepts unauthenticated clients.")
if not _MAILERSEND_API_KEY:
    print("[mailer-mcp] Warning: MAILERSEND_API_KEY is not configured; send calls will fail unless dryRun=true.")
if not _MAILERSEND_VERIFY_SSL:
    print("[mailer-mcp] Warning: MAILERSEND_VERIFY_SSL is disabled; MailerSend TLS certificates will not be verified.")


class _BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "GET" and _wants_html(request):
            return await call_next(request)
        if _MCP_TOKEN:
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {_MCP_TOKEN}":
                return PlainTextResponse("Unauthorized", status_code=401)
        return await call_next(request)


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _json_text(payload: dict[str, Any]) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


def _render_landing_page(endpoint_url: str, scheme: str) -> str:
    auth_status = (
        "Bearer token enabled"
        if _MCP_TOKEN
        else "Warning: MCP_AUTH_TOKEN is not configured; the endpoint accepts unauthenticated clients."
    )
    api_status = "configured" if _MAILERSEND_API_KEY else "missing MAILERSEND_API_KEY"
    confirm = "required" if _REQUIRE_CONFIRMATION else "not required"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>agent-mailer-api MCP connector</title>
  <style>
    :root {{ color-scheme: light dark; --bg:#f8fafc; --panel:#fff; --text:#111827; --muted:#64748b; --line:#d8dee8; --accent:#2563eb; --code:#eef2ff; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f172a; --panel:#111827; --text:#f8fafc; --muted:#94a3b8; --line:#253044; --accent:#60a5fa; --code:#1e293b; }} }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; min-height:100vh; background:var(--bg); color:var(--text); font:15px/1.55 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(920px,calc(100% - 32px)); margin:0 auto; padding:56px 0; }}
    .eyebrow {{ color:var(--accent); font-weight:700; letter-spacing:.04em; text-transform:uppercase; font-size:12px; }}
    h1 {{ margin:8px 0 10px; font-size:clamp(32px,6vw,52px); line-height:1.05; letter-spacing:0; }}
    h2 {{ margin:0 0 16px; font-size:20px; letter-spacing:0; }}
    .lead {{ margin:0 0 28px; color:var(--muted); max-width:720px; font-size:17px; }}
    .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:22px; margin:18px 0; }}
    dl {{ display:grid; grid-template-columns:170px 1fr; gap:10px 18px; margin:0; }}
    dt {{ color:var(--muted); }}
    dd {{ margin:0; min-width:0; overflow-wrap:anywhere; }}
    code {{ background:var(--code); border:1px solid var(--line); border-radius:6px; padding:2px 6px; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:13px; }}
    ul {{ list-style:none; margin:0; padding:0; display:grid; gap:10px; }}
    li {{ display:grid; grid-template-columns:minmax(170px,240px) 1fr; gap:14px; align-items:start; padding:12px 0; border-top:1px solid var(--line); }}
    li:first-child {{ border-top:0; padding-top:0; }}
    li span {{ color:var(--muted); }}
    @media (max-width:640px) {{ dl,li {{ grid-template-columns:1fr; }} main {{ padding:32px 0; }} }}
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">MCP Streamable HTTP</div>
    <h1>agent-mailer-api MCP connector</h1>
    <p class="lead">Send-only MailerSend connector for AI agents. Secrets stay in the container environment.</p>
    <section class="panel">
      <dl>
        <dt>Status</dt><dd>Ready</dd>
        <dt>Version</dt><dd><code>{_escape_html(_AGENT_VERSION)}</code></dd>
        <dt>Endpoint</dt><dd><code>{_escape_html(endpoint_url)}</code></dd>
        <dt>Transport</dt><dd>MCP Streamable HTTP over {_escape_html(scheme.upper())}</dd>
        <dt>Authentication</dt><dd>{_escape_html(auth_status)}</dd>
        <dt>MailerSend</dt><dd>{_escape_html(api_status)}</dd>
        <dt>From</dt><dd><code>{_escape_html(_MAILERSEND_FROM_EMAIL)}</code></dd>
        <dt>Confirmation</dt><dd>{_escape_html(confirm)}</dd>
      </dl>
    </section>
    <section class="panel">
      <h2>Available tools</h2>
      <ul>
        <li><code>mailer_status</code><span>Check MailerSend connector configuration.</span></li>
        <li><code>mailer_send_email</code><span>Send one email through MailerSend. Use dryRun=true to preview without sending.</span></li>
      </ul>
    </section>
  </main>
</body>
</html>"""


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="mailer_status",
            description="Check agent-mailer-api MailerSend configuration and readiness. Does not expose secrets.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        Tool(
            name="mailer_send_email",
            description=(
                "Send an email through MailerSend. Use only after the user explicitly asks to send an email "
                "and the recipient, subject, and body are known. If confirmation is required, set confirmed=true "
                "only when the user has clearly approved the send. Use dryRun=true to preview without sending."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address."},
                    "subject": {"type": "string", "description": "Email subject."},
                    "text": {"type": "string", "description": "Plain-text body."},
                    "html": {"type": "string", "description": "HTML body."},
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional CC recipient email addresses.",
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional BCC recipient email addresses.",
                    },
                    "replyTo": {"type": "string", "description": "Optional reply-to email address."},
                    "dryRun": {"type": "boolean", "description": "Preview payload without sending."},
                    "confirmed": {"type": "boolean", "description": "Set true only after explicit user approval."},
                },
                "required": ["to", "subject"],
                "additionalProperties": False,
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    start = time.time()
    print(f"[mailer-mcp] tools/call {name}")
    try:
        match name:
            case "mailer_status":
                result = _tool_status()
            case "mailer_send_email":
                result = await _tool_send_email(arguments)
            case _:
                raise ValueError(f"Unknown tool: {name}")
        print(f"[mailer-mcp] tools/result {name} ok {int((time.time() - start) * 1000)}ms")
        return result
    except Exception as exc:
        print(f"[mailer-mcp] tools/result {name} error {int((time.time() - start) * 1000)}ms {exc}")
        return _json_text({"ok": False, "error": str(exc)})


def _tool_status() -> list[TextContent]:
    return _json_text(
        {
            "ok": True,
            "service": "agent-mailer-api",
            "version": _AGENT_VERSION,
            "provider": "mailersend",
            "apiKeyConfigured": bool(_MAILERSEND_API_KEY),
            "from": {"email": _MAILERSEND_FROM_EMAIL, "name": _MAILERSEND_FROM_NAME},
            "requireConfirmation": _REQUIRE_CONFIRMATION,
            "defaultDryRun": _DEFAULT_DRY_RUN,
            "userAgent": _MAILERSEND_USER_AGENT,
        }
    )


async def _tool_send_email(args: dict[str, Any]) -> list[TextContent]:
    to = str(args.get("to", "")).strip()
    subject = str(args.get("subject", "")).strip()
    text = str(args.get("text", "") or "")
    html = str(args.get("html", "") or "")
    dry_run = bool(args.get("dryRun", _DEFAULT_DRY_RUN))
    confirmed = bool(args.get("confirmed", False))

    if not to or "@" not in to:
        raise ValueError("A valid recipient email is required.")
    if not subject:
        raise ValueError("Email subject is required.")
    if not text and not html:
        raise ValueError("Either text or html body is required.")
    if _REQUIRE_CONFIRMATION and not confirmed and not dry_run:
        raise ValueError("Sending requires confirmed=true. Ask the user for explicit approval first, or use dryRun=true.")
    if not _MAILERSEND_API_KEY and not dry_run:
        raise ValueError("MAILERSEND_API_KEY is not configured.")

    payload: dict[str, Any] = {
        "from": {"email": _MAILERSEND_FROM_EMAIL, "name": _MAILERSEND_FROM_NAME},
        "to": [{"email": to}],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html
    cc = _email_list(args.get("cc"))
    bcc = _email_list(args.get("bcc"))
    if cc:
        payload["cc"] = [{"email": email} for email in cc]
    if bcc:
        payload["bcc"] = [{"email": email} for email in bcc]
    reply_to = str(args.get("replyTo", "") or "").strip()
    if reply_to:
        payload["reply_to"] = {"email": reply_to}

    if dry_run:
        return _json_text({"ok": True, "dryRun": True, "provider": "mailersend", "payload": payload})

    status, response_headers, response_body = await asyncio.to_thread(_post_mailersend, payload)
    return _json_text(
        {
            "ok": 200 <= status < 300,
            "provider": "mailersend",
            "status": status,
            "messageId": response_headers.get("x-message-id") or response_headers.get("X-Message-Id"),
            "response": response_body,
        }
    )


def _email_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = value
    else:
        raise ValueError("cc/bcc must be arrays of email strings.")
    emails = [str(item).strip() for item in raw if str(item).strip()]
    invalid = [email for email in emails if "@" not in email]
    if invalid:
        raise ValueError(f"Invalid email address: {invalid[0]}")
    return emails


def _post_mailersend(payload: dict[str, Any]) -> tuple[int, dict[str, str], str]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        _MAILERSEND_API_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "X-Requested-With": "XMLHttpRequest",
            "Authorization": f"Bearer {_MAILERSEND_API_KEY}",
            "User-Agent": _MAILERSEND_USER_AGENT,
        },
    )
    ssl_context = None if _MAILERSEND_VERIFY_SSL else _unverified_ssl_context()
    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return response.status, dict(response.headers.items()), response_body
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), response_body


def _unverified_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def create_starlette_app() -> Starlette:
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8080"))
    streamable_http = StreamableHTTPSessionManager(
        app=app,
        event_store=None,
        json_response=False,
        stateless=True,
    )

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path not in {"/mcp", "/mcp/"}:
            response = PlainTextResponse("Not found", status_code=404)
            await response(scope, receive, send)
            return
        request = Request(scope, receive)
        if request.method == "GET" and _wants_html(request):
            scheme = "https" if request.url.scheme == "https" else "http"
            endpoint_url = f"{scheme}://{request.headers.get('host', f'{host}:{port}')}/mcp/"
            response = HTMLResponse(_render_landing_page(endpoint_url, scheme))
            await response(scope, receive, send)
            return

        mcp_scope = dict(scope)
        mcp_scope["path"] = "/"
        mcp_scope["root_path"] = f"{scope.get('root_path', '').rstrip('/')}/mcp"
        await streamable_http.handle_request(mcp_scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with streamable_http.run():
            yield

    middleware = [
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
        Middleware(_BearerAuthMiddleware),
    ]
    return Starlette(routes=[Mount("/", app=handle_mcp)], middleware=middleware, lifespan=lifespan)


def main() -> None:
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8080"))
    print(f"[mailer-mcp] Streamable HTTP on http://{host}:{port}/mcp")
    uvicorn.run(create_starlette_app(), host=host, port=port)


if __name__ == "__main__":
    main()
