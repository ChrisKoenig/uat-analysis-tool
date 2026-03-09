"""
chkoenig environment configuration
====================================
Chris Koenig's personal dev/test environment.

All values are loaded from ``config/environments/chkoenig.json``.

To activate:  set APP_ENV=chkoenig
"""

from shared.config import _load_from_json

CHKOENIG_CONFIG = _load_from_json("chkoenig.json")
