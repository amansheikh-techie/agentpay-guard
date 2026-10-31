# AgentPay Guard

> **Hackathon Prototype** — PayPal Sandbox only. No real money. Not a production financial product.

A safety layer for AI-assisted commerce built for the **PayPal AI Hackathon 2026**.

A user defines spending limits and approved merchants. An AI agent proposes a product from a controlled catalogue. A **deterministic backend policy engine** checks the proposal independently of the AI. The user must explicitly approve any eligible purchase before PayPal Sandbox checkout. The backend verifies the payment capture before recording a successful transaction.

**Core principle:** AI proposes → deterministic rules decide → human approves → backend verifies.

---

## Architecture

```
React UI  ──────── natural-language request ──────► FastAPI
   │                                                    │
   │                                        ┌───────────┤
   │                                        │  AI provider (proposal only)
   │                                        │  Catalogue  (authoritative data)
   │                                        │  Policy engine (deterministic)
   │◄───────── proposal + ALLOWED/BLOCKED ──┘
   │
   │  user explicitly clicks Approve
   ▼
FastAPI re-checks policy ──► PayPal Sandbox Orders API
   ▲                                │
   └──── verify/capture ◄─── buyer approval in PayPal
   │
   └──► SQLite: proposals, payments, audit events, budget state
```

**Trust boundary:** The backend is authoritative. The AI never sets price, merchant, policy outcome, or payment status. The frontend never supplies an authoritative amount.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite + TypeScript |
| Backend | Python 3.11 + FastAPI + Uvicorn |
| Persistence | SQLite + SQLAlchemy 2 |
| Validation | Pydantic v2 |
| Payments | PayPal Orders v2 REST API (Sandbox) |
| AI | OpenAI-compatible via provider adapter + deterministic fallback |
| Tests | pytest + FastAPI TestClient |

---

## Prerequisites

- **Python 3.11+** — `python --version`
- **Node.js 18+** — `node --version`
- **npm 9+** — `npm --version`
- **Git** — `git --version`
- A **PayPal Developer** account (free) for sandbox credentials: https://developer.paypal.com/
- *(Optional)* An OpenAI API key for live AI mode; the app runs in fallback mode without one.

---

## Setup (Windows PowerShell)

### 1. Clone the repository

```powershell
git clone https://github.com/amansheikh-techie/agentpay-guard.git
cd agentpay-guard
```

### 2. Backend setup

```powershell
cd backend

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy the environment template
Copy-Item .env.example .env
```

Open `backend\.env` in a text editor and fill in your credentials:

```ini
# PayPal Sandbox (required for payments)
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret

# AI Provider (optional — leave blank for deterministic fallback mode)
AI_PROVIDER=openai        # or "none"
AI_API_KEY=your_api_key
AI_MODEL=gpt-4o-mini

# Admin Security (optional in development; required in production)
ADMIN_TOKEN=your_secure_admin_token
```

> **NEVER commit `.env` to Git.** It is listed in `.gitignore`.

### 3. Run the backend

```powershell
# From the backend/ directory, with .venv activated
uvicorn app.main:app --reload --port 8000
```

Verify: open http://localhost:8000/api/health in your browser. You should see:
```json
{"status": "ok", "paypal_mode": "sandbox", ...}
```

Interactive API docs: http://localhost:8000/docs

### 4. Frontend setup (new terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the dashboard should load and show "API Online" in the header.

---

## Running Tests

```powershell
cd backend
.venv\Scripts\Activate.ps1
pytest tests/ -v
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | No | `development` (default) |
| `DATABASE_URL` | No | SQLite path, default `sqlite:///./agentpay_guard.db` |
| `FRONTEND_ORIGIN` | No | CORS origin for frontend, default `http://localhost:5173` |
| `ADMIN_TOKEN` | No* | Required outside `development` for `PUT /api/policy` and `POST /api/policy/reset` |
| `AI_PROVIDER` | No | `openai`, or `none` (fallback) |
| `AI_API_KEY` | No | Provider API key — backend only, never in frontend |
| `AI_MODEL` | No | Model name for the selected provider |
| `PAYPAL_MODE` | Yes | Must be `sandbox` for this project |
| `PAYPAL_CLIENT_ID` | Yes* | Sandbox Client ID from developer.paypal.com |
| `PAYPAL_CLIENT_SECRET` | Yes* | Sandbox Client Secret — **never commit or expose** |
| `PAYPAL_BASE_URL` | No | `https://api-m.sandbox.paypal.com` |
| `PAYPAL_CURRENCY` | No | `USD` |

*Required for PayPal checkout flow. Without them, the UI shows a clear "PayPal unconfigured" message; all non-payment features still work.
*`ADMIN_TOKEN` is verified using constant-time `secrets.compare_digest` via the `X-Admin-Token` header. Allowed without a token only when `APP_ENV=development`.

---

## Concurrency & Budget Safety

AgentPay Guard provides robust multi-order safety:
- **Budget Reservation:** When `POST /api/payments/create-order` evaluates spending policy, it counts not only settled transactions but also active in-flight orders (`pending`, `approved`, `capturing`, `needs_verification` created within the last 30 minutes via `reserved_cents()`). This prevents concurrent requests from exceeding the total budget.
- **Atomic Capture Claim:** In `capture_payment_order()`, the system atomically claims the payment record (`UPDATE payments SET status='capturing' WHERE status IN ('pending', 'approved')`). If another capture attempt is in progress, the second request immediately receives `409 Conflict`.
- **Pre-Capture Budget Recheck & Atomic Deduction:** The backend verifies that the budget remains sufficient before calling PayPal, and updates `successful_spend_cents` with an atomic SQL expression. On `ORDER_NOT_APPROVED`, the status safely reverts to `pending` so the buyer can complete checkout.

---

## PayPal Sandbox Setup

1. Sign up at https://developer.paypal.com/
2. Go to **Apps & Credentials → Create App** (Sandbox)
3. Copy **Client ID** and **Client Secret** into `backend/.env`
4. Use the auto-created sandbox buyer account (or create one under **Sandbox → Accounts**) to approve test payments

---

## AI Tools Used

| Tool | Role |
|---|---|
| OpenAI (optional) | Interprets user's natural-language shopping request and recommends a product **ID** from the backend-supplied catalogue. The model has no authority over price, merchant, policy outcome, or payment status. |
| Deterministic fallback | Keyword-matching engine that selects a catalogue product when no AI key is configured. Clearly labelled "Demo Fallback Mode" — never misrepresented as an LLM response. |

---

## Demo Scenarios

| Scenario | Setup | Expected Result |
|---|---|---|
| A — Allowed purchase | Budget $100, cap $40, approved merchant, product $30 | ALLOWED → user approves → PayPal Sandbox checkout → backend verifies capture |
| B — Over per-order limit (Smart Alternatives) | Same policy, user requests $79.99 mechanical keyboard | BLOCKED: `MAX_ORDER_AMOUNT_EXCEEDED` → Agent suggests in-policy alternatives (e.g. $29.99 mouse / $34.99 desk lamp) → user can click "Review this instead" and proceed to PayPal checkout |
| C — Merchant not approved | Product $25, unapproved merchant | BLOCKED: `MERCHANT_NOT_APPROVED` → In-policy alternatives suggested from approved allowlist |
| D — Budget exhausted | $80 spent, $30 product proposed | BLOCKED: `TOTAL_BUDGET_EXCEEDED` |
| E — Payment cancelled | User cancels PayPal checkout | Status: `cancelled` — budget unchanged |

---

## Smart Alternatives

When a user's request results in a **BLOCKED** primary recommendation (such as exceeding the per-order limit or targeting an unapproved seller):
1. **Plain-English Explanation:** The backend generates an easy-to-understand breakdown of why the item violated policy (`block_explanation`).
2. **Safe Suggestions:** The AI suggests candidate catalogue products, and the deterministic policy engine verifies each candidate against active limits. Up to 2 verified **ALLOWED** alternatives are returned.
3. **Seamless Transition:** Each alternative is persisted with its own proposal ID. In the UI, users can simply click **"Review this instead →"** to make the alternative their active proposal, unlocking the standard "Approve & Pay" PayPal Sandbox checkout flow.
4. **Strict Trust Boundary Preserved:** The AI only suggests product IDs and rationales. Prices, merchant allowlists, and policy decisions come strictly from the server-side database and policy engine. Any unknown product ID is discarded.

---

## Deployment Notes

- Set `APP_ENV=production` when deploying.
- Configure a strong `ADMIN_TOKEN` in the environment; all policy modification endpoints (`PUT /api/policy` and `POST /api/policy/reset`) enforce `X-Admin-Token` authentication outside development mode.
- Set `FRONTEND_ORIGIN` to match your deployed web client URL to configure CORS properly.
- Ensure PayPal credentials and AI API keys are provided only to the server via environment variables and never exposed to client-side bundles.

---

## Limitations

- Hackathon prototype — not production-grade security.
- Uses a curated local demo catalogue; does not scrape live stores.
- PayPal Sandbox only — no real money is ever charged.
- Single demo policy (no multi-user isolation in MVP).
- The AI is not a trust boundary; it only suggests product IDs.

---

## Hackathon Submission Materials

For the full Devpost submission description, video recording script, screenshot checklist, and evaluation guide, see [SUBMISSION_MATERIALS.md](./SUBMISSION_MATERIALS.md).

---

## Licence

MIT — see [LICENSE](./LICENSE).
