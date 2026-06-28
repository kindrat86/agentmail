#!/usr/bin/env python3
"""
agentmail CLI — email + SMS verification for AI agents.

  python -m agentmail.cli create signup --prefix bot
  python -m agentmail.cli latest signup --wait 90 --from noreply
  python -m agentmail.cli list

  python -m agentmail.cli number signup --country usa --service discord
  python -m agentmail.cli sms signup --wait 90
  python -m agentmail.cli release signup
  python -m agentmail.cli status
"""
from __future__ import annotations
import argparse
import json
from . import core


def main():
    ap = argparse.ArgumentParser(prog="agentmail")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="create (or reuse) an email inbox")
    c.add_argument("label"); c.add_argument("--prefix", default=None)

    f = sub.add_parser("latest", help="fetch latest email message")
    f.add_argument("label"); f.add_argument("--wait", type=float, default=0)
    f.add_argument("--from", dest="match_from", default=None); f.add_argument("--subject", default=None)

    sub.add_parser("list")

    n = sub.add_parser("number", help="rent an SMS phone number")
    n.add_argument("label"); n.add_argument("--country", default="any"); n.add_argument("--service", default="any")

    s = sub.add_parser("sms", help="fetch latest SMS/OTP for a number")
    s.add_argument("label"); s.add_argument("--wait", type=float, default=90)

    r = sub.add_parser("release", help="stop renting a number")
    r.add_argument("label")

    sub.add_parser("status", help="show SMS provider status")

    # ── compliance ──
    kya = sub.add_parser("kya", help="verify an agent's identity (Know Your Agent)")
    kya.add_argument("agent_id")
    kya.add_argument("--wallet", default=None)
    kya.add_argument("--wallet-age", type=int, default=0)
    kya.add_argument("--domain", default=None)
    kya.add_argument("--pubkey", default=None)
    kya.add_argument("--owner-email", default=None)
    kya.add_argument("--country", default=None)

    risk = sub.add_parser("risk", help="score a transaction's fraud risk before payment")
    risk.add_argument("counterparty_id")
    risk.add_argument("amount")
    risk.add_argument("--currency", default="USDC")
    risk.add_argument("--rail", default="x402")
    risk.add_argument("--category", default="digital_goods")

    san = sub.add_parser("sanctions", help="screen against OFAC/EU/UN/UK lists")
    san.add_argument("--name", default="")
    san.add_argument("--wallet", default="")
    san.add_argument("--country", default="")

    dsp = sub.add_parser("dispute", help="open a dispute on a transaction")
    dsp.add_argument("transaction_id")
    dsp.add_argument("reason")
    dsp.add_argument("--evidence", default=None, help="JSON string of evidence")

    sub.add_parser("compliance-status", help="show compliance provider status")

    args = ap.parse_args()
    if args.cmd == "create":
        print(json.dumps(core.create_inbox(label=args.label, prefix=args.prefix), indent=2))
    elif args.cmd == "latest":
        m = core.fetch_latest(args.label, wait=args.wait, match_from=args.match_from, match_subject=args.subject)
        print(json.dumps(m or {"empty": True}, indent=2))
    elif args.cmd == "list":
        print(json.dumps(core.list_inboxes(), indent=2))
    elif args.cmd == "number":
        print(json.dumps(core.create_number(label=args.label, country=args.country, service=args.service), indent=2))
    elif args.cmd == "sms":
        print(json.dumps(core.fetch_sms(args.label, wait=args.wait) or {"empty": True}, indent=2))
    elif args.cmd == "release":
        print(json.dumps(core.release_number(args.label), indent=2))
    elif args.cmd == "status":
        print(json.dumps(core.sms_status(), indent=2))
    elif args.cmd == "kya":
        evidence = {}
        if args.wallet: evidence["wallet_address"] = args.wallet
        if args.wallet_age: evidence["wallet_age_days"] = args.wallet_age
        if args.domain: evidence["domain"] = args.domain
        if args.pubkey: evidence["pubkey"] = args.pubkey
        if args.owner_email: evidence["owner_email"] = args.owner_email
        if args.country: evidence["declared_country"] = args.country
        print(json.dumps(core.kya_verify(args.agent_id, evidence), indent=2))
    elif args.cmd == "risk":
        print(json.dumps(core.risk_score(args.counterparty_id, args.amount,
                                         currency=args.currency, rail=args.rail,
                                         category=args.category), indent=2))
    elif args.cmd == "sanctions":
        print(json.dumps(core.sanctions_check(name=args.name, wallet=args.wallet,
                                              country=args.country), indent=2))
    elif args.cmd == "dispute":
        ev = json.loads(args.evidence) if args.evidence else None
        print(json.dumps(core.dispute_open(args.transaction_id, args.reason, ev), indent=2))
    elif args.cmd == "compliance-status":
        print(json.dumps(core.compliance_status(), indent=2))


if __name__ == "__main__":
    main()
