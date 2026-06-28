#!/usr/bin/env python3
"""
agentmail live SMS test (5sim) — proves the real receive path end-to-end.

Usage:
  export AGENTMAIL_FIVESIM_KEY=your_key_here
  python3 live_test_sms.py [product] [country]
    # defaults: product=telegram, country=russia  (telegram is widely available + cheap)

Flow:
  1. show balance
  2. rent a number (cheapest we can find for the product)
  3. PRINT the number and tell you to trigger an OTP there
  4. poll up to 180s for the SMS
  5. extract + print the code
  6. finish the activation (release)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("AGENTMAIL_SMS_PROVIDER", "fivesim")
if "AGENTMAIL_FIVESIM_KEY" not in os.environ:
    print("ERROR: set AGENTMAIL_FIVESIM_KEY first (get one at https://5sim.net)")
    sys.exit(1)

from agentmail import core

product = sys.argv[1] if len(sys.argv) > 1 else "telegram"
country = sys.argv[2] if len(sys.argv) > 2 else "russia"
label = f"live-{product}"

print("=" * 60)
print(f"  5SIM LIVE TEST   product={product}  country={country}")
print("=" * 60)

# 1. balance
st = core.sms_status()
print(f"\n[1/5] Provider: {st.get('provider')}  ready={st.get('ready')}  balance={st.get('balance')}")
if not st.get("ready"):
    print("  ✗ provider not ready — check your key")
    sys.exit(1)

# 2. rent
print(f"\n[2/5] Renting number for '{product}' in '{country}'...")
try:
    num = core.create_number(label=label, country=country, service=product)
except RuntimeError as e:
    print(f"  ✗ rent failed: {e}")
    print("  → try: python3 live_test_sms.py telegram russia")
    print("  → or:  python3 live_test_sms.py discord usa")
    sys.exit(1)
print(f"  ✓ rented: {num['number']}  (id={num['id']})")

# 3. tell user to trigger OTP
print("\n" + "=" * 60)
print(f"  👉 GO NOW: use this number to register on {product.upper()}")
print(f"     {num['number']}")
print("  (it's a real number. Enter it in the app's phone-verify step.)")
print("=" * 60)
print("\n[3/5] Waiting for the OTP SMS (polling up to 180s)...")

# 4. poll
t0 = time.time()
sms = core.fetch_sms(label=label, wait=180)
dt = time.time() - t0

# 5. result
if sms:
    print(f"\n[4/5] ✓ SMS received in {dt:.0f}s")
    print(f"   from: {sms.get('from')}")
    print(f"   text: {sms.get('text')}")
    print(f"\n   ★ OTP CODE: {sms.get('code')}")
else:
    print(f"\n[4/5] ✗ no SMS received after {dt:.0f}s")
    print("   (did you actually trigger an OTP to that number? number may have expired)")

# 6. release
print("\n[5/5] Releasing number...")
try:
    core.release_number(label=label)
    print("  ✓ released")
except Exception as e:
    print(f"  release: {e}")

print("\nDone. ✅" if sms else "\nDone (no OTP). Check the number worked on the app side.")
