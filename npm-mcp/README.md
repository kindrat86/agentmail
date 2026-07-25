# sanctions-mcp

**OFAC sanctions screening as an MCP server.** Check whether a name, crypto wallet, or country is
on the US Treasury Specially Designated Nationals (SDN) list — before your agent pays them.

Free tier needs no API key. **Zero dependencies.**

```bash
npx sanctions-mcp
```

## Install

### Claude Desktop / Claude Code

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sanctions": {
      "command": "npx",
      "args": ["-y", "sanctions-mcp"]
    }
  }
}
```

Or from the command line:

```bash
claude mcp add sanctions -- npx -y sanctions-mcp
```

### Cursor / Windsurf / VS Code

`mcp.json`:

```json
{
  "mcpServers": {
    "sanctions": {
      "command": "npx",
      "args": ["-y", "sanctions-mcp"]
    }
  }
}
```

### With an API key

The free tier is rate-limited by IP. For higher volume:

```json
{
  "mcpServers": {
    "sanctions": {
      "command": "npx",
      "args": ["-y", "sanctions-mcp"],
      "env": { "SANCTIONS_API_KEY": "sk_live_..." }
    }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `sanctions_check` | Screen a name, wallet and/or country against the OFAC SDN list. Returns `{matches, clean, action}`. Cheapest call — use it first. |
| `risk_score` | Score a payment before authorizing it. Returns `{score, recommendation: allow\|review\|decline, reasons}`. Includes a sanctions check. |
| `kya_verify` | Know Your Agent — trust-score a counterparty agent from evidence you supply. Returns `{kya_score, verdict}`. |
| `dispute_open` | Open a dispute with an audit trail and 7-day auto-escalation. |
| `sdn_list_info` | Which SDN publication is being screened against — OFAC's own publication date, counts, and bulk-download URLs. Costs no quota. |

### Example

> "Before I pay BANCO NACIONAL DE CUBA, screen them."

```json
{
  "matches": [
    {
      "list": "OFAC_SDN",
      "entity": "BANCO NACIONAL DE CUBA",
      "match_type": "name_exact",
      "confidence": 0.97
    }
  ],
  "clean": false,
  "action": "BLOCK"
}
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SANCTIONS_API_KEY` | *(none)* | API key. Omit for the free, IP-rate-limited tier. |
| `SANCTIONS_API_URL` | `https://sanctionsai.dev` | Point at a self-hosted instance. |
| `SANCTIONS_TIMEOUT_MS` | `20000` | Per-request timeout. |

## Bulk download

To work with the whole list rather than screening one counterparty at a time, skip the API:

- JSON — <https://sanctionsai.dev/data/ofac-sdn-list/ofac-sdn.json>
- CSV — <https://sanctionsai.dev/data/ofac-sdn-list/ofac-sdn.csv>
- Mirror — <https://github.com/kindrat86/ofac-sdn-json>

19,254 designated entries and 20,350 alternate identities, parsed verbatim from Treasury's own
export. Public domain (17 U.S.C. § 105); packaging CC0.

## Scope — read this before relying on it

This screens the **SDN list only**. It does **not** cover:

- the OFAC **Consolidated (non-SDN)** lists
- the **Sectoral Sanctions Identifications (SSI)** list
- **EU, UK, UN** or any other jurisdiction's list

It performs no **50 Percent Rule** ownership analysis — an entity owned 50% or more by blocked
persons is itself blocked whether or not it appears on this list.

A `clean: true` result means *no match was found in the SDN list*. It is not a compliance opinion
and not a sanctions clearance. OFAC's own [sanctions search](https://sanctionssearch.ofac.treas.gov/)
is authoritative for any compliance decision. **Nothing here is legal or compliance advice.**

## Self-hosting

The server behind this API is MIT-licensed and runs locally — no key, no quota. See
[kindrat86/agentmail](https://github.com/kindrat86/agentmail). Point `SANCTIONS_API_URL` at it.

There is also a Python implementation on PyPI:

```bash
pip install sanctions-mcp
```

## Licence

MIT. See [LICENSE](LICENSE).
