# AgentPay Guard — GCET ASCEND Project Submission
## Theme: Voice AI & Conversational Agents

---

## 1. Problem Statement

As artificial intelligence systems evolve from conversational text assistants into autonomous agents capable of interacting with external tools, allowing them unconstrained access to payment credentials introduces severe financial risks:

1. **Hallucination & Prompt Injection Vulnerabilities:** Large Language Models (LLMs) cannot serve as security boundaries. A prompt injection or hallucinated recommendation can trigger unapproved purchases, charge inflated amounts, or divert funds to rogue merchants.
2. **Autonomous Budget Bleed:** Without deterministic, server-enforced spending limits, conversational agents can rapidly deplete personal or enterprise budgets across automated tasks.
3. **The Voice Checkout Vulnerability:** Voice-first conversational agents that execute checkout automatically risk accidental purchases from ambient speech, misheard background audio, or unauthorized third-party voices.

---

## 2. Solution Summary

**AgentPay Guard** establishes a deterministic trust and policy boundary between conversational AI agents and financial checkout:

- **Conversational Voice Shopping:** Users can speak natural-language requests using the browser's native Web Speech API (with interim live transcript display, mic permission handling, and mute controls).
- **Catalogue-Constrained Intent Resolution:** The AI model (Google Gemini or deterministic fallback) only identifies user intent and proposes a catalogue `product_id`. It has **no authority** over pricing, merchant identification, or payment execution.
- **Deterministic Spending Guardrails:** A server-side Python policy engine evaluates each proposal against hard rules:
  - Total organizational/personal budget limit
  - Per-order maximum spending cap
  - Calendar daily and monthly velocity limits
  - Approved merchant allowlist and category restrictions
  - Instant agent kill-switch
- **Deterministic Spoken Feedback:** The system deterministically synthesizes speech (`window.speechSynthesis` with Indian/US English voice preferences) stating the item, exact price in USD, policy decision (`ALLOWED` or `BLOCKED` with specific rule name), and an approval reminder.
- **Mandatory Human-in-the-Loop Checkout Gate:** Even when an item is within policy limits, voice cannot trigger checkout. The user must review the proposal and explicitly click to authorize the PayPal Sandbox order.
- **Server-Verified PayPal Sandbox Capture:** PayPal Orders v2 REST APIs run server-side with unique idempotency keys (`PayPal-Request-Id`) and server-side capture verification before budget deduction.
- **Immutable Audit Logging:** Every voice and text interaction, transcript, policy decision, approval, and capture is logged with millisecond timestamps in an append-only audit trail.

---

## 3. Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 19, Vite, TypeScript, Tailwind CSS, Lucide Icons |
| **Voice AI & Speech** | Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`), Web Speech Synthesis API (`SpeechSynthesisUtterance`) |
| **Backend API** | Python 3.11, FastAPI, Uvicorn, Pydantic v2 |
| **Database & ORM** | SQLite, SQLAlchemy 2 |
| **Payments** | PayPal Developer Platform — Orders v2 REST API (Sandbox, USD only) |
| **AI / LLM Adapter** | Google Gemini API (via OpenAI-compatible REST endpoint) + Deterministic Offline Fallback Matcher |
| **Testing Suite** | pytest, FastAPI TestClient (81 automated tests) |

---

## 4. Key Architectural Invariants

```text
[ User Voice / Speech ] ──► Web Speech API (Browser Recognition)
                                    │
                                    ▼ (Transcript + input_mode="voice")
[ FastAPI Backend ] ──────► Rule Engine Pre-Check (Reject unclear noise)
         │                          │
         ▼ (Valid speech)           ▼
[ Gemini / Fallback ] ──► Suggests product_id only
         │
         ▼
[ Deterministic Engine ] ──► Validates Cap, Budget, Allowlist against SQLite
         │
         ├──► Deterministic Spoken Response (Item, USD, Verdict, Approval Reminder)
         ├──► Logs to Immutable Audit Trail (input_mode="voice")
         ▼
[ Mandatory Human Gate ] ──► User explicitly clicks "Approve & Pay" in Approvals Tab
         │
         ▼
[ PayPal Sandbox Orders v2 ] ──► Authoritative Server-Side Capture & Verification
```

1. **Voice Boundary:** Voice is exclusively for conversational discovery. Voice can **never** authorize or pay.
2. **Authority Invariant:** Spoken verdicts are generated deterministically in Python backend code from the rule engine result.
3. **Deterministic Reset:** The "Reset Demo" capability restores budget and spend meters to pristine state without destroying historical audit logs.

---

## 5. Team Contributions

| Team Member | Role & Key Contributions |
| :--- | :--- |
| **Member 1: [Team Member 1 Name]** | Full-Stack Architecture, Deterministic Policy Engine, PayPal Sandbox Integration, and Backend Automated Test Suites. |
| **Member 2: [Team Member 2 Name]** | Voice Assistant Integration (Web Speech API Recognition & SpeechSynthesis), Frontend UI/UX, and Showcase Scenarios. |

