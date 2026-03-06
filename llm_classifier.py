"""
LLM Classification Service
Uses GPT-4 for intelligent context classification with reasoning.
Designed as independent service for future agent architecture.

Dynamic Classification Config:
    Categories, intents, and business-impact levels are loaded at runtime
    from the Cosmos DB `classification-config` container (5-minute cache).
    Hardcoded _FALLBACK_* lists are used only when Cosmos is unavailable.
    When the AI returns a value not in the official list, it is recorded as
    a "discovered" item for admin review instead of raising an error.
"""

import json
import hashlib
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from openai import AzureOpenAI
import numpy as np

from ai_config import get_config
from cache_manager import CacheManager


@dataclass
class ClassificationResult:
    """Result from LLM classification"""
    category: str
    intent: str
    business_impact: str
    confidence: float
    reasoning: str
    pattern_features: Optional[Dict] = None  # Features from pattern matching
    
    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "intent": self.intent,
            "business_impact": self.business_impact,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "pattern_features": self.pattern_features
        }


class LLMClassifier:
    """
    LLM-based classification service using GPT-4
    
    Features:
    - Structured JSON output
    - Confidence scoring
    - Reasoning explanation
    - Pattern matching features integration
    - Smart caching with 7-day TTL
    - Dynamic classification config from Cosmos DB (categories, intents, impacts)
    - AI auto-discovery of new classification values with admin review workflow
    """
    
    # Fallback lists — used when Cosmos is unavailable
    _FALLBACK_CATEGORIES = [
        "compliance_regulatory", "technical_support", "feature_request",
        "migration_modernization", "security_governance", "performance_optimization",
        "integration_connectivity", "cost_billing", "training_documentation",
        "service_retirement", "service_availability", "data_sovereignty",
        "product_roadmap", "aoai_capacity", "business_desk", "capacity",
        "retirements", "roadmap", "support", "support_escalation"
    ]
    _FALLBACK_INTENTS = [
        "seeking_guidance", "reporting_issue", "requesting_feature",
        "need_migration_help", "compliance_support", "troubleshooting",
        "configuration_help", "best_practices", "requesting_service",
        "sovereignty_concern", "roadmap_inquiry", "capacity_request",
        "escalation_request", "business_engagement", "sustainability_inquiry",
        "regional_availability"
    ]
    _FALLBACK_BUSINESS_IMPACTS = ["critical", "high", "medium", "low"]

    # Dynamic config cache (TTL = 5 minutes)
    _CONFIG_CACHE_TTL = 300  # seconds
    
    def __init__(self):
        print(f"\n[LLMClassifier] 🚀 Initializing LLM Classifier...")
        self.config = get_config()
        self.azure_config = self.config.azure_openai
        self.caching_config = self.config.caching

        # Dynamic classification config state
        self._config_lock = threading.Lock()
        self._cached_categories: List[str] = []
        self._cached_intents: List[str] = []
        self._cached_business_impacts: List[str] = []
        self._config_loaded_at: float = 0.0
        self._cosmos_container = None  # lazy-init
        
        print(f"[LLMClassifier] 📋 Configuration loaded:")
        print(f"[LLMClassifier]   Endpoint: {self.azure_config.endpoint}")
        print(f"[LLMClassifier]   API Version: {self.azure_config.api_version}")
        print(f"[LLMClassifier]   Has API Key: {bool(self.azure_config.api_key)}")
        
        # Initialize Azure OpenAI client with Azure AD or API key
        use_aad = self.azure_config.use_aad if hasattr(self.azure_config, 'use_aad') else False
        print(f"[LLMClassifier]   Use AAD: {use_aad}")
        
        if use_aad:
            # Use shared credential (single auth for all services)
            print(f"[LLMClassifier] 🔐 Setting up Azure AD authentication (shared credential)...")
            from shared_auth import get_credential, get_credential_type
            from azure.identity import get_bearer_token_provider
            credential = get_credential()
            print(f"[LLMClassifier] Using shared credential (type: {get_credential_type()})")
            token_provider = get_bearer_token_provider(
                credential,
                "https://cognitiveservices.azure.com/.default"
            )
            self.client = AzureOpenAI(
                azure_endpoint=self.azure_config.endpoint,
                azure_ad_token_provider=token_provider,
                api_version=self.azure_config.api_version
            )
            print(f"[LLMClassifier] Client initialized successfully")
        else:
            # Use API key authentication
            self.client = AzureOpenAI(
                azure_endpoint=self.azure_config.endpoint,
                api_key=self.azure_config.api_key,
                api_version=self.azure_config.api_version
            )
            print(f"[LLMClassifier] Client initialized successfully")
        
        # Get service-specific configuration
        service_config = self.config.get_service_config("llm_classifier")
        
        # Initialize cache manager
        self.cache = CacheManager(
            cache_path=service_config["cache_path"],
            ttl_days=self.caching_config.ttl_days,
            api_first=self.caching_config.api_first,
            slow_threshold=self.caching_config.slow_threshold_seconds
        )
        
        self.model = service_config["model"]
        self.deployment = service_config["deployment"]
        self.temperature = service_config["temperature"]
        self.max_tokens = service_config["max_tokens"]
        
        print(f"[LLMClassifier] Deployment: {self.deployment}, Model: {self.model}")

    # ─── Dynamic classification config from Cosmos ──────────────────────

    def _get_cosmos_container(self):
        """Lazy-init Cosmos container for classification-config."""
        if self._cosmos_container is None:
            try:
                import sys as _sys
                import os as _os
                _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "triage"))
                from triage.config.cosmos_config import CosmosDBConfig
                cosmos = CosmosDBConfig()
                self._cosmos_container = cosmos.get_container("classification-config")
                print("[LLMClassifier] ✅ Connected to classification-config container")
            except Exception as e:
                print(f"[LLMClassifier] ⚠️ Could not connect to classification-config: {e}")
                self._cosmos_container = None
        return self._cosmos_container

    def _load_dynamic_config(self) -> tuple:
        """Load categories/intents/impacts from Cosmos (cached 5 min).

        Returns (categories, intents, business_impacts) as lists of strings.
        Falls back to hardcoded _FALLBACK_* lists if Cosmos is unreachable.
        """
        now = time.time()
        if (now - self._config_loaded_at) < self._CONFIG_CACHE_TTL and self._cached_categories:
            return self._cached_categories, self._cached_intents, self._cached_business_impacts

        with self._config_lock:
            # Double-check after acquiring lock
            if (time.time() - self._config_loaded_at) < self._CONFIG_CACHE_TTL and self._cached_categories:
                return self._cached_categories, self._cached_intents, self._cached_business_impacts

            container = self._get_cosmos_container()
            if container is None:
                print("[LLMClassifier] Using fallback hardcoded classification lists")
                self._cached_categories = list(self._FALLBACK_CATEGORIES)
                self._cached_intents = list(self._FALLBACK_INTENTS)
                self._cached_business_impacts = list(self._FALLBACK_BUSINESS_IMPACTS)
                self._config_loaded_at = time.time()
                return self._cached_categories, self._cached_intents, self._cached_business_impacts

            try:
                cats, intents, impacts = [], [], []
                query = "SELECT c.configType, c.value, c.status, c.redirectTo FROM c WHERE c.status IN ('official', 'discovered')"
                items = list(container.query_items(query=query, enable_cross_partition_query=True))
                for item in items:
                    val = item.get("redirectTo") or item["value"]
                    ct = item["configType"]
                    if ct == "category":
                        cats.append(val)
                    elif ct == "intent":
                        intents.append(val)
                    elif ct == "business_impact":
                        impacts.append(val)

                # De-dup while preserving order
                self._cached_categories = list(dict.fromkeys(cats)) or list(self._FALLBACK_CATEGORIES)
                self._cached_intents = list(dict.fromkeys(intents)) or list(self._FALLBACK_INTENTS)
                self._cached_business_impacts = list(dict.fromkeys(impacts)) or list(self._FALLBACK_BUSINESS_IMPACTS)
                self._config_loaded_at = time.time()
                print(f"[LLMClassifier] 🔄 Loaded dynamic config: {len(self._cached_categories)} categories, "
                      f"{len(self._cached_intents)} intents, {len(self._cached_business_impacts)} impacts")
            except Exception as e:
                print(f"[LLMClassifier] ⚠️ Error loading dynamic config: {e} — using fallback")
                self._cached_categories = list(self._FALLBACK_CATEGORIES)
                self._cached_intents = list(self._FALLBACK_INTENTS)
                self._cached_business_impacts = list(self._FALLBACK_BUSINESS_IMPACTS)
                self._config_loaded_at = time.time()

        return self._cached_categories, self._cached_intents, self._cached_business_impacts

    def _record_discovery(self, config_type: str, value: str, work_item_id: Optional[str] = None):
        """Persist a newly AI-discovered category/intent to Cosmos.

        If the value already exists as 'discovered', increment its counter.
        """
        container = self._get_cosmos_container()
        if container is None:
            print(f"[LLMClassifier] ⚠️ Cannot record discovery (no Cosmos connection): {config_type}/{value}")
            return

        prefix_map = {"category": "cat", "intent": "int", "business_impact": "biz"}
        prefix = prefix_map.get(config_type, config_type[:3])
        doc_id = f"{prefix}_{value}"
        now = datetime.now(timezone.utc).isoformat()

        try:
            existing = container.read_item(item=doc_id, partition_key=config_type)
            # Already tracked — bump counter
            existing["discoveredCount"] = existing.get("discoveredCount", 0) + 1
            existing["updatedAt"] = now
            container.replace_item(item=doc_id, body=existing)
            print(f"[LLMClassifier] 🔄 Discovery count updated: {config_type}/{value} → {existing['discoveredCount']}")
        except Exception:
            # New discovery
            doc = {
                "id": doc_id,
                "configType": config_type,
                "value": value,
                "status": "discovered",
                "displayName": value.replace("_", " ").title(),
                "description": "",
                "keywords": [],
                "discoveredFrom": work_item_id,
                "discoveredCount": 1,
                "redirectTo": None,
                "source": "ai",
                "createdAt": now,
                "updatedAt": now,
            }
            container.create_item(body=doc)
            print(f"[LLMClassifier] 🆕 New AI discovery recorded: {config_type}/{value}")
            # Invalidate cache so next classification picks up the new value
            self._config_loaded_at = 0.0

    # ─── Convenience properties ─────────────────────────────────────────

    @property
    def VALID_CATEGORIES(self) -> List[str]:
        cats, _, _ = self._load_dynamic_config()
        return cats

    @property
    def VALID_INTENTS(self) -> List[str]:
        _, intents, _ = self._load_dynamic_config()
        return intents

    @property
    def VALID_BUSINESS_IMPACTS(self) -> List[str]:
        _, _, impacts = self._load_dynamic_config()
        return impacts

    def _make_cache_key(self, title: str, description: str, impact: str, pattern_features: Optional[Dict]) -> str:
        """Generate cache key for classification"""
        key_data = json.dumps({
            "model": self.model,
            "title": title,
            "description": description,
            "impact": impact,
            "pattern_features": pattern_features
        }, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for GPT-4"""
        return f"""You are an expert Azure support ticket classifier. Your task is to analyze customer inquiries and classify them accurately.

You must classify each inquiry into ONE category and ONE intent:

CATEGORIES:
{chr(10).join(f'- {cat}' for cat in self.VALID_CATEGORIES)}

INTENTS:
{chr(10).join(f'- {intent}' for intent in self.VALID_INTENTS)}

BUSINESS IMPACT:
{', '.join(self.VALID_BUSINESS_IMPACTS)}

CLASSIFICATION RULES:
1. **Context is critical**: Understand WHY the customer is asking, not just WHAT they mention
2. **Technical problems take priority**: If error messages, failures, or "not working" appear, it's likely technical_support
3. **Distinguish product names from inquiries**: Mentioning "Azure Planner" doesn't mean roadmap inquiry
4. **Migration context**: "roadmap" in customer's migration plan ≠ Azure product roadmap
5. **Regional availability**: "required in <region>" or "needed in <region>" indicates service_availability + regional_availability

6. **CRITICAL: Feature Request vs Roadmap Inquiry distinction**:
   
   **USE category=feature_request + intent=requesting_feature WHEN:**
   - Customer lists specific capabilities they WANT/NEED
   - Customer says "we need X", "looking for Y", "requesting Z", "can you add/support"
   - Customer compares your product with competitors asking for missing features
   - Customer describes gaps in functionality they want filled
   - Example: "We need XDR functionality" → category: feature_request, intent: requesting_feature
   - Example: "Looking for SOC capabilities, here are the requested features" → category: feature_request, intent: requesting_feature
   - Example: "Comparing with Wiz, we need these capabilities" → category: feature_request, intent: requesting_feature
   
   **USE category=roadmap + intent=roadmap_inquiry ONLY WHEN:**
   - Customer explicitly asks about TIMELINE: "when will X be available?"
   - Customer asks about ETA: "what's the ETA for feature Y?"
   - Customer asks what's PLANNED: "is Z on the roadmap?", "what features are planned?"
   - Customer asks about release dates: "when is the next release?"
   - Example: "When will XDR be available?" → category: roadmap, intent: roadmap_inquiry
   - Example: "What's the ETA for SOC capabilities?" → category: roadmap, intent: roadmap_inquiry
   - Example: "Need a clear roadmap and ETA for 3rd party patching" → category: roadmap, intent: roadmap_inquiry
   
   **IF IN DOUBT:** Customer listing what they want = category: feature_request + intent: requesting_feature, NOT roadmap

7. **Timeline requests**: ONLY phrases like "when will", "ETA", "release date", "what's planned" indicate roadmap_inquiry
8. **Seeking guidance**: Demos, comparisons for decision-making, architecture advice = seeking_guidance + architecture_advice

You MUST respond with valid JSON only (no markdown):
{{
    "category": "<one of the valid categories>",
    "intent": "<one of the valid intents>",
    "business_impact": "<critical|high|medium|low>",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<brief explanation of classification decision>"
}}"""
    
    def _build_user_prompt(
        self, 
        title: str, 
        description: str, 
        impact: str,
        pattern_features: Optional[Dict] = None
    ) -> str:
        """Build user prompt with context"""
        prompt_parts = [
            f"**Title:** {title}",
            f"**Description:** {description}",
            f"**Stated Impact:** {impact}"
        ]
        
        # Include pattern matching features if available
        if pattern_features and self.config.pattern_matching.use_as_features:
            prompt_parts.append("\n**Pattern Analysis Features (from legacy system):**")
            
            if "detected_products" in pattern_features:
                products = pattern_features["detected_products"]
                if products:
                    prompt_parts.append(f"- Detected Microsoft products: {', '.join(products)}")
            
            if "technical_indicators" in pattern_features:
                indicators = pattern_features["technical_indicators"]
                if indicators:
                    prompt_parts.append(f"- Technical problem indicators: {', '.join(indicators)}")
            
            if "category_scores" in pattern_features:
                scores = pattern_features["category_scores"]
                top_patterns = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
                if top_patterns:
                    prompt_parts.append("- Top pattern matches:")
                    for cat, score in top_patterns:
                        if score > 0.3:
                            prompt_parts.append(f"  * {cat}: {score:.2f}")
            
            # NEW for Phase 1: Include relevant corrections
            if "relevant_corrections" in pattern_features:
                corrections = pattern_features["relevant_corrections"]
                if corrections:
                    prompt_parts.append("\n**⚠️ Learn from Previous Corrections (User Feedback):**")
                    prompt_parts.append("Similar issues were misclassified in the past. Please learn from these corrections:")
                    for i, corr in enumerate(corrections, 1):
                        orig_cat = corr.get('original_category', 'unknown')
                        correct_cat = corr.get('corrected_category', 'unknown')
                        notes = corr.get('correction_notes', '')
                        prompt_parts.append(f"  {i}. Was classified as '{orig_cat}' but should be '{correct_cat}'")
                        if notes:
                            prompt_parts.append(f"     Reason: {notes}")

            # ENG-003 Step 4: Inject training signals as few-shot examples
            if "relevant_training_signals" in pattern_features:
                signals = pattern_features["relevant_training_signals"]
                if signals:
                    prompt_parts.append("\n**📊 Classification Examples from Human Feedback:**")
                    prompt_parts.append("Humans reviewed these similar disagreements and chose the correct answer:")
                    for i, sig in enumerate(signals, 1):
                        llm_cat = sig.get('llmCategory', '?')
                        pat_cat = sig.get('patternCategory', '?')
                        choice = sig.get('humanChoice', '?')
                        resolved = sig.get('resolvedCategory', '?')
                        notes = sig.get('notes', '')
                        if choice == 'llm':
                            prompt_parts.append(f"  {i}. LLM said '{llm_cat}', Pattern said '{pat_cat}' → Human chose LLM: **{resolved}**")
                        elif choice == 'pattern':
                            prompt_parts.append(f"  {i}. LLM said '{llm_cat}', Pattern said '{pat_cat}' → Human chose Pattern: **{resolved}**")
                        else:
                            prompt_parts.append(f"  {i}. LLM said '{llm_cat}', Pattern said '{pat_cat}' → Human overrode both: **{resolved}**")
                        if notes:
                            prompt_parts.append(f"     Reason: {notes}")
        
        prompt_parts.append("\nClassify this inquiry:")
        
        return "\n".join(prompt_parts)
    
    # ─── ENG-004: Retry configuration ──────────────────────────────────
    # Transient Azure OpenAI errors (429 rate-limit, 5xx server errors,
    # network timeouts) are retried with exponential backoff + jitter.
    # Without retry, a single transient failure causes full fallback to
    # pattern-only analysis.  See ENG-004 in CHANGE_LOG.md.
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 1.0   # 1s, 2s, 4s exponential
    RATE_LIMIT_BACKOFF = 5.0     # Extra wait on 429s

    def _call_llm_api(
        self,
        title: str,
        description: str,
        impact: str,
        pattern_features: Optional[Dict]
    ) -> Dict:
        """Call GPT-4 API for classification with exponential-backoff retry.
        
        Retries up to MAX_RETRIES times on transient errors (429 rate-limit,
        network errors, 5xx server errors).  Validation errors (bad JSON,
        invalid category/intent) are NOT retried.
        """
        print(f"\n[LLMClassifier] 🔍 Starting LLM API call")
        print(f"[LLMClassifier]   Endpoint: {self.azure_config.endpoint}")
        print(f"[LLMClassifier]   Deployment: {self.deployment}")
        print(f"[LLMClassifier]   Model: {self.model}")
        print(f"[LLMClassifier]   Temperature: {self.temperature}")
        print(f"[LLMClassifier]   Max Tokens: {self.max_tokens}")
        
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(title, description, impact, pattern_features)
        
        print(f"[LLMClassifier]   System prompt length: {len(system_prompt)} chars")
        print(f"[LLMClassifier]   User prompt length: {len(user_prompt)} chars")

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                print(f"[LLMClassifier] 📡 Calling Azure OpenAI API (attempt {attempt}/{self.MAX_RETRIES})...")
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}
                )
                
                print(f"[LLMClassifier] ✅ API call successful!")
                print(f"[LLMClassifier]   Tokens used: {response.usage.total_tokens} (prompt: {response.usage.prompt_tokens}, completion: {response.usage.completion_tokens})")
                
                result_text = response.choices[0].message.content
                print(f"[LLMClassifier]   Response length: {len(result_text)} chars")
                print(f"[LLMClassifier]   Response preview: {result_text[:200]}...")
                
                result = json.loads(result_text)
                
                # Validate result — don't retry validation errors
                if not all(k in result for k in ["category", "intent", "business_impact", "confidence", "reasoning"]):
                    raise ValueError(f"Missing required fields in LLM response: {result}")
                
                # ── Dynamic validation: accept AI discoveries ────────
                if result["category"] not in self.VALID_CATEGORIES:
                    print(f"[LLMClassifier] 🆕 AI discovered new category: '{result['category']}'")
                    try:
                        self._record_discovery("category", result["category"])
                    except Exception as rec_err:
                        print(f"[LLMClassifier] ⚠️ Could not record category discovery: {rec_err}")
                
                if result["intent"] not in self.VALID_INTENTS:
                    print(f"[LLMClassifier] 🆕 AI discovered new intent: '{result['intent']}'")
                    try:
                        self._record_discovery("intent", result["intent"])
                    except Exception as rec_err:
                        print(f"[LLMClassifier] ⚠️ Could not record intent discovery: {rec_err}")
                
                if result["business_impact"] not in self.VALID_BUSINESS_IMPACTS:
                    print(f"[LLMClassifier] 🆕 AI discovered new business_impact: '{result['business_impact']}'")
                    try:
                        self._record_discovery("business_impact", result["business_impact"])
                    except Exception as rec_err:
                        print(f"[LLMClassifier] ⚠️ Could not record impact discovery: {rec_err}")
                    # Still default to medium for safety
                    result["business_impact"] = result.get("business_impact", "medium")
                
                print(f"[LLMClassifier] ✅ Classification complete: category={result['category']}, intent={result['intent']}, confidence={result['confidence']}")
                return result
                
            except json.JSONDecodeError as e:
                # Bad JSON from the model — unlikely to improve on retry
                print(f"[LLMClassifier] ❌ JSON decode error: {e}")
                print(f"[LLMClassifier]   Response text: {result_text}")
                raise ValueError(f"LLM returned invalid JSON: {result_text}")
            except ValueError:
                # Validation errors (missing fields, invalid category) — don't retry
                raise
            except Exception as e:
                last_error = e
                error_name = type(e).__name__
                error_str = str(e)
                print(f"[LLMClassifier] ❌ API call failed (attempt {attempt}/{self.MAX_RETRIES}): {error_name}: {error_str}")

                # Determine backoff: longer for 429 rate limits
                is_rate_limit = "429" in error_str or "RateLimitError" in error_name
                if attempt < self.MAX_RETRIES:
                    backoff = self.RATE_LIMIT_BACKOFF if is_rate_limit else self.BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    print(f"[LLMClassifier] ⏳ Retrying in {backoff:.1f}s {'(rate-limited)' if is_rate_limit else ''}...")
                    time.sleep(backoff)
                else:
                    print(f"[LLMClassifier] ❌ All {self.MAX_RETRIES} attempts exhausted")
                    import traceback
                    traceback.print_exc()

        # All retries exhausted — raise last error so caller can fallback
        raise last_error
    
    def classify(
        self,
        title: str,
        description: str,
        impact: str = "medium",
        pattern_features: Optional[Dict] = None,
        use_cache: bool = True
    ) -> ClassificationResult:
        """
        Classify customer inquiry using LLM
        
        Args:
            title: Issue title
            description: Issue description
            impact: Business impact statement
            pattern_features: Features from pattern matching (optional)
            use_cache: Whether to use cache
            
        Returns:
            ClassificationResult with category, intent, confidence, reasoning
        """
        if not title or not description:
            raise ValueError("Title and description are required")
        
        cache_key = self._make_cache_key(title, description, impact, pattern_features)
        
        if use_cache and self.caching_config.enabled:
            # Use API-first strategy
            result, source = self.cache.get_or_compute_with_api_first(
                cache_key,
                lambda: self._call_llm_api(title, description, impact, pattern_features)
            )
            print(f"[LLMClassifier] Classification from: {source}")
        else:
            # Direct API call
            print(f"[LLMClassifier] Direct API call (cache disabled)")
            result = self._call_llm_api(title, description, impact, pattern_features)
        
        # Boost confidence if pattern matching agrees
        if pattern_features and self.config.pattern_matching.use_as_features:
            if "category_scores" in pattern_features:
                pattern_top_category = max(
                    pattern_features["category_scores"].items(),
                    key=lambda x: x[1]
                )[0]
                if pattern_top_category == result["category"]:
                    boost = self.config.pattern_matching.boost_confidence_when_agree
                    result["confidence"] = min(1.0, result["confidence"] + boost)
                    print(f"[LLMClassifier] Confidence boosted by {boost} (pattern agreement)")
        
        return ClassificationResult(
            category=result["category"],
            intent=result["intent"],
            business_impact=result["business_impact"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            pattern_features=pattern_features
        )
    
    def classify_batch(
        self,
        items: List[Dict[str, str]],
        use_cache: bool = True
    ) -> List[ClassificationResult]:
        """
        Classify multiple items
        
        Args:
            items: List of dicts with 'title', 'description', 'impact' keys
            use_cache: Whether to use cache
            
        Returns:
            List of ClassificationResults
        """
        results = []
        for item in items:
            try:
                result = self.classify(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    impact=item.get("impact", "medium"),
                    pattern_features=item.get("pattern_features"),
                    use_cache=use_cache
                )
                results.append(result)
            except Exception as e:
                print(f"[LLMClassifier] Error classifying item: {e}")
                # Return fallback result
                results.append(ClassificationResult(
                    category="technical_support",
                    intent="service_inquiry",
                    business_impact="medium",
                    confidence=0.3,
                    reasoning=f"Classification failed: {e}",
                    pattern_features=item.get("pattern_features")
                ))
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()
    
    def clear_cache(self) -> None:
        """Clear classification cache"""
        self.cache.clear()


def test_llm_classifier():
    """Test the LLM classifier"""
    print("LLM Classifier Test")
    print("=" * 50)
    
    try:
        classifier = LLMClassifier()
        
        # Test case 1: Technical support
        print("\nTest 1: SCVMM migration (should be technical_support)")
        result1 = classifier.classify(
            title="SCVMM to Azure Migrate Roadmap",
            description="We are looking to migrate several workloads from SCVMM to Azure Migrate, but I am running into trouble connecting the SCVMM service to Azure Migrate. Is this possible?",
            impact="Blocking our migration to Azure",
            pattern_features={
                "detected_products": ["SCVMM", "Azure Migrate"],
                "technical_indicators": ["trouble", "connecting"],
                "category_scores": {
                    "migration": 0.7,
                    "roadmap": 0.5,
                    "technical_support": 0.4
                }
            }
        )
        print(f"Category: {result1.category}")
        print(f"Intent: {result1.intent}")
        print(f"Confidence: {result1.confidence:.2f}")
        print(f"Reasoning: {result1.reasoning}")
        
        # Test case 2: Regional availability
        print("\nTest 2: SQL MI in West Europe (should be service_availability)")
        result2 = classifier.classify(
            title="SQL MI in West Europe",
            description="Is SQL Managed Instance with Azure SQL Database Hyperscale available in West Europe region? This service is required in West Europe.",
            impact="Critical for production deployment"
        )
        print(f"Category: {result2.category}")
        print(f"Intent: {result2.intent}")
        print(f"Confidence: {result2.confidence:.2f}")
        print(f"Reasoning: {result2.reasoning}")
        
        # Test case 3: Seeking guidance (demo)
        print("\nTest 3: Planner demo (should be seeking_guidance)")
        result3 = classifier.classify(
            title="Planner & Roadmap demo",
            description="Can you give me a demo of the Planner & Roadmap feature to understand how it works?",
            impact="Want to evaluate if it fits our needs"
        )
        print(f"Category: {result3.category}")
        print(f"Intent: {result3.intent}")
        print(f"Confidence: {result3.confidence:.2f}")
        print(f"Reasoning: {result3.reasoning}")
        
        # Cache stats
        print("\nCache Statistics:")
        stats = classifier.get_cache_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n✓ LLM classifier test complete!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        print("\nMake sure to set environment variables:")
        print("  - AZURE_OPENAI_ENDPOINT")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT (optional)")


if __name__ == "__main__":
    test_llm_classifier()
