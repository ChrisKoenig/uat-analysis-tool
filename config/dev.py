"""
Dev environment configuration
==============================
Local developer workstation settings.

All values are loaded from ``config/environments/dev.json`` — the single
source of truth shared by both Python and PowerShell scripts.

To activate:  set APP_ENV=dev   (or omit APP_ENV entirely — dev is the default)
"""

from config import _load_from_json

DEV_CONFIG = _load_from_json("dev.json")

