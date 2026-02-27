"""
Centralized Logging Configuration
====================================

Provides structured, consistent logging across the entire Triage Management
System. All modules use Python's standard ``logging`` library with hierarchical
logger names under the ``triage`` namespace.

Logger Naming Convention:
    triage.engines.rules      → RulesEngine
    triage.engines.trigger    → TriggerEngine
    triage.engines.routes     → RoutesEngine
    triage.services.eval      → EvaluationService
    triage.services.crud      → CrudService
    triage.services.ado       → AdoClient
    triage.services.ado_write → AdoWriterService
    triage.services.audit     → AuditService
    triage.services.webhook   → WebhookProcessor
    triage.api                → API routes / endpoints
    triage.config.cosmos      → Cosmos DB configuration
    triage.config.memory      → In-memory store

Configuration:
    Call ``setup_logging()`` once at application startup (in triage_service.py).

    Environment variables:
        TRIAGE_LOG_LEVEL    Override the root log level (DEBUG, INFO, WARNING, ERROR)
                            Default: INFO

    For detailed debug tracing (every rule evaluation, trigger walk step, etc.)
    set TRIAGE_LOG_LEVEL=DEBUG before starting the service.

Usage (inside any module):
    import logging
    logger = logging.getLogger("triage.engines.rules")
    logger.debug("Evaluating rule %s: field=%s operator=%s", rule_id, field, op)
"""

import os
import logging

# The root logger namespace for the entire triage system
TRIAGE_LOGGER_ROOT = "triage"


def setup_logging(level_override: str | None = None) -> None:
    """
    Configure logging for the Triage Management System.

    Sets up:
        - Root ``triage`` logger at the configured level
        - Consistent format  ``timestamp - logger - level - message``
        - StreamHandler to stdout (console / container logs)

    Call this once from ``triage_service.py`` at startup.

    Args:
        level_override: Force a specific level (DEBUG / INFO / WARNING / ERROR).
                        If None, reads ``TRIAGE_LOG_LEVEL`` env var, defaulting
                        to INFO.
    """
    # Determine level
    level_name = (
        level_override
        or os.environ.get("TRIAGE_LOG_LEVEL", "INFO")
    ).upper()
    level = getattr(logging, level_name, logging.INFO)

    # Formatter — consistent across all triage loggers
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # StreamHandler to console
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Configure the triage root logger
    root = logging.getLogger(TRIAGE_LOGGER_ROOT)
    root.setLevel(level)

    # Avoid duplicate handlers if called more than once
    if not root.handlers:
        root.addHandler(handler)

    # Prevent propagation to the Python root logger (avoids double output
    # when uvicorn's own logger also writes to stderr)
    root.propagate = False

    # Suppress verbose Azure SDK HTTP logging that floods the console.
    # The OpenTelemetry exporter still sends telemetry to App Insights;
    # we just stop printing every HTTP request/response with full headers.
    for _azure_logger_name in (
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.monitor.opentelemetry.exporter",
        "azure.monitor.opentelemetry.exporter.export",
        "azure.monitor.opentelemetry.exporter.export._base",
        "azure.identity",
        "azure.identity._credentials",
    ):
        logging.getLogger(_azure_logger_name).setLevel(logging.WARNING)

    root.info(
        "Triage logging initialised — level=%s, loggers under '%s.*'",
        level_name,
        TRIAGE_LOGGER_ROOT,
    )
