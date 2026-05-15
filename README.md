# agent-mailer-api

Send-only MCP server for MailerSend.

`agent-mailer-api` is intentionally small: it exposes MailerSend as a
Streamable HTTP MCP server so an AI agent can send approved emails without
learning MailerSend API details or seeing the API key.

## Tools

| Tool | Purpose |
| --- | --- |
| `mailer_status` | Check runtime configuration without exposing secrets. |
| `mailer_send_email` | Send one email through MailerSend, or preview with `dryRun=true`. |

`MAILER_REQUIRE_CONFIRMATION=true` by default. When enabled, real sends require
the tool argument `confirmed=true`; otherwise the tool returns an error asking
for explicit user approval. `dryRun=true` never sends.

## Configuration

```bash
export MAILERSEND_API_KEY=...
export MAILERSEND_FROM_EMAIL=donna@itsdonna.events
export MAILERSEND_FROM_NAME=Donna
```

Optional:

```bash
export MCP_AUTH_TOKEN=local-token
export MAILER_MCP_PORT=3335
export MAILER_DRY_RUN=true
```

## Run Locally

```bash
docker compose up --build
```

The MCP endpoint is:

```txt
http://localhost:3335/mcp/
```

Browsers can open the endpoint to view the status page. MCP clients should send
Streamable HTTP requests to the same URL.

## Manager Integration

`llm-wiki-manager` runs this service like `agent-cme`: the manager compose pulls
the Docker image, maps a local port, and passes `MAILER_MCP_PROXY_URL` to
`llm-wiki serve` so `/chat` can connect to it as `donna-mailer`.
