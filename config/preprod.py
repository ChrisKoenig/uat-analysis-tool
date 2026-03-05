"""
Pre-prod environment configuration
====================================
Non-production Azure App Service deployment.

All values are loaded from ``config/environments/preprod.json`` — the single
source of truth shared by both Python and PowerShell scripts.

To activate:  set APP_ENV=preprod
"""

from config import _load_from_json

PREPROD_CONFIG = _load_from_json("preprod.json")

