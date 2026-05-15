FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "mcp>=1.9.4" \
    starlette \
    uvicorn

COPY mailer_mcp_server.py .

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8080
ENV MAILERSEND_FROM_EMAIL=no-reply@example.com
ENV MAILERSEND_FROM_NAME="Mailer Agent"
ENV MAILER_REQUIRE_CONFIRMATION=true

EXPOSE 8080

CMD ["python", "mailer_mcp_server.py"]
