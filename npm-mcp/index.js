#!/usr/bin/env node
/**
 * sanctions-mcp — OFAC sanctions screening as an MCP server.
 *
 * Zero dependencies, on purpose. This is installed by `npx sanctions-mcp` inside
 * agent runtimes, where a dependency tree is both a startup cost paid on every
 * cold start and a supply chain the operator did not choose. MCP's stdio
 * transport is newline-delimited JSON-RPC 2.0, which Node can speak unaided.
 *
 * Talks to the hosted API at sanctionsai.dev. The free tier needs no key and is
 * rate-limited by IP; set SANCTIONS_API_KEY for a paid tier, or SANCTIONS_API_URL
 * to point at a self-hosted instance (the server is MIT-licensed and runs
 * locally — see https://github.com/kindrat86/agentmail).
 */

'use strict';

const BASE = (process.env.SANCTIONS_API_URL || 'https://sanctionsai.dev').replace(/\/+$/, '');
const API_KEY = process.env.SANCTIONS_API_KEY || '';
const TIMEOUT_MS = Number(process.env.SANCTIONS_TIMEOUT_MS || 20000);
const NAME = 'sanctions-mcp';
const VERSION = '0.1.0';

// Echoed back to the client when it asks for something we can speak. MCP
// negotiates by version string, and a client that asks for a version we do not
// recognise still gets a working session on our default rather than a failure.
const DEFAULT_PROTOCOL = '2025-06-18';
const SUPPORTED_PROTOCOLS = new Set(['2024-11-05', '2025-03-26', '2025-06-18']);

/* ------------------------------------------------------------------ HTTP -- */

async function call(path, { method = 'GET', body, query } = {}) {
  const url = new URL(BASE + path);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
    }
  }
  const headers = { Accept: 'application/json' };
  if (body) headers['Content-Type'] = 'application/json';
  if (API_KEY) headers['X-API-Key'] = API_KEY;

  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: ac.signal,
    });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      // A non-JSON body is a real outcome (proxy error page, HTML 502). Surface
      // it rather than throwing a parse error that hides the status code.
      return { ok: res.ok, status: res.status, raw: text.slice(0, 600) };
    }
    if (!res.ok) return { ok: false, status: res.status, error: data };
    return { ok: true, status: res.status, data };
  } catch (err) {
    const aborted = err && (err.name === 'AbortError' || err.name === 'TimeoutError');
    return {
      ok: false,
      status: 0,
      error: {
        message: aborted ? `request timed out after ${TIMEOUT_MS}ms` : String((err && err.message) || err),
      },
    };
  } finally {
    clearTimeout(timer);
  }
}

/* ----------------------------------------------------------------- TOOLS -- */

const TOOLS = [
  {
    name: 'sanctions_check',
    description:
      'Screen a counterparty against the US Treasury OFAC Specially Designated Nationals (SDN) list ' +
      'before paying them. Accepts a name, a crypto wallet address, a country, or any combination — ' +
      'at least one is required. Returns {matches, clean, action}. This is the cheapest check; call it ' +
      'first. Covers the SDN list only: not the OFAC Consolidated/SSI lists, not EU/UK/UN lists, and it ' +
      'performs no 50 Percent Rule ownership analysis. A "clean" result is not a compliance opinion.',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string', description: 'Legal or trading name of the counterparty.' },
        wallet: { type: 'string', description: 'Crypto wallet address (any supported chain).' },
        country: { type: 'string', description: 'Country name or ISO code, for embargo screening.' },
      },
      additionalProperties: false,
    },
  },
  {
    name: 'risk_score',
    description:
      'Score a payment for fraud and sanctions risk before authorizing it. Returns ' +
      '{score, recommendation: allow|review|decline, reasons}. Runs a sanctions check as part of scoring.',
    inputSchema: {
      type: 'object',
      properties: {
        counterparty_id: { type: 'string', description: 'Identifier for the party being paid.' },
        amount: { type: 'string', description: 'Payment amount, as a string, e.g. "100".' },
        currency: { type: 'string', description: 'Currency code. Default USDC.' },
        rail: { type: 'string', description: 'Payment rail, e.g. x402, ap2, acp. Default x402.' },
        category: { type: 'string', description: 'Merchant category, e.g. digital_goods.' },
      },
      required: ['counterparty_id', 'amount'],
      additionalProperties: false,
    },
  },
  {
    name: 'kya_verify',
    description:
      'Know Your Agent: score how much to trust a counterparty AI agent, from evidence you supply ' +
      '(wallet address, wallet age, domain, public key, declared country). Returns {kya_score, verdict}.',
    inputSchema: {
      type: 'object',
      properties: {
        agent_id: { type: 'string', description: 'Identifier of the agent being verified.' },
        evidence: {
          type: 'object',
          description:
            'Any of: wallet_address, wallet_age_days, domain, pubkey, owner_email, declared_country.',
          additionalProperties: true,
        },
      },
      required: ['agent_id'],
      additionalProperties: false,
    },
  },
  {
    name: 'dispute_open',
    description:
      'Open a dispute against a transaction that went bad, with an audit trail and 7-day ' +
      'auto-escalation. Returns {dispute_id, status, escalation_at}.',
    inputSchema: {
      type: 'object',
      properties: {
        transaction_id: { type: 'string', description: 'The transaction being disputed.' },
        reason: { type: 'string', description: 'Why it is disputed.' },
        evidence: { type: 'object', description: 'Optional supporting evidence.', additionalProperties: true },
      },
      required: ['transaction_id', 'reason'],
      additionalProperties: false,
    },
  },
  {
    name: 'sdn_list_info',
    description:
      'Report which OFAC SDN publication this server is screening against: the publication date OFAC ' +
      'itself assigned, entry and name counts, entity-type breakdown, and the URLs for the full list as ' +
      'JSON and CSV. Costs no screening quota. Call this to answer "how current is your sanctions data" ' +
      'or to fetch the whole list instead of screening one name at a time.',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  },
];

const HANDLERS = {
  async sanctions_check(args) {
    const { name = '', wallet = '', country = '' } = args || {};
    if (!name && !wallet && !country) {
      return { isError: true, text: 'Provide at least one of: name, wallet, country.' };
    }
    const r = await call('/sanctions', { query: { name, wallet, country } });
    return fmt(r);
  },

  async risk_score(args) {
    const a = args || {};
    if (!a.counterparty_id || a.amount === undefined) {
      return { isError: true, text: 'counterparty_id and amount are both required.' };
    }
    const r = await call('/risk', {
      method: 'POST',
      body: {
        counterparty_id: a.counterparty_id,
        amount: String(a.amount),
        currency: a.currency || 'USDC',
        rail: a.rail || 'x402',
        category: a.category || 'digital_goods',
      },
    });
    return fmt(r);
  },

  async kya_verify(args) {
    const a = args || {};
    if (!a.agent_id) return { isError: true, text: 'agent_id is required.' };
    const r = await call('/kya', { method: 'POST', body: { agent_id: a.agent_id, evidence: a.evidence || {} } });
    return fmt(r);
  },

  async dispute_open(args) {
    const a = args || {};
    if (!a.transaction_id || !a.reason) {
      return { isError: true, text: 'transaction_id and reason are both required.' };
    }
    const body = { transaction_id: a.transaction_id, reason: a.reason };
    if (a.evidence) body.evidence = a.evidence;
    const r = await call('/disputes', { method: 'POST', body });
    return fmt(r);
  },

  async sdn_list_info() {
    const r = await call('/data/ofac-sdn-list/metadata.json');
    if (!r.ok) return fmt(r);
    const d = r.data || {};
    // Hand back the card without the prose fields an agent would only have to
    // skip past, but keep scope and disclaimer: they are the parts a caller
    // most needs and least expects.
    return fmt({
      ok: true,
      data: {
        published_by_ofac: d.published,
        retrieved: d.retrieved,
        counts: d.counts,
        typeCounts: d.typeCounts,
        downloads: {
          json: `${BASE}/data/ofac-sdn-list/ofac-sdn.json`,
          csv: `${BASE}/data/ofac-sdn-list/ofac-sdn.csv`,
          landing_page: `${BASE}/data/ofac-sdn-list/`,
          mirror: 'https://github.com/kindrat86/ofac-sdn-json',
        },
        license: d.license,
        scope: d.scope,
        disclaimer: d.disclaimer,
      },
    });
  },
};

function fmt(r) {
  if (!r.ok) {
    const detail = r.error ? JSON.stringify(r.error) : r.raw || 'unknown error';
    return { isError: true, text: `Request failed (HTTP ${r.status}): ${detail}` };
  }
  return { isError: false, text: JSON.stringify(r.data !== undefined ? r.data : r, null, 2) };
}

/* ------------------------------------------------------------ JSON-RPC -- */

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n');
}

function reply(id, result) {
  send({ jsonrpc: '2.0', id, result });
}

function fail(id, code, message) {
  send({ jsonrpc: '2.0', id, error: { code, message } });
}

async function handle(msg) {
  const { id, method, params } = msg;
  // Notifications carry no id and must never be answered — replying to one is a
  // protocol violation that some clients treat as fatal.
  const isNotification = id === undefined || id === null;

  switch (method) {
    case 'initialize': {
      const asked = params && params.protocolVersion;
      const version = SUPPORTED_PROTOCOLS.has(asked) ? asked : DEFAULT_PROTOCOL;
      return reply(id, {
        protocolVersion: version,
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: NAME, version: VERSION },
      });
    }
    case 'notifications/initialized':
    case 'notifications/cancelled':
      return;
    case 'ping':
      return isNotification ? undefined : reply(id, {});
    case 'tools/list':
      return reply(id, { tools: TOOLS });
    case 'tools/call': {
      const toolName = params && params.name;
      const fn = HANDLERS[toolName];
      if (!fn) return fail(id, -32602, `Unknown tool: ${toolName}`);
      try {
        const out = await fn((params && params.arguments) || {});
        return reply(id, { content: [{ type: 'text', text: out.text }], isError: out.isError });
      } catch (err) {
        // A thrown handler is reported as a tool error, not a protocol error:
        // the call was well-formed, the work failed, and the model can react.
        return reply(id, {
          content: [{ type: 'text', text: `Tool failed: ${String((err && err.message) || err)}` }],
          isError: true,
        });
      }
    }
    default:
      if (isNotification) return;
      return fail(id, -32601, `Method not found: ${method}`);
  }
}

function main() {
  if (process.argv.includes('--version') || process.argv.includes('-v')) {
    process.stdout.write(VERSION + '\n');
    return;
  }
  if (process.argv.includes('--help') || process.argv.includes('-h')) {
    process.stdout.write(
      `${NAME} ${VERSION} — OFAC sanctions screening over MCP (stdio).\n\n` +
        `Speaks MCP on stdin/stdout; run it from an MCP client, not directly.\n\n` +
        `Environment:\n` +
        `  SANCTIONS_API_URL     API base URL (default https://sanctionsai.dev)\n` +
        `  SANCTIONS_API_KEY     API key; omit to use the free, IP-rate-limited tier\n` +
        `  SANCTIONS_TIMEOUT_MS  per-request timeout (default 20000)\n\n` +
        `Tools: ${TOOLS.map((t) => t.name).join(', ')}\n`
    );
    return;
  }

  let buf = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => {
    buf += chunk;
    let nl;
    while ((nl = buf.indexOf('\n')) !== -1) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let msg;
      try {
        msg = JSON.parse(line);
      } catch {
        send({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Parse error' } });
        continue;
      }
      Promise.resolve(handle(msg)).catch((err) => {
        if (msg && msg.id !== undefined && msg.id !== null) {
          fail(msg.id, -32603, String((err && err.message) || err));
        }
      });
    }
  });
  // Deliberately no process.exit() here. Exiting the moment stdin closes kills
  // any request still in flight, and its response is never written — a client
  // that closes stdin right after a tools/call would silently lose the result.
  // With no explicit exit, Node ends on its own once stdin is closed and no
  // work remains pending, which is the same shutdown one message later.
  process.stdin.on('end', () => {});
}

main();
