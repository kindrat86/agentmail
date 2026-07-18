[Research] I quantified OFAC sanctions exposure for autonomous AI agent payments — introducing the agentmail Sanctions Exposure Index (SEI)

I've been building sanctions screening for AI agents that pay autonomously (x402, AgentKit, etc.), and realized nobody has quantified the actual exposure. So I published the 2026 Agent-Payment Sanctions Exposure Report.

The SEI is a 5-factor model:
1. **Velocity** (30%) — unattended transactions/day
2. **Jurisdiction overlap** (25%) — counterparties in embargoed regions
3. **Asset class** (20%) — crypto has highest SDN wallet coverage
4. **Screening posture** (15%) — do you screen before payment?
5. **Disclosure readiness** (10%) — can you produce a VSD in 5 days?

Score 10 (min exposure) → 1000 (max). Worked example: an uncontrolled x402 agent doing 500 tx/day with 12% jurisdiction overlap = SEI 990/1000. Expected exposure ceiling: $165.5M/day.

The report includes real OFAC enforcement data (Binance $968M, Kraken $362K, EtherDelta $450K, etc.) and is CC BY 4.0 — cite freely.

Full report: https://sanctionsai.dev/research/agent-payment-sanctions-exposure-2026
Interactive calculator: https://sanctionsai.dev/tools/sei-calculator

Would love critique on the methodology — especially from compliance/legal folks who've dealt with OFAC.
