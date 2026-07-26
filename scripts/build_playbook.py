#!/usr/bin/env python3
"""Build the Agent Compliance Playbook (the /start lead magnet).

This is the bait rung of the Dotcom Secrets Value Ladder. The squeeze page at
/start promises "7 patterns for adding OFAC sanctions screening to your AI
agent's payment path" — for ~two months the form saved the email but never
delivered the PDF. This script regenerates the playbook so the promise is kept.

Output: public/agent-compliance-playbook.pdf  (served at /playbook.pdf)

Stdlib-only (no reportlab dep): we hand-write a minimal valid PDF. It is ugly
but correct and dependency-free, matching the rest of this repo's philosophy.

Run:
    python scripts/build_playbook.py
"""
from __future__ import annotations
import os
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "public", "agent-compliance-playbook.pdf"))

TITLE = "The Agent Compliance Playbook"
SUBTITLE = "7 patterns for adding OFAC sanctions screening to your AI agent's payment path"

# Each pattern: (number, name, one-liner, problem, pattern, code)
PATTERNS = [
    (
        1,
        "Screen-Before-Sign",
        "The single rule that prevents 100% of sanctioned-wallet payments.",
        "Your agent decides to pay, signs the tx, then screens. By then it is too late — the tx is on-chain.",
        "Call sanctions_check BEFORE the signing step, in the same code path that authorises payment. Treat the screen as a hard gate, not a log line.",
        "if not sanctions_check(wallet=to_addr).get('clean'):\n"
        "    abort('blocked: OFAC SDN match')\n"
        "sign_tx(to_addr, amount)  # only reached if clean",
    ),
    (
        2,
        "The 100ms Budget",
        "Compliance that costs more than one network hop gets ripped out in week two.",
        "A 900ms screening call blocks the payment path, an engineer removes it, and you are unscreened again.",
        "Enforce a hard latency budget. agentmail returns in <100ms p95; fail closed only if the call exceeds 500ms (configurable). Cache clean results for 60s to coalesce bursts.",
        "result = sanctions_check(wallet=w, timeout=0.5)\n"
        "if result is None:          # timed out\n"
        "    return 'review'          # do NOT auto-allow on timeout",
    ),
    (
        3,
        "Risk-Score the Amount, Not Just the Wallet",
        "A clean wallet moving $50k on day one is not the same as one moving $5.",
        "You screen the wallet, it is clean, you allow — and miss that a clean wallet is being used as a mule for a sanctioned actor.",
        "Layer risk_score on top of sanctions_check. It weighs amount anomalies, rail (x402/AP2/ACP), wallet age, and category exposure into a 0-100 score with an explicit allow/review/decline recommendation.",
        "r = risk_score(counterparty=w, amount=amt, rail='x402')\n"
        "if r['recommendation'] == 'decline':\n"
        "    return block_with_reason(r['reasons'])",
    ),
    (
        4,
        "Know Your Agent (KYA)",
        "The counterparty is another agent. Who vouches for it?",
        "Two agents transact and neither knows the other's operator. There is no KYC analogue for agents.",
        "Before trusting a counterparty agent, call kya_verify with its wallet age, on-chain history, and domain. It returns a trust score and flags (fresh wallet, no history, sanctioned-adjacent).",
        "k = kya_verify(agent_id=peer, wallet=peer_w,\n"
        "               wallet_age_days=age, domain=peer_domain)\n"
        "if k['trust_score'] < 40:\n"
        "    require_human_approval()",
    ),
    (
        5,
        "The Audit Trail Is the Product",
        "Regulators do not ask 'did it work.' They ask 'prove it worked, for every tx, for 5 years.'",
        "You screened, but you have no timestamped, tamper-evident record. A regulator asks for proof and you cannot produce it.",
        "Log every screen: the wallet, the timestamp, the result, the list version. agentmail's hosted tier writes a tamper-evident audit log you can export. Self-hosters should append to a write-once store.",
        "# every screen becomes an append-only row\n"
        "audit.append(ts=now, wallet=w, result=r,\n"
        "             list_version=sdn_version, hash=prev_hash)",
    ),
    (
        6,
        "Dispute-First, Not Litigate-First",
        "When a payment goes wrong, a 7-day auto-escalation beats a 7-month legal fight.",
        "A bad payment happens and you have no structured way to contest, freeze, or recover. It becomes a lawsuit.",
        "Call dispute_open the moment a paid transaction is flagged. It opens a structured dispute with a 7-day auto-escalation timer and a full evidence trail attached.",
        "dispute_open(transaction_id=txid,\n"
        "             reason='post-payment SDN match')\n"
        "# auto-escalates at day 7 if unresolved",
    ),
    (
        7,
        "Fail Closed, Degrade Loudly",
        "Silent failure is worse than no screening — it gives you false confidence.",
        "The screening API goes down, your agent catches the exception and pays anyway, and you do not find out until the fine.",
        "On provider failure: (a) fail CLOSED for high-value txs, (b) fail OPEN only with explicit operator policy, and (c) ALWAYS emit a 'degraded' signal so you know screening is running on stale data. agentmail's /health and /compliance/status report this.",
        "status = compliance_status()\n"
        "if status.get('degraded'):\n"
        "    page_oncall('screening on stale cache')",
    ),
]

CLOSING = (
    "These seven patterns are the difference between 'we have a compliance tool' "
    "and 'we can prove to OFAC that every payment our agent made was screened.' "
    "Pattern 1 alone — Screen-Before-Sign — would have prevented every agent-"
    "payment sanctions violation on record.\n\n"
    "If you want the version that is already wired up, pip install sanctions-mcp "
    "or hit https://agentmail-api.fly.dev/sanctions?wallet=0x... right now.\n\n"
    "— The agentmail team\nsanctionsai.dev"
)


def build_pdf(path: str = OUT) -> str:
    # Build the logical line list
    lines = [("h1", TITLE), ("body", SUBTITLE), ("body", "")]
    for num, name, one, problem, pattern, code in PATTERNS:
        lines.append(("h2", f"Pattern {num}: {name}"))
        lines.append(("body", one))
        lines.append(("body", ""))
        lines.append(("body", "The problem:"))
        lines.append(("body", problem))
        lines.append(("body", ""))
        lines.append(("body", "The pattern:"))
        lines.append(("body", pattern))
        lines.append(("body", ""))
        lines.append(("body", "Example:"))
        lines.append(("code", code))
        lines.append(("body", ""))
    lines.append(("h2", "Closing"))
    for para in CLOSING.split("\n\n"):
        lines.append(("body", para))
        lines.append(("body", ""))

    # Lay out into pages with explicit op tagging so the renderer knows which
    # font/size each line uses.
    pages = []
    cur_page = []
    x0 = 72
    ytop = 792 - 72
    ybot = 72 + 40
    lh = 14
    y = ytop

    def newpage():
        nonlocal y, cur_page
        pages.append(cur_page)
        cur_page = []
        y = ytop

    for kind, seg in lines:
        if kind == "h1":
            if y < ytop - 10:
                newpage()
            cur_page.append(("BT_F1_16", seg, x0, y))
            y -= lh + 8
        elif kind == "h2":
            if y <= ybot + 20:
                newpage()
            cur_page.append(("BT_F2_13", seg, x0, y))
            y -= lh + 4
        elif kind == "code":
            for cl in seg.split("\n"):
                if y <= ybot:
                    newpage()
                cur_page.append(("BT_CODE", cl, x0, y))
                y -= lh
            y -= 4
        else:
            wrapped = textwrap.wrap(seg, width=78) or [""]
            for wl in wrapped:
                if y <= ybot:
                    newpage()
                cur_page.append(("BT_BODY", wl, x0, y))
                y -= lh
    pages.append(cur_page)

    return _build_sequential(pages, path)


def _build_sequential(pages, path):
    """Build the PDF with sequential 1-based object numbering and correct refs."""
    objs = []  # each entry: bytes (the object body, without 'N 0 obj' wrapper)

    # We need font refs. Assign: 1=Catalog, 2=Pages, pages start at 3.
    n_pages = len(pages)
    page_first = 3
    content_first = page_first + n_pages
    font_f1 = content_first + n_pages          # helvetica-bold (titles)
    font_f2 = font_f1 + 1                       # helvetica-bold (h2)
    font_f3 = font_f1 + 2                       # courier (body + code)

    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")  # obj 1
    kids = " ".join("%d 0 R" % (page_first + i) for i in range(n_pages)).encode()
    objs.append(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n_pages))  # obj 2

    for i in range(n_pages):
        objs.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R /F3 %d 0 R >> >> "
            b"/Contents %d 0 R >>" % (font_f1, font_f2, font_f3, content_first + i)
        )
    for page in pages:
        stream = []
        for op, text, px, py in page:
            t = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            if op == "BT_F1_16":
                stream.append("BT /F1 16 Tf %d %d Td (%s) Tj ET" % (px, py, t))
            elif op == "BT_F2_13":
                stream.append("BT /F2 13 Tf %d %d Td (%s) Tj ET" % (px, py, t))
            elif op == "BT_CODE":
                stream.append("BT /F3 9 Tf 80 %d Td (%s) Tj ET" % (py, t))
            else:
                stream.append("BT /F3 11 Tf %d %d Td (%s) Tj ET" % (px, py, t))
        content = ("\n".join(stream) + "\n").encode("latin-1", "replace")
        objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content))
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    # Serialize with xref
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i
        out += body
        out += b"\nendobj\n"
    xref_offset = len(out)
    n_obj = len(objs) + 1
    out += b"xref\n0 %d\n" % n_obj
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (n_obj, xref_offset)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)
    return path


if __name__ == "__main__":
    p = build_pdf()
    print(f"Wrote {p} ({os.path.getsize(p)} bytes, {len(PATTERNS)} patterns)")
