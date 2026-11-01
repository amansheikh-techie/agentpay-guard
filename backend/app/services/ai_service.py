"""
services/ai_service.py — AI shopping agent recommendation service.

Architecture & Trust Boundary:
- The AI is NOT the security boundary.
- The AI receives ONLY the user request and backend-supplied product catalogue.
- The AI can ONLY propose product_ids from the catalogue; it CANNOT set price,
  merchant identity, policy decision, budget remaining, or payment status.
- If AI credentials are not configured or the call fails, a deterministic fallback
  engine selects the best matching products and labels the output clearly.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)


class AICandidate(BaseModel):
    product_id: str
    reason: str = ""


class AIRecommendation(BaseModel):
    product_id: str
    rationale: str
    matched_requirements: list[str] = Field(default_factory=list)
    unmet_requirements: list[str] = Field(default_factory=list)
    confidence_note: str = ""
    candidates: list[AICandidate] = Field(default_factory=list)


class AIProposalResult(BaseModel):
    recommendation: AIRecommendation
    ai_mode: str  # "live" | "fallback"


def _deterministic_fallback(user_request: str, catalogue: list[dict[str, Any]]) -> AIRecommendation:
    """
    Deterministic rule-based keyword matcher when no live LLM API is available.
    Guarantees a valid product_id from the provided catalogue and provides a ranked list
    of up to 3 candidates (keyword matches first, then cheapest remaining products).
    """
    req_lower = user_request.lower()
    scored_products: list[tuple[int, int, dict[str, Any]]] = []

    for prod in catalogue:
        score = 0
        name = prod.get("name", "").lower()
        desc = prod.get("description", "").lower()
        merchant = prod.get("merchant_name", "").lower()
        merchant_id = prod.get("merchant_id", "").lower()
        features = [f.lower() for f in prod.get("features", [])]
        price_cents = prod.get("price_cents", 0)

        # Tokenize user request into words
        tokens = set(re.findall(r"\b[a-z0-9]+\b", req_lower))

        for token in tokens:
            if len(token) < 3:
                continue
            if token in name:
                score += 5
            if token in desc:
                score += 2
            if token in merchant or token in merchant_id:
                score += 4
            for f in features:
                if token in f:
                    score += 3

        # Exact word matches
        if any(w in req_lower for w in ["mouse", "mice"]) and "mouse" in name:
            score += 10
        if "monitor" in req_lower and "monitor" in name:
            score += 10
        if "chair" in req_lower and "chair" in name:
            score += 10
        if "keyboard" in req_lower and "keyboard" in name:
            score += 10
        if "headset" in req_lower and "headset" in name:
            score += 10
        if "hub" in req_lower and "hub" in name:
            score += 10

        scored_products.append((score, price_cents, prod))

    # Rank: highest score first; if tied, cheapest price first
    scored_products.sort(key=lambda item: (-item[0], item[1]))

    best_product = scored_products[0][2] if scored_products else None

    # Build ranked candidates list (up to 3 distinct items)
    candidates: list[AICandidate] = []
    seen_ids = set()
    for s, p_cents, prod in scored_products:
        pid = prod["id"]
        if pid not in seen_ids:
            seen_ids.add(pid)
            if s > 0:
                reason = f"Keyword match for '{prod.get('name')}'"
            else:
                reason = f"Affordable alternative '{prod.get('name')}'"
            candidates.append(AICandidate(product_id=pid, reason=reason))
            if len(candidates) >= 3:
                break

    matched = []
    unmet = []
    if best_product:
        matched.append(f"Found product category matching keywords: {best_product.get('name')}")
        if best_product.get("merchant_name"):
            matched.append(f"Sold by {best_product.get('merchant_name')}")
        rationale = (
            f"[Demo Fallback Mode - No LLM API Key Configured] "
            f"Selected '{best_product.get('name')}' by deterministic keyword matching. "
            f"Note: Backend policy engine will independently enforce all budget and merchant rules."
        )
        return AIRecommendation(
            product_id=best_product["id"],
            rationale=rationale,
            matched_requirements=matched,
            unmet_requirements=unmet,
            confidence_note="Deterministic keyword scoring (offline fallback mode).",
            candidates=candidates,
        )

    # Edge case: empty catalogue
    return AIRecommendation(
        product_id="",
        rationale="No products available in catalogue.",
        confidence_note="Fallback unable to match empty catalogue.",
        candidates=[],
    )


def _call_openai(user_request: str, catalogue: list[dict[str, Any]], settings: Any) -> AIRecommendation:
    """Call OpenAI API in JSON mode with support for ranked candidate suggestions."""
    import httpx

    simplified_catalogue = [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "merchant_id": p["merchant_id"],
            "merchant_name": p["merchant_name"],
            "price_usd": f"${p['price_cents'] / 100:.2f}",
            "features": p.get("features", []),
        }
        for p in catalogue
    ]

    system_prompt = (
        "You are an AI purchasing assistant for AgentPay Guard.\n"
        "Your task: recommend a primary product_id and up to 2 alternative product_ids from the provided catalogue that best match the user's request.\n"
        "STRICT SECURITY RULES:\n"
        "1. You MUST select product_ids that appear in the catalogue.\n"
        "2. You DO NOT determine price, policy eligibility, remaining budget, or payment approval.\n"
        "3. Output MUST be valid JSON adhering strictly to this schema:\n"
        "{\n"
        '  "product_id": "<exact_primary_id_from_catalogue>",\n'
        '  "rationale": "<why this product fits user request>",\n'
        '  "matched_requirements": ["<requirement 1>", "<requirement 2>"],\n'
        '  "unmet_requirements": ["<any requirement not met>"],\n'
        '  "confidence_note": "<brief confidence note>",\n'
        '  "candidates": [\n'
        '    {"product_id": "<exact_id_from_catalogue>", "reason": "<short 1-line reason>"}\n'
        '  ]\n'
        "}"
    )

    user_prompt = f"User Request: {user_request}\n\nAvailable Catalogue:\n{json.dumps(simplified_catalogue, indent=2)}"

    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.ai_model or "gpt-4o-mini",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    with httpx.Client(timeout=15.0) as client:
        resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        rec = AIRecommendation.model_validate(parsed)
        # Ensure candidates includes at least the primary product_id
        if not rec.candidates and rec.product_id:
            rec.candidates = [AICandidate(product_id=rec.product_id, reason=rec.rationale)]
        elif rec.candidates and rec.product_id not in [c.product_id for c in rec.candidates]:
            rec.candidates.insert(0, AICandidate(product_id=rec.product_id, reason=rec.rationale))
        return rec


def generate_block_explanation(
    user_request: str,
    product_name: str,
    reasons: list[str],
    explanations: list[str],
    ai_mode: str,
) -> str:
    """
    Generate a plain-English explanation for why a purchase was blocked.
    Uses AI if live mode is active and configured, or a deterministic template.
    """
    settings = get_settings()

    def _fallback_explanation() -> str:
        parts = []
        if "MAX_ORDER_AMOUNT_EXCEEDED" in reasons:
            parts.append("exceeds your per-order spending limit")
        if "MERCHANT_NOT_APPROVED" in reasons:
            parts.append("is sold by a merchant not on your approved allowlist")
        if "TOTAL_BUDGET_EXCEEDED" in reasons:
            parts.append("exceeds your remaining total budget")
        if "INVALID_CURRENCY" in reasons:
            parts.append("uses a currency not matching your spending policy")
        if not parts:
            parts.append("did not pass your active spending policy checks")

        joined = " and ".join(parts)
        return (
            f"'{product_name}' was blocked because it {joined}. "
            "Here are approved alternatives within your spending rules:"
        )

    if ai_mode != "live" or not settings.ai_configured or settings.ai_provider != "openai":
        return _fallback_explanation()

    try:
        import httpx
        system_prompt = (
            "You are an assistant for AgentPay Guard. "
            "Write a concise, friendly 1-2 sentence explanation of why a purchase proposal was blocked, "
            "and introduce safer alternatives. State the product name and reason clearly without jargon."
        )
        user_prompt = (
            f"User asked for: {user_request}\n"
            f"Product: {product_name}\n"
            f"Policy block reasons: {', '.join(explanations)}"
        )
        headers = {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.ai_model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 100,
            "temperature": 0.3,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("AI block explanation failed (%s). Falling back to template.", exc)

    return _fallback_explanation()


def validate_extracted_requirements(data: Any, valid_categories: set[str]) -> Optional[dict[str, Any]]:
    """
    Validate AI requirements strictly:
    - category must be one of the catalogue categories (else None/null)
    - max_price_cents a positive integer (else None/null)
    - features at most 5 short strings
    Returns None if data is not a dict.
    """
    if not isinstance(data, dict):
        return None

    raw_cat = data.get("category")
    cat = None
    if raw_cat and isinstance(raw_cat, str):
        cleaned_cat = raw_cat.strip().lower()
        if cleaned_cat in {c.lower() for c in valid_categories}:
            cat = cleaned_cat

    raw_price = data.get("max_price_cents")
    max_price = None
    if raw_price is not None:
        try:
            val = int(raw_price)
            if val > 0:
                max_price = val
        except (ValueError, TypeError):
            max_price = None

    raw_features = data.get("features")
    features: list[str] = []
    if isinstance(raw_features, list):
        for f in raw_features:
            if isinstance(f, str) and f.strip():
                features.append(f.strip()[:60])
            if len(features) >= 5:
                break

    return {
        "category": cat,
        "max_price_cents": max_price,
        "features": features,
    }


def extract_requirements_from_ai(
    user_request: str,
    valid_categories: list[str],
) -> Optional[dict[str, Any]]:
    """
    In live AI mode, ask the model for JSON {category, max_price_cents, features}.
    Validates strictly: category in valid_categories, max_price_cents > 0, at most 5 features.
    If the AI call fails or returns invalid JSON, returns None.
    """
    settings = get_settings()
    if not settings.ai_configured or settings.ai_provider != "openai":
        return None

    try:
        import httpx
        valid_cats_str = ", ".join(valid_categories)
        system_prompt = (
            "You are a shopping requirement parser for AgentPay Guard.\n"
            f"The valid product categories are: {valid_cats_str}.\n"
            "Extract the user request into JSON format adhering strictly to this schema:\n"
            "{\n"
            '  "category": "<one of valid categories, or null>",\n'
            '  "max_price_cents": <positive integer price in cents or null>,\n'
            '  "features": ["<feature 1>", "<feature 2>"]\n'
            "}\n"
            "Rules:\n"
            "- category must match one of the valid categories exactly, or be null.\n"
            "- max_price_cents must be an integer in cents (e.g. $40 -> 4000), or null.\n"
            "- features must be at most 5 short strings describing specific desired features."
        )
        headers = {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.ai_model or "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User request: {user_request}"},
            ],
            "temperature": 0.0,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return validate_extracted_requirements(parsed, set(c.lower() for c in valid_categories))
    except Exception as exc:
        logger.warning("AI requirement extraction failed (%s). Falling back to keyword matcher.", exc)
        return None


def generate_recommendation(
    user_request: str,
    catalogue: list[dict[str, Any]]
) -> AIProposalResult:
    """
    Generate product recommendation using configured AI provider or fallback.
    Never raises an uncaught exception — gracefully falls back to deterministic engine.
    """
    settings = get_settings()

    if not settings.ai_configured:
        return AIProposalResult(
            recommendation=_deterministic_fallback(user_request, catalogue),
            ai_mode="fallback"
        )

    # Attempt live AI provider
    try:
        if settings.ai_provider == "openai":
            rec = _call_openai(user_request, catalogue, settings)
            valid_ids = {p["id"] for p in catalogue}
            if rec.product_id not in valid_ids:
                logger.warning("AI model returned product_id not in catalogue: %s", rec.product_id)
                fallback = _deterministic_fallback(user_request, catalogue)
                fallback.rationale = f"[Fallback: Model proposed unknown ID '{rec.product_id}'] {fallback.rationale}"
                return AIProposalResult(recommendation=fallback, ai_mode="fallback")
            # Filter candidates so only valid catalogue ids remain
            rec.candidates = [c for c in rec.candidates if c.product_id in valid_ids]
            return AIProposalResult(recommendation=rec, ai_mode="live")
        else:
            return AIProposalResult(
                recommendation=_deterministic_fallback(user_request, catalogue),
                ai_mode="fallback"
            )
    except Exception as exc:
        logger.warning("AI provider failed (%s: %s). Falling back to deterministic engine.", type(exc).__name__, exc)
        fallback = _deterministic_fallback(user_request, catalogue)
        fallback.rationale = f"[Fallback: AI provider error] {fallback.rationale}"
        return AIProposalResult(recommendation=fallback, ai_mode="fallback")
