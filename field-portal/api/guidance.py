"""
Category-Specific Guidance Rules

Extracted from the Flask app's _get_category_guidance() function.
These rules tell field personnel what to do based on the AI-detected category.
"""

from .models import CategoryGuidance


def get_category_guidance(category: str) -> CategoryGuidance | None:
    """Return category-specific guidance for the user, or None if no special guidance."""

    guidance_map = {
        "technical_support": CategoryGuidance(
            title="Technical Support Issue Detected",
            variant="warning",
            items=[
                "This appears to be a technical support issue that may require a support case.",
                "Consider opening a support case via CSS Compass for direct technical assistance.",
                "Work with your CSAM for reactive escalation if needed.",
                "You can also submit a GetHelp request for general support.",
            ],
            links={
                "CSS Compass": "https://aka.ms/csscompass",
                "Reactive Escalation": "https://aka.ms/reactiveescalation",
                "GetHelp": "https://aka.ms/GetHelp",
            },
        ),
        "cost_billing": CategoryGuidance(
            title="Billing Issue - Out of Scope",
            variant="danger",
            items=[
                "Billing and cost issues are out of scope for this forum.",
                "Please submit billing inquiries through the GetHelp portal.",
                "Your CSAM can assist with escalating billing concerns if needed.",
            ],
            links={
                "GetHelp Portal": "https://aka.ms/GetHelp",
            },
        ),
        "aoai_capacity": CategoryGuidance(
            title="Azure OpenAI Capacity Request",
            variant="info",
            items=[
                "Please review Azure OpenAI capacity guidelines before submitting.",
                "Capacity requests should be completed from the Milestone in MSX.",
                "Review the AI Capacity Hub for current availability and request process.",
            ],
            links={
                "AI Capacity Hub": "https://aka.ms/aicapacityhub",
            },
        ),
        "capacity": CategoryGuidance(
            title="Capacity Request Guidelines",
            variant="info",
            items=[
                "For AI capacity (Azure OpenAI, Azure AI Services): review the AI Capacity Hub.",
                "For Non-AI capacity (VMs, Storage, etc.): follow the published guidelines on SharePoint.",
                "Both types of capacity requests should originate from the MSX Milestone.",
            ],
            links={
                "AI Capacity Hub": "https://aka.ms/aicapacityhub",
            },
        ),
        "feature_request": CategoryGuidance(
            title="Feature Request Submission",
            variant="info",
            items=[
                "Feature requests are tracked in the Technical Feedback (TFT) system.",
                "If a matching TFT Feature is found below, select it to link your UAT.",
                "Include specific customer impact and business justification for faster triage.",
            ],
            links={
                "TFT Dashboard": "https://aka.ms/tft",
            },
        ),
    }

    return guidance_map.get(category)
