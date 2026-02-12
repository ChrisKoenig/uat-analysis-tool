"""
Analysis Result Model
=====================

Represents the structured output from the analysis engine.
Stored in Cosmos DB for analytics, fine-tuning, and rule evaluation.

The analysis result contains the complete output of the existing
Intelligent Context Analysis System: category classification,
product detection, sentiment analysis, confidence scores, and
extracted entities.

This data is used by the rules engine to evaluate conditions like:
    - Analysis.Category = "Feature Request"
    - Analysis.Products contains "Route Server"
    - Analysis.Confidence > 0.8

Cosmos DB Container: analysis-results
Partition Key: /workItemId
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .base import utc_now


@dataclass
class AnalysisResult:
    """
    Structured output from the analysis engine for a single work item.
    
    Contains all analysis dimensions used by the triage rules engine:
        - Classification (category, intent, confidence)
        - Entity extraction (products, services, regions)
        - Business context (impact, complexity, urgency)
        - Pattern matching (corrections, similar issues)
    
    Not a BaseEntity - analysis results are immutable snapshots,
    not managed entities with lifecycle.
    
    Attributes:
        id:                 analysis-{workItemId}-{date}
        workItemId:         ADO work item ID (partition key)
        timestamp:          When the analysis was performed
        originalTitle:      Work item title at time of analysis
        originalDescription: Work item description at time of analysis
        
    Classification:
        category:           Primary category (e.g., "feature_request")
        intent:             Inferred intent (e.g., "requesting_feature")
        confidence:         Overall confidence score (0.0 - 1.0)
        source:             Analysis source (e.g., "hybrid", "llm", "pattern")
        agreement:          Whether pattern and LLM agree
        
    Business Context:
        businessImpact:     Impact level (high/medium/low)
        technicalComplexity: Complexity (high/medium/low)
        urgencyLevel:       Urgency (high/medium/low)
        
    Extracted Entities:
        detectedProducts:   List of Azure products mentioned
        azureServices:      Azure service names
        regions:            Azure regions mentioned
        technologies:       Technologies referenced
        
    Semantic Context:
        keyConcepts:        Key concepts extracted
        semanticKeywords:   Keywords for search/matching
        contextSummary:     Brief summary of the item
        reasoning:          LLM reasoning for the classification
    """
    
    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    id: str = ""                              # analysis-{workItemId}-{date}
    workItemId: int = 0                       # ADO work item ID (partition key)
    timestamp: str = field(default_factory=utc_now)
    
    # -------------------------------------------------------------------------
    # Original Data
    # -------------------------------------------------------------------------
    originalTitle: str = ""
    originalDescription: str = ""
    
    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------
    category: str = ""                        # Primary category
    intent: str = ""                          # Inferred intent
    confidence: float = 0.0                   # Overall confidence (0.0-1.0)
    source: str = ""                          # Analysis source
    agreement: bool = False                   # Pattern/LLM agreement
    
    # -------------------------------------------------------------------------
    # Business Context
    # -------------------------------------------------------------------------
    businessImpact: str = ""                  # high/medium/low
    technicalComplexity: str = ""             # high/medium/low
    urgencyLevel: str = ""                    # high/medium/low
    
    # -------------------------------------------------------------------------
    # Extracted Entities
    # -------------------------------------------------------------------------
    detectedProducts: List[str] = field(default_factory=list)
    azureServices: List[str] = field(default_factory=list)
    complianceFrameworks: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)
    businessDomains: List[str] = field(default_factory=list)
    technicalAreas: List[str] = field(default_factory=list)
    
    # -------------------------------------------------------------------------
    # Semantic Context
    # -------------------------------------------------------------------------
    keyConcepts: List[str] = field(default_factory=list)
    semanticKeywords: List[str] = field(default_factory=list)
    contextSummary: str = ""
    reasoning: str = ""
    
    # -------------------------------------------------------------------------
    # Pattern Matching
    # -------------------------------------------------------------------------
    patternCategory: str = ""                 # Category from pattern engine
    patternConfidence: float = 0.0            # Pattern confidence
    categoryScores: Dict[str, float] = field( # All category scores
        default_factory=dict
    )
    
    # -------------------------------------------------------------------------
    # Technical Indicators
    # -------------------------------------------------------------------------
    technicalIndicators: List[str] = field(default_factory=list)
    relevantCorrections: List[str] = field(default_factory=list)
    similarIssues: List[str] = field(default_factory=list)
    
    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    aiAvailable: bool = True                  # Was AI available for analysis
    aiError: Optional[str] = None             # Any AI error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Cosmos DB storage"""
        from dataclasses import asdict
        from enum import Enum

        def _sanitize(obj):
            """Recursively convert enums to their values for JSON serialization."""
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize(v) for v in obj]
            if isinstance(obj, Enum):
                return obj.value
            return obj

        return _sanitize(asdict(self))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisResult':
        """Create from Cosmos DB document"""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if analysis confidence meets the threshold"""
        return self.confidence >= threshold
    
    def has_products(self) -> bool:
        """Check if any products were detected"""
        return len(self.detectedProducts) > 0
    
    def get_analysis_field(self, field_name: str) -> Any:
        """
        Get an analysis field value by name.
        
        Used by the rules engine to resolve Analysis.* field references.
        
        Args:
            field_name: Field name without "Analysis." prefix
                       (e.g., "Category", "Products", "Confidence")
        
        Returns:
            Field value, or None if not found
        """
        # Map common Analysis.* names to attributes
        field_map = {
            "Category": self.category,
            "Intent": self.intent,
            "Confidence": self.confidence,
            "Source": self.source,
            "Agreement": self.agreement,
            "BusinessImpact": self.businessImpact,
            "TechnicalComplexity": self.technicalComplexity,
            "UrgencyLevel": self.urgencyLevel,
            "Products": self.detectedProducts,
            "Services": self.azureServices,
            "Regions": self.regions,
            "Technologies": self.technologies,
            "KeyConcepts": self.keyConcepts,
            "SemanticKeywords": self.semanticKeywords,
            "ContextSummary": self.contextSummary,
            "Reasoning": self.reasoning,
            "PatternCategory": self.patternCategory,
            "PatternConfidence": self.patternConfidence,
        }
        return field_map.get(field_name)
    
    def __repr__(self) -> str:
        return (
            f"AnalysisResult(workItem={self.workItemId}, "
            f"category='{self.category}', confidence={self.confidence}, "
            f"products={len(self.detectedProducts)})"
        )
