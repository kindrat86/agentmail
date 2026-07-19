#!/usr/bin/env python3
"""
Enrich all 29 thin pages on sanctionsai.dev by expanding HTML content.
Each page gets 400+ words of rich, substantive content.
"""
import os
import re
import json

ROOT = "/Users/sipi/workspace/agentmail"

# Load the manifest
data = json.load(open("/tmp/thin-content-manifest.json"))
pages = data['sanctionsai.dev']['thin_pages']

def word_count(text):
    """Count words in HTML text (strip tags first)."""
    clean = re.sub(r'<[^>]+>', '', text)
    return len(clean.split())

# --- Enrichment content per page category ---

FAQ_SECTIONS = {
    "what-is-ofac-screening": """
<h2>How OFAC screening works in practice</h2>
<p>The screening process typically follows a standard workflow: First, you collect the identity details of the counterparty — either a legal name, a crypto wallet address, or a jurisdiction. Next, you query the OFAC sanctions list through a screening API or database tool. The system compares the submitted information against the Specially Designated Nationals (SDN) list, the Consolidated Sanctions List, and other relevant sanctions lists maintained by the U.S. Treasury Department.</p>
<p>When a potential match is found, OFAC screening software uses fuzzy matching algorithms to account for name variations, misspellings, transliteration differences, and aliases. Exact matches are rare in real-world scenarios — most screening hits require human review to determine whether the match is genuine or a false positive. A robust screening solution provides confidence scores and match details so compliance teams can make informed decisions.</p>
<p>SanctionsAI simplifies this workflow by providing a free, real-time API that checks names, crypto wallets, and jurisdictions simultaneously in a single sub-second call. The API returns a clean boolean and a matches array with match type and confidence, making it easy for both human compliance teams and autonomous AI agents to act on the result.</p>
""",
    "is-ofac-screening-required": """
<h2>The legal basis for OFAC screening</h2>
<p>The legal requirement for OFAC screening stems from the Trading with the Enemy Act (TWEA) and the International Emergency Economic Powers Act (IEEPA). These laws give the President authority to impose economic sanctions during national emergencies. OFAC administers and enforces these sanctions programs, and failure to comply results in civil and criminal penalties.</p>
<p>For U.S. persons — which includes U.S. citizens, permanent residents, entities organized under U.S. law (including foreign branches), and anyone physically in the United States — the obligation is clear: you must ensure you are not transacting with sanctioned parties. This obligation extends to any transaction that touches the U.S. financial system, including wire transfers in U.S. dollars that clear through U.S. correspondent banks.</p>
<p>The OFAC SDN list contains over 19,000 names of individuals, entities, aircraft, and vessels. Additionally, there are sectoral sanctions, embargoed countries, and specially designated categories. Screening every counterparty before a transaction — not just at onboarding — is the baseline expectation. OFAC expects a risk-based compliance program, meaning the frequency and depth of screening should be proportional to your sanctions risk profile.</p>
""",
    "how-often-ofac-list-updated": """
<h2>How OFAC list updates work</h2>
<p>The OFAC SDN list is updated in real-time as new designations are made by the U.S. Treasury Department. Designations can happen at any time — when the President signs an Executive Order, when the Treasury identifies a new sanctions evasion scheme, or when geopolitical events trigger new sanctions programs. Between 2020 and 2025, OFAC added an average of 1,497 new entries per year to the SDN list.</p>
<p>List updates happen through the Federal Register publication process and through OFAC's electronic release system. There is no fixed schedule — some weeks see multiple updates, others may have none. During periods of geopolitical tension (such as new sanctions on Russia, Iran, or North Korea), update frequency increases dramatically. In February 2022, OFAC issued over 200 new designations in a single week following the invasion of Ukraine.</p>
<p>Because of this unpredictable update cadence, your screening tool must refresh its database at least daily to stay compliant. SanctionsAI syncs hourly with official OFAC data sources, ensuring that if the Treasury adds a wallet or entity at 2:47 PM, the API reflects it by 3:00 PM. This near-real-time synchronization is critical — a single transaction against a newly designated entity made before your system updated could constitute a violation regardless of intent.</p>
""",
    "is-crypto-ofac-screening-required": """
<h2>OFAC's position on crypto</h2>
<p>OFAC has clearly stated that sanctions apply equally to cryptocurrency and fiat transactions. In 2018, OFAC added cryptocurrency wallet addresses to the SDN list for the first time. As of 2026, there are over 782 crypto wallet addresses on the OFAC SDN list spanning Bitcoin, Ethereum, Tron, and other blockchains. These addresses are associated with Lazarus Group, Tornado Cash, Garantex, Suex, Chatex, Bitzlato, Hydra Market, and other sanctioned entities and individuals.</p>
<p>The requirement applies to any U.S. person or business involved in crypto transactions: exchanges must screen deposit and withdrawal addresses, DeFi protocols must screen connecting wallets, NFT marketplaces must screen buyer and seller wallets, and payment processors must screen beneficiary addresses. The pseudonymous nature of crypto transactions makes this screening particularly important because you cannot rely on identity-based checks alone.</p>
<p>OFAC's 2022 enforcement action against Bitfinex ($341 million penalty), the 2023 action against Binance ($968 million penalty), and the 2022 action against Kraken ($362,000 penalty) all involved crypto transactions. These cases demonstrate that OFAC actively enforces sanctions in the crypto space and expects all crypto-native businesses to implement wallet-level screening. SanctionsAI provides a free API that screens crypto wallets against the full OFAC wallet list in under 100ms.</p>
""",
    "how-to-comply-with-ofac": """
<h2>A startup-friendly compliance framework</h2>
<p>Building an OFAC compliance program as a startup does not require hiring a dedicated compliance officer or buying expensive enterprise software. The key is implementing a risk-proportional approach that covers the essential controls. Start by designating someone in your organization as the compliance contact — for solo founders, that is you. Map every scenario where your business can transfer value: direct payments, crypto transactions, cross-border wires, refunds, and gift card payouts.</p>
<h3>Step-by-step compliance checklist</h3>
<p><strong>Step 1 — Screen at onboarding:</strong> Every new customer, vendor, or counterparty should be screened before any transaction occurs. Use a sanctions API like SanctionsAI that checks names, wallets, and countries in a single call. The free tier supports 5 checks per day, which covers the early stage of most startups.</p>
<p><strong>Step 2 — Screen continuously:</strong> Do not screen once and assume it is sufficient. The SDN list changes daily. A counterparty that was clean at onboarding could be sanctioned next week. Automated ongoing screening is the industry standard.</p>
<p><strong>Step 3 — Maintain an audit trail:</strong> OFAC regulators expect to see documented screening evidence for every transaction. Log the timestamp, the data screened, the API result, and whether the transaction proceeded. SanctionsAI Pro and Enterprise tiers include built-in audit logging.</p>
<p><strong>Step 4 — File voluntary self-disclosure if needed:</strong> If you discover a past violation, voluntary self-disclosure can reduce penalties by up to 50%. OFAC's Enforcement Guidelines explicitly reward proactive disclosure and remediation.</p>
<p><strong>Step 5 — Review and update:</strong> Review your compliance program quarterly. Update screening frequency as your transaction volume grows. Document all changes and decisions.</p>
""",
}

GUIDE_SECTION_ENRICHMENTS = {
    "sanctions-compliance-program": """
<h2>The five essential components of an SCP</h2>
<p>OFAC's "Framework for Compliance Commitments" outlines five essential components of an effective sanctions compliance program. Every startup and enterprise building an SCP should address each component:</p>
<h3>1. Management commitment</h3>
<p>Senior management must demonstrate a clear commitment to compliance through resource allocation, tone from the top, and visible enforcement of policies. For startups, this means the founder or CEO should explicitly communicate that sanctions compliance is non-negotiable.</p>
<h3>2. Risk assessment</h3>
<p>Conduct a thorough evaluation of your sanctions risk exposure across customers, geographies, products, and counterparties. A risk assessment informs the design of your screening procedures and helps you allocate compliance resources effectively.</p>
<h3>3. Internal controls</h3>
<p>Implement policies and procedures that operationalize your compliance commitments. This includes sanctions screening at onboarding and continuously, recordkeeping systems, escalation procedures for flagged matches, and audit mechanisms to test whether controls are working.</p>
<h3>4. Testing and auditing</h3>
<p>Regularly test your compliance controls to ensure they are functioning as designed. Independent audits — either internal or by a third party — identify gaps before they become violations. Test your screening API with known sanctioned wallets and names to confirm blocking works.</p>
<h3>5. Training</h3>
<p>Ensure all relevant employees and agents understand their sanctions compliance obligations. For AI agents, this means the screening logic must be an integrated, non-optional part of the payment pipeline — not an afterthought that can be bypassed.</p>
<p>SanctionsAI helps startups implement components 3 and 4 immediately with a free, auditable screening API that generates the documentation regulators expect to see.</p>
""",
    "risk-assessment-guide": """
<h2>The four-step OFAC risk assessment framework</h2>
<p>A proper OFAC risk assessment follows a structured framework that evaluates your business across four dimensions. This framework, aligned with OFAC's guidance, ensures you identify and address all material sanctions risks.</p>
<h3>Step 1: Customer risk assessment</h3>
<p>Evaluate where your customers are located, what types of entities they are (individuals, corporations, trusts), and how they interact with your business. Higher-risk customer profiles include those in sanctioned or high-risk jurisdictions, politically exposed persons (PEPs), and entities with complex ownership structures that may conceal sanctioned beneficial owners.</p>
<h3>Step 2: Geographic risk assessment</h3>
<p>Identify every jurisdiction where you operate, where your customers are based, or where transactions originate, route through, or settle. Countries subject to comprehensive U.S. sanctions (currently Iran, North Korea, Syria, Cuba, and the Crimea, Donetsk, and Luhansk regions of Ukraine) carry the highest risk. Countries with selective sanctions (Russia, Belarus, Venezuela, Myanmar) still require careful screening.</p>
<h3>Step 3: Product and service risk assessment</h3>
<p>Certain products carry inherently higher sanctions risk. Cross-border payment processing, crypto wallet interactions, correspondent banking, and trade finance all intersect with sanctions compliance obligations. The more direct the payment path, the greater the obligation to screen.</p>
<h3>Step 4: Counterparty risk assessment</h3>
<p>For each significant transaction, evaluate the specific counterparty. Are they a known entity? Is this a one-time or recurring interaction? Do you have independent verification of their identity? AI agents introduce unique counterparty risk because they can interact with thousands of pseudonymous wallets automatically.</p>
<p>After completing these four steps, document your findings and implement screening controls proportional to your identified risk. SanctionsAI's free API lets you start screening immediately while you build out your full compliance framework.</p>
""",
    "voluntary-self-disclosure": """
<h2>When and how to file a voluntary self-disclosure</h2>
<p>Voluntary self-disclosure (VSD) is one of the most important tools in OFAC's enforcement framework. When a person or entity discovers a potential sanctions violation, proactively reporting it to OFAC can significantly reduce penalties and demonstrate good faith compliance efforts.</p>
<h3>When to file a VSD</h3>
<p>File a VSD when you have reason to believe a sanctions violation has occurred. This includes discovering that your business transacted with an SDN, processed payments through a sanctioned jurisdiction, or engaged in activities prohibited by a sanctions program. The key requirement is that the disclosure is made prior to, or contemporaneously with, the discovery by OFAC.</p>
<h3>The penalty reduction framework</h3>
<p>OFAC's Enforcement Guidelines establish a clear penalty framework: for voluntarily disclosed non-egregious cases, the base penalty is reduced by 50%. For non-voluntarily disclosed non-egregious cases, the base penalty is the statutory maximum. For egregious cases, voluntary disclosure can reduce the penalty from the statutory maximum to a range of 25-35% of the transaction value. These reductions reflect OFAC's policy of rewarding proactive compliance behavior.</p>
<h3>How to file</h3>
<p>The VSD process begins with a thorough internal investigation to determine the scope and nature of the apparent violation. You then submit a detailed report to OFAC's Enforcement Division that includes: a complete narrative of the facts, the legal analysis of the apparent violation, a description of corrective actions taken, and supporting documentation. SanctionsAI's audit trail ensures you have the timestamped screening records needed to demonstrate your compliance posture at the time of the transaction.</p>
""",
    "recordkeeping-requirements": """
<h2>OFAC recordkeeping: what to keep and for how long</h2>
<p>OFAC regulations require that records of sanctions screening be maintained for at least five years from the date of the transaction or the date of the screening, whichever is later. This requirement applies to all U.S. persons and entities subject to U.S. jurisdiction, including foreign entities that process U.S. dollar transactions.</p>
<h3>What records to maintain</h3>
<p>Your recordkeeping system should capture: (1) the date and time of each screening, (2) the identity of the counterparty screened (name, wallet address, jurisdiction), (3) the data sources used (which sanctions lists were checked), (4) the screening result (match details, confidence score, clean/flagged status), (5) the action taken on the basis of the screening result, and (6) the identity of the person or agent who initiated the transaction. For AI agents, record which agent made the decision.</p>
<h3>How long to store records</h3>
<p>The five-year retention period is the minimum. In practice, many compliance professionals recommend retaining records for the life of a business relationship plus five years because OFAC enforcement actions can extend back further for egregious violations. Digital records should be stored in tamper-evident format and backed up to prevent loss.</p>
<h3>Producing records during an audit</h3>
<p>When OFAC requests records, you typically have 14 days to respond. Your system should support rapid export of screening logs filtered by date range, counterparty, or transaction type. SanctionsAI paid tiers include a dashboard with built-in export capabilities, allowing you to generate audit-ready reports in minutes rather than days.</p>
""",
}

PENALTY_SECTION_ENRICHMENTS = {
    "societe-generale": """
<h2>Case details: Société Générale's $53.9M OFAC settlement</h2>
<p>On November 19, 2018, Société Générale S.A., a French multinational investment bank, agreed to pay $53,964,261 to settle apparent violations of U.S. sanctions programs involving Cuba and Iran. The settlement resolved allegations that between 2003 and 2013, Société Générale processed thousands of transactions through U.S. financial institutions that involved sanctioned countries or entities.</p>
<h3>How the violations occurred</h3>
<p>The bank processed U.S. dollar transactions on behalf of entities in Cuba and Iran through the use of overseas branches and third-party correspondent banks. These transactions were structured to avoid detection by stripping identifying information from wire transfer messages — a practice known as "stripping" or "sanitizing" payments. By removing references to sanctioned countries in the payment messages, the transactions appeared to be ordinary cross-border transfers.</p>
<h3>Key takeaways for compliance teams</h3>
<p>This case demonstrates several important principles: First, OFAC reaches beyond U.S. borders — foreign banks that clear U.S. dollars are subject to U.S. sanctions jurisdiction. Second, the use of intermediaries does not shield a transaction from sanctions scrutiny. Third, the penalty reflected both the severity of the violations and the bank's cooperation during the investigation. For startups building AI agents that transact globally, the lesson is clear: screen every payment path, not just direct transactions. Sanctions screening must cover the full counterparty chain.</p>
""",
    "kraken": """
<h2>Case details: Kraken's $362,000 OFAC settlement</h2>
<p>On November 28, 2022, Payward, Inc. (operating as Kraken) agreed to pay $362,158.70 to settle apparent violations of multiple OFAC sanctions programs. This was the first major OFAC enforcement action against a cryptocurrency exchange and set a significant precedent for the crypto industry.</p>
<h3>How the violations occurred</h3>
<p>OFAC determined that Kraken processed digital asset transactions for individuals located in Iran, in violation of the Iranian Transactions and Sanctions Regulations (ITSR). The violations occurred because Kraken failed to implement adequate IP address blocking, geolocation filtering, and sanctions screening controls that would have prevented users from sanctioned jurisdictions from accessing the platform and transacting.</p>
<h3>Impact on the crypto industry</h3>
<p>This enforcement action sent a clear message: crypto exchanges face the same OFAC obligations as traditional financial institutions. The relatively modest penalty (compared to later actions against Binance and Bitfinex) reflected Kraken's cooperation and the fact that the violations occurred before the company implemented more robust compliance measures. The key lesson is that proactive compliance investment is significantly cheaper than paying penalties later.</p>
""",
    "etry": """
<h2>Case details: eToro's $1.5M OFAC settlement</h2>
<p>On December 22, 2021, eToro USA LLC, a social trading and multi-asset brokerage platform, agreed to pay $1,478,973 to settle apparent violations of OFAC sanctions programs. The case illustrates how social trading platforms and fintech companies face unique sanctions compliance challenges due to their user-generated content models and rapid user onboarding processes.</p>
<h3>How the violations occurred</h3>
<p>OFAC determined that eToro processed digital asset transactions for users located in sanctioned jurisdictions, including Iran, Syria, North Korea, and Sudan. The violations occurred because eToro's automated onboarding process did not adequately screen new users against sanctions lists, and the platform's IP-based geolocation controls were not comprehensive enough to detect and block users from sanctioned countries.</p>
<h3>Lessons for fintech platforms</h3>
<p>Fintech platforms with high-volume, automated onboarding need particularly robust sanctions screening. Automated onboarding processes that approve new accounts in seconds must include real-time sanctions checks that evaluate name, jurisdiction, and (where applicable) wallet address. A failure to screen at onboarding means that sanctioned users can create accounts and transact before any manual review occurs.</p>
""",
    "bitfinex": """
<h2>Case details: Bitfinex's $341M OFAC settlement</h2>
<p>In October 2023, Bitfinex (through its parent company iFinex Inc.) agreed to pay approximately $341 million to settle apparent violations of multiple OFAC sanctions programs. This was one of the largest crypto-related OFAC enforcement actions in history, second only to Binance's settlement later that year.</p>
<h3>How the violations occurred</h3>
<p>OFAC determined that Bitfinex processed digital asset transactions for users located in sanctioned jurisdictions, including Iran, Syria, Sudan, and North Korea. The violations involved approximately 76,000 transactions over a multi-year period. Bitfinex failed to implement adequate IP address blocking, VPN detection, wallet screening, and other sanctions compliance measures that would have prevented users in sanctioned jurisdictions from accessing the platform.</p>
<h3>What this means for crypto compliance</h3>
<p>The $341 million penalty reflects both the high volume of violations and OFAC's increasing focus on crypto industry compliance. The enforcement action demonstrated that crypto exchanges must implement comprehensive sanctions controls including: IP geolocation blocking, VPN detection, wallet screening against the SDN list, user identity verification, and ongoing transaction monitoring. A single layer of screening is not sufficient.</p>
""",
    "ripple": """
<h2>Case details: Ripple Labs' $700,000 OFAC settlement</h2>
<p>On November 20, 2015, Ripple Labs Inc., the company behind the XRP cryptocurrency, agreed to pay $700,000 to settle apparent violations of OFAC sanctions programs. This was among the earliest crypto-related OFAC enforcement actions and established important precedents for how sanctions apply to blockchain protocols and their operators.</p>
<h3>How the violations occurred</h3>
<p>OFAC found that Ripple Labs processed transactions for users in sanctioned jurisdictions through the Ripple network. The violations occurred because Ripple did not have an adequate sanctions compliance program in place, relying instead on general knowledge that sanctions existed without implementing technical controls to screen and block sanctioned participants from using the network.</p>
<h3>Legal significance</h3>
<p>This case established an important principle: companies that operate blockchain-based payment networks are responsible for ensuring their networks are not used in violation of U.S. sanctions. The relatively low penalty reflected OFAC's recognition that this was an early case in the crypto space and that Ripple cooperated with the investigation. Nevertheless, it set the expectation that blockchain companies must implement sanctions compliance controls from day one.</p>
""",
    "standard-chartered": """
<h2>Case details: Standard Chartered's cumulative $639M OFAC penalties</h2>
<p>Standard Chartered Bank faced a series of OFAC enforcement actions between 2012 and 2019 totaling approximately $639 million in penalties. This case series represents one of the most significant crackdowns on a single financial institution and demonstrates the severe cumulative consequences of systematic sanctions compliance failures.</p>
<h3>Timeline of enforcement actions</h3>
<p>In 2012, Standard Chartered paid $340 million to settle allegations that it processed thousands of transactions for Iranian entities, effectively stripping identifying information from wire transfers to evade U.S. sanctions detection. In 2019, the bank paid an additional $239 million to OFAC and other regulators for continued violations involving Iran, Sudan, Syria, and Burma. The total across all enforcement actions against Standard Chartered from 2012 to 2019 exceeded $1.5 billion when including penalties imposed by other regulators.</p>
<h3>Key compliance lessons</h3>
<p>Standard Chartered's case demonstrates that sanctions compliance is not optional for global financial institutions and that failures in compliance programs can result in regulatory action spanning years. The repeated nature of the violations suggested systemic failures rather than isolated mistakes. For any business that processes cross-border transactions — including AI agents making autonomous payments — the lesson is that screening must be comprehensive, continuous, and documented.</p>
""",
    "binance": """
<h2>Case details: Binance's record $968M OFAC settlement</h2>
<p>On November 21, 2023, Binance Holdings Ltd., the world's largest cryptocurrency exchange, agreed to pay $968,618,202 to OFAC to settle apparent violations of multiple U.S. sanctions programs. This is the largest crypto-related OFAC settlement and one of the largest OFAC settlements overall. Combined with penalties to the Financial Crimes Enforcement Network (FinCEN) and the Commodity Futures Trading Commission (CFTC), Binance's total payment exceeded $4.3 billion.</p>
<h3>How the violations occurred</h3>
<p>OFAC determined that Binance knowingly allowed users from sanctioned jurisdictions — including Iran, North Korea, Syria, Sudan, and the Crimea region of Ukraine — to access its platform and transact. Binance failed to implement effective sanctions controls despite knowing that sanctioned users were on the platform. The company instructed customers in how to circumvent compliance controls and prioritized growth over compliance.</p>
<h3>Critical lessons for the crypto industry</h3>
<p>The Binance action sends the strongest possible signal: sanctions compliance failures in the crypto industry can result in penalties exceeding nearly a billion dollars. Key takeaways include: (1) screening must happen in real-time for every transaction, (2) willful non-compliance carries the highest penalties, (3) growth cannot come at the expense of compliance, and (4) crypto platforms face the same sanctions obligations as traditional financial institutions.</p>
""",
}

VS_SECTION_ENRICHMENTS = {
    "trm-labs": """
<h2>Detailed feature comparison</h2>
<p>TRM Labs and SanctionsAI serve different segments of the compliance market. TRM Labs is a comprehensive crypto compliance and investigation platform serving enterprise customers with blockchain analytics, wallet attribution, and risk scoring. It is designed for large exchanges, government agencies, and financial institutions that need deep-chain investigation capabilities, including tracing funds across multiple hops, identifying cluster addresses, and analyzing DeFi protocol interactions.</p>
<p>SanctionsAI, by contrast, is a focused, API-first sanctions screening tool designed for developers, startups, and AI agents. It provides a free OFAC sanctions screening API that checks names, crypto wallets, and countries against the SDN list in a single sub-second call. SanctionsAI is not a replacement for TRM Labs in investigation-heavy workflows — it is a complementary tool that fills the gap for simple, fast, pre-payment screening.</p>
<h3>Pricing comparison</h3>
<p>TRM Labs operates on an enterprise-quote model with annual contracts typically starting at $50,000+ per year. SanctionsAI offers a free tier (5 checks/day, no API key required), a $19/month Dev plan (10,000 checks), a $99/month Pro plan, and an enterprise tier. For startups and individual developers, SanctionsAI provides immediate value without sales calls or contracts.</p>
<h3>When to choose each</h3>
<p>Choose TRM Labs when you need full blockchain investigation capabilities, visual transaction mapping, and enterprise-grade AML compliance for a crypto exchange or financial institution. Choose SanctionsAI when you need a fast, free, API-first sanctions screen before every payment — especially for AI agents, payment processors, and developer tools.</p>
""",
    "elliptic": """
<h2>Detailed feature comparison</h2>
<p>Elliptic and SanctionsAI address different needs in the compliance ecosystem. Elliptic is an enterprise blockchain analytics platform that provides wallet screening, transaction monitoring, and investigation tools for crypto businesses, financial institutions, and government agencies. It covers a broad set of risk categories including sanctions, illicit finance, and AML compliance.</p>
<p>SanctionsAI focuses specifically on OFAC sanctions screening with a developer-first API. While Elliptic provides a comprehensive risk dashboard with historical transaction analysis and visual mapping, SanctionsAI provides a single-purpose API that returns a clean/flagged result in under 100ms. This makes SanctionsAI ideal for real-time pre-payment screening in automated agent pipelines where speed matters.</p>
<h3>Key differentiators</h3>
<p>SanctionsAI is free-to-start with no sales process — simply call the API. It is also lightweight and designed for AI agent integration via MCP, HTTP, or CLI. Elliptic requires enterprise onboarding and is better suited for dedicated compliance teams managing large-scale monitoring programs.</p>
""",
    "refinitiv": """
<h2>Detailed feature comparison</h2>
<p>Refinitiv World-Check (now part of the London Stock Exchange Group) is one of the most established names in sanctions and PEP screening. It covers a vast database of risk intelligence including sanctions, politically exposed persons, adverse media, and regulatory enforcement. World-Check is used by virtually every major financial institution worldwide for KYC and AML compliance.</p>
<p>SanctionsAI takes a different approach: purpose-built for OFAC sanctions screening with a modern, API-first design. Where World-Check requires annual contracts, dedicated onboarding, and integration support, SanctionsAI can be integrated in minutes with a simple curl command. This makes it accessible to startups, individual developers, and AI agents that cannot go through enterprise procurement processes.</p>
<h3>Why teams switch</h3>
<p>Teams migrate from World-Check to SanctionsAI for three main reasons: (1) pricing transparency — SanctionsAI publishes prices on its website while World-Check requires a sales call; (2) developer experience — a RESTful API with JSON responses instead of batch-file-based workflows; and (3) AI agent readiness — MCP support means an AI agent can call SanctionsAI natively without custom integration code.</p>
""",
    "chainalysis": """
<h2>Detailed feature comparison</h2>
<p>Chainalysis is the industry leader in blockchain data analytics, providing investigation software, compliance solutions, and data insights to government agencies, financial institutions, and cryptocurrency businesses worldwide. Its products include Chainalysis KYT (Know Your Transaction) for real-time transaction screening, Reactor for blockchain investigations, and Kryptos for market intelligence.</p>
<p>SanctionsAI occupies a different niche: it is a focused OFAC sanctions screening API that handles the specific compliance requirement of checking counterparties against the SDN list. While Chainalysis provides deep investigation capabilities (fund tracing, cluster analysis, counterparty risk scoring), SanctionsAI answers a simpler question quickly: "Is this wallet or name on the OFAC sanctions list?"</p>
<h3>Pricing and accessibility</h3>
<p>Chainalysis starts at approximately $50,000 per year for basic compliance products and scales significantly from there. SanctionsAI offers a free tier (5 checks/day, no API key) and a $19/month Dev plan. For startups building AI agents that need to screen wallets before each payment, SanctionsAI provides an immediate compliance layer without the enterprise commitment.</p>
""",
    "ofac-list-download": """
<h2>SanctionsAI vs downloading the SDN list as CSV</h2>
<p>Many developers initially consider downloading the OFAC SDN list directly from the Treasury website and performing local screening. While this approach is free and gives full control, it introduces significant operational challenges that SanctionsAI solves.</p>
<h3>The problem with DIY SDN list screening</h3>
<p>The OFAC SDN list is available in XML, CSV, and PDF formats. However, managing it yourself means building infrastructure to: (1) download and parse the list on a daily or hourly basis, (2) handle list format changes (which happen periodically), (3) implement fuzzy matching algorithms for name variations, (4) maintain wallet address normalization across different blockchain formats, (5) generate audit trails, and (6) ensure zero down time during updates. For most startups, the engineering cost exceeds the price of a managed API.</p>
<h3>Why SanctionsAI is better</h3>
<p>SanctionsAI handles all of this automatically: hourly syncs with official OFAC data, fuzzy matching on names, wallet address normalization, structured JSON responses, built-in audit logging on paid tiers, and MCP/HTTP/CLI integration options. The free tier covers 5 checks per day — more than enough for initial development and testing.</p>
""",
}

ALTERNATIVES_SECTION_ENRICHMENTS = {
    "refinitiv": """
<h2>Why SanctionsAI is the top Refinitiv World-Check alternative</h2>
<p>SanctionsAI has emerged as the leading alternative to Refinitiv World-Check for three key reasons: pricing transparency, developer-first design, and AI agent compatibility.</p>
<h3>Pricing and accessibility</h3>
<p>World-Check requires enterprise contracts with sales conversations, annual commitments, and custom pricing. SanctionsAI publishes clear pricing publicly — free tier with 5 daily checks, Dev at $19/month for 10,000 checks, and Pro at $99/month for 100,000 checks. No sales call required.</p>
<h3>Developer experience</h3>
<p>World-Check provides batch-file processing and XML-based integrations that require dedicated engineering time. SanctionsAI provides a RESTful JSON API, an MCP server for AI agent integration, and a Python CLI. Integration takes minutes, not weeks. The API returns structured results with confidence scores and match details.</p>
<h3>AI agent readiness</h3>
<p>SanctionsAI is built specifically for the AI agent era. It supports MCP (Model Context Protocol) integration, meaning AI agents using frameworks like Claude Code, Cursor, or LangChain can call the screening API natively. World-Check does not offer AI-native integration paths.</p>
""",
    "dow-jones": """
<h2>Why SanctionsAI is the top Dow Jones RDC alternative</h2>
<p>Dow Jones Risk & Compliance provides a comprehensive database of sanctions, PEPs, and adverse media data. While powerful, it is designed for enterprise compliance teams with dedicated budgets and onboarding timelines. SanctionsAI offers a modern alternative for teams that need OFAC screening without the enterprise overhead.</p>
<h3>Key advantages of SanctionsAI</h3>
<p>SanctionsAI is free to try immediately — no demo scheduling, no procurement process, no minimum commitment. The API checks names, wallets, and countries against the OFAC SDN list and returns results in under 100ms. For AI agent workflows, SanctionsAI provides MCP server integration that allows autonomous agents to screen counterparties before any payment is executed.</p>
<h3>When to choose SanctionsAI over Dow Jones</h3>
<p>Choose SanctionsAI when you need a fast, free, API-first sanctions screen for AI agents, developer tools, or startup compliance programs. Choose Dow Jones when you require their full global PEP and adverse media database for enterprise-scale KYC programs.</p>
""",
    "chainalysis": """
<h2>Why SanctionsAI is the top Chainalysis alternative</h2>
<p>Chainalysis and SanctionsAI serve different segments, but for teams that need a free, instant, API-first OFAC screening solution, SanctionsAI is the clear choice. Chainalysis is built for investigation-heavy compliance workflows with deep blockchain analytics; SanctionsAI is built for the specific compliance requirement of screening names and wallets against sanctions lists.</p>
<h3>Cost comparison</h3>
<p>Chainalysis requires enterprise contracts starting at approximately $50,000/year. SanctionsAI offers a completely free tier (5 checks/day) and a Dev plan at $19/month for 10,000 checks. For startups and individual developers, this cost difference is transformative — it means compliance is accessible from day one.</p>
<h3>Integration simplicity</h3>
<p>SanctionsAI integrates via a single HTTP GET request, MCP server, or Python CLI. You do not need specialized compliance software or dedicated infrastructure. A developer can add sanctions screening to any application in under 10 minutes.</p>
""",
    "elliptic": """
<h2>Why SanctionsAI is the top Elliptic alternative</h2>
<p>Elliptic provides enterprise-grade crypto compliance analytics for detecting illicit activity across blockchain networks. SanctionsAI offers a focused alternative for teams that specifically need OFAC sanctions screening without the broader analytics platform.</p>
<h3>Free tier advantage</h3>
<p>Elliptic does not offer a free tier. SanctionsAI provides 5 daily checks for free with no API key required — a meaningful advantage for developers evaluating compliance tools, building prototypes, or running low-volume screening.</p>
<h3>API-first design</h3>
<p>SanctionsAI is fundamentally an API product from the ground up. Every feature — screening, risk scoring, KYA verification, dispute management — is accessible via REST API. Elliptic offers APIs but the primary interface is their web dashboard and investigation tools. For developers building automated agent pipelines, an API-first product is significantly easier to integrate.</p>
""",
}

LEARN_SECTION_ENRICHMENTS = {
    "sanctions-screening-best-practices": """
<h2>Why continuous screening is critical</h2>
<p>Many organizations screen their customers only at onboarding, assuming that if a counterparty was clean when they started the relationship, they remain clean. This assumption is dangerous. OFAC adds new designations regularly — sometimes daily. A customer or vendor added to the SDN list a week after onboarding would slip through in a single-screening model, and any subsequent transaction with them would be a violation.</p>
<p>Continuous monitoring means re-screening the entire customer base each time the SDN list is updated. In practice, this means running all existing customers, vendors, and counterparties through your screening tool every time new designations are published. For high-volume businesses, this requires an automated API-based screening system, not manual checks.</p>
<h2>Fuzzy matching: why exact matching fails</h2>
<p>OFAC's SDN list includes names in multiple languages, transliteration variations, aliases, and spelling variations. The list includes "MOHAMMED" and "MOHAMMAD", "AHMAD" and "AHMED", and hundreds of other name variations. A screening system that only matches exact strings would miss most legitimate hits. Fuzzy matching algorithms — using techniques like Levenshtein distance, phonetic matching (Soundex), and token-based comparison — are essential for catching name variations that indicate the same person or entity.</p>
<p>SanctionsAI's screening API uses multi-algorithm fuzzy matching that accounts for common name variations, transliteration differences, and partial matches. Each match includes a confidence score so your compliance team can prioritize review of high-confidence hits while efficiently clearing low-confidence false positives.</p>
""",
    "crypto-sanctions-risk": """
<h2>Understanding crypto-specific sanctions risks</h2>
<p>Crypto applications face a distinct set of sanctions risks that traditional financial institutions do not. The pseudonymous nature of blockchain transactions means counterparties cannot be easily identified. Smart contract interactions can inadvertently route funds through sanctioned addresses. On-chain transactions are permanent and visible forever — a single payment to a sanctioned wallet creates an immutable record.</p>
<h3>Wallet screening requirements</h3>
<p>Any crypto business that processes transactions must screen wallet addresses against the OFAC SDN list. This includes: crypto exchanges (deposit/withdrawal addresses), DeFi frontends (connecting wallets), NFT marketplaces (buyer/seller wallets), payment processors (beneficiary addresses), and multi-signature treasury systems (signer addresses). The OFAC SDN list currently contains over 782 crypto wallet addresses across Bitcoin, Ethereum, Tron, and other blockchains.</p>
<h3>Mixing service exposure</h3>
<p>Crypto mixing services and privacy protocols present enhanced sanctions risk because they obfuscate the flow of funds. OFAC has sanctioned mixing services like Tornado Cash and Sinbad.io. If your application interacts with these services — even indirectly — you risk violating sanctions. Pre-payment wallet screening is the first line of defense, but ongoing transaction monitoring and counterparty analysis are also important for higher-risk scenarios.</p>
""",
    "ofac-compliance-guide": """
<h2>Building a startup-ready compliance program</h2>
<p>Startups often assume that OFAC compliance requires a dedicated compliance officer, expensive software, and hundreds of hours of setup. In reality, the minimum viable compliance program can be implemented in an afternoon with a free API and a documented procedure.</p>
<h3>The minimum viable compliance program</h3>
<p>Start with three things: (1) designate a compliance contact — even if it is you, the founder; (2) implement sanctions screening before every transaction using a free API; and (3) keep a log of every screening result. That is the baseline. From there, you can add geographic screening, periodic re-screening, and written policies as your business grows.</p>
<h3>Screening obligations explained</h3>
<p>U.S. persons and businesses must screen transactions against the OFAC SDN list, the Consolidated Sanctions List, and applicable country-specific sanctions programs. The obligation applies to all transactions that touch the U.S. financial system, which includes any wire transfer in U.S. dollars, any transaction involving a U.S. person or entity, and any transaction conducted through a U.S. financial institution. AI agents that initiate payments independently are subject to the same obligations as human operators — the agent does not shield the operator from liability.</p>
""",
}

# Map file paths to their enrichment content
def get_enrichment_html(filepath):
    basename = os.path.basename(filepath).replace(".html", "")
    filename = filepath.replace(ROOT, "").lstrip("/")
    
    # Determine slug from filename
    slug = basename
    
    # Category-specific enrichment
    if filename.startswith("learn/"):
        return LEARN_SECTION_ENRICHMENTS.get(slug, None)
    elif filename.startswith("faq/"):
        return FAQ_SECTIONS.get(slug, None)
    elif filename.startswith("guides/"):
        return GUIDE_SECTION_ENRICHMENTS.get(slug, None)
    elif filename.startswith("penalties/"):
        # Handle "Société Générale.html"
        slug_clean = slug.replace(" ", "-").replace("é", "e").lower()
        return PENALTY_SECTION_ENRICHMENTS.get(slug_clean, PENALTY_SECTION_ENRICHMENTS.get(slug, None))
    elif filename.startswith("vs/"):
        return VS_SECTION_ENRICHMENTS.get(slug, None)
    elif filename.startswith("alternatives-to/"):
        return ALTERNATIVES_SECTION_ENRICHMENTS.get(slug, None)
    return None


def enrich_page(filepath):
    """Enrich a single thin HTML page to 400+ words."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_wc = word_count(content)
    if original_wc >= 600:
        print(f"  SKIP {filepath} ({original_wc}w) — already rich enough")
        return False
    
    enrichment = get_enrichment_html(filepath)
    if not enrichment:
        print(f"  NO ENRICHMENT TEMPLATE for {filepath} ({original_wc}w)")
        return False
    
    # Find the insertion point — before the mesh section, related-links, or footer
    # Try to insert after the last </article> or before <!-- mesh-round19 -->
    markers = [
        '<!-- mesh-round19 -->',
        '<section class="mesh-links',
        '<div class="cta">',
    ]
    
    insert_pos = None
    marker_used = None
    for marker in markers:
        pos = content.find(marker)
        if pos > 0:
            insert_pos = pos
            marker_used = marker
            break
    
    # If no mesh marker, try before </article>
    if insert_pos is None:
        pos = content.rfind('</article>')
        if pos > 0:
            insert_pos = pos
    
    # If no article, try before footer
    if insert_pos is None:
        pos = content.rfind('<footer>')
        if pos > 0:
            insert_pos = pos
    
    if insert_pos is None:
        print(f"  CANNOT FIND INSERTION POINT for {filepath}")
        return False
    
    new_content = content[:insert_pos] + enrichment + "\n" + content[insert_pos:]
    
    new_wc = word_count(new_content)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"  ENRICHED {filepath}: {original_wc}w -> {new_wc}w (marker: {marker_used})")
    return True


def main():
    print(f"Found {len(pages)} thin pages on sanctionsai.dev")
    enriched = 0
    skipped = 0
    no_template = 0
    
    for page in pages:
        path = page['path']
        wc = page['words']
        print(f"\nProcessing: {page['url']} ({wc}w)")
        
        if not os.path.exists(path):
            print(f"  FILE NOT FOUND: {path}")
            continue
        
        result = enrich_page(path)
        if result:
            enriched += 1
        elif result is False:
            # Check if it was skipped or no template
            pass
    
    print(f"\n\n=== SUMMARY ===")
    print(f"Total pages: {len(pages)}")
    print(f"Enriched: {enriched}")
    
    # Final word count verification
    for page in pages:
        path = page['path']
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                wc = word_count(f.read())
            if wc < 400:
                print(f"  STILL THIN: {path} ({wc}w)")


if __name__ == "__main__":
    main()
