"""Buyer instructions for the existing x402 handler, not payment proof."""

def render():
    return '''<section><h1>x402 sanctions screening quickstart</h1>
<p>Inspect the challenge for free before authorizing any payment. No API key is required on this route.</p>
<h2>1. Request the payment contract</h2>
<pre><code>curl -i 'https://sanctionsai.dev/x402/sanctions?name=ACME'</code></pre>
<p>An unsigned request returns HTTP 402, not a screening result. Decode the base64 JSON in the <code>Payment-Required</code> header. Check the amount, asset, network and payTo address before signing. The standard price is 50000 atomic USDC units ($0.05) on Base (<code>eip155:8453</code>); the returned challenge is authoritative.</p>
<h2>2. Authorize and retry</h2>
<p>Use an x402 v2-compatible client and a wallet you control with sufficient USDC on Base. The client signs a payment authorization and retries the same request with a <code>Payment-Signature</code> header. Do not send a separate manual transfer. Never paste private keys into this site.</p>
<pre><code>curl -i 'https://sanctionsai.dev/x402/sanctions?name=ACME' \\
  -H 'Payment-Signature: &lt;base64-signed-payment-authorization&gt;'</code></pre>
<p>The placeholder is not a valid signature. The server verifies and settles the authorization through its facilitator before screening. A rejected payment returns 402, not a successful screen.</p>
<h2>3. Inspect the result</h2>
<p>A successful request returns HTTP 200, screening JSON (<code>clean</code> and <code>matches</code>), and a base64 JSON <code>Payment-Response</code> receipt. This page does not show a real payment or customer result.</p>
<p>Supply at least one of <code>name</code>, <code>wallet</code> or <code>country</code>. A signed request with no subject returns 400 before settlement. An unconfigured payment service returns 503. An unsigned challenge does not charge your wallet.</p>
<p>Screening is a control, not legal advice or a certification of compliance. A no-match result does not guarantee a counterparty is safe.</p>
<p><a href="/docs">API documentation</a> | <a href="/pricing">Subscription options</a></p>
<p>By SanctionsAI team. Updated 2026-09-06.</p></section>'''
