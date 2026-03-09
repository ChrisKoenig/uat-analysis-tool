"""
AI-Powered Hybrid Context Analyzer
====================================

OVERVIEW:
---------
This module implements a sophisticated hybrid analysis system that combines:
- Traditional pattern matching (fast, rule-based, 50-90% confidence)
- Large Language Model classification (intelligent, context-aware, 95%+ confidence)
- Vector similarity search (finds related historical issues)
- Corrective learning (improves from user feedback)

ARCHITECTURE:
-------------
The hybrid approach uses a "pattern-first, AI-enhanced" strategy:

1. PATTERN MATCHING (Always runs first):
   - Fast rule-based analysis using intelligent_context_analyzer
   - Provides baseline classification and rich features
   - Extracts semantic keywords, domain entities, concepts
   - Generates confidence scores and search strategies
   - Serves as fallback if AI unavailable

2. AI ENHANCEMENT (When enabled):
   - LLM receives pattern features as context
   - Makes final classification decision with reasoning
   - Incorporates user corrections for continuous learning
   - Provides natural language explanations
   - Higher confidence (95%+) with semantic understanding

3. SIMILARITY SEARCH:
   - Embeds issue text into vector space
   - Finds semantically similar historical issues
   - Provides examples for better matching

4. CORRECTIVE LEARNING (Phase 1):
   - Loads user corrections from corrections.json
   - Matches corrections to similar issues
   - Includes correction hints in LLM prompts
   - Improves accuracy over time

USAGE:
------
    analyzer = HybridContextAnalyzer(use_ai=True)
    result = analyzer.analyze(title, description, impact)
    
    # Result contains:
    # - category, intent, business_impact (primary classification)
    # - confidence score
    # - reasoning (explanation)
    # - pattern_features (supporting evidence)
    # - similar_issues (historical matches)
    # - All pattern analyzer fields (semantic_keywords, domain_entities, etc.)

FALLBACK BEHAVIOR:
------------------
- If Azure OpenAI unavailable → Falls back to pattern matching
- If LLM errors → Falls back to pattern matching
- Pattern results always available as backup
- Graceful degradation ensures system reliability

DESIGN DECISIONS:
-----------------
- Pattern-first ensures fast baseline results
- AI enhancement provides semantic understanding
- Hybrid results include both for transparency
- Full backward compatibility with existing code
- Learning from corrections improves over time

Author: Enhanced Matching Development Team
Version: 2.0 (Hybrid AI + Pattern Analysis with Corrective Learning)
Last Updated: December 2025
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import os
import json
from pathlib import Path
from difflib import SequenceMatcher

# Import existing pattern-based analyzer
from shared.intelligent_context_analyzer import IntelligentContextAnalyzer

# Import AI services
from shared.ai_config import get_config, validate_config
from shared.llm_classifier import LLMClassifier, ClassificationResult
from shared.embedding_service import EmbeddingService
from shared.vector_search import VectorSearchService


@dataclass
class HybridAnalysisResult:
    """
    Complete result from hybrid AI+pattern analysis
    
    This dataclass contains all information from both the AI classification
    and the pattern matching analysis, providing full transparency and
    enabling downstream code to use whichever source is most appropriate.
    
    IMPORTANT: Python dataclass field ordering requirement
    -------------------------------------------------------
    Once a field has a default value, ALL subsequent fields must also have
    default values. This is why pattern_reasoning, similar_issues, and all
    fields after them have default values (even if None).
    
    FIELDS ORGANIZATION:
    --------------------
    
    PRIMARY RESULTS (from LLM or pattern fallback):
        category: Issue category (e.g., "technical_support", "feature_request")
        intent: User intent (e.g., "seeking_guidance", "requesting_feature")
        business_impact: Impact assessment (e.g., "high", "medium", "low")
        confidence: Confidence score 0.0-1.0
        reasoning: Explanation (str from LLM, Dict from pattern)
    
    PATTERN MATCHING EVIDENCE (always available):
        pattern_category: Category from pattern analyzer
        pattern_intent: Intent from pattern analyzer
        pattern_confidence: Pattern matching confidence
        pattern_features: Detailed pattern analysis features
    
    SEMANTIC SEARCH RESULTS:
        similar_issues: List of historically similar issues
    
    PATTERN ANALYZER FIELDS (for downstream processing):
        semantic_keywords: Key terms extracted from text
        key_concepts: High-level concepts identified
        recommended_search_strategy: Which data sources to prioritize
        urgency_level: Urgency assessment ("high", "medium", "low")
        technical_complexity: Technical difficulty assessment
        context_summary: Brief summary of the issue context
        domain_entities: Extracted entities (services, frameworks, regions, etc.)
    
    METADATA:
        source: "llm" (AI only), "pattern" (fallback), or "hybrid" (both agree)
        agreement: Boolean indicating if LLM and pattern results match
    
    USAGE:
    ------
    The result object can be used in different ways:
    
    1. For display: Use primary fields (category, intent, confidence, reasoning)
    2. For matching: Use pattern_features and semantic_keywords
    3. For routing: Use recommended_search_strategy and urgency_level
    4. For transparency: Compare LLM vs pattern results
    """
    
    # LLM results (primary)
    category: str
    intent: str
    business_impact: str
    confidence: float
    reasoning: Any  # Can be str (LLM) or Dict (pattern)
    
    # Pattern matching features (supporting evidence)
    pattern_category: str
    pattern_intent: str
    pattern_confidence: float
    pattern_features: Dict[str, Any]
    pattern_reasoning: Any = None  # Original pattern analyzer reasoning dict (for step-by-step display)
    
    # Semantic search results
    similar_issues: List[Dict] = None
    
    # Additional pattern analysis fields (for downstream processing)
    semantic_keywords: List[str] = None  # From pattern analyzer
    key_concepts: List[str] = None  # From pattern analyzer
    recommended_search_strategy: Dict[str, bool] = None  # From pattern analyzer
    urgency_level: str = None  # From pattern analyzer
    technical_complexity: str = None  # From pattern analyzer
    context_summary: str = None  # From pattern analyzer
    domain_entities: Dict[str, List[str]] = None  # From pattern analyzer
    
    # Metadata
    source: str = "pattern"  # "llm", "pattern", or "hybrid"
    agreement: bool = False  # LLM and patterns agree
    
    # Error tracking (NEW - for user notification)
    ai_error: Optional[str] = None  # Error message if AI failed
    ai_available: bool = True  # Whether AI was available for this analysis
    
    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "intent": self.intent,
            "business_impact": self.business_impact,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "pattern_features": {
                "category": self.pattern_category,
                "intent": self.pattern_intent,
                "confidence": self.pattern_confidence,
                "features": self.pattern_features
            },
            "similar_issues": self.similar_issues,
            "metadata": {
                "source": self.source,
                "agreement": self.agreement
            }
        }


class HybridContextAnalyzer:
    """
    Hybrid analyzer combining LLM and pattern matching
    
    Strategy:
    1. Run pattern matching first (fast, provides features)
    2. Pass pattern features to LLM as context
    3. LLM makes final decision with pattern insights
    4. Search for similar issues using embeddings
    5. Fall back to patterns if LLM fails
    """
    
    def __init__(self, use_ai: bool = True):
        """
        Initialize hybrid analyzer with AI and pattern matching capabilities
        
        INITIALIZATION SEQUENCE:
        ------------------------
        1. Initialize pattern analyzer (always, serves as baseline/fallback)
        2. Load AI configuration from environment variables
        3. Load corrections database for learning (Phase 1)
        4. Initialize AI services if enabled (LLM, embeddings, vector search)
        5. Verify AI connectivity and fall back gracefully if unavailable
        
        Args:
            use_ai (bool): Whether to use AI services. Default True.
                          If False, system uses pure pattern matching.
                          If True but AI unavailable, falls back to patterns.
        
        ENVIRONMENT VARIABLES REQUIRED (if use_ai=True):
        ------------------------------------------------
        - AZURE_OPENAI_ENDPOINT: Your Azure OpenAI endpoint URL
        - AZURE_OPENAI_API_KEY: Your Azure OpenAI API key
        - AZURE_OPENAI_DEPLOYMENT: Your GPT-4 deployment name
        - AZURE_OPENAI_EMBEDDING_DEPLOYMENT: Your embedding model deployment
        - AZURE_OPENAI_API_VERSION: API version (e.g., "2024-02-15-preview")
        
        GRACEFUL DEGRADATION:
        ---------------------
        - Missing AI config → Logs warning, falls back to patterns
        - AI service errors → Logs error, falls back to patterns
        - Pattern analyzer always works (no external dependencies)
        """
        print("[DEBUG HYBRID 1] HybridContextAnalyzer.__init__() starting...", flush=True)
        # Always initialize pattern matcher (baseline + fallback)
        print("[DEBUG HYBRID 2] Creating IntelligentContextAnalyzer...", flush=True)
        self.pattern_analyzer = IntelligentContextAnalyzer()
        print("[DEBUG HYBRID 3] IntelligentContextAnalyzer created.", flush=True)
        
        # AI configuration
        self.use_ai = use_ai
        self._init_error = None  # Track init errors for propagation to health dashboard and results
        print("[DEBUG HYBRID 4] Getting AI config...", flush=True)
        self.config = get_config()
        print("[DEBUG HYBRID 5] AI config loaded.", flush=True)
        
        # Load corrections for learning (Phase 1 - Corrective Learning System)
        print("[DEBUG HYBRID 6] Loading corrections...", flush=True)
        self.corrections_data = self._load_corrections()
        print(f"[HybridAnalyzer] Loaded {len(self.corrections_data.get('corrections', []))} corrections for learning")
        print("[DEBUG HYBRID 7] Corrections loaded.", flush=True)

        # Load training signals for few-shot injection (ENG-003 Step 4)
        print("[DEBUG HYBRID 7b] Loading training signals...", flush=True)
        self.training_signals = self._load_training_signals()
        print(f"[HybridAnalyzer] Loaded {len(self.training_signals)} training signals for few-shot injection")
        
        # Initialize AI services if enabled
        if self.use_ai:
            print("[DEBUG HYBRID 8] use_ai=True, initializing AI services...", flush=True)
            try:
                print("[DEBUG HYBRID 9] Validating config...", flush=True)
                validate_config()
                print("[DEBUG HYBRID 10] Config validated. Creating LLMClassifier...", flush=True)
                
                self.llm_classifier = LLMClassifier()
                print("[DEBUG HYBRID 11] LLMClassifier created. Creating EmbeddingService...", flush=True)
                self.embedding_service = EmbeddingService()
                print("[DEBUG HYBRID 12] EmbeddingService created. Creating VectorSearchService...", flush=True)
                self.vector_search = VectorSearchService()
                print("[DEBUG HYBRID 13] VectorSearchService created!", flush=True)
                
                print("[HybridAnalyzer] AI services initialized successfully")
                print(f"[HybridAnalyzer] Mode: AI-powered with pattern features")
                print("[DEBUG HYBRID 14] AI services initialization complete!", flush=True)
            except Exception as e:
                print(f"[HybridAnalyzer] AI initialization failed: {e}")
                print("[HybridAnalyzer] Falling back to pattern matching only")
                self.use_ai = False
                self._init_error = str(e)  # Store init error so it reaches the result
                print("[DEBUG HYBRID 15] Fell back to pattern-only mode.", flush=True)
        else:
            print("[HybridAnalyzer] Mode: Pattern matching only (AI disabled)")
            print("[DEBUG HYBRID 16] AI disabled by parameter.", flush=True)
        
        print("[DEBUG HYBRID 17] HybridContextAnalyzer.__init__() completed successfully!", flush=True)
    
    def _load_corrections(self) -> Dict:
        """
        Load user corrections for continuous learning.
        
        Tries Cosmos DB first, falls back to corrections.json.
        
        USAGE IN ANALYSIS:
        ------------------
        Corrections are used in two ways:
        1. Pattern Matching: Similar corrections add context to features
        2. LLM Prompting: Relevant corrections included in prompt as examples
        
        Returns:
            Dict: Corrections data structure with 'corrections' list
                  Empty dict with empty list if unavailable
        """
        # Try Cosmos first
        try:
            from triage.config.cosmos_config import get_cosmos_config
            cfg = get_cosmos_config()
            if not cfg._in_memory:
                container = cfg.get_container("corrections")
                items = list(container.query_items(
                    "SELECT * FROM c",
                    enable_cross_partition_query=True
                ))
                if items:
                    print(f"[HybridAnalyzer] Loaded {len(items)} corrections from Cosmos")
                    return {"corrections": items}
        except Exception as e:
            print(f"[HybridAnalyzer] Cosmos corrections load failed, falling back to file: {e}")
        
        # Fallback to JSON file
        try:
            module_dir = Path(__file__).resolve().parent
            corrections_file = module_dir / 'data' / 'corrections.json'
            if corrections_file.exists():
                with open(corrections_file, 'r') as f:
                    return json.load(f)
            else:
                print("[HybridAnalyzer] No corrections.json found - starting fresh")
        except Exception as e:
            print(f"[HybridAnalyzer] Error loading corrections: {e}")
        return {"corrections": []}
    
    def _load_training_signals(self) -> List[Dict]:
        """
        Load resolved training signals from Cosmos for few-shot LLM injection.

        ENG-003 Step 4: Training signals capture human resolutions of LLM/Pattern
        disagreements. By injecting the most recent resolved examples into the LLM
        prompt, we give the model concrete evidence of correct classifications.

        Returns:
            List of training signal dicts (most recent first, max 50)
        """
        try:
            from triage.config.cosmos_config import get_cosmos_config
            cfg = get_cosmos_config()
            if not cfg._in_memory:
                container = cfg.get_container("training-signals")
                items = list(container.query_items(
                    "SELECT * FROM c WHERE c.workItemId != '_system' ORDER BY c.timestamp DESC",
                    enable_cross_partition_query=True,
                    max_item_count=50,
                ))[:50]
                if items:
                    print(f"[HybridAnalyzer] Loaded {len(items)} training signals from Cosmos")
                    return items
        except Exception as e:
            print(f"[HybridAnalyzer] Training signals load failed: {e}")
        return []

    def _find_relevant_training_signals(self, text: str, pattern_category: str, llm_category: str) -> List[Dict]:
        """
        Find training signals most relevant to the current classification.

        ENG-003 Step 4: Select signals that relate to the categories being
        considered, giving the LLM concrete examples of correct human choices.

        Priority:
        1. Signals where llmCategory or patternCategory matches the current categories
        2. Signals with 'neither' resolutions (rarest, most valuable)
        3. Most recent first

        Args:
            text: Combined title + description for keyword matching
            pattern_category: Current pattern engine category
            llm_category: Current LLM category (empty string if not yet classified)

        Returns:
            List of relevant training signals (max 5)
        """
        if not self.training_signals:
            return []

        scored = []
        text_lower = text.lower()
        text_words = set(w for w in text_lower.split() if len(w) > 3)

        for sig in self.training_signals:
            score = 0.0
            sig_llm = sig.get("llmCategory", "")
            sig_pat = sig.get("patternCategory", "")
            resolved = sig.get("resolvedCategory", "")

            # Category relevance: boost if the signal's categories overlap with current
            if pattern_category and (sig_pat == pattern_category or sig_llm == pattern_category):
                score += 3.0
            if llm_category and (sig_llm == llm_category or sig_pat == llm_category):
                score += 3.0
            if resolved and (resolved == pattern_category or resolved == llm_category):
                score += 2.0

            # 'neither' resolutions are most informative
            if sig.get("humanChoice") == "neither":
                score += 1.5

            # Light keyword overlap
            notes = (sig.get("notes", "") or "").lower()
            if text_words and notes:
                note_words = set(w for w in notes.split() if len(w) > 3)
                if note_words:
                    overlap = len(text_words & note_words)
                    score += min(overlap * 0.3, 1.5)

            if score > 0:
                scored.append((score, sig))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [s for _, s in scored[:5]]

    def _find_relevant_corrections(self, text: str) -> List[Dict]:
        """
        Find corrections relevant to the current issue
        Uses simple keyword matching to find similar past issues
        
        Args:
            text: Combined text (title + description + impact)
            
        Returns:
            List of relevant corrections (max 3)
        """
        corrections = self.corrections_data.get('corrections', [])
        if not corrections:
            return []
        
        text_lower = text.lower()
        text_words = set(word for word in text_lower.split() if len(word) > 3)
        
        scored_corrections = []
        
        for correction in corrections:
            original_text = correction.get('original_text', '').lower()
            if not original_text:
                continue
            
            original_words = set(word for word in original_text.split() if len(word) > 3)
            
            # Calculate word overlap
            if original_words and text_words:
                overlap = len(text_words & original_words)
                similarity = overlap / len(text_words | original_words)
                
                if similarity > 0.2:  # At least 20% word overlap
                    scored_corrections.append((similarity, correction))
        
        # Sort by similarity, take top 3
        scored_corrections.sort(reverse=True, key=lambda x: x[0])
        return [corr for _, corr in scored_corrections[:3]]
    
    def _extract_pattern_features(self, pattern_result: Any) -> Dict[str, Any]:
        """
        Extract features from pattern matching result
        
        Args:
            pattern_result: Result from IntelligentContextAnalyzer
            
        Returns:
            Dictionary of features for LLM
        """
        features = {}
        
        # Basic classification
        features["category_scores"] = {}
        features["detected_products"] = []
        features["technical_indicators"] = []
        
        # Extract category if available
        if hasattr(pattern_result, 'category'):
            # Add the pattern category with its confidence
            category_str = str(pattern_result.category)
            if hasattr(pattern_result, 'confidence'):
                features["category_scores"][category_str] = pattern_result.confidence
            else:
                features["category_scores"][category_str] = 0.5
            
            # Get additional category scores from reasoning if available
            if hasattr(pattern_result, 'reasoning') and isinstance(pattern_result.reasoning, dict):
                reasoning = pattern_result.reasoning
                
                # Look for confidence factors or category analysis
                if "confidence_factors" in reasoning:
                    for factor in reasoning["confidence_factors"]:
                        if "Category confidence" in factor:
                            confidence = float(factor.split(":")[-1].strip())
                            features["category_scores"][category_str] = confidence
                
                # Extract Microsoft products
                if "microsoft_products_detected" in reasoning:
                    products = reasoning["microsoft_products_detected"]
                    if isinstance(products, list):
                        for product in products:
                            if isinstance(product, dict):
                                features["detected_products"].append(product.get("name", ""))
                            else:
                                features["detected_products"].append(str(product))
        
        # Look for technical indicators in text
        technical_keywords = [
            "error", "issue", "problem", "not working", "failing", "failed",
            "unable to", "cannot", "can't", "trouble", "difficulty"
        ]
        
        # Add relevant corrections (NEW for Phase 1)
        features["relevant_corrections"] = []
        
        return features
    
    def analyze(
        self,
        title: str,
        description: str,
        impact: str = "",
        search_similar: bool = True
    ) -> HybridAnalysisResult:
        """
        Perform hybrid analysis using AI + patterns
        
        Args:
            title: Issue title
            description: Issue description
            impact: Business impact statement
            search_similar: Whether to search for similar issues
            
        Returns:
            HybridAnalysisResult with complete analysis
        """
        print(f"\n{'='*80}")
        print(f"🔬 HYBRID CONTEXT ANALYZER - Processing Issue")
        print(f"{'='*80}")
        print(f"Title: {title[:70]}...")
        print(f"Mode: {'AI-Powered' if self.use_ai else 'Pattern Only'}")
        print(f"{'='*80}\n")
        print(f"[DEBUG TRACE 1] Starting pattern matching analysis...", flush=True)
        
        # STEP 1: Run pattern matching (always, provides features)
        print("📊 Step 1: Pattern Matching Analysis...")
        print(f"[DEBUG TRACE 2] About to call pattern_analyzer.analyze_context...", flush=True)
        pattern_result = self.pattern_analyzer.analyze_context(title, description, impact)
        print(f"[DEBUG TRACE 3] Pattern analysis complete!", flush=True)
        
        # Extract pattern features
        print(f"[DEBUG TRACE 4] Extracting pattern features...", flush=True)
        pattern_features = self._extract_pattern_features(pattern_result)
        print(f"[DEBUG TRACE 5] Pattern features extracted!", flush=True)
        
        # Find relevant corrections (NEW for Phase 1)
        print(f"[DEBUG TRACE 6] Finding relevant corrections...", flush=True)
        combined_text = f"{title} {description} {impact}"
        relevant_corrections = self._find_relevant_corrections(combined_text)
        pattern_features["relevant_corrections"] = relevant_corrections
        print(f"[DEBUG TRACE 7] Corrections found: {len(relevant_corrections)}", flush=True)
        
        if relevant_corrections:
            print(f"   ℹ️ Found {len(relevant_corrections)} relevant corrections from past feedback")

        pattern_category = pattern_result.category if hasattr(pattern_result, 'category') else "technical_support"
        # ─── B0001 fix: Normalize enum to string for comparison with LLM string output ───
        # Pattern matcher returns TriageCategory enum, but the LLM classifier returns
        # plain strings.  Without .value extraction the agreement check at Step 3
        # always evaluates False because "Enum.x" != "x".
        # See docs/CHANGE_LOG.md → B0001 for full root-cause analysis.
        if hasattr(pattern_category, 'value'):
            pattern_category = pattern_category.value
        pattern_intent = pattern_result.intent if hasattr(pattern_result, 'intent') else "service_inquiry"
        if hasattr(pattern_intent, 'value'):
            pattern_intent = pattern_intent.value
        pattern_confidence = pattern_result.confidence if hasattr(pattern_result, 'confidence') else 0.5

        # Find relevant training signals for few-shot injection (ENG-003 Step 4)
        relevant_signals = self._find_relevant_training_signals(
            combined_text, pattern_category, llm_category=""
        )
        pattern_features["relevant_training_signals"] = relevant_signals
        if relevant_signals:
            print(f"   ℹ️ Injecting {len(relevant_signals)} training signals as few-shot examples")
        
        print(f"   ✓ Pattern Category: {pattern_category}")
        print(f"   ✓ Pattern Intent: {pattern_intent}")
        print(f"   ✓ Pattern Confidence: {pattern_confidence:.2f}")
        print(f"[DEBUG TRACE 8] Pattern analysis complete, moving to step 2...", flush=True)
        
        # STEP 2: Search for similar issues (if enabled)
        similar_issues = []
        if search_similar and self.use_ai:
            print("\n🔍 Step 2: Semantic Similarity Search...")
            try:
                # This would search indexed UATs/issues
                # For now, return empty list (needs indexed data)
                similar_results = []
                for result in similar_results:
                    similar_issues.append({
                        "id": result.item_id,
                        "title": result.title,
                        "similarity": result.similarity
                    })
                print(f"   ✓ Found {len(similar_issues)} similar issues")
            except Exception as e:
                print(f"   ⚠ Similarity search failed: {e}")
        
        # STEP 3: LLM Classification (if AI enabled)
        ai_error_message = None  # Track any AI errors
        if self.use_ai:
            print("\n🤖 Step 3: LLM Classification with Pattern Features...")
            try:
                llm_result = self.llm_classifier.classify(
                    title=title,
                    description=description,
                    impact=impact,
                    pattern_features=pattern_features,
                    use_cache=True
                )
                
                # Check if LLM and patterns agree (category match is what matters for triage).
                # Works correctly now that pattern_category is normalized to a plain
                # string above (B0001).
                agreement = (
                    llm_result.category == pattern_category
                )
                
                print(f"   ✓ LLM Category: {llm_result.category}")
                print(f"   ✓ LLM Intent: {llm_result.intent}")
                print(f"   ✓ LLM Confidence: {llm_result.confidence:.2f}")
                print(f"   {'✓' if agreement else '⚠'} LLM/Pattern Agreement: {agreement}")
                
                # Extract semantic keywords and key concepts from pattern result
                semantic_kw = pattern_result.semantic_keywords if hasattr(pattern_result, 'semantic_keywords') else []
                key_conc = pattern_result.key_concepts if hasattr(pattern_result, 'key_concepts') else []
                search_strat = pattern_result.recommended_search_strategy if hasattr(pattern_result, 'recommended_search_strategy') else {}
                urgency = pattern_result.urgency_level if hasattr(pattern_result, 'urgency_level') else "medium"
                tech_complex = pattern_result.technical_complexity if hasattr(pattern_result, 'technical_complexity') else "medium"
                domain_ents = pattern_result.domain_entities if hasattr(pattern_result, 'domain_entities') else {}
                
                # Keep pattern's original reasoning for step-by-step display
                pattern_reasoning = pattern_result.reasoning if hasattr(pattern_result, 'reasoning') else {}
                
                # Use LLM's reasoning as context summary (it's much better than pattern-based generic summaries)
                # The LLM reasoning already provides a clear, concise explanation of the issue
                ctx_summary = llm_result.reasoning if llm_result.reasoning else self.pattern_analyzer._generate_context_summary(
                    llm_result.category, llm_result.intent, domain_ents, key_conc, 
                    llm_result.business_impact, f"{title}\n{description}"
                )
                
                # Use LLM results as primary
                result = HybridAnalysisResult(
                    category=llm_result.category,
                    intent=llm_result.intent,
                    business_impact=llm_result.business_impact,
                    confidence=llm_result.confidence,
                    reasoning=llm_result.reasoning,
                    pattern_category=pattern_category,
                    pattern_intent=pattern_intent,
                    pattern_confidence=pattern_confidence,
                    pattern_features=pattern_features,
                    pattern_reasoning=pattern_reasoning,  # NEW: Include pattern's step-by-step reasoning
                    similar_issues=similar_issues,
                    semantic_keywords=semantic_kw,
                    key_concepts=key_conc,
                    recommended_search_strategy=search_strat,
                    urgency_level=urgency,
                    technical_complexity=tech_complex,
                    context_summary=ctx_summary,
                    domain_entities=domain_ents,
                    source="hybrid" if agreement else "llm",
                    agreement=agreement,
                    ai_error=None,  # No error - AI worked
                    ai_available=True
                )
                
                print(f"\n✅ Analysis Complete (Source: {result.source})")
                return result
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ✗ LLM classification failed: {error_msg}")
                print(f"   ↩️  Falling back to pattern matching")
                # Store error for user notification
                ai_error_message = error_msg
        
        # STEP 4: Fallback to pattern matching
        print("\n📋 Using Pattern Matching Results...")
        
        # If AI was disabled at init time (not during classify), include that error
        if ai_error_message is None and self._init_error:
            ai_error_message = f"AI init failed: {self._init_error}"
        
        # Use pattern analyzer's full reasoning if available
        pattern_reasoning = pattern_result.reasoning if hasattr(pattern_result, 'reasoning') else {}
        
        # Extract semantic keywords and key concepts from pattern result
        semantic_kw = pattern_result.semantic_keywords if hasattr(pattern_result, 'semantic_keywords') else []
        key_conc = pattern_result.key_concepts if hasattr(pattern_result, 'key_concepts') else []
        search_strat = pattern_result.recommended_search_strategy if hasattr(pattern_result, 'recommended_search_strategy') else {}
        urgency = pattern_result.urgency_level if hasattr(pattern_result, 'urgency_level') else "medium"
        tech_complex = pattern_result.technical_complexity if hasattr(pattern_result, 'technical_complexity') else "medium"
        ctx_summary = pattern_result.context_summary if hasattr(pattern_result, 'context_summary') else ""
        domain_ents = pattern_result.domain_entities if hasattr(pattern_result, 'domain_entities') else {}
        
        result = HybridAnalysisResult(
            category=pattern_category,
            intent=pattern_intent,
            business_impact=pattern_result.business_impact if hasattr(pattern_result, 'business_impact') else (impact if impact else "medium"),
            confidence=pattern_confidence,
            reasoning=pattern_reasoning,
            pattern_category=pattern_category,
            pattern_intent=pattern_intent,
            pattern_confidence=pattern_confidence,
            pattern_features=pattern_features,
            pattern_reasoning=pattern_reasoning,  # Same as reasoning when using pattern fallback
            similar_issues=similar_issues,
            semantic_keywords=semantic_kw,
            key_concepts=key_conc,
            recommended_search_strategy=search_strat,
            urgency_level=urgency,
            technical_complexity=tech_complex,
            context_summary=ctx_summary,
            domain_entities=domain_ents,
            source="pattern",
            agreement=None,  # B0003: No LLM to compare — agreement is not applicable
            ai_error=ai_error_message,  # Include any AI error that occurred
            ai_available=self.use_ai and ai_error_message is None
        )
        
        if ai_error_message:
            print(f"⚠️  Note: AI unavailable, used pattern matching (Reason: {ai_error_message})")
        print(f"✅ Analysis Complete (Source: pattern fallback)")
        return result
    
    def get_ai_status(self) -> Dict[str, Any]:
        """Get status of AI services for health dashboard.
        
        Returns a dict with:
          - enabled (bool): Whether AI services are active
          - reason (str, if disabled): The init error or 'AI disabled'
          - endpoint (str, if disabled): The configured OpenAI endpoint (for diagnostics)
          - use_aad (bool, if disabled): Whether AAD auth is configured
          - llm_cache_stats / embedding_cache_stats (if enabled): Cache metrics
          
        Updated Feb 27, 2026: Now propagates _init_error and endpoint info
        so the admin health dashboard can show actionable diagnostics instead
        of a generic 'AI disabled' message.
        """
        if not self.use_ai:
            return {
                "enabled": False,
                "reason": self._init_error or "AI disabled",
                "endpoint": getattr(self.config.azure_openai, 'endpoint', '') if self.config else '',
                "use_aad": getattr(self.config.azure_openai, 'use_aad', None) if self.config else None,
            }
        
        try:
            return {
                "enabled": True,
                "llm_cache_stats": self.llm_classifier.get_cache_stats(),
                "embedding_cache_stats": self.embedding_service.get_cache_stats()
            }
        except Exception as e:
            return {
                "enabled": False,
                "reason": f"Error: {e}"
            }


def test_hybrid_analyzer():
    """Test the hybrid analyzer with real cases"""
    print("Hybrid Context Analyzer Test")
    print("=" * 80)
    
    # Test cases from previous issues
    test_cases = [
        {
            "title": "SCVMM to Azure Migrate Roadmap",
            "description": "We are looking to migrate several workloads from SCVMM to Azure Migrate, but I am running into trouble connecting the SCVMM service to Azure Migrate. Is this possible?",
            "impact": "Blocking our migration to Azure",
            "expected_category": "technical_support"
        },
        {
            "title": "SQL MI in West Europe",
            "description": "Is SQL Managed Instance with Azure SQL Database Hyperscale available in West Europe region? This service is required in West Europe.",
            "impact": "Critical for production deployment",
            "expected_category": "service_availability"
        },
        {
            "title": "Planner & Roadmap demo",
            "description": "Can you give me a demo of the Planner & Roadmap feature to understand how it works?",
            "impact": "Want to evaluate if it fits our needs",
            "expected_category": "seeking_guidance"
        }
    ]
    
    analyzer = HybridContextAnalyzer(use_ai=True)
    
    print("\n" + "="*80)
    print("AI Services Status:")
    status = analyzer.get_ai_status()
    print(json.dumps(status, indent=2))
    print("="*80)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST CASE {i}: {test_case['title']}")
        print(f"Expected Category: {test_case['expected_category']}")
        print(f"{'='*80}")
        
        result = analyzer.analyze(
            title=test_case['title'],
            description=test_case['description'],
            impact=test_case['impact'],
            search_similar=False  # Don't search without indexed data
        )
        
        print(f"\n📊 RESULTS:")
        print(f"   Category: {result.category}")
        print(f"   Intent: {result.intent}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Source: {result.source}")
        print(f"   Agreement: {result.agreement}")
        print(f"   Reasoning: {result.reasoning[:200]}...")
        
        # Check if matches expected
        matches = result.category == test_case['expected_category']
        print(f"\n   {'✅ CORRECT' if matches else '❌ INCORRECT'}")


if __name__ == "__main__":
    import json
    test_hybrid_analyzer()
