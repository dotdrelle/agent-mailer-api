# agent-mailer-api

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue)](LICENSE)

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
export MAILERSEND_API_KEY=<mailersend-api-key>
export MAILERSEND_FROM_EMAIL=<sender@example.com>
export MAILERSEND_FROM_NAME="Mailer Agent"
export MAILERSEND_USER_AGENT=curl/8.7.1
```

Optional:

```bash
export MCP_AUTH_TOKEN=<generated-local-token>
export MAILER_MCP_PORT=3335
export MAILER_DRY_RUN=false
export MAILERSEND_VERIFY_SSL=true
```

The standalone Docker Compose file defaults optional values to empty strings, `MAILER_DRY_RUN=false`, and `MAILERSEND_VERIFY_SSL=true` to avoid interpolation warnings.

Set `MAILERSEND_VERIFY_SSL=false` only for local debugging behind a trusted TLS-intercepting proxy.

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

`agent-mailer-api` is external infrastructure for `llm-wiki-manager`. Run it
separately and keep `MAILERSEND_*` secrets in this service's environment. The
manager only needs the MCP endpoint URL and the same bearer token:

```env
MAILER_MCP_PROXY_URL=http://host.docker.internal:3335/mcp/
MAILER_MCP_AUTH_TOKEN=<same-generated-local-token>
```

`llm-wiki serve` uses those values to connect `/chat` to the mailer as
`donna-mailer`.

## License

Released under the **PolyForm Noncommercial License 1.0.0**. See [LICENSE](LICENSE).
