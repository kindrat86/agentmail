
#!/usr/bin/env python3
"""Email template builder for agentmail. Returns HTML string for each email type."""

_HEADER = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>agentmail</title></head>
<body style="margin:0;padding:0;background-color:#f4f6f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f8">
<tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" style="max-width:560px;background-color:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
<tr><td style="padding:0">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#0f172a,#1e293b)">
<tr><td style="padding:32px 32px 24px;text-align:center">
<h1 style="margin:0;font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.3px">agent<span style="color:#14b8a6">mail</span></h1>
<p style="margin:4px 0 0;font-size:13px;color:#64748b;letter-spacing:0.3px">OFAC COMPLIANCE FOR AI AGENTS</p>
</td></tr></table></td></tr>
<tr><td style="padding:0 32px">CONTENT_BLOCK
</td></tr>
<tr><td style="padding:0">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;border-top:1px solid #e2e8f0">
<tr><td style="padding:24px 32px;text-align:center">
<p style="margin:0 0 8px;font-size:12px;color:#94a3b8;line-height:1.5">
agentmail &mdash; OFAC sanctions screening for AI agents<br>
<a href="https://sanctionsai.dev" style="color:#14b8a6;text-decoration:none">sanctionsai.dev</a>
&nbsp;&middot;&nbsp;
<a href="https://github.com/kindrat86/agentmail" style="color:#14b8a6;text-decoration:none">GitHub</a>
&nbsp;&middot;&nbsp;
<a href="https://sanctionsai.dev/pricing" style="color:#14b8a6;text-decoration:none">Pricing</a>
</p>
<p style="margin:0;font-size:11px;color:#cbd5e1">UNSUBSCRIBE_LINK</p>
</td></tr></table></td></tr></table>
<p style="margin:16px 0 0;font-size:11px;color:#94a3b8;text-align:center">You received this because you signed up for agentmail.</p>
</td></tr></table></body></html>"""

def build(subject, content_html, unsubscribe_url):
    """Build a complete email HTML with header, content, and footer."""
    unsub_link = f'<a href="{unsubscribe_url}" style="color:#cbd5e1;text-decoration:underline">Unsubscribe</a>'
    html = _HEADER.replace("CONTENT_BLOCK", content_html).replace("UNSUBSCRIBE_LINK", unsub_link)
    return html

def welcome_email(unsubscribe_url):
    """Build welcome email HTML."""
    content = (
        '<div style="text-align:center;padding:32px 0 24px">'
        '<div style="display:inline-block;background:#fef2f2;color:#dc2626;font-size:11px;font-weight:600;padding:4px 12px;border-radius:4px;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:16px">COMPLIANCE ALERT</div>'
        '<h2 style="margin:0 0 8px;font-size:20px;font-weight:700;color:#0f172a;line-height:1.3">Your AI agent just sent USDC<br>to a sanctioned wallet.</h2>'
        '<p style="margin:0;font-size:15px;color:#64748b;line-height:1.5">OFAC fines start at <strong style="color:#dc2626">$356,000 per violation</strong>. The agent that made the payment is yours. So is the liability.</p>'
        '</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;margin-bottom:24px"><tr><td style="padding:20px">'
        '<p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#0f172a">Your free tier is ready. No API key needed.</p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#1e293b;border-radius:6px"><tr><td style="padding:14px 16px;font-family:SF Mono,Consolas,monospace;font-size:13px;color:#34d399;line-height:1.6;word-break:break-all">curl "https://agentmail-api.fly.dev/sanctions?wallet=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"</td></tr></table>'
        '<p style="margin:6px 0 0;font-size:12px;color:#94a3b8">50 checks/day &middot; No signup &middot; Free forever</p>'
        '</td></tr></table>'
        '<h3 style="margin:0 0 16px;font-size:15px;font-weight:700;color:#0f172a">The 4 tools your agent needs</h3>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:0">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:12px 0;vertical-align:top;width:24px;font-size:13px;font-weight:700;color:#14b8a6">1</td><td style="padding:12px 0;vertical-align:top;font-size:13px;color:#475569"><strong style="color:#0f172a">sanctions_check</strong><br><span style="color:#94a3b8;font-size:12px">782 wallets, 19,086 names, 16 jurisdictions</span></td><td style="padding:12px 0;vertical-align:top;text-align:right;font-size:11px;color:#94a3b8;white-space:nowrap">VALUE $499</td></tr>'
        '<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:12px 0;vertical-align:top;width:24px;font-size:13px;font-weight:700;color:#14b8a6">2</td><td style="padding:12px 0;vertical-align:top;font-size:13px;color:#475569"><strong style="color:#0f172a">risk_score</strong><br><span style="color:#94a3b8;font-size:12px">Amount anomalies, rail risk, category exposure</span></td><td style="padding:12px 0;vertical-align:top;text-align:right;font-size:11px;color:#94a3b8;white-space:nowrap">VALUE $299</td></tr>'
        '<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:12px 0;vertical-align:top;width:24px;font-size:13px;font-weight:700;color:#14b8a6">3</td><td style="padding:12px 0;vertical-align:top;font-size:13px;color:#475569"><strong style="color:#0f172a">kya_verify</strong><br><span style="color:#94a3b8;font-size:12px">Know Your Agent trust scoring</span></td><td style="padding:12px 0;vertical-align:top;text-align:right;font-size:11px;color:#94a3b8;white-space:nowrap">VALUE $199</td></tr>'
        '<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:12px 0;vertical-align:top;width:24px;font-size:13px;font-weight:700;color:#14b8a6">4</td><td style="padding:12px 0;vertical-align:top;font-size:13px;color:#475569"><strong style="color:#0f172a">dispute_open</strong><br><span style="color:#94a3b8;font-size:12px">File disputes with 7-day auto-escalation</span></td><td style="padding:12px 0;vertical-align:top;text-align:right;font-size:11px;color:#94a3b8;white-space:nowrap">VALUE $99</td></tr>'
        '<tr><td style="padding:14px 0;font-size:12px;color:#94a3b8" colspan="2">Total value</td><td style="padding:14px 0;text-align:right;font-size:14px;font-weight:700;color:#0f172a"><span style="color:#94a3b8;text-decoration:line-through;font-weight:400">$1,096</span> &nbsp;$19<span style="font-size:11px;color:#64748b;font-weight:400">/mo</span></td></tr>'
        '</table></td></tr></table>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#f0fdfa,#ecfdf5);border:1px solid #14b8a630;border-radius:8px;margin-bottom:24px"><tr><td style="padding:20px;text-align:center">'
        '<p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#0f766e">The MCP tool your agent already needs</p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px auto"><tr><td style="background:#0f172a;border-radius:4px;padding:6px 14px;font-family:SF Mono,Consolas,monospace;font-size:13px;color:#14b8a6">pip install sanctions-mcp</td></tr></table>'
        '<p style="margin:6px 0 0;font-size:12px;color:#64748b">Add to Claude Code, Cursor, or Windsurf in 30 seconds</p>'
        '</td></tr></table>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:16px 0 0;text-align:center">'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto"><tr><td style="background:#14b8a6;border-radius:6px;padding:0"><a href="https://sanctionsai.dev/checkout/dev" style="display:inline-block;padding:14px 36px;font-size:14px;font-weight:600;color:#fff;text-decoration:none;background:#14b8a6;border-radius:6px">Upgrade to Dev &rarr;</a></td></tr></table>'
        '<p style="margin:6px 0 0;font-size:11px;color:#94a3b8">10,000 checks/month &middot; All 4 tools &middot; API key &middot; Audit log</p>'
        '</td></tr></table>'
    )
    return build("Your agentmail API key is ready", content, unsubscribe_url)
