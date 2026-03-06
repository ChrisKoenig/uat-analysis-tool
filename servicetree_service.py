"""
ServiceTree Integration Service
================================

Fetches and caches the service catalog from the ServiceTree BFF API
(tf-servicetree-api.azurewebsites.net), which proxies to a backend
Azure Function App (F051-PRD-Automation).

Data Retrieved:
    - Offerings: 123 offerings containing 1,439 services
    - Solution Areas: AI Business Process, AI Workforce, Cloud and AI platform, Security
    - Area Paths: Security, Data and AI, Digital and App Innovation, Infrastructure, etc.

Each service record includes:
    - name:             Service name (e.g., "Cosmos DB", "App Service")
    - devContact:       Dev team alias
    - csuDri:           CSU DRI alias (used for triage routing)
    - releaseManager:   Release manager alias(es)
    - solutionAreaGcs:  GCS solution area
    - areaPathAdo:      ADO area path (used for triage routing)

Cache Pattern:
    Uses the same {timestamp, data} JSON pattern as intelligent_context_analyzer.py.
    7-day TTL, stored in .cache/servicetree_offerings.json.
    Falls back to static snapshot if API is unreachable.

Usage:
    from servicetree_service import ServiceTreeService

    svc = ServiceTreeService()
    match = svc.lookup_service("Cosmos DB")
    # → {"name": "Cosmos DB", "offering": "Cosmos DB", "solutionArea": "Cloud and AI platform",
    #    "csuDri": "...", "areaPathAdo": "Data and AI", "devContact": "...", ...}

Auth:
    Bearer token for api://73b8d7d8-5640-4047-879f-7f0a0298905b
    acquired via `az account get-access-token` (same as existing CLI calls).
"""

import json
import logging
import os
import subprocess
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("servicetree")

# =============================================================================
# Configuration
# =============================================================================

SERVICETREE_BFF_URL = os.environ.get(
    "SERVICETREE_API_URL",
    "https://tf-servicetree-api.azurewebsites.net",
)
SERVICETREE_AAD_RESOURCE = os.environ.get(
    "SERVICETREE_AAD_RESOURCE",
    "api://73b8d7d8-5640-4047-879f-7f0a0298905b",
)
SERVICETREE_AAD_TENANT = os.environ.get(
    "SERVICETREE_AAD_TENANT",
    "72f988bf-86f1-41af-91ab-2d7cd011db47",
)

CACHE_DIR = Path(".cache")
CACHE_KEY = "servicetree_offerings"
STATIC_SNAPSHOT = Path("servicetree_offerings.json")  # downloaded fallback
CACHE_TTL_HOURS = 168  # 7 days


# =============================================================================
# ServiceTreeService
# =============================================================================

class ServiceTreeService:
    """
    Manages the ServiceTree service catalog: fetch, cache, lookup.

    The catalog is a flat list of service records, each enriched with
    the parent offering name and solution area.  Lookups are done
    by exact-then-fuzzy matching on service name.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = CACHE_TTL_HOURS,
    ):
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        # Flat catalog: list of enriched service dicts
        self._catalog: List[Dict[str, Any]] = []
        # Lookup index: lowercase service name → catalog entry
        self._index: Dict[str, Dict[str, Any]] = {}
        # Solution areas & area paths (reference data)
        self.solution_areas: List[str] = []
        self.area_paths: List[str] = []

        # Load on init (from cache, API, or static)
        self._load_catalog()

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def lookup_service(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Look up a service in the ServiceTree catalog.

        Matching strategy:
            1. Exact match (case-insensitive)
            2. Substring match (service name contained in catalog entry or vice versa)
            3. Fuzzy match (SequenceMatcher ratio >= 0.75)

        Returns:
            Enriched service dict or None if no match.
        """
        if not service_name or not self._catalog:
            return None

        name_lower = service_name.strip().lower()

        # 1) Exact match
        if name_lower in self._index:
            return self._index[name_lower]

        # 2) Substring match (prefer shorter key that contains or is contained)
        for key, entry in self._index.items():
            if name_lower in key or key in name_lower:
                return entry

        # 3) Fuzzy match
        best_match = None
        best_ratio = 0.0
        for key, entry in self._index.items():
            ratio = SequenceMatcher(None, name_lower, key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = entry
        if best_ratio >= 0.75:
            return best_match

        return None

    def lookup_services(self, service_names: List[str]) -> List[Dict[str, Any]]:
        """Look up multiple services, returning all matches (no duplicates)."""
        seen = set()
        results = []
        for name in service_names:
            match = self.lookup_service(name)
            if match and match["name"] not in seen:
                seen.add(match["name"])
                results.append(match)
        return results

    def get_best_match(self, service_names: List[str]) -> Optional[Dict[str, Any]]:
        """
        From a list of detected service/product names, return the single
        best ServiceTree match (first exact, then first fuzzy).
        """
        for name in service_names:
            match = self.lookup_service(name)
            if match:
                return match
        return None

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Return the full flat catalog."""
        return self._catalog

    def get_catalog_stats(self) -> Dict[str, Any]:
        """Return summary stats about the cached catalog."""
        cache_file = self.cache_dir / f"{CACHE_KEY}.json"
        cache_age = None
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached = json.load(f)
                ts = datetime.fromisoformat(cached.get("timestamp", ""))
                cache_age = str(datetime.now() - ts)
            except Exception:
                pass

        return {
            "total_services": len(self._catalog),
            "total_offerings": len(set(s.get("offering", "") for s in self._catalog)),
            "solution_areas": self.solution_areas,
            "area_paths": self.area_paths,
            "cache_age": cache_age,
            "cache_file": str(cache_file),
        }

    def refresh(self, force: bool = False) -> Dict[str, Any]:
        """
        Force-refresh the catalog from the API.

        Args:
            force: If True, ignore cache TTL and fetch fresh data.

        Returns:
            Stats dict with refresh result.
        """
        if force:
            # Remove cache to force re-fetch
            cache_file = self.cache_dir / f"{CACHE_KEY}.json"
            if cache_file.exists():
                cache_file.unlink()

        offerings = self._fetch_from_api()
        if offerings is not None:
            self._build_catalog(offerings)
            self._cache_data(CACHE_KEY, offerings)
            return {
                "success": True,
                "source": "api",
                **self.get_catalog_stats(),
            }
        return {
            "success": False,
            "error": "Failed to fetch from ServiceTree API",
            **self.get_catalog_stats(),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Loading pipeline
    # ─────────────────────────────────────────────────────────────────────

    def _load_catalog(self):
        """Load catalog from cache → API → static fallback."""
        # 1) Try valid cache
        cached = self._get_cached_data(CACHE_KEY)
        if cached:
            logger.info("ServiceTree catalog loaded from cache")
            self._build_catalog(cached)
            return

        # 2) Try API
        offerings = self._fetch_from_api()
        if offerings is not None:
            logger.info("ServiceTree catalog fetched from API")
            self._build_catalog(offerings)
            self._cache_data(CACHE_KEY, offerings)
            return

        # 3) Try expired cache
        expired = self._get_expired_cached_data(CACHE_KEY)
        if expired:
            logger.warning("ServiceTree: using expired cache (API unavailable)")
            self._build_catalog(expired)
            return

        # 4) Try static snapshot file
        if STATIC_SNAPSHOT.exists():
            try:
                with open(STATIC_SNAPSHOT, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.warning("ServiceTree: loaded from static snapshot file")
                self._build_catalog(data)
                return
            except Exception as e:
                logger.error(f"ServiceTree: static snapshot failed: {e}")

        # 5) Empty catalog
        logger.error("ServiceTree: no data available — catalog is empty")
        self._catalog = []
        self._index = {}

    def _build_catalog(self, offerings: List[Dict[str, Any]]):
        """
        Flatten the offerings → services hierarchy into a flat catalog
        and build the lookup index.
        """
        catalog = []
        for offering in offerings:
            offering_name = offering.get("name", "")
            solution_area = offering.get("solutionArea", "")
            for svc in offering.get("services", []):
                entry = {
                    "name": svc.get("name", ""),
                    "offering": offering_name,
                    "solutionArea": solution_area,
                    "devContact": svc.get("devContact", ""),
                    "csuDri": svc.get("csuDri", ""),
                    "releaseManager": svc.get("releaseManager", ""),
                    "solutionAreaGcs": svc.get("solutionAreaGcs", ""),
                    "areaPathAdo": svc.get("areaPathAdo", ""),
                }
                catalog.append(entry)

        self._catalog = catalog
        self._index = {s["name"].lower(): s for s in catalog if s.get("name")}

        # Derive reference lists
        self.solution_areas = sorted(set(
            s["solutionArea"] for s in catalog if s.get("solutionArea")
        ))
        self.area_paths = sorted(set(
            s["areaPathAdo"] for s in catalog if s.get("areaPathAdo")
        ))

        logger.info(
            f"ServiceTree catalog: {len(catalog)} services, "
            f"{len(set(s['offering'] for s in catalog))} offerings, "
            f"{len(self.solution_areas)} solution areas"
        )

    # ─────────────────────────────────────────────────────────────────────
    # API interaction
    # ─────────────────────────────────────────────────────────────────────

    def _fetch_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch the offerings catalog from the ServiceTree BFF.

        Uses `az account get-access-token` for auth (same pattern as
        the existing Azure CLI calls in intelligent_context_analyzer.py).
        """
        token = self._get_token()
        if not token:
            logger.warning("ServiceTree: could not acquire bearer token")
            return None

        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                f"{SERVICETREE_BFF_URL}/api/offerings",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if isinstance(data, list) and len(data) > 0:
                logger.info(f"ServiceTree API returned {len(data)} offerings")
                return data
            else:
                logger.warning(f"ServiceTree API returned unexpected data: {type(data)}")
                return None

        except urllib.error.HTTPError as e:
            logger.error(f"ServiceTree API HTTP error: {e.code} {e.reason}")
            return None
        except Exception as e:
            logger.error(f"ServiceTree API fetch failed: {e}")
            return None

    def _get_token(self) -> Optional[str]:
        """Acquire a bearer token via Azure CLI."""
        try:
            result = subprocess.run(
                [
                    r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
                    "account", "get-access-token",
                    "--resource", SERVICETREE_AAD_RESOURCE,
                    "--tenant", SERVICETREE_AAD_TENANT,
                    "--query", "accessToken",
                    "-o", "tsv",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            logger.warning(f"az token failed (rc={result.returncode}): {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            logger.error("ServiceTree: az token acquisition timed out")
        except FileNotFoundError:
            # Try without full path (Linux / Mac / PATH-based)
            try:
                result = subprocess.run(
                    [
                        "az", "account", "get-access-token",
                        "--resource", SERVICETREE_AAD_RESOURCE,
                        "--tenant", SERVICETREE_AAD_TENANT,
                        "--query", "accessToken",
                        "-o", "tsv",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
            logger.error("ServiceTree: Azure CLI not found")
        except Exception as e:
            logger.error(f"ServiceTree: token error: {e}")
        return None

    # ─────────────────────────────────────────────────────────────────────
    # Cache (same pattern as intelligent_context_analyzer.py)
    # ─────────────────────────────────────────────────────────────────────

    def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached data if it exists and hasn't expired."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
            cached_time = datetime.fromisoformat(cached.get("timestamp", ""))
            if datetime.now() - cached_time < self.cache_ttl:
                return cached.get("data")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid ServiceTree cache file: {e}")
        return None

    def _get_expired_cached_data(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached data even if expired (fallback)."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
            return cached.get("data")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid expired ServiceTree cache: {e}")
        return None

    def _cache_data(self, cache_key: str, data: Any) -> None:
        """Cache data with timestamp."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {"timestamp": datetime.now().isoformat(), "data": data},
                    f,
                    indent=2,
                )
            logger.info(f"ServiceTree data cached to {cache_file}")
        except Exception as e:
            logger.error(f"Failed to cache ServiceTree data: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # Admin override support
    # ─────────────────────────────────────────────────────────────────────

    def apply_overrides(self, overrides: List[Dict[str, Any]]) -> int:
        """
        Apply admin overrides to the in-memory catalog.

        Each override dict should have at least {"name": "..."} to identify
        the service, plus fields to override (csuDri, areaPathAdo, etc.).

        Returns:
            Number of overrides applied.
        """
        applied = 0
        for override in overrides:
            svc_name = override.get("name", "").lower()
            if svc_name in self._index:
                entry = self._index[svc_name]
                for field in ("csuDri", "areaPathAdo", "devContact",
                              "releaseManager", "solutionArea", "solutionAreaGcs"):
                    if field in override and override[field]:
                        entry[field] = override[field]
                entry["adminOverride"] = True
                applied += 1
        return applied


# =============================================================================
# Module-level singleton
# =============================================================================

_instance: Optional[ServiceTreeService] = None


def get_servicetree_service() -> ServiceTreeService:
    """Get or create the ServiceTreeService singleton."""
    global _instance
    if _instance is None:
        _instance = ServiceTreeService()
    return _instance
