"""
Microsoft Graph User Lookup  (FR-1998)
=======================================
Look up user info (displayName, jobTitle, department) from Microsoft Graph
using their email address (requestor value).

Uses the shared Azure credential from shared_auth.py so there is no extra
auth prompt.  Falls through four lookup strategies — the same sequence used
by the original JS Azure-Function implementation:

  1. Direct UPN lookup
  2. Filter by mailNickname
  3. Filter by mail / userPrincipalName
  4. $search on mailNickname
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests

from shared_auth import get_credential

logger = logging.getLogger(__name__)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"

_SELECT_FIELDS = "displayName,jobTitle,department,mail,userPrincipalName,mailNickname"


# ── result type ────────────────────────────────────────────────────────────
@dataclass
class GraphUserInfo:
    """The subset of Graph user fields we care about."""
    display_name: str
    job_title: str
    department: str


# ── public API ─────────────────────────────────────────────────────────────
def get_user_info(email: str) -> Optional[GraphUserInfo]:
    """
    Look up a user in Microsoft Graph by email address.

    Args:
        email: The user's email / UPN (the "requestor" value on a work item).

    Returns:
        A ``GraphUserInfo`` with displayName, jobTitle, and department,
        or ``None`` if the user could not be found.
    """
    if not email:
        logger.info("Graph lookup skipped: no email provided")
        return None

    try:
        token = _get_graph_token()
        headers = _build_headers(token)
        alias = email.split("@")[0].lower()

        logger.info("Looking up user in Graph: %s (alias: %s)", email, alias)

        # ── Strategy 1: Direct lookup by UPN ────────────────────────────
        url = (
            f"https://graph.microsoft.com/v1.0/users/{quote(email, safe='')}"
            f"?$select={_SELECT_FIELDS}"
        )
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.ok:
            data = resp.json()
            logger.info("Graph direct lookup success: %s - %s",
                        data.get("displayName"), data.get("jobTitle", "No title"))
            return _to_user_info(data, email)

        # ── Strategy 2: Filter by mailNickname ──────────────────────────
        logger.info("Direct lookup failed (%s), trying mailNickname filter: %s",
                     resp.status_code, alias)
        result = _filter_users(f"mailNickname eq '{alias}'", headers)
        if result:
            logger.info("Graph mailNickname filter success: %s - %s",
                        result.get("displayName"), result.get("jobTitle", "No title"))
            return _to_user_info(result, email)

        # ── Strategy 3: Filter by mail or UPN ───────────────────────────
        logger.info("mailNickname filter failed, trying mail/UPN filter")
        result = _filter_users(
            f"mail eq '{email}' or userPrincipalName eq '{email}'", headers
        )
        if result:
            logger.info("Graph mail/UPN filter success: %s - %s",
                        result.get("displayName"), result.get("jobTitle", "No title"))
            return _to_user_info(result, email)

        # ── Strategy 4: $search on mailNickname ─────────────────────────
        logger.info("Filters failed, trying $search on mailNickname: %s", alias)
        url = (
            f'https://graph.microsoft.com/v1.0/users'
            f'?$search="mailNickname:{alias}"'
            f'&$select={_SELECT_FIELDS}&$count=true'
        )
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.ok:
            items = resp.json().get("value", [])
            if items:
                logger.info("Graph $search success: %s - %s",
                            items[0].get("displayName"), items[0].get("jobTitle", "No title"))
                return _to_user_info(items[0], email)

        logger.warning("Graph lookup failed for %s — all strategies exhausted", email)
        return None

    except Exception:
        logger.exception("Graph lookup error for %s", email)
        return None


# ── helpers ────────────────────────────────────────────────────────────────
def _get_graph_token() -> str:
    """Acquire a bearer token for Microsoft Graph from the shared credential."""
    cred = get_credential()
    return cred.get_token(GRAPH_SCOPE).token


def _build_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "ConsistencyLevel": "eventual",
    }


def _filter_users(filter_expr: str, headers: dict) -> Optional[dict]:
    """Run a Graph /users?$filter=… query and return the first match (or None)."""
    url = (
        f"https://graph.microsoft.com/v1.0/users"
        f"?$filter={quote(filter_expr, safe='')}"
        f"&$select={_SELECT_FIELDS}&$count=true"
    )
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.ok:
        items = resp.json().get("value", [])
        if items:
            return items[0]
    return None


def _to_user_info(data: dict, fallback_email: str) -> GraphUserInfo:
    """Convert a raw Graph JSON object to our dataclass."""
    return GraphUserInfo(
        display_name=data.get("displayName") or fallback_email,
        job_title=data.get("jobTitle") or "Unknown",
        department=data.get("department") or "Unknown",
    )


# ── CLI quick-test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    email_arg = sys.argv[1] if len(sys.argv) > 1 else input("Email: ").strip()
    info = get_user_info(email_arg)
    if info:
        print(f"\n  Name:       {info.display_name}")
        print(f"  Title:      {info.job_title}")
        print(f"  Department: {info.department}")
    else:
        print(f"\n  No Graph result for '{email_arg}'")
