# AgentPay Guard — Manual Test Scenarios Checklist (Voice Assistant & Safety Engine)

This document provides a 10-scenario manual test checklist designed for verifying the **Voice AI & Conversational Agents** integration alongside the deterministic spending safety engine for the GCET ASCEND showcase and evaluators.

---

## Pre-Requisites
1. Backend running: `cd backend && .\.venv\Scripts\uvicorn.exe app.main:app --port 8000`
2. Frontend running: `cd frontend && npm run dev`
3. Web browser: Google Chrome or Microsoft Edge (with microphone permission enabled).

---

## Test Scenarios Matrix

| # | Scenario Name | Test Steps | Expected Outcome | Verification Status |
| :-: | :--- | :--- | :--- | :---: |
| **1** | **Normal Purchase via Voice** | Click the microphone icon in AI Shopping tab. Say: *"Find a wireless mouse under $35 from an approved merchant"*. | Speech transcript appears in real time. Backend evaluates `ALLOWED`. Product card displays TechCore Wireless Mouse ($29.99). Spoken voice reads verdict aloud. | [ ] PASS |
| **2** | **Over-Limit Request via Voice** | Click microphone icon. Say: *"I need a high-end mechanical keyboard for typing"*. | Proposal returned as `BLOCKED` with reason `MAX_ORDER_AMOUNT_EXCEEDED` ($79.99 > $40 cap). Voice reads block reason aloud and states checkout is disabled. Smart alternatives are displayed. | [ ] PASS |
| **3** | **Unclear Speech Rejection** | Click microphone icon. Say random noise or filler words (e.g. *"uh um hello"* or silence). | System rejects with 422 message: *"Speech unclear. Please repeat your shopping request with an item name or description"*. **No proposal row created in DB, no order created, no PayPal call made**. | [ ] PASS |
| **4** | **Microphone Permission Denied** | In browser site settings (padlock in URL bar), set Microphone to **Block** and reload. Click the mic button. | Friendly amber banner appears: *"Microphone permission denied. Please allow microphone access in your browser or type your request."* UI remains fully functional. | [ ] PASS |
| **5** | **Unsupported Browser Graceful Fallback** | Open application in a browser without Web Speech API (or disable recognition via browser flag). | Microphone button is cleanly hidden. Natural-language text input remains 100% active and functional. No runtime JavaScript crashes. | [ ] PASS |
| **6** | **Mute / Unmute Toggle & Stop Audio** | Click "Voice Reply ON" in the shopping header to switch to "Muted". Run a shopping request. While audio is speaking, click "Stop". | When muted, no speech synthesis audio plays. Clicking "Stop" immediately silences in-progress speech playback (`window.speechSynthesis.cancel()`). | [ ] PASS |
| **7** | **Reset Demo State & Overview Counters** | Complete a purchase, then click **Reset Demo** on the Overview tab or Policy card. | Policy resets to $100 budget, $40 cap. Overview counters immediately show $0 spent, 0 completed purchases, 0 violations, and full $100 remaining. | [ ] PASS |
| **8** | **Human Approval Mandatory After Voice** | Speak an allowed purchase request. Inspect the Decision Card and Approvals tab. | **Voice cannot authorize or execute payment**. No order is created until user navigates to Approvals and explicitly clicks *"Explicitly Approve & Pay"*. | [ ] PASS |
| **9** | **Audit Trail Logging for Voice** | Submit a voice shopping request. Navigate to the **Audit Log** tab. | A `PROPOSAL_CREATED` event appears with `input_mode: "voice"`, recognized transcript, and deterministic `spoken_response` logged in event details. | [ ] PASS |
| **10** | **Seamless Fallback to Typing** | Click a quick demo chip or type *"Find a shadowtech gadget for my desk"* in the textarea and click **Propose Purchase**. | Text request processes through the exact same policy engine. Unapproved merchant ShadowTech is `BLOCKED` with `MERCHANT_NOT_APPROVED`. Spoken verdict reads result aloud. | [ ] PASS |

---

## Invariant Summary

1. **Safety Invariant:** `input_mode` ("text" vs "voice") has zero impact on policy outcomes, prices, or allowances.
2. **Authority Invariant:** Spoken verdicts are generated deterministically in Python backend code, not by generative hallucination.
3. **Consent Invariant:** Voice is purely conversational discovery. Payment execution strictly requires manual human click.

