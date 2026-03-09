"""
Pattern Engine Weight Tuner (ENG-003 Step 3)
=============================================

Batch process that reads accumulated training signals from the Cosmos
`training-signals` container, aggregates human resolution data per category,
and computes weight-adjustment multipliers for the pattern engine.

HOW IT WORKS:
-------------
1. Reads all training signals from Cosmos
2. Groups signals by `patternCategory`
3. For each category, tallies:
   - pattern_wins  (humanChoice == "pattern")
   - llm_wins      (humanChoice == "llm")
   - neither_wins  (humanChoice == "neither")
4. Computes pattern accuracy = pattern_wins / total
5. Derives a multiplier:
   - accuracy >= 0.7  → boost   (1.0 – 1.3)
   - accuracy 0.4–0.7 → neutral (0.9 – 1.0)
   - accuracy < 0.4   → penalize (0.6 – 0.9)
6. Stores the adjustments as a single document in the `training-signals`
   Cosmos container (id="pattern-weight-adjustments", workItemId="_system")

USAGE:
------
    from weight_tuner import PatternWeightTuner

    tuner = PatternWeightTuner()
    result = tuner.run()        # compute + store
    weights = tuner.get_weights()  # read stored weights

The pattern engine (intelligent_context_analyzer.py) loads these multipliers
at init time and applies them to category_scores before selecting the winner.

Author: ENG-003 Active Learning
Date: March 2026
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from collections import defaultdict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_SIGNALS_THRESHOLD = 3   # Don't adjust a category with fewer signals
BOOST_CEILING = 1.30        # Max multiplier (30% boost)
PENALTY_FLOOR = 0.60        # Min multiplier (40% penalty)
NEUTRAL_BAND = (0.40, 0.70) # Accuracy range considered "neutral"

WEIGHT_DOC_ID = "pattern-weight-adjustments"
WEIGHT_DOC_PARTITION = "_system"


# ---------------------------------------------------------------------------
# Helper: compute multiplier from accuracy
# ---------------------------------------------------------------------------

def _accuracy_to_multiplier(accuracy: float) -> float:
    """
    Convert pattern accuracy (0-1) to a score multiplier.

    Mapping (piecewise linear):
        accuracy 0.0 → 0.60  (heavy penalty)
        accuracy 0.4 → 0.90  (mild penalty)
        accuracy 0.7 → 1.00  (neutral)
        accuracy 1.0 → 1.30  (strong boost)

    This ensures the multiplier changes smoothly and stays within
    [PENALTY_FLOOR .. BOOST_CEILING].
    """
    if accuracy < NEUTRAL_BAND[0]:
        # 0.0 → 0.60,  0.4 → 0.90   (linear)
        t = accuracy / NEUTRAL_BAND[0]  # 0..1
        return PENALTY_FLOOR + t * (0.90 - PENALTY_FLOOR)
    elif accuracy <= NEUTRAL_BAND[1]:
        # 0.4 → 0.90,  0.7 → 1.00   (linear)
        t = (accuracy - NEUTRAL_BAND[0]) / (NEUTRAL_BAND[1] - NEUTRAL_BAND[0])
        return 0.90 + t * (1.00 - 0.90)
    else:
        # 0.7 → 1.00,  1.0 → 1.30   (linear)
        t = (accuracy - NEUTRAL_BAND[1]) / (1.0 - NEUTRAL_BAND[1])
        return 1.00 + t * (BOOST_CEILING - 1.00)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class PatternWeightTuner:
    """
    Reads training signals, computes per-category weight adjustments,
    and persists them back to Cosmos for the pattern engine to consume.
    """

    def __init__(self):
        self._container = None

    # -- Cosmos access ------------------------------------------------------

    def _get_container(self):
        """Lazy-load the training-signals Cosmos container."""
        if self._container is None:
            from triage.config.cosmos_config import get_cosmos_config
            cfg = get_cosmos_config()
            self._container = cfg.get_container("training-signals")
        return self._container

    # -- Read signals -------------------------------------------------------

    def _fetch_signals(self) -> list:
        """Fetch all training signal documents (exclude system docs)."""
        container = self._get_container()
        query = "SELECT * FROM c WHERE c.workItemId != '_system'"
        return list(container.query_items(query, enable_cross_partition_query=True))

    # -- Aggregate ----------------------------------------------------------

    @staticmethod
    def _aggregate(signals: list) -> Dict[str, Dict[str, int]]:
        """
        Group signals by patternCategory and tally outcomes.

        Returns::

            {
                "technical_support": {
                    "pattern_wins": 3,
                    "llm_wins": 7,
                    "neither_wins": 1,
                    "total": 11
                },
                ...
            }
        """
        agg: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"pattern_wins": 0, "llm_wins": 0, "neither_wins": 0, "total": 0}
        )

        for sig in signals:
            pat_cat = sig.get("patternCategory", "").lower().strip()
            choice = sig.get("humanChoice", "").lower().strip()
            if not pat_cat or not choice:
                continue

            bucket = agg[pat_cat]
            bucket["total"] += 1
            if choice == "pattern":
                bucket["pattern_wins"] += 1
            elif choice == "llm":
                bucket["llm_wins"] += 1
            elif choice == "neither":
                bucket["neither_wins"] += 1

        return dict(agg)

    # -- Compute adjustments ------------------------------------------------

    @staticmethod
    def _compute_adjustments(agg: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, Any]]:
        """
        Derive per-category multiplier from aggregated tallies.

        Returns::

            {
                "technical_support": {
                    "multiplier": 0.82,
                    "accuracy": 0.27,
                    "signals": 11,
                    "pattern_wins": 3,
                    "llm_wins": 7,
                    "neither_wins": 1,
                    "status": "penalized"
                },
                ...
            }
        """
        adjustments: Dict[str, Dict[str, Any]] = {}

        for cat, tallies in agg.items():
            total = tallies["total"]
            if total < MIN_SIGNALS_THRESHOLD:
                adjustments[cat] = {
                    "multiplier": 1.0,
                    "accuracy": tallies["pattern_wins"] / total if total else 0,
                    "signals": total,
                    **tallies,
                    "status": "insufficient_data"
                }
                continue

            accuracy = tallies["pattern_wins"] / total
            multiplier = round(_accuracy_to_multiplier(accuracy), 3)

            if multiplier > 1.0:
                status = "boosted"
            elif multiplier < 0.95:
                status = "penalized"
            else:
                status = "neutral"

            adjustments[cat] = {
                "multiplier": multiplier,
                "accuracy": round(accuracy, 3),
                "signals": total,
                **tallies,
                "status": status
            }

        return adjustments

    # -- Persist to Cosmos --------------------------------------------------

    def _store_weights(self, adjustments: Dict[str, Dict[str, Any]], total_signals: int) -> dict:
        """Upsert the weight-adjustments document into Cosmos."""
        container = self._get_container()
        doc = {
            "id": WEIGHT_DOC_ID,
            "workItemId": WEIGHT_DOC_PARTITION,
            "type": "weight_adjustments",
            "adjustments": adjustments,
            "totalSignals": total_signals,
            "lastTuned": datetime.now(timezone.utc).isoformat(),
        }
        container.upsert_item(doc)
        return doc

    # -- Public API ---------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """
        Execute the full tuning batch:
        1. Fetch signals
        2. Aggregate
        3. Compute adjustments
        4. Store in Cosmos

        Returns the weight-adjustments document.
        """
        signals = self._fetch_signals()
        if not signals:
            return {
                "status": "no_signals",
                "message": "No training signals found — nothing to tune.",
                "totalSignals": 0,
                "adjustments": {},
            }

        agg = self._aggregate(signals)
        adjustments = self._compute_adjustments(agg)
        doc = self._store_weights(adjustments, len(signals))

        # Summary for logging
        boosted = [c for c, a in adjustments.items() if a["status"] == "boosted"]
        penalized = [c for c, a in adjustments.items() if a["status"] == "penalized"]
        print(f"[WeightTuner] Processed {len(signals)} signals across {len(agg)} categories")
        if boosted:
            print(f"[WeightTuner] Boosted:   {', '.join(boosted)}")
        if penalized:
            print(f"[WeightTuner] Penalized: {', '.join(penalized)}")

        return doc

    def get_weights(self) -> Optional[Dict[str, Any]]:
        """
        Read the current weight-adjustments document from Cosmos.
        Returns None if no tuning has been performed yet.
        """
        try:
            container = self._get_container()
            doc = container.read_item(
                item=WEIGHT_DOC_ID,
                partition_key=WEIGHT_DOC_PARTITION,
            )
            return doc
        except Exception:
            return None

    def get_multipliers(self) -> Dict[str, float]:
        """
        Convenience method: return a plain {category: multiplier} dict.
        Returns empty dict if no weights stored.
        """
        doc = self.get_weights()
        if not doc or "adjustments" not in doc:
            return {}
        return {
            cat: info["multiplier"]
            for cat, info in doc["adjustments"].items()
        }
