# Repository Guide

Current coordinated release: **0.15.66**. Keep `_AGENT_VERSION` aligned with
the coordinated workspace stack.

## Goal

`agent-mailer-api` is a send-only MailerSend MCP Streamable HTTP server. It gives
agents a narrow tool surface for approved email sending while keeping the
MailerSend API key in the service environment.

## Architecture

- `mailer_mcp_server.py`: Starlette/uvicorn MCP server, bearer-auth middleware,
  HTML status page, `mailer_status`, and `mailer_send_email`.
- `Dockerfile`: Python runtime with MCP, Starlette, and uvicorn.
- `docker-compose.yml`: standalone local service with environment-driven
  MailerSend and MCP settings.

## Constraints

- Never expose `MAILERSEND_API_KEY` in tool output, logs, status pages, or error
  messages.
- `MAILER_REQUIRE_CONFIRMATION=true` is the safe default. Real sends should
  require the `confirmed=true` tool argument unless the deployment explicitly
  disables that guard.
- `dryRun=true` must never send email.
- Bearer auth is a local MCP coordination token, not a MailerSend credential.
  Document examples with placeholders such as `<generated-local-token>`.
- Keep this service send-only. Do not add inbox, mailbox search, or broad email
  account actions here.
- Keep TLS verification enabled by default. `MAILERSEND_VERIFY_SSL=false` is
  only for local debugging behind a trusted TLS-intercepting proxy.
- `MAILERSEND_CA_CERT` (optional): path to a CA bundle passed as `cafile` to
  `ssl.create_default_context()` when verification is on. **Open question, not
  yet resolved:** this may duplicate the manager's `--cacert` mechanism
  (`llm-wiki-manager/CLAUDE.md`, Docker And Security), which already injects
  `SSL_CERT_FILE` into agent containers — and `create_default_context()`
  without an explicit `cafile` already honors `SSL_CERT_FILE`. Do not remove
  `MAILERSEND_CA_CERT` without deciding whether `--cacert` alone is sufficient
  for this service.
- Keep `_AGENT_VERSION` aligned with the coordinated `llm-wiki-manager`
  release version so status responses identify the deployed agent bundle.
  Current release line: `0.15.66`. Alignment is checked by
  `llm-wiki-manager/scripts/check-versions.js` and synced by the root
  `build-and-push.sh`.
- **Auth, scopes, rate limiting** (0.10.3): `MCP_AUTH_TOKEN` remains a legacy
  full-access (read+write) token; `MCP_READ_TOKEN`/`MCP_WRITE_TOKEN` grant
  scoped access instead. `_token_scopes` compares with `hmac.compare_digest`
  (constant-time). `_require_tool_scope` denies `_WRITE_TOOLS`
  (`mailer_send_email`) to read-only callers; the current request's scope is
  threaded through a `contextvars.ContextVar` set by
  `_BearerAuthMiddleware`, not passed explicitly. Requests are rate-limited
  (`MCP_RATE_LIMIT_REQUESTS`/`MCP_RATE_LIMIT_WINDOW_SECONDS`, default
  120/60s) keyed by token or remote IP. `_any_token_configured()` is the
  single "is any token set" check. This whole block is copy-pasted
  near-verbatim across all four agent repos plus `llm-wiki`'s `mcpHttp.ts`
  (TypeScript) — see `agent-cme/CLAUDE.md`'s fuller note on why that hasn't
  been consolidated into a shared package.
- **Multi-user status**: the wikiLLM workspace remains a single-user
  deployment baseline; the multi-user model is specified in
  `llm-wiki/docs/industrialisation.md` and planned next — see
  `agent-cme/CLAUDE.md`'s fuller note. This agent's token scoping is
  read/write, not per-user; do not deploy it as a shared endpoint for
  distinct end users before that lot lands.
- MCP tool descriptions, `_activity` metadata, status page text, previews, and
  operator-facing errors must stay in English. Email body content is provided by
  the caller and may be in any language.

## Common Commands

```bash
docker compose up --build
```

Useful local environment variables:

```bash
export MAILERSEND_API_KEY=<mailersend-api-key>
export MAILERSEND_FROM_EMAIL=<sender@example.com>
export MCP_AUTH_TOKEN=<generated-local-token>
export MAILER_DRY_RUN=false
```

`llm-wiki-manager` consumes this service through `MAILER_MCP_PROXY_URL` and
`MAILER_MCP_AUTH_TOKEN`; it does not own MailerSend secrets.
