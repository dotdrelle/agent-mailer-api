# Repository Guide

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
- Keep `_AGENT_VERSION` aligned with the coordinated `llm-wiki-manager`
  release version so status responses identify the deployed agent bundle.
  Current release line: `0.7.0`.
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
