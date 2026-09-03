"""sanctionsai-mcp: Model Context Protocol server for sanctionsai.dev screening.

Distributable MCP server exposing SanctionsAI screening as tools:

  screen_name(name, country?)     - x402-gated paid screen of a person name
  screen_company(name, country?)  - x402-gated paid screen of a company name
  x402_info()                     - free: pricing, endpoint, quickstart

Paid tool calls hit the existing production endpoint
https://sanctionsai.dev/x402/sanctions ($0.05 USDC on Base per call).
The first unpaid call returns the x402 402 Payment-Required challenge; this
server surfaces it as a structured result so an MCP client (or operator)
can settle it. Stdlib only - no third-party dependencies.

Run (stdio transport, newline-delimited JSON-RPC 2.0):
    python3 -m sanctionsai_mcp.server

Wire into an MCP client config:
    {"command": "python3", "args": ["-m", "sanctionsai_mcp.server"],
     "cwd": "/path/to/repo"}
"""
from .server import main, serve  # noqa: F401

__version__ = "0.1.0"
