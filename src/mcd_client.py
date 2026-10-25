# -*- coding: utf-8 -*-
"""McDonald's China MCP thin client (stdlib only, streamable HTTP).

Only readonly tools are exposed. Write tools (create-order etc.) are
deliberately NOT wrapped — this client cannot place an order by design.
"""
import json
import urllib.request

MCP_URL = "https://mcp.mcd.cn"

# readonly allowlist (subset actually used by the coach)
READONLY_TOOLS = (
    "now-time-info", "query-nearby-stores", "query-meals", "query-meal-detail",
    "calculate-price", "list-nutrition-foods", "available-coupons",
    "query-my-coupons", "query-my-account", "campaign-calendar",
)


class McdMcpClient:
    def __init__(self, token: str, url: str = MCP_URL, timeout: int = 25):
        if not token or " " in token:
            raise ValueError("token must be a non-empty MCP bearer token")
        self._token = token
        self._url = url
        self._timeout = timeout
        self._id = 0

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        req = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer " + self._token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            body = resp.read().decode()
        for line in body.splitlines():  # SSE framing fallback
            if line.startswith("data:"):
                body = line[5:].strip()
                break
        out = json.loads(body)
        if "error" in out:
            raise RuntimeError(f"MCP error: {out['error']}")
        return out["result"]

    def call(self, name: str, arguments: dict | None = None) -> dict:
        """Call a readonly tool, return the raw upstream JSON object.

        The MCP server wraps responses with a field-documentation preamble;
        the authoritative payload is the embedded JSON starting with
        {"success": ...}. We locate and parse it deterministically.
        """
        if name not in READONLY_TOOLS:
            raise PermissionError(f"tool {name!r} is not in the readonly allowlist")
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        text = "\n".join(
            c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"
        )
        return extract_json(text)


def extract_json(text: str) -> dict:
    """Pull the first embedded upstream JSON object out of an MCP text block."""
    start = text.find('{"success"')
    if start < 0:
        return {"success": False, "code": -1, "message": "no payload found", "data": text[:200]}
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj
