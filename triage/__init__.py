"""
Triage Management System
========================

Automated triage processing for Azure DevOps Actions. Evaluates incoming
items against configurable rules and triggers, then applies routing
to direct items to the appropriate team.

Architecture:
    - Four-layer composable model: Rules → Triggers → Routes → Actions
    - Cosmos DB for persistent storage (rules, evaluations, audit)
    - FastAPI REST API for CRUD and evaluation operations
    - React frontend for admin and triage UI

Modules:
    - models/       Data models for rules, actions, triggers, routes
    - engines/      Core evaluation engines (rules, triggers, routes)
    - services/     Business logic services (CRUD, evaluation, ADO)
    - api/          REST API endpoints
    - config/       Configuration and database setup

Service Port: 8009
"""

__version__ = "1.0.0"
__author__ = "Brad Price"
