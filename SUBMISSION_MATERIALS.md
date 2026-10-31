# AgentPay Guard — PayPal AI Hackathon 2026 Submission Kit

> **Project Name:** AgentPay Guard  
> **Tagline:** A deterministic safety layer for AI shopping agents with human-in-the-loop PayPal Sandbox checkout.  
> **Built for:** PayPal AI Hackathon 2026  
> **Repository:** [https://github.com/amansheikh-techie/agentpay-guard](https://github.com/amansheikh-techie/agentpay-guard)

---

## 1. Project Description (Devpost Submission Copy)

### Elevator Pitch

AgentPay Guard provides an authoritative safety and policy layer between autonomous AI shopping agents and financial checkout. Users set granular spending caps and merchant allowlists; an AI recommends products from a catalogue; a deterministic backend policy engine independently verifies all rules; and the user explicitly authorizes every PayPal Sandbox payment before funds can be captured.

### Inspiration & Problem Statement

As generative AI agents advance from passive text assistants to autonomous purchasing agents, allowing them direct, unsupervised access to payment credentials creates catastrophic financial risks:

1. **Prompt Injections & Hallucinations:** An LLM cannot be the security boundary. If an attacker tricks the model into recommending a $500 item or buying from a fraudulent store, an agent with autonomous payment authority will execute the charge.
2. **Budget Creep:** Without deterministic accumulation tracking, small automated purchases quickly blow past organizational or personal budgets.
3. **The "Check-Out" Black Box:** Users are understandably reluctant to delegate purchasing to AI without complete transparency and an explicit authorization gate.

### What It Does

AgentPay Guard demonstrates a practical architecture for safe, AI-assisted commerce:

- **Deterministic Trust Boundary:** The AI agent only proposes product IDs. Authoritative pricing, merchant identity, and policy evaluation are executed exclusively by server-side Python code.
- **Spending Policies:** Users set total budgets, per-order caps, and merchant allowlists that are strictly enforced regardless of what the AI outputs.
- **Mandatory Human-in-the-Loop:** Even if an item is within policy limits, no payment order can be created without an explicit user authorization click.
- **PayPal Sandbox Orders v2:** Uses server-side PayPal REST APIs with idempotency keys (`PayPal-Request-Id`) and server verification on capture to guarantee accurate reconciliation.
- **Immutable Audit Trail:** Every proposal, policy decision, approval, capture, and cancellation is logged with millisecond timestamps and machine-readable reason codes.

### How the PayPal Developer Platform is Central

The PayPal developer platform is the core transaction engine of AgentPay Guard:

- **Server-Side Orders v2 API:** Implemented in `backend/app/services/paypal_service.py` to create orders with `intent=CAPTURE` using authoritative server-side prices converted from minor units (cents).
- **OAuth 2.0 Client Credentials:** Tokens are obtained securely on the server with in-memory caching to minimize latency.
- **Idempotency Protection:** Every order creation and capture call includes a unique idempotency key to prevent accidental duplicate charges.
- **Server Verification on Capture:** The app never marks a transaction successful based solely on frontend redirects or URL parameters. The backend verifies the PayPal API response (`status=COMPLETED`, matched amount, and currency) before deducting from the user's budget.
- **Clean Cancellation Flow:** If a user cancels in PayPal Sandbox, the transaction status is marked `cancelled` without touching the user's budget.

### How AI is Used

- **Natural-Language Understanding:** Users describe what they want in plain English (e.g., *"Find a wireless mouse for work, under $35, from an approved merchant"*).
- **Catalogue-Constrained Recommendation:** The AI service receives the user request alongside the available catalogue metadata. The model's sole job is to identify user intent and recommend a matching `product_id` with a structured rationale.
- **Robust Deterministic Fallback Mode:** When an external LLM API key is not configured, the platform activates a deterministic keyword-matching fallback engine clearly tagged in the UI as `Demo Fallback Mode`. This ensures evaluators can test all flows without needing paid API keys.

### What We Learned

- **Separation of Concerns:** Keep the generative layer strictly isolated from the financial layer. The LLM suggests; deterministic code validates; humans decide.
- **Monetary Precision:** Always use integer minor units (cents) end-to-end to avoid IEEE-754 floating-point inaccuracies.
- **Server-Side Truth:** Never accept pricing or merchant parameters from the client browser.

### Accomplishments We're Proud Of

- 35/35 automated unit and integration tests passing in `pytest` covering edge cases, policy violations, and idempotency.
- Zero secrets leaked: credentials are kept strictly in backend environment variables.
- One-click demo state reset to facilitate repeatable evaluations and live testing.

---

## 2. Technical Architecture & Trust Boundaries

```text
[ User Browser / React 18 UI ]
       │
       │ 1. Natural Language Shopping Prompt
       ▼
[ FastAPI Backend ] ── 2. Request + Catalogue ──► [ AI Model / Fallback Engine ]
       │                                                 │
       │ ◄────────── 3. Proposes Product ID only ────────┘
       │
       ├──► [ SQLite DB ] (Fetch Authoritative Price & Merchant)
       │
       ├──► [ Deterministic Policy Engine ] (Check Cap, Budget, Allowlist)
       │
       │ 4. Return Proposal + ALLOWED/BLOCKED + Reason Codes
       ▼
[ React Decision Card ]
       │
       │ 5. User clicks "Explicitly Approve & Pay" (Mandatory Gate)
       ▼
[ FastAPI Backend ] ── 6. Live Policy Re-Check + Authoritative Amount
       │
       ├──► [ PayPal Orders v2 Sandbox API ] (Creates Sandbox Order)
       │
       │ 7. Redirects to PayPal Sandbox Checkout
       ▼
[ PayPal Sandbox Buyer Approval ]
       │
       │ 8. Buyer Approves Test Payment
       ▼
[ FastAPI Capture Endpoint ] ── 9. Server Captures & Verifies Amount
       │
       ├──► Updates Payment to "captured"
       ├──► Reconciles Budget Spend (Idempotent)
       └──► Logs to Immutable Audit Trail
```

---

## 3. Scripted 2-Minute-40-Second Video Walkthrough

**Target Total Duration:** 2 minutes, 40 seconds (well under the 3:00 Devpost limit).

| Timestamp | Screen Action | Voiceover Narration |
| --- | --- | --- |
| **0:00 – 0:25** | Open dashboard (`http://localhost:5173`). Highlight header badges and Policy Overview ($100 budget, $40 cap, approved merchants). | *"Welcome to AgentPay Guard, a safety layer for AI-assisted shopping built for the PayPal AI Hackathon 2026. While AI agents are great at finding products, giving them direct access to your wallet is dangerous. AgentPay Guard enforces strict spending rules: AI proposes, deterministic code validates, and the human explicitly authorizes every payment."* |
| **0:25 – 0:50** | Click **Scenario A (Allowed)** quick button. Prompt appears: *"Find a wireless mouse under $35 from an approved merchant"*. Click **"Propose Purchase"**. | *"Let's test Scenario A. Our user asks for a wireless mouse under $35. The AI agent analyzes the request against our catalogue and recommends the TechCore Wireless Mouse. The server resolves the real price of $29.99 and evaluates our policy. It passes all checks: under the $40 cap and TechCore is an approved merchant. The proposal is marked ALLOWED BY POLICY."* |
| **0:50 – 1:25** | Point to the **Mandatory Approval Gate**. Click **"Explicitly Approve & Pay $29.99"**. Click **"Complete Buyer Approval in PayPal Sandbox"** (or show Sandbox login). Click **"Verify & Capture Sandbox Payment"**. | *"Notice that no payment occurred automatically. Autonomous spending is forbidden. To proceed, the user must explicitly click 'Approve & Pay'. Our backend calls the PayPal Orders v2 API with an idempotency key and server-side pricing. Once approved in the PayPal Sandbox, our server verifies the capture directly with PayPal and updates our remaining budget from $100 down to $70.01."* |
| **1:25 – 1:55** | Click **Scenario B (Blocked: Cap)** quick button. Prompt appears: *"I need a high-end mechanical keyboard"*. Click **"Propose Purchase"**. | *"Now let's test Scenario B: a prompt that exceeds our spending limit. The AI recommends a mechanical keyboard priced at $79.99. The policy engine immediately flags this as BLOCKED with the reason code MAX_ORDER_AMOUNT_EXCEEDED. Notice that checkout is completely disabled—no PayPal order can be created."* |
| **1:55 – 2:20** | Click **Scenario C (Blocked: Merchant)** quick button. Prompt appears: *"Find a shadowtech gadget for my desk"*. Click **"Propose Purchase"**. | *"In Scenario C, the request asks for a product from ShadowTech. The backend checks its merchant allowlist and immediately blocks the purchase with MERCHANT_NOT_APPROVED. Rules are enforced strictly on the server regardless of prompt wording."* |
| **2:20 – 2:40** | Scroll down to the **Audit Timeline**. Highlight recent events. Click **"Reset Demo"** in Policy Overview to show reset state. | *"Finally, our Immutable Audit Trail logs every proposal, policy verdict, and PayPal capture with millisecond timestamps. With a single click of 'Reset Demo', the entire environment returns to pristine state. AgentPay Guard demonstrates that AI commerce can be safe, transparent, and user-controlled with PayPal. Thank you!"* |

---

## 4. Screenshot Capture List

Capture these 5 screenshots for the Devpost gallery:

1. **`01_dashboard_overview.png`**  
   *View:* Full dashboard on clean boot.  
   *Highlight:* Header status badges (`PayPal Sandbox`, `API Online`), Policy Overview cards ($100 budget, $40 cap), and empty request panel.

2. **`02_scenario_a_allowed.png`**  
   *View:* Decision Card showing `ALLOWED BY POLICY` for the TechCore Wireless Mouse ($29.99).  
   *Highlight:* Green policy badge, authoritative server price, and explicit approval button.

3. **`03_scenario_b_blocked_cap.png`**  
   *View:* Decision Card showing `BLOCKED BY POLICY ENGINE` for the $79.99 Mechanical Keyboard.  
   *Highlight:* Red banner, reason code `MAX_ORDER_AMOUNT_EXCEEDED`, and disabled checkout warning.

4. **`04_scenario_c_blocked_merchant.png`**  
   *View:* Decision Card showing `BLOCKED BY POLICY ENGINE` for the ShadowTech item.  
   *Highlight:* Reason code `MERCHANT_NOT_APPROVED` and explanation bullet.

5. **`05_paypal_capture_and_audit.png`**  
   *View:* Verified capture banner with updated remaining budget ($70.01) and populated Audit Trail with timestamps.

---

## 5. AI Tools Disclosure

| Tool | Application & Scope |
| --- | --- |
| **Google Gemini / OpenAI** | Interprets natural-language shopping requests and extracts matching `product_id` from the server-supplied catalogue. |
| **Deterministic Fallback Engine** | Offline keyword scoring matcher used when API keys are absent, clearly labelled as `Demo Fallback Mode`. |
| **Google Antigravity Agent** | Used for pair-programming, scaffolding, full-stack implementation, testing, and documentation generation. |

---

## 6. Implemented MVP vs. Future Roadmap

### Implemented in MVP (Ready for Judging)

- ✅ Curated 11-product catalogue across 3 demo merchants in SQLite
- ✅ Deterministic policy engine enforcing caps, budget exhaustion, allowlists, and human approval gates
- ✅ Server-side PayPal Sandbox Orders v2 creation and capture verification
- ✅ Idempotency protection against duplicate captures and double budget spend
- ✅ Live interactive rule editor and demo state reset
- ✅ Real-time immutable audit logging
- ✅ 35/35 passing automated pytest tests and clean TypeScript build

### Future Roadmap (Post-Hackathon)

- 🔮 Multi-tenant user accounts with role-based budget allocations (e.g. employee vs. manager limits)
- 🔮 Real-time webhook listeners for asynchronous dispute and refund notifications
- 🔮 Integration with PayPal Subscriptions and Vault API for recurring agent allowances
