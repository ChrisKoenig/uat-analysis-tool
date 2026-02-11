"""
Triage Management System
========================

Automated triage processing for Azure DevOps Actions. Evaluates incoming
items against configurable rules and decision trees, then applies routing
to direct items to the appropriate team.

Architecture:
    - Four-layer composable model: Rules → Trees → Routes → Actions
    - Cosmos DB for persistent storage (rules, evaluations, audit)
    - Flask/FastAPI REST API for CRUD and evaluation operations
    - React frontend for admin and triage UI

Modules:
    - models/       Data models for rules, actions, trees, routes
    - engines/      Core evaluation engines (rules, trees, routes)
    - services/     Business logic services (CRUD, evaluation, ADO)
    - api/          REST API endpoints
    - config/       Configuration and database setup

Service Port: 8009
"""

__version__ = "1.0.0"
__author__ = "Brad Price"
