"""
services/ai_service.py — AI shopping agent recommendation service.

Architecture & Trust Boundary:
- The AI is NOT the security boundary.
- The AI receives ONLY the user request and backend-supplied product catalogue.
- The AI can ONLY propose a product_id from the catalogue; it CANNOT set price,
  merchant identity, policy decision, budget remaining, or payment status.
- If AI credentials are not configured or the call fails, a deterministic fallback
  engine selects the best matching product and labels the output clearly.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)


class AIRecommendation(BaseModel):
    product_id: str
    rationale: str
    matched_requirements: list[str] = Field(default_factory=list)
    unmet_requirements: list[str] = Field(default_factory=list)
    confidence_note: str = ""


class AIProposalResult(BaseModel):
    recommendation: AIRecommendation
    ai_mode: str  # "live" | "fallback"


def _deterministic_fallback(user_request: str, catalogue: list[dict[str, Any]]) -> AIRecommendation:
    """
    Deterministic rule-based keyword matcher when no live LLM API is available.
    Guarantees a valid product_id from the provided catalogue.
    """
    req_lower = user_request.lower()
    best_product = None
    best_score = -1

    for prod in catalogue:
        score = 0
        name = prod.get("name", "").lower()
        desc = prod.get("description", "").lower()
        merchant = prod.get("merchant_name", "").lower()
        merchant_id = prod.get("merchant_id", "").lower()
        features = [f.lower() for f in prod.get("features", [])]

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

        if score > best_score:
            best_score = score
            best_product = prod

    if not best_product and catalogue:
        best_product = catalogue[0]

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
            confidence_note="Deterministic keyword scoring (offline fallback mode)."
        )

    # Edge case: empty catalogue
    return AIRecommendation(
        product_id="",
        rationale="No products available in catalogue.",
        confidence_note="Fallback unable to match empty catalogue."
    )


def _call_openai(user_request: str, catalogue: list[dict[str, Any]], settings: Any) -> AIRecommendation:
    """Call OpenAI API in JSON mode."""
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
        "Your task: recommend EXACTLY ONE product_id from the provided catalogue that best matches the user's request.\n"
        "STRICT SECURITY RULES:\n"
        "1. You MUST select a product_id that appears in the catalogue.\n"
        "2. You DO NOT determine price, policy eligibility, remaining budget, or payment approval.\n"
        "3. Output MUST be valid JSON adhering strictly to this schema:\n"
        "{\n"
        '  "product_id": "<exact_id_from_catalogue>",\n'
        '  "rationale": "<why this product fits user request>",\n'
        '  "matched_requirements": ["<requirement 1>", "<requirement 2>"],\n'
        '  "unmet_requirements": ["<any requirement not met>"],\n'
        '  "confidence_note": "<brief confidence note>"\n'
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
        return AIRecommendation.model_validate(parsed)


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
            # Verify the suggested product_id actually exists in the catalogue
            valid_ids = {p["id"] for p in catalogue}
            if rec.product_id not in valid_ids:
                logger.warning("AI model returned product_id not in catalogue: %s", rec.product_id)
                fallback = _deterministic_fallback(user_request, catalogue)
                fallback.rationale = f"[Fallback: Model proposed unknown ID '{rec.product_id}'] {fallback.rationale}"
                return AIProposalResult(recommendation=fallback, ai_mode="fallback")
            return AIProposalResult(recommendation=rec, ai_mode="live")
        else:
            # Other provider or unsupported
            return AIProposalResult(
                recommendation=_deterministic_fallback(user_request, catalogue),
                ai_mode="fallback"
            )
    except Exception as exc:
        logger.warning("AI provider failed (%s: %s). Falling back to deterministic engine.", type(exc).__name__, exc)
        fallback = _deterministic_fallback(user_request, catalogue)
        fallback.rationale = f"[Fallback: AI provider error] {fallback.rationale}"
        return AIProposalResult(recommendation=fallback, ai_mode="fallback")
