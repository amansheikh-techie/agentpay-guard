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
| Frontend | React 18 + Vite + TypeScript |
| Backend | Python 3.11 + FastAPI + Uvicorn |
| Persistence | SQLite + SQLAlchemy 2 |
| Validation | Pydantic v2 |
| Payments | PayPal Orders v2 REST API (Sandbox) |
| AI | Gemini or OpenAI-compatible via provider adapter + deterministic fallback |
| Tests | pytest + FastAPI TestClient |

---

## Prerequisites

- **Python 3.11+** — `python --version`
- **Node.js 18+** — `node --version`
- **npm 9+** — `npm --version`
- **Git** — `git --version`
- A **PayPal Developer** account (free) for sandbox credentials: https://developer.paypal.com/
- *(Optional)* A Gemini or OpenAI API key for live AI mode; the app runs in fallback mode without one.

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
AI_PROVIDER=gemini        # or "openai"
AI_API_KEY=your_api_key
AI_MODEL=gemini-1.5-flash # or gpt-4o-mini
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
| `AI_PROVIDER` | No | `gemini`, `openai`, or `none` (fallback) |
| `AI_API_KEY` | No | Provider API key — backend only, never in frontend |
| `AI_MODEL` | No | Model name for the selected provider |
| `PAYPAL_MODE` | Yes | Must be `sandbox` for this project |
| `PAYPAL_CLIENT_ID` | Yes* | Sandbox Client ID from developer.paypal.com |
| `PAYPAL_CLIENT_SECRET` | Yes* | Sandbox Client Secret — **never commit or expose** |
| `PAYPAL_BASE_URL` | No | `https://api-m.sandbox.paypal.com` |
| `PAYPAL_CURRENCY` | No | `USD` |

*Required for PayPal checkout flow. Without them, the UI shows a clear "PayPal unconfigured" message; all non-payment features still work.

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
| Gemini / OpenAI (optional) | Interprets user's natural-language shopping request and recommends a product **ID** from the backend-supplied catalogue. The model has no authority over price, merchant, policy outcome, or payment status. |
| Deterministic fallback | Keyword-matching engine that selects a catalogue product when no AI key is configured. Clearly labelled "Demo Fallback Mode" — never misrepresented as an LLM response. |

---

## Demo Scenarios

| Scenario | Setup | Expected Result |
|---|---|---|
| A — Allowed purchase | Budget $100, cap $40, approved merchant, product $30 | ALLOWED → user approves → PayPal Sandbox checkout → backend verifies capture |
| B — Over per-order limit | Same policy, product $55 | BLOCKED: `MAX_ORDER_AMOUNT_EXCEEDED` |
| C — Merchant not approved | Product $25, unapproved merchant | BLOCKED: `MERCHANT_NOT_APPROVED` |
| D — Budget exhausted | $80 spent, $30 product proposed | BLOCKED: `TOTAL_BUDGET_EXCEEDED` |
| E — Payment cancelled | User cancels PayPal checkout | Status: `cancelled` — budget unchanged |

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
