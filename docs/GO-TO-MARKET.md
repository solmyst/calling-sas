# Initial commercial plan

Planning hypothesis, 2026-10-25. No customer demand, cost savings, production capacity or unit economics have been validated yet.

## First niche and offer

Start with independent automobile dealerships handling opted-in test-drive enquiries. Qualify vehicle interest, purchase timeframe and preferred visit time, then send a human-reviewed follow-up task. This is a bounded, measurable workflow with less sensitive content than clinical calls. Real estate qualification is a second option but has broad inventory/availability questions; coaching brings possible child-data issues; clinics add health-data and emergency boundaries. These are product judgments, not market survey findings.

Pitch: “We help your team follow up consistently on consented enquiries and hand over interested test-drive prospects with a clear conversation summary.” Demonstrate one prospect who qualifies, one who requests a later time, and one who asks an unsupported financing question and gets a human handoff request. Never portray the local browser demo as a completed phone integration.

## First customers and pilot

Build a list of 20 nearby dealerships; seek warm introductions and permission-based owner/manager conversations. Ask about monthly enquiry volume, response delays, current follow-up labour and lost contact reasons. Do not run automated cold outreach as customer acquisition.

Run a five-minute browser demo using fictional data, including interruption and an objection. Show the resulting transcript, outcome and next task. Offer a two-week paid pilot with one language/workflow, a bounded consented lead cohort and a usage cap, after telephone integration is tested if the pilot requires phone calls. Agree on baseline, lead eligibility, support scope and exit conditions before starting.

Measure attempted/connected calls, qualified leads, human-verified appointment requests, opt-outs, failures, cost per qualified lead and staff time. Attribute bookings only to confirmed scheduling results. Compare with a comparable baseline cohort; do not attribute all later sales to the bot. Convert when the customer agrees the measured outcome justifies the recurring fee. Expand workflow and concurrency only after monitoring and load testing.

## Pricing hypothesis and cost model

Proposed offer to test, not published pricing: ₹10,000 setup, ₹5,000 monthly management and support, plus metered usage. Offer the initial pilot at ₹5,000 plus capped usage, credited toward setup if converted. State support hours and included configuration changes. Validate willingness to pay through interviews.

Per-call variable cost = streaming STT session duration + TTS characters + LLM input/output tokens (including growing history) + telephone legs/rounding + retries. Add hosting, monitoring, storage, support labour, payment fees and applicable taxes. Do not promise unlimited calls.

For a transparent illustrative calculation: 5 minutes at Sarvam's listed pay-as-you-go STT ₹0.49/min plus 2,000 Bulbul v3 characters at ₹3/1,000 = ₹8.45 for speech services alone. This is an alternative all-Sarvam speech illustration, NOT the recommended AssemblyAI route's cost or a measured call. LLM, telephony, hosting, support and GST are additional. Rates checked on [Sarvam pricing](https://docs.sarvam.ai/api/getting-started/pricing); account contract controls actual billing.

Use the chosen AssemblyAI model's actual rate. Its streaming charges depend on open session duration, including idle time, so cleanup matters: [AssemblyAI billing](https://www.assemblyai.com/docs/faq/how-to-get-your-api-key). Measure 20 representative calls before setting a retail per-minute price. A 60% target variable gross margin implies a price of measured variable cost / 0.40; the platform fee must also cover fixed costs and support. This is a target, not a guarantee.

## First sellable version

Essential: reliable voice sessions, editable approved context, explicit mode labels, consent and suppression records, accurate history/outcomes, human follow-up, usage limits, secure authentication, customer separation, deletion/retention controls, monitoring and tested provider failure handling. Telephone adapter and verified outbound permissions are essential before selling automated phone outreach. Scheduling integration is essential before selling automatic bookings.

Later: broad CRM marketplace, automatic multi-workflow campaigns, self-service billing, sophisticated analytics, custom voice cloning and high concurrency. Existing single-workspace demo authentication is insufficient for multi-customer SaaS.

## India launch requirements

Commercial voice calling falls within TRAI's UCC/TCCCPR framework, including AI/robocalls. Before a phone pilot, work with the access/telephony provider on principal entity/telemarketer registration, applicable calling category and number series, consent/preference verification, permitted hours and opt-out handling. Requirements vary by call type; do not assume a lead spreadsheet or a normal mobile number permits automated promotional calling. See [TRAI guidance](https://www.trai.gov.in/what-spam-or-ucc). Confirm current provider implementation and applicable directions before launch.

Document business/operator roles, processing purpose, notice/consent where applicable, data minimization, access controls, vendor/subprocessor terms, cross-border processing, retention, deletion, grievance handling and breach response. Explain audio recording separately from transcript storage. Avoid children and health/financial advice in the first workflow. Do not assert universal India-only storage requirements without checking applicable restrictions and sector rules.

The DPDP Rules 2025 and Act have phased commencement; verify the effective provisions at the actual pilot date using [MeitY's official rules and enforcement materials](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digital-Personal-Data-Protection-Rules-2025%3B). Obtain an India privacy/telecom review before real-customer production; this document is a product readiness plan, not a legal opinion.

Deployment: HTTPS, least-privilege service identity, private secrets, restricted firewall, authenticated signaling, encrypted backups with restore tests, persistent database, session ownership and concurrency caps, structured redacted logs, health checks and process supervision. Evaluate TURN and provider egress. Record retention/deletion and incident procedures before collecting live customer conversations. Nothing has been deployed by this plan.
