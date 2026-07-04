import asyncio
import importlib.util
import json
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TextContent:
    type: str
    text: str


class Tool:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Server:
    def __init__(self, *_args, **_kwargs):
        pass

    def list_tools(self):
        return lambda fn: fn

    def call_tool(self):
        return lambda fn: fn


def install_stubs():
    mcp = types.ModuleType("mcp")
    mcp_server = types.ModuleType("mcp.server")
    mcp_server.Server = Server
    mcp_manager = types.ModuleType("mcp.server.streamable_http_manager")
    mcp_manager.StreamableHTTPSessionManager = object
    mcp_types = types.ModuleType("mcp.types")
    mcp_types.TextContent = TextContent
    mcp_types.Tool = Tool
    sys.modules.update({
        "mcp": mcp,
        "mcp.server": mcp_server,
        "mcp.server.streamable_http_manager": mcp_manager,
        "mcp.types": mcp_types,
    })
    for name in [
        "starlette.applications",
        "starlette.middleware",
        "starlette.middleware.base",
        "starlette.middleware.cors",
        "starlette.requests",
        "starlette.responses",
        "starlette.routing",
        "starlette.types",
        "uvicorn",
    ]:
        module = types.ModuleType(name)
        sys.modules[name] = module
    sys.modules["starlette.applications"].Starlette = object
    sys.modules["starlette.middleware"].Middleware = lambda *args, **kwargs: (args, kwargs)
    sys.modules["starlette.middleware.base"].BaseHTTPMiddleware = object
    sys.modules["starlette.middleware.cors"].CORSMiddleware = object
    sys.modules["starlette.requests"].Request = object
    sys.modules["starlette.responses"].HTMLResponse = object
    sys.modules["starlette.responses"].PlainTextResponse = object
    sys.modules["starlette.routing"].Mount = object
    sys.modules["starlette.types"].Receive = object
    sys.modules["starlette.types"].Scope = dict
    sys.modules["starlette.types"].Send = object
    sys.modules["uvicorn"].run = lambda *args, **kwargs: None


def load_module():
    install_stubs()
    path = Path(__file__).with_name("mailer_mcp_server.py")
    spec = importlib.util.spec_from_file_location("mailer_mcp_server_test_subject", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MailerMcpServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = load_module()

    def payload(self, result):
        return json.loads(result[0].text)

    def test_dry_run_does_not_require_api_key_or_confirmation(self):
        self.server._MAILERSEND_API_KEY = ""
        result = asyncio.run(self.server._tool_send_email({
            "to": "user@example.com",
            "subject": "Preview",
            "text": "Body",
            "dryRun": True,
        }))
        payload = self.payload(result)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dryRun"])
        self.assertEqual(payload["payload"]["to"][0]["email"], "user@example.com")

    def test_confirmed_required_for_real_send(self):
        self.server._MAILERSEND_API_KEY = "secret-key"
        with self.assertRaisesRegex(ValueError, "confirmed=true"):
            asyncio.run(self.server._tool_send_email({
                "to": "user@example.com",
                "subject": "Send",
                "text": "Body",
                "dryRun": False,
            }))

    def test_log_redaction_masks_secret_values(self):
        masked = self.server._mask_secret_text("Authorization: Bearer abc123 api_key=sk-live token:foo password='bar'")
        self.assertNotIn("abc123", masked)
        self.assertNotIn("sk-live", masked)
        self.assertNotIn("foo", masked)
        self.assertNotIn("bar", masked)

    def test_read_scope_cannot_send_email(self):
        token = self.server._CURRENT_SCOPES.set({"read"})
        try:
            denied = self.server._require_tool_scope("mailer_send_email")
            allowed = self.server._require_tool_scope("mailer_status")
        finally:
            self.server._CURRENT_SCOPES.reset(token)

        self.assertFalse(self.payload(denied)["ok"])
        self.assertIn("write scope", self.payload(denied)["error"])
        self.assertIsNone(allowed)


if __name__ == "__main__":
    unittest.main()
