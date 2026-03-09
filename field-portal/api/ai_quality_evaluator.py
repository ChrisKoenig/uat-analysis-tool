"""
AI-Powered Quality Evaluator for Field Portal Submissions

Uses Azure OpenAI (GPT-4o) to semantically evaluate whether a submission
is clear, actionable, and complete — replacing the old regex/word-count system.
"""

import sys
import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Add project root so we can import ai_config, keyvault_config, etc.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _get_openai_client():
    """
    Create an AzureOpenAI client using the project's existing ai_config.
    Supports both AAD and API-key auth (same pattern as llm_classifier.py).
    """
    from openai import AzureOpenAI
    from services.ai_config import get_config

    config = get_config()
    azure_cfg = config.azure_openai

    if azure_cfg.use_aad:
        from services.shared_auth import get_credential
        from azure.identity import get_bearer_token_provider
        credential = get_credential()
        token_provider = get_bearer_token_provider(
            credential,
            "https://cognitiveservices.azure.com/.default",
        )
        client = AzureOpenAI(
            azure_endpoint=azure_cfg.endpoint,
            azure_ad_token_provider=token_provider,
            api_version=azure_cfg.api_version,
        )
    else:
        client = AzureOpenAI(
            azure_endpoint=azure_cfg.endpoint,
            api_key=azure_cfg.api_key,
            api_version=azure_cfg.api_version,
        )

    return client, azure_cfg.classification_deployment


# ── The evaluation prompt ──────────────────────────────────────────────────

QUALITY_SYSTEM_PROMPT = """\
You are a quality evaluator for an internal Azure support-issue submission portal.
Your job is to assess whether a field engineer's submission is clear, specific, and
actionable enough for a triage team to understand and route correctly.

Evaluate the submission on four dimensions.  For each dimension give a score from
0 to 25 (integer) and a one-sentence justification.

### Dimensions

1. **Title Clarity (0-25)**
   - Does the title uniquely identify the service/product and the nature of the request?
   - A great title (24-25): "Azure OpenAI GPT-4o quota increase — Contoso production tenant"
   - A poor title (0-8): "Need help" or "Issue"

2. **Description Quality (0-25)**
   - Does the description give enough context (who, what, why, technical details) for
     someone unfamiliar with the situation to understand the request?
   - Look for: customer name, service names, regions, deployment details, error messages,
     or clear justification.
   - Penalize if the text is vague, repetitive filler, or mostly jargon without substance.

3. **Business Impact (0-25)**
   - Does the submission articulate *why* this matters: revenue at risk, blocked deployment,
     number of users affected, deadlines, SLA implications?
   - If the Business Impact field is empty, this score MUST be 0.
   - If the impact is stated only inside the description, give partial credit (max 12).

4. **Actionability (0-25)**
   - Could a triage engineer route or act on this today?
   - Are there enough specifics (subscription ID, tenant, region, model, SKU, error code)
     to avoid a back-and-forth?
   - Deduct heavily if critical routing information is missing.

### Output format (strict JSON — no markdown fences)
{
  "title_clarity":    { "score": <int 0-25>, "reason": "<one sentence>" },
  "description_quality": { "score": <int 0-25>, "reason": "<one sentence>" },
  "business_impact":  { "score": <int 0-25>, "reason": "<one sentence>" },
  "actionability":    { "score": <int 0-25>, "reason": "<one sentence>" },
  "overall_score":    <int 0-100>,
  "summary":          "<two-sentence overall assessment>",
  "suggestions":      ["<improvement 1>", "<improvement 2>", ...]
}

Rules:
- overall_score = sum of the four dimension scores.
- suggestions: list 1-4 concrete, actionable improvements. If the submission is great, return an empty list.
- Be fair but rigorous — most real submissions should land between 40 and 85.
- Do NOT be generous just because the text is long.
"""


def _build_user_message(title: str, description: str, impact: str) -> str:
    return (
        f"**Title:** {title or '(empty)'}\n\n"
        f"**Description:** {description or '(empty)'}\n\n"
        f"**Business Impact:** {impact or '(empty)'}"
    )


# ── Public API ─────────────────────────────────────────────────────────────

async def evaluate_quality(title: str, description: str, impact: str) -> Dict[str, Any]:
    """
    Call Azure OpenAI to evaluate the quality of a submission.

    Returns a dict compatible with the existing QualityReviewResponse shape:
      completeness_score, is_complete, issues, suggestions, garbage_detected, ...
    """
    import time as _t
    try:
        _t0 = _t.time()
        client, deployment = _get_openai_client()
        _t1 = _t.time()
        logger.info(f"[TIMING] _get_openai_client: {_t1-_t0:.1f}s")

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": QUALITY_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(title, description, impact)},
            ],
            temperature=0.2,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        _t2 = _t.time()
        logger.info(f"[TIMING] OpenAI API call: {_t2-_t1:.1f}s  (total: {_t2-_t0:.1f}s)")

        raw = response.choices[0].message.content
        result = json.loads(raw or "{}")
        logger.info(f"AI quality evaluation: score={result.get('overall_score')}")

        return _format_result(result)

    except Exception as e:
        logger.error(f"AI quality evaluation failed: {e}", exc_info=True)
        # Fall back to the legacy rules engine so the user isn't blocked
        return _fallback_rules_engine(title, description, impact, str(e))


def _format_result(ai: Dict) -> Dict[str, Any]:
    """Convert the AI JSON response into the shape the API route expects."""
    score = ai.get("overall_score", 50)

    # Build human-readable issues list from any low-scoring dimensions
    issues = []
    for dim_key, label in [
        ("title_clarity", "Title"),
        ("description_quality", "Description"),
        ("business_impact", "Business Impact"),
        ("actionability", "Actionability"),
    ]:
        dim = ai.get(dim_key, {})
        dim_score = dim.get("score", 0)
        if dim_score < 15:
            severity = "error" if dim_score < 8 else "warning"
            issues.append(f"{label} ({dim_score}/25): {dim.get('reason', 'Needs improvement')}")

    # Build suggestions — combine AI suggestions with dimension reasons for low scores
    suggestions = []
    for s in ai.get("suggestions", []):
        if s:
            suggestions.append(f"\u2139\ufe0f {s}")

    summary = ai.get("summary", "")
    if summary:
        suggestions.insert(0, summary)

    return {
        "completeness_score": score,
        "is_complete": score >= 80 and len(issues) == 0,
        "issues": issues,
        "suggestions": suggestions,
        "garbage_detected": False,
        "garbage_details": {"title": None, "description": None, "impact": None},
        "needs_improvement": len(issues) > 0,
        "ai_evaluation": True,
        "dimensions": {
            "title_clarity": ai.get("title_clarity", {}),
            "description_quality": ai.get("description_quality", {}),
            "business_impact": ai.get("business_impact", {}),
            "actionability": ai.get("actionability", {}),
        },
    }


def _fallback_rules_engine(title: str, description: str, impact: str, error_msg: str) -> Dict[str, Any]:
    """Use the old regex/word-count engine if AI is unavailable."""
    try:
        from services.enhanced_matching import AIAnalyzer
        result = AIAnalyzer.analyze_completeness(title=title, description=description, impact=impact)
        result["ai_evaluation"] = False
        result["ai_error"] = error_msg
        return result
    except Exception as e2:
        logger.error(f"Fallback rules engine also failed: {e2}")
        word_count = len((description or "").split())
        return {
            "completeness_score": 100 if word_count >= 5 else 40,
            "is_complete": word_count >= 5,
            "issues": [],
            "suggestions": [f"AI evaluation unavailable: {error_msg}"],
            "garbage_detected": False,
            "ai_evaluation": False,
            "ai_error": error_msg,
        }
