"""MCP server (stdio transport) for sanctionsai.dev - stdlib only.

Implements the Model Context Protocol JSON-RPC 2.0 surface that MCP hosts
(Claude Desktop, Cursor, Hermes, etc.) speak over stdio, one JSON message
per line:

  initialize -> serverInfo + capabilities
  tools/list -> the three tools below
  tools/call -> dispatch to a tool
  ping       -> {}

Tools:
  screen_name(name, country?)    paid ($0.05 x402) person screen
  screen_company(name, country?) paid ($0.05 x402) company screen
  x402_info()                    free: endpoint, price, quickstart URL
"""
from __future__ import annotations

import json
import sys

from . import client

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "sanctionsai-mcp", "version": "0.1.0",
               "homepage": "https://sanctionsai.dev"}

TOOLS = [
    {
        "name": "screen_name",
        "description": ("Screen a person's full name against consolidated sanctions "
                        "lists (OFAC SDN / EU / UN). PAID: each call is x402-gated at "
                        "$0.05 USDC on Base; if unpaid, returns the 402 payment "
                        "challenge with payment instructions."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Full person name to screen"},
                "country": {"type": "string", "description": "Optional country filter"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "screen_company",
        "description": ("Screen a company / legal-entity name against consolidated "
                        "sanctions lists. PAID: each call is x402-gated at $0.05 USDC "
                        "on Base; if unpaid, returns the 402 payment challenge with "
                        "payment instructions."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Company or entity name to screen"},
                "country": {"type": "string", "description": "Optional country filter"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "x402_info",
        "description": ("Free: pricing and setup info for the SanctionsAI x402 screening "
                        "endpoint - price per call, network, quickstart URL."),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _tool_result(payload: dict, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
            "isError": is_error}


def call_tool(name: str, arguments: dict, transport=None) -> dict:
    """Execute a tool call; returns an MCP tool result object."""
    if name == "x402_info":
        return _tool_result({
            "service": "SanctionsAI",
            "endpoint": client.DEFAULT_BASE_URL + client.X402_SCREEN_PATH,
            "price": client.PRICE_DESCRIPTION,
            "payment_protocol": "x402 v2 (HTTP 402 challenge, settle and retry)",
            "quickstart": client.QUICKSTART_URL,
            "note": ("screen_name and screen_company are paid tools. The first call "
                     "returns the 402 payment challenge; settle it and retry to get "
                     "the screening result."),
        })
    if name in ("screen_name", "screen_company"):
        who = "person" if name == "screen_name" else "company"
        value = str(arguments.get("name", "") or "").strip()
        if not value:
            return _tool_result({"error": f"'name' is required to screen a {who}"},
                                is_error=True)
        return _tool_result(client.screen(subject_type=who, name=value,
                                          country=str(arguments.get("country", "") or ""),
                                          transport=transport))
    return _tool_result({"error": f"Unknown tool: {name}. Available: "
                                  + ", ".join(t["name"] for t in TOOLS)},
                        is_error=True)


def handle_message(message: dict, transport=None) -> dict | None:
    """Handle one JSON-RPC message; return the response dict or None for
    notifications."""
    method = message.get("method", "")
    msg_id = message.get("id")
    is_request = msg_id is not None

    def reply(result=None, error=None):
        out = {"jsonrpc": "2.0", "id": msg_id}
        if error is not None:
            out["error"] = error
        else:
            out["result"] = result
        return out

    if method == "initialize":
        return reply({"protocolVersion": PROTOCOL_VERSION,
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": SERVER_INFO})
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None  # notifications never get a response
    if method == "ping":
        return reply({})
    if method == "tools/list":
        return reply({"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        return reply(call_tool(params.get("name", ""),
                               params.get("arguments", {}) or {}, transport=transport))
    if is_request:
        return reply(error={"code": -32601, "message": f"Method not found: {method}"})
    return None  # unknown notification


def serve(stdin=sys.stdin, stdout=sys.stdout, transport=None) -> None:
    """Main stdio loop: newline-delimited JSON-RPC in, newline-delimited out."""
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Parse error"}}
        else:
            if not isinstance(message, dict):
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32600, "message": "Invalid request"}}
            else:
                response = handle_message(message, transport=transport)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
