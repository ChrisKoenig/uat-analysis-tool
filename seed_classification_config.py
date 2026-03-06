"""
Seed Classification Config to Cosmos DB
=========================================

One-time migration that writes the current hardcoded categories, intents,
and business-impact levels into the `classification-config` container so
the system can manage them dynamically from that point forward.

Usage:
    $env:PYTHONPATH = "C:\\Projects\\Hack"
    $env:COSMOS_ENDPOINT = "https://cosmos-gcs-dev.documents.azure.com:443/"
    $env:COSMOS_USE_AAD = "true"
    $env:COSMOS_TENANT_ID = "16b3c013-d300-468d-ac64-7eda0820b6d3"
    python seed_classification_config.py

Re-running is safe — existing docs are skipped (upsert is NOT used so
admin edits are never overwritten).
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "triage"))

from triage.config.cosmos_config import CosmosDBConfig
from azure.cosmos import exceptions as cosmos_exceptions


# ── Current hardcoded values (source of truth for seed) ─────────────────────

CATEGORIES = [
    "compliance_regulatory",
    "technical_support",
    "feature_request",
    "migration_modernization",
    "security_governance",
    "performance_optimization",
    "integration_connectivity",
    "cost_billing",
    "training_documentation",
    "service_retirement",
    "service_availability",
    "data_sovereignty",
    "product_roadmap",
    "aoai_capacity",
    "business_desk",
    "capacity",
    "retirements",
    "roadmap",
    "support",
    "support_escalation",
]

INTENTS = [
    "seeking_guidance",
    "reporting_issue",
    "requesting_feature",
    "need_migration_help",
    "compliance_support",
    "troubleshooting",
    "configuration_help",
    "best_practices",
    "requesting_service",
    "sovereignty_concern",
    "roadmap_inquiry",
    "capacity_request",
    "escalation_request",
    "business_engagement",
    "sustainability_inquiry",
    "regional_availability",
]

BUSINESS_IMPACTS = [
    "critical",
    "high",
    "medium",
    "low",
]


def seed():
    print("=" * 60)
    print("  Seed Classification Config → Cosmos DB")
    print("=" * 60)

    cosmos = CosmosDBConfig()
    container = cosmos.get_container("classification-config")
    now = datetime.now(timezone.utc).isoformat()

    created = 0
    skipped = 0

    def _upsert_if_new(doc):
        nonlocal created, skipped
        try:
            container.read_item(item=doc["id"], partition_key=doc["configType"])
            print(f"  ⏩  {doc['configType']}/{doc['value']} — already exists, skipping")
            skipped += 1
        except cosmos_exceptions.CosmosResourceNotFoundError:
            container.create_item(body=doc)
            print(f"  ✅  {doc['configType']}/{doc['value']} — created")
            created += 1

    # ── Categories ──────────────────────────────────────────────
    print("\n>> Seeding categories...")
    for cat in CATEGORIES:
        _upsert_if_new({
            "id": f"cat_{cat}",
            "configType": "category",
            "value": cat,
            "status": "official",
            "displayName": cat.replace("_", " ").title(),
            "description": "",
            "keywords": [],
            "discoveredFrom": None,
            "discoveredCount": 0,
            "redirectTo": None,
            "source": "seed",
            "createdAt": now,
            "updatedAt": now,
        })

    # ── Intents ─────────────────────────────────────────────────
    print("\n>> Seeding intents...")
    for intent in INTENTS:
        _upsert_if_new({
            "id": f"int_{intent}",
            "configType": "intent",
            "value": intent,
            "status": "official",
            "displayName": intent.replace("_", " ").title(),
            "description": "",
            "keywords": [],
            "discoveredFrom": None,
            "discoveredCount": 0,
            "redirectTo": None,
            "source": "seed",
            "createdAt": now,
            "updatedAt": now,
        })

    # ── Business Impacts ────────────────────────────────────────
    print("\n>> Seeding business impacts...")
    for impact in BUSINESS_IMPACTS:
        _upsert_if_new({
            "id": f"biz_{impact}",
            "configType": "business_impact",
            "value": impact,
            "status": "official",
            "displayName": impact.title(),
            "description": "",
            "keywords": [],
            "discoveredFrom": None,
            "discoveredCount": 0,
            "redirectTo": None,
            "source": "seed",
            "createdAt": now,
            "updatedAt": now,
        })

    print(f"\n{'=' * 60}")
    print(f"  Done!  Created: {created}  |  Skipped: {skipped}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    seed()
