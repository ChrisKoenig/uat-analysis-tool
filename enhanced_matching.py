#!/usr/bin/env python3
"""
ENHANCED MATCHING SYSTEM v3.0 - AI-Powered Issue Analysis and Matching

=============================================================================
COMPREHENSIVE ISSUE MATCHING WITH INTELLIGENT CONTEXT ANALYSIS
=============================================================================

⚠️ PRODUCTION DEPLOYMENT NOTE:
   Currently using Azure CLI authentication for Azure DevOps searches.
   Before production deployment:
   - Switch to Service Principal authentication
   - Create Azure AD App Registration with Azure DevOps permissions
   - Update EnhancedMatchingConfig to use Service Principal credentials
   - Remove dependency on 'az login'

This module serves as the central orchestrator for intelligent issue matching,
combining AI-powered context analysis with multi-source knowledge base searches
and enterprise Azure DevOps integration.

MAJOR ENHANCEMENTS IN v3.0:
✅ Integration with Intelligent Context Analyzer for transparent AI reasoning
✅ Comprehensive step-by-step analysis display for user visibility
✅ Multi-source data integration (Azure APIs, retirements, corrections)
✅ Microsoft product detection with context awareness
✅ Corrective learning system for continuous improvement
✅ Real-time confidence scoring and decision tracking

CORE CAPABILITIES:
- AI-Powered Context Analysis: Understands user intent and issue category
- Multi-Source Knowledge Search: Azure DevOps, retirements, UATs, features
- Quality Analysis: Validates input completeness and provides improvement suggestions
- Progress Tracking: Real-time updates during analysis and matching operations
- Similarity Algorithms: Intelligent matching with confidence scoring
- Enterprise Integration: Seamless Azure DevOps workflow management

KEY COMPONENTS:
- EnhancedMatchingConfig: Centralized configuration for all integrations
- ProgressTracker: Real-time progress updates with detailed status messages
- AIAnalyzer: Input quality analysis and completeness scoring
- EnhancedMatching: Main orchestrator integrating all analysis and matching capabilities

WORKFLOW INTEGRATION:
1. Input Quality Analysis: Validates and scores user input completeness
2. Intelligent Context Analysis: AI-powered understanding with full transparency
3. Multi-Source Search: Searches retirements, UATs, features based on analysis
4. Similarity Matching: Finds similar issues with confidence scoring
5. Result Synthesis: Combines all findings with reasoning and recommendations

DATA SOURCES INTEGRATED:
- Azure DevOps Organizations (UAT, TFT, multiple projects)
- Service Retirement Database (retirements.json)
- Azure Services and Regions APIs
- User Corrections Database (corrections.json)
- Microsoft Learn Documentation

Author: Enhanced Matching Development Team
Version: 3.0 (Transparent AI Analysis with Multi-Source Integration)
Last Updated: December 2025
"""

# =============================================================================
# ENHANCED MATCHING SYSTEM - IMPORTS AND DEPENDENCIES
# =============================================================================
# Core system imports for comprehensive issue matching and AI analysis

# Standard library imports for API communication and data processing
import os                                               # Environment variable access
import requests                                         # Azure DevOps API communication
import json                                             # JSON data handling
import base64                                           # Authentication encoding
import re                                               # Regular expression processing
from typing import Dict, List, Optional, Tuple          # Type hinting for code clarity
from datetime import datetime, timedelta                # Time and date processing
from difflib import SequenceMatcher                     # Similarity matching algorithms
from urllib.parse import quote                          # URL encoding for API calls
import time                                             # Performance timing and delays

# Custom module imports for specialized functionality
from hybrid_context_analyzer import HybridContextAnalyzer
from intelligent_context_analyzer import IssueCategory, IntentType
# ↑ AI-powered hybrid context analysis with LLM and pattern matching

# =============================================================================
# SYSTEM INTEGRATION ARCHITECTURE
# =============================================================================
# This module serves as the central orchestrator that integrates:
# 1. AI-powered context analysis (IntelligentContextAnalyzer)
# 2. Service retirement checking (RetirementChecker)
# 3. Multi-source Azure DevOps searching
# 4. Quality analysis and progress tracking
# 5. Similarity matching and confidence scoring
# =============================================================================


class EnhancedMatchingConfig:
    """
    ENHANCED MATCHING SYSTEM CONFIGURATION
    
    Centralized configuration hub for all aspects of the enhanced matching system
    including Azure DevOps integrations, API endpoints, authentication, and
    analysis parameters.
    
    AZURE DEVOPS INTEGRATION:
    - Multiple organization support for comprehensive search coverage
    - Secure authentication with Personal Access Tokens
    - Configurable project scoping and search parameters
    
    QUALITY ANALYSIS PARAMETERS:
    - Input validation thresholds for completeness scoring
    - Similarity matching confidence levels
    - Progress tracking and timeout settings
    
    CONFIGURATION CATEGORIES:
    
    1. AZURE DEVOPS ORGANIZATIONS:
       - UAT_ORGANIZATION: Primary organization for User Acceptance Testing
       - TFT_ORGANIZATION: Secondary organization for Technical Feedback Teams
       - Additional organizations can be added for comprehensive coverage
    
    2. AUTHENTICATION:
       - PAT: Personal Access Token for secure Azure DevOps API access
       - Base64 encoding for API authentication headers
    
    3. QUALITY THRESHOLDS:
       - MIN_DESCRIPTION_WORDS: Minimum word count for quality descriptions
       - SIMILARITY_THRESHOLD: Minimum similarity score for issue matching
       - CONFIDENCE_THRESHOLD: Minimum confidence for automated recommendations
    
    4. PERFORMANCE SETTINGS:
       - API_TIMEOUT: Maximum time for API calls
       - MAX_RESULTS: Maximum number of search results to process
       - CACHE_DURATION: How long to cache API responses
    """
    # UAT Azure DevOps Configuration (for searching existing UATs)
    UAT_ORGANIZATION = "unifiedactiontracker"
    UAT_PROJECT = "Unified Action Tracker"
    UAT_BASE_URL = f"https://dev.azure.com/{UAT_ORGANIZATION}"
    
    # Technical Feedback Azure DevOps Configuration (for searching existing Features)
    TFT_ORGANIZATION = "acrblockers"
    TFT_PROJECT = "Technical Feedback"
    TFT_BASE_URL = f"https://dev.azure.com/{TFT_ORGANIZATION}"
    
    API_VERSION = "7.0"
    
    # Azure DevOps scope for authentication
    ADO_SCOPE = "499b84ac-1321-427f-aa17-267ca6975798/.default"
    
    # Cached credentials to avoid re-authentication
    _uat_credential = None
    _uat_token = None
    _tft_credential = None
    _tft_token = None
    
    @staticmethod
    def get_uat_credential():
        """
        Get Azure credential for UAT organization (unifiedactiontracker) access.

        Uses InteractiveBrowserCredential with the same persistent disk cache
        as AzureDevOpsConfig so the user only authenticates once for all ADO
        orgs.  Auth chain:
        1. Return in-memory cached credential/token
        2. Reuse credential from AzureDevOpsConfig (if write-org already authed)
        3. ManagedIdentityCredential (headless deployment)
        4. InteractiveBrowserCredential with persistent cache "gcs-ado-auth"

        Returns:
            Tuple of (credential, token_string)
        """
        from azure.identity import (
            InteractiveBrowserCredential,
            ManagedIdentityCredential,
            TokenCachePersistenceOptions,
        )

        ADO_CACHE_NAME = "gcs-ado-auth"  # same cache as ado_integration.py

        # 1. Return in-memory cached credential if available
        if EnhancedMatchingConfig._uat_credential is not None and EnhancedMatchingConfig._uat_token is not None:
            print("[UAT Auth] Reusing cached credential", flush=True)
            return EnhancedMatchingConfig._uat_credential, EnhancedMatchingConfig._uat_token

        # 2. Try to reuse credential from the write-org client (already prompted)
        try:
            from ado_integration import AzureDevOpsConfig
            if AzureDevOpsConfig._cached_credential is not None:
                print("[UAT Auth] Reusing credential from AzureDevOpsConfig", flush=True)
                token = AzureDevOpsConfig._cached_credential.get_token(EnhancedMatchingConfig.ADO_SCOPE)
                EnhancedMatchingConfig._uat_credential = AzureDevOpsConfig._cached_credential
                EnhancedMatchingConfig._uat_token = token.token
                return EnhancedMatchingConfig._uat_credential, EnhancedMatchingConfig._uat_token
        except Exception as e:
            print(f"[UAT Auth] Could not reuse AzureDevOpsConfig credential: {e}", flush=True)

        # 3. Managed Identity (container / cloud)
        # Falls back to AZURE_CLIENT_ID if ADO_MANAGED_IDENTITY_CLIENT_ID is not set
        # (same pattern as ado_integration.py get_credential)
        ado_mi_client_id = os.environ.get("ADO_MANAGED_IDENTITY_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID")
        if ado_mi_client_id:
            try:
                credential = ManagedIdentityCredential(client_id=ado_mi_client_id)
                token = credential.get_token(EnhancedMatchingConfig.ADO_SCOPE)
                EnhancedMatchingConfig._uat_credential = credential
                EnhancedMatchingConfig._uat_token = token.token
                print("[UAT Auth] Managed Identity successful", flush=True)
                return credential, token.token
            except Exception as e:
                print(f"[UAT Auth] Managed Identity failed: {e}", flush=True)

        # 4. Interactive Browser with persistent disk cache
        cache_opts = TokenCachePersistenceOptions(name=ADO_CACHE_NAME)
        print("[UAT Auth] Using Interactive Browser credential (persistent cache)...", flush=True)
        credential = InteractiveBrowserCredential(
            cache_persistence_options=cache_opts,
        )
        token = credential.get_token(EnhancedMatchingConfig.ADO_SCOPE)
        print("[UAT Auth] Authentication successful (token cached to disk)", flush=True)
        EnhancedMatchingConfig._uat_credential = credential
        EnhancedMatchingConfig._uat_token = token.token
        return credential, token.token
    
    @staticmethod
    def get_tft_credential():
        """
        Get Azure credential for TFT organization (acrblockers) access.
        
        Reuses the cached UAT credential if available (same Microsoft account),
        otherwise creates a new InteractiveBrowserCredential.
        
        Returns:
            Tuple of (credential, token) for TFT Azure DevOps authentication
        """
        from azure.identity import InteractiveBrowserCredential, ManagedIdentityCredential
        
        # First check if TFT credential is already cached
        if EnhancedMatchingConfig._tft_credential is not None and EnhancedMatchingConfig._tft_token is not None:
            print("🔐 [TFT Auth] Reusing cached TFT credential...")
            return EnhancedMatchingConfig._tft_credential, EnhancedMatchingConfig._tft_token
        
        # Check if we can reuse the UAT credential (same account)
        if EnhancedMatchingConfig._uat_credential is not None:
            print("🔐 [TFT Auth] Checking if UAT credential works for TFT org...")
            try:
                token = EnhancedMatchingConfig._uat_credential.get_token(EnhancedMatchingConfig.ADO_SCOPE)
                print("✅ [TFT Auth] UAT credential reused successfully")
                EnhancedMatchingConfig._tft_credential = EnhancedMatchingConfig._uat_credential
                EnhancedMatchingConfig._tft_token = token.token
                return EnhancedMatchingConfig._uat_credential, token.token
            except Exception as e:
                print(f"⚠️  [TFT Auth] Cannot reuse UAT credential for TFT: {e}")
        
        # Managed Identity (container / cloud) — same pattern as get_uat_credential
        ado_mi_client_id = os.environ.get("ADO_MANAGED_IDENTITY_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID")
        if ado_mi_client_id:
            try:
                print(f"🔐 [TFT Auth] Trying Managed Identity (client_id={ado_mi_client_id[:8]}...)...")
                credential = ManagedIdentityCredential(client_id=ado_mi_client_id)
                token = credential.get_token(EnhancedMatchingConfig.ADO_SCOPE)
                print("✅ [TFT Auth] Managed Identity successful")
                EnhancedMatchingConfig._tft_credential = credential
                EnhancedMatchingConfig._tft_token = token.token
                return credential, token.token
            except Exception as e:
                print(f"⚠️  [TFT Auth] Managed Identity failed: {e}")
        
        # Try Azure CLI (no prompts)
        try:
            from azure.identity import AzureCliCredential
            print("🔐 [TFT Auth] Trying Azure CLI credential...")
            credential = AzureCliCredential()
            token = credential.get_token(EnhancedMatchingConfig.ADO_SCOPE)
            print("✅ [TFT Auth] Azure CLI works for TFT org")
            EnhancedMatchingConfig._tft_credential = credential
            EnhancedMatchingConfig._tft_token = token.token
            return credential, token.token
        except Exception:
            pass
        
        # Fallback: Interactive Browser with Microsoft tenant ID
        print("🔐 [TFT Auth] Using Interactive Browser credential (one-time)...")
        tenant_id = "72f988bf-86f1-41af-91ab-2d7cd011db47"  # Microsoft tenant
        credential = InteractiveBrowserCredential(tenant_id=tenant_id)
        token = credential.get_token(EnhancedMatchingConfig.ADO_SCOPE)
        print("✅ [TFT Auth] Authentication successful (cached for session)")
        EnhancedMatchingConfig._tft_credential = credential
        EnhancedMatchingConfig._tft_token = token.token
        return credential, token.token
    
    # AI Analysis Configuration Parameters
    MIN_DESCRIPTION_WORDS = 5      # Minimum words required in description
    MIN_IMPACT_WORDS = 3           # Minimum words required in impact statement
    SIMILARITY_THRESHOLD = 0.7     # Minimum similarity score for matches
    MAX_RESULTS_PER_PAGE = 15      # Maximum results to display per page
    LOOKBACK_MONTHS = 12           # How far back to search for issues


class ProgressTracker:
    """
    Handles progress tracking and user feedback during the matching process
    
    This class provides real-time updates to users about the current state
    of the enhanced matching operation, including step-by-step progress
    indicators and completion status.
    
    Attributes:
        steps (List[str]): Ordered list of processing steps
        current_step (int): Index of currently executing step
        progress (float): Overall completion percentage
    """
    
    def __init__(self):
        """Initialize progress tracker with predefined steps"""
        self.steps = [
            "Analyzing submission for completeness",
            "Enhancing description and impact statements", 
            "Evaluating Retirements database",
            "Evaluating UAT work items",
            "Examining existing features",
            "Compiling results"
        ]
        self.current_step = 0
        self.progress_data = {}
    
    def start_step(self, step_name: str) -> Dict:
        """Start a new processing step"""
        self.current_step += 1
        progress_percent = min(int((self.current_step / len(self.steps)) * 100), 100)
        
        return {
            'step': self.current_step,
            'total_steps': len(self.steps),
            'current_task': step_name,
            'progress_percent': progress_percent,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_progress(self) -> Dict:
        """Get current progress status"""
        return {
            'step': self.current_step,
            'total_steps': len(self.steps),
            'progress_percent': min(int((self.current_step / len(self.steps)) * 100), 100)
        }


class AIAnalyzer:
    """AI-powered analysis for issue completeness and enhancement"""
    
    @staticmethod
    def _detect_garbage_text(text: str) -> Dict:
        """Detect if text appears to be garbage/meaningless input"""
        if not text or not text.strip():
            return {'is_garbage': True, 'reason': 'empty', 'confidence': 1.0}
        
        text = text.strip().lower()
        
        # Check for keyboard mashing patterns
        repeating_chars = re.findall(r'(.)\1{3,}', text)  # 4+ repeated chars
        if repeating_chars:
            return {'is_garbage': True, 'reason': 'repeating_characters', 'confidence': 0.9}
        
        # Check for random character sequences (high consonant clusters)
        consonant_clusters = re.findall(r'[bcdfghjklmnpqrstvwxyz]{4,}', text)
        if consonant_clusters and len(''.join(consonant_clusters)) > len(text) * 0.3:
            return {'is_garbage': True, 'reason': 'consonant_clusters', 'confidence': 0.8}
        
        # Check for alternating character patterns (like "fdsafdsafdsa")
        if len(text) > 6:
            pattern_size = 3
            for i in range(len(text) - pattern_size * 2):
                pattern = text[i:i + pattern_size]
                if text[i + pattern_size:i + pattern_size * 2] == pattern:
                    # Found repeating pattern
                    pattern_count = 1
                    j = i + pattern_size
                    while j + pattern_size <= len(text) and text[j:j + pattern_size] == pattern:
                        pattern_count += 1
                        j += pattern_size
                    if pattern_count >= 3:  # Pattern repeats 3+ times
                        return {'is_garbage': True, 'reason': 'repeating_pattern', 'confidence': 0.9}
        
        # Enhanced check for keyboard mashing (like "fdsafdsafdsa", "asdfasdf")
        # Look for alternating key patterns common in keyboard mashing
        if len(text) > 6:
            # Check for alternating 2-3 char patterns
            for pattern_len in [2, 3, 4]:
                if len(text) >= pattern_len * 3:
                    pattern = text[:pattern_len]
                    repetitions = 0
                    pos = 0
                    while pos + pattern_len <= len(text):
                        if text[pos:pos + pattern_len] == pattern:
                            repetitions += 1
                            pos += pattern_len
                        else:
                            break
                    if repetitions >= 3:  # Pattern repeats 3+ times
                        return {'is_garbage': True, 'reason': 'keyboard_mashing_pattern', 'confidence': 0.9}
            
            # Special check for common keyboard row patterns
            keyboard_patterns = ['asdf', 'qwer', 'zxcv', 'hjkl', 'tyui', 'bnm', 'dfgh', 'cvbn']
            for pattern in keyboard_patterns:
                if pattern in text and len(text) <= len(pattern) * 2:
                    return {'is_garbage': True, 'reason': 'keyboard_row_pattern', 'confidence': 0.9}
        
        # Check for very low vowel ratio (strengthened)
        vowels = re.findall(r'[aeiou]', text)
        consonants = re.findall(r'[bcdfghjklmnpqrstvwxyz]', text)
        if len(text) > 5 and len(consonants) > 0:
            vowel_ratio = len(vowels) / len(consonants)
            if vowel_ratio < 0.15:  # Very low vowel to consonant ratio
                return {'is_garbage': True, 'reason': 'unnatural_letter_distribution', 'confidence': 0.7}
        
        # Check for no actual words (using basic English patterns)
        words = text.split()
        meaningful_words = 0
        for word in words:
            # Basic check for word-like patterns (contains vowels, reasonable consonant distribution)
            if len(word) > 1 and re.search(r'[aeiou]', word) and not re.match(r'^[bcdfghjklmnpqrstvwxyz]+$', word):
                # Additional check: does it look like a real word pattern?
                word_vowels = len(re.findall(r'[aeiou]', word))
                word_consonants = len(re.findall(r'[bcdfghjklmnpqrstvwxyz]', word))
                if word_consonants > 0 and word_vowels / word_consonants > 0.2:
                    meaningful_words += 1
        
        if len(words) > 0 and meaningful_words / len(words) < 0.3:
            return {'is_garbage': True, 'reason': 'no_meaningful_words', 'confidence': 0.8}
        
        # Check for specific garbage patterns like "fdsafdsafdsa"
        # Look for alternating consonant-vowel patterns that don't form real words
        if len(text) > 6 and re.match(r'^[a-z]+$', text):
            # Split into potential syllables and check if they make sense
            potential_syllables = re.findall(r'[bcdfghjklmnpqrstvwxyz]*[aeiou][bcdfghjklmnpqrstvwxyz]*', text)
            if len(potential_syllables) > 2:
                # Check if syllables are repetitive or nonsensical
                unique_syllables = set(potential_syllables)
                if len(unique_syllables) <= 2 and len(potential_syllables) > 3:
                    return {'is_garbage': True, 'reason': 'repetitive_syllable_pattern', 'confidence': 0.8}
        
        return {'is_garbage': False, 'reason': None, 'confidence': 0.0}
    
    @staticmethod
    def _generate_dynamic_suggestions(title: str, description: str, impact: str, issues: list) -> list:
        """Generate dynamic suggestions based on the actual input analysis"""
        suggestions = []
        
        # Analyze what the user actually provided vs what's missing
        title_analysis = AIAnalyzer._analyze_text_quality(title or "")
        desc_analysis = AIAnalyzer._analyze_text_quality(description or "")
        impact_analysis = AIAnalyzer._analyze_text_quality(impact or "")
        
        # Dynamic title suggestions
        if 'title_insufficient' in issues or 'title_garbage' in issues:
            if title_analysis['is_garbage']:
                suggestions.append(f"Your title '{title}' appears to be random characters. Please write a clear Azure-related title describing your problem, like 'Azure VM login button not working' or 'Azure Function notifications not sending'.")
            elif len((title or "").split()) < 3:
                suggestions.append(f"Your title '{title}' is too short. Try expanding it to describe the specific Azure problem, like 'Cannot access [Azure service] when [doing what]'.")
        
        # Check for vague titles that need more specificity
        if 'title_too_vague' in issues or 'title_missing_specificity' in issues:
            if title and re.search(r'\b(extension|license|access|permission|subscription)\b', title.lower()) and not re.search(r'\b(azure|subscription|resource|service|app|function|vm|storage|database|cosmos|sql)\b', title.lower()):
                suggestions.append(f"Your title '{title}' mentions an extension/license but doesn't specify for what Azure service. Try: 'Azure [Service Name] license extension needed' or '[Specific Azure Resource] subscription expiring'.")
        
        # Dynamic description suggestions  
        if 'description_insufficient' in issues or 'description_garbage' in issues:
            if desc_analysis['is_garbage']:
                suggestions.append(f"Your description '{description}' appears to be random text. Please describe your Azure problem clearly: What Azure service were you using? What happened? What error did you see?")
            elif len((description or "").split()) < 5:
                suggestions.append("Please provide more detail in your description for this Azure issue. Include: 1) Which Azure service/resource, 2) What you were trying to do, 3) What went wrong, 4) Any error messages.")
        
        # Check for vague time references in descriptions
        if 'description_vague_timing' in issues:
            if description and re.search(r'\b(as soon as possible|asap|soon|quickly|urgent|immediately)\b', description.lower()):
                suggestions.append(f"Your description uses vague timing like 'as soon as possible'. Please be specific: When exactly does this Azure service expire? Provide a specific date like 'expires on [date]' or 'needed by [specific date]'.")
        
        # Check for generic application references
        if 'description_generic_terms' in issues:
            if description and re.search(r'\b(application|app|system)\b', description.lower()) and not re.search(r'\b(azure function|azure app service|azure web app|logic app|function app|[a-z]+-[a-z]+\.azurewebsites\.net)\b', description.lower()):
                suggestions.append(f"Your description mentions 'application' or 'system' but doesn't specify which Azure service. Please be specific: Is this an Azure Function, App Service, Logic App, or which specific Azure resource?")
        
        # Check for context issues that would prevent AI understanding
        if 'description_lacks_context' in issues:
            suggestions.append("To help our AI provide the best assistance, please include more context: What Microsoft or Azure service are you working with? What are you trying to accomplish? This helps us understand your situation better.")
        
        # Dynamic impact suggestions
        if 'impact_optional_recommended' in issues:
            suggestions.append("📋 No impact statement provided. While optional, adding an impact statement helps us prioritize and understand how this affects your business. Consider including: Who is affected? What are the consequences? What's the urgency?")
        elif 'impact_insufficient' in issues or 'impact_garbage' in issues:
            if impact_analysis['is_garbage']:
                suggestions.append(f"Your impact statement '{impact}' doesn't describe the business effect. Please explain how this problem affects users, productivity, or business operations.")
            elif len((impact or "").split()) < 3:
                suggestions.append("Please expand your impact description. Who is affected? How does this impact their work or the business?")
        
        # Context and detail-specific suggestions
        if 'description_lacks_context' in issues:
            if description:
                suggestions.append("Please provide more context in your description so our AI can better understand and help you. Include: Which Azure service or Microsoft product are you working with? What specifically are you trying to accomplish? What's not working as expected?")
        
        if 'impact_lacks_detail' in issues:
            if impact:
                suggestions.append("Please provide more details about who is affected and how. For example: 'Entire sales team cannot access customer data, blocking all new orders' or 'Development team productivity reduced by 80% due to build failures'.")
        
        if impact and re.search(r'^\s*(bad|not good|problem|issue)\s*\.?\s*$', impact.lower()):
            suggestions.append(f"Instead of saying '{impact}', please be specific about the business impact. For example: 'Users cannot complete orders' or 'Team productivity reduced by 50%'.")
        
        return suggestions
    
    @staticmethod
    def _analyze_text_quality(text: str) -> Dict:
        """Analyze the quality of a text input"""
        garbage_check = AIAnalyzer._detect_garbage_text(text)
        words = len(text.split()) if text else 0
        
        return {
            'is_garbage': garbage_check['is_garbage'],
            'garbage_reason': garbage_check['reason'],
            'garbage_confidence': garbage_check['confidence'],
            'word_count': words,
            'has_content': bool(text and text.strip())
        }
    
    @staticmethod
    def analyze_completeness(title: str, description: str, impact: str) -> Dict:
        """Analyze if the issue description is complete enough for matching"""
        issues = []
        
        # Analyze each field for garbage content first
        title_analysis = AIAnalyzer._analyze_text_quality(title or "")
        desc_analysis = AIAnalyzer._analyze_text_quality(description or "")
        # Impact is optional - only analyze if provided
        impact_analysis = AIAnalyzer._analyze_text_quality(impact or "") if impact and impact.strip() else {'is_garbage': False, 'reason': 'empty_optional', 'confidence': 0.0}
        
        # Check for garbage input (this is critical and heavily penalized)
        if title_analysis['is_garbage']:
            issues.append("title_garbage")
        if desc_analysis['is_garbage']:
            issues.append("description_garbage")
        # Only flag impact as garbage if it has content but that content is garbage
        # Empty impact is acceptable since it's optional
        if impact and impact.strip() and impact_analysis['is_garbage']:
            issues.append("impact_garbage")
        
        # Traditional quality checks (only if not garbage)
        if not title_analysis['is_garbage']:
            title_words = len(title.split()) if title else 0
            if title_words < 3:
                issues.append("title_insufficient")
            elif title and re.match(r'^\s*(issue|problem|bug|error|help|fix)\s*$', title.lower()):
                issues.append("title_too_generic")
            elif title and re.search(r'^\s*(something|stuff|thing|it|this)\s', title.lower()):
                issues.append("title_too_vague")
            # Check for vague titles missing specificity (like "extension for what?")
            elif title and re.search(r'\b(extension|license|access|permission|subscription)\b', title.lower()) and not re.search(r'\b(azure|subscription|resource|service|app|function|vm|storage|database|cosmos|sql)\b', title.lower()):
                issues.append("title_missing_specificity")
                
            # Check for extremely vague requests that lack any context
            elif title and re.search(r'^\s*(need help|help|please help|can someone help)\s*\.?\s*$', title.lower()):
                issues.append("title_too_vague")
        
        if not desc_analysis['is_garbage']:
            description_words = len(description.split()) if description else 0
            if description_words < EnhancedMatchingConfig.MIN_DESCRIPTION_WORDS:
                issues.append("description_insufficient")
            elif description and re.search(r'^\s*(not working|broken|problem|issue|error)\s*\.?\s*$', description.lower()):
                issues.append("description_too_generic")
            
            # Check if description lacks sufficient context for AI understanding
            elif description and not re.search(r'\b(azure|microsoft|office|365|tenant|subscription|resource|service|app|function|vm|storage|database|cosmos|sql|active directory|ad|graph|api|portal|powershell|cli)\b', description.lower()) and len(description.split()) < 10:
                issues.append("description_lacks_context")
            
            # Check for vague time references in descriptions
            if description and re.search(r'\b(as soon as possible|asap|soon|quickly|urgent|immediately)\b', description.lower()):
                issues.append("description_vague_timing")
            
            # Check for generic application references without specificity
            if description and re.search(r'\b(application|app|system)\b', description.lower()) and not re.search(r'\b(azure function|azure app service|azure web app|logic app|function app|[a-z]+-[a-z]+\.azurewebsites\.net)\b', description.lower()):
                issues.append("description_generic_terms")
        
        if not impact_analysis['is_garbage']:
            impact_words = len(impact.split()) if impact else 0
            if impact_words < EnhancedMatchingConfig.MIN_IMPACT_WORDS:
                issues.append("impact_optional_recommended")  # Changed to indicate it's optional
            elif impact and re.search(r'^\s*(bad|not good|problem|issue)\s*\.?\s*$', impact.lower()):
                issues.append("impact_too_vague")
            
            # Check if impact lacks sufficient detail about consequences or affected parties
            elif impact and not re.search(r'\b(user|users|team|teams|business|productivity|revenue|cost|time|delay|block|affect|impact|work|workflow|operation|customer|client|department|organization)\b', impact.lower()) and len(impact.split()) < 5:
                issues.append("impact_lacks_detail")
        
        # Generate dynamic suggestions based on actual input
        suggestions = AIAnalyzer._generate_dynamic_suggestions(title, description, impact, issues)
        
        # Calculate completeness score focused on AI understanding capability
        base_score = 100
        for issue in issues:
            if 'garbage' in issue:
                base_score -= 40  # Heavy penalty for garbage input
            elif 'insufficient' in issue:
                base_score -= 25  # Major penalty for insufficient content
            elif 'impact_optional_recommended' in issue:
                base_score -= 5  # Minor penalty - impact is optional but recommended
            elif 'lacks_context' in issue or 'lacks_detail' in issue:
                base_score -= 20  # Significant penalty for insufficient information for AI understanding
            elif 'missing_specificity' in issue or 'vague_timing' in issue or 'generic_terms' in issue:
                base_score -= 18  # Significant penalty for vague/generic content
            elif 'generic' in issue or 'vague' in issue:
                base_score -= 15  # Moderate penalty for poor quality
            else:
                base_score -= 10  # Minor penalty for other issues
        
        completeness_score = max(0, base_score)
        
        return {
            'is_complete': len(issues) == 0,
            'issues': issues,
            'suggestions': suggestions,
            'completeness_score': completeness_score,
            'needs_improvement': len(issues) > 0,
            'garbage_detected': any('garbage' in issue for issue in issues),
            'garbage_details': {
                'title': title_analysis if title_analysis['is_garbage'] else None,
                'description': desc_analysis if desc_analysis['is_garbage'] else None,
                'impact': impact_analysis if impact_analysis['is_garbage'] else None
            }
        }
    
    @staticmethod
    def enhance_description(title: str, description: str, impact: str, 
                          opportunity_id: str = "", milestone_id: str = "") -> Dict:
        """Generate enhanced description and impact statements using AI-like analysis"""
        
        # Enhanced description generation
        enhanced_desc = description
        
        # Check if description is meaningful before adding enhancements
        desc_analysis = AIAnalyzer._detect_garbage_text(description)
        
        # Only add enhancements to meaningful content
        if not desc_analysis['is_garbage'] and len(description.strip()) > 20:
            # Add context from title if not already included (only for significant missing keywords)
            title_keywords = set(word.lower() for word in title.split() if len(word) > 3)
            desc_keywords = set(word.lower() for word in description.split() if len(word) > 3)
            # Exclude common words and only include meaningful technical terms
            exclude_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'this', 'that', 'issue', 'problem'}
            missing_keywords = title_keywords - desc_keywords - exclude_words
            
            if missing_keywords and len(missing_keywords) <= 2 and len(missing_keywords) >= 1:
                enhanced_desc += f"\n\nContext: Related to {', '.join(missing_keywords)}."
            
            # Add intelligent technical categorization
            category_added = False
            if re.search(r'\b(login|authentication|password|access|permission|authorization)', description.lower()):
                enhanced_desc += "\n\nCategory: Authentication/Access"
                category_added = True
            elif re.search(r'\b(email|mail|message|notification|alert|sms)', description.lower()):
                enhanced_desc += "\n\nCategory: Communication"
                category_added = True
            elif re.search(r'\b(performance|slow|timeout|delay|speed|lag|response)', description.lower()):
                enhanced_desc += "\n\nCategory: Performance"
                category_added = True
            elif re.search(r'\b(data|file|document|sync|backup|storage|database)', description.lower()):
                enhanced_desc += "\n\nCategory: Data/File Management"
                category_added = True
            elif re.search(r'\b(ui|interface|display|layout|design|visual)', description.lower()):
                enhanced_desc += "\n\nCategory: User Interface"
                category_added = True
            elif re.search(r'\b(api|integration|service|endpoint|connection)', description.lower()):
                enhanced_desc += "\n\nCategory: Integration/API"
                category_added = True
        
        # Enhanced impact statement
        enhanced_impact = impact
        
        # Analyze content quality first - don't add severity to garbage text
        impact_analysis = AIAnalyzer._detect_garbage_text(impact)
        
        # Add intelligent severity assessment only if content is meaningful
        severity_added = False
        if not impact_analysis['is_garbage'] and len(impact.strip()) > 10:
            # Critical severity indicators (most specific first)
            if re.search(r'\b(critical|urgent|emergency|down|stopped|broken|failed|crash|outage|security|breach|data.*loss)', impact.lower()):
                enhanced_impact += "\n\nSeverity: Critical - Immediate attention required"
                severity_added = True
            # Low severity indicators (check before generic terms)
            elif re.search(r'\b(minor|small|cosmetic|enhancement|nice.*to.*have|improvement|suggestion|visual.*issue)', impact.lower()):
                enhanced_impact += "\n\nSeverity: Low - Can be addressed in regular cycle"
                severity_added = True
            # High severity indicators (more specific)
            elif re.search(r'\b(blocks?|prevents?|cannot|unable|error|bug|important|significant|major)', impact.lower()):
                enhanced_impact += "\n\nSeverity: High - Should be prioritized"
                severity_added = True
            # Business impact indicators for medium priority
            elif re.search(r'\b(users?|customers?|business|revenue|productivity|efficiency|experience)', impact.lower()):
                enhanced_impact += "\n\nSeverity: Medium - Standard business impact"
                severity_added = True
            # If no clear indicators found, don't add severity assessment
        
        # Add business context if IDs provided
        if opportunity_id or milestone_id:
            enhanced_impact += "\n\nBusiness Context:"
            if opportunity_id:
                enhanced_impact += f" Opportunity ID: {opportunity_id}"
            if milestone_id:
                enhanced_impact += f" Milestone ID: {milestone_id}"
        
        return {
            'enhanced_description': enhanced_desc,
            'enhanced_impact': enhanced_impact,
            'original_description': description,
            'original_impact': impact
        }


class AzureDevOpsSearcher:
    """
    Handles searching Azure DevOps work items for similar issues across multiple organizations.
    
    This class provides comprehensive searching capabilities across UAT and Technical Feedback
    organizations, with intelligent similarity matching and result ranking.
    
    Attributes:
        config (EnhancedMatchingConfig): Configuration object with API settings
        headers (Dict[str, str]): Authentication headers for Azure DevOps API
        cutoff_date (datetime): Date threshold for searching recent work items
    """
    
    def __init__(self):
        """
        Initialize the Azure DevOps searcher with authentication and date filtering.
        
        Sets up separate credentials for UAT and TFT organizations to prevent
        dual authentication prompts. Reuses cached credentials if available.
        """
        print("[DEBUG ADO 1] AzureDevOpsSearcher.__init__() starting...", flush=True)
        self.config = EnhancedMatchingConfig()
        print("[DEBUG ADO 2] EnhancedMatchingConfig created. Checking for cached credentials...", flush=True)
        # Check if credentials are already cached from app startup or previous instance
        if EnhancedMatchingConfig._uat_credential is not None and EnhancedMatchingConfig._uat_token is not None:
            print("🔐 [UAT Auth] Reusing cached credential from previous authentication...", flush=True)
            print("[DEBUG ADO 3] Using cached UAT credential...", flush=True)
            self.uat_credential = EnhancedMatchingConfig._uat_credential
            self.uat_token = EnhancedMatchingConfig._uat_token
            print("[DEBUG ADO 4] Cached credential assigned to instance.", flush=True)
        else:
            # Get UAT credential and token (for UAT searches) - will cache for next time
            print("[DEBUG ADO 5] No cached credential found. Calling get_uat_credential()...", flush=True)
            self.uat_credential, self.uat_token = self.config.get_uat_credential()
            print("[DEBUG ADO 6] get_uat_credential() returned successfully!", flush=True)
        # TFT credential will be lazy-loaded when needed (for Feature searches)
        self.tft_credential = None
        self.tft_token = None
        print("[DEBUG ADO 7] Setting cutoff date...", flush=True)
        self.cutoff_date = datetime.now() - timedelta(days=30 * self.config.LOOKBACK_MONTHS)
        print("[DEBUG ADO 8] AzureDevOpsSearcher.__init__() completed successfully!", flush=True)
    
    def _get_headers(self, org: str = 'uat') -> Dict[str, str]:
        """
        Generate authentication headers for Azure DevOps API calls.
        
        Uses appropriate credential based on organization (UAT or TFT) to prevent
        dual authentication prompts.
        
        Args:
            org (str): Organization type - 'uat' for UAT searches, 'tft' for Feature searches
        
        Returns:
            Dict[str, str]: HTTP headers including Authorization, Content-Type, and Accept
        """
        if org == 'tft':
            # Check if TFT credential is already cached from initialization
            if self.tft_credential is None or self.tft_token is None:
                # Check if we already have it cached globally before prompting
                if EnhancedMatchingConfig._tft_credential is not None and EnhancedMatchingConfig._tft_token is not None:
                    print("🔐 [TFT Auth] Using globally cached TFT credential...")
                    self.tft_credential = EnhancedMatchingConfig._tft_credential
                    self.tft_token = EnhancedMatchingConfig._tft_token
                else:
                    try:
                        self.tft_credential, self.tft_token = self.config.get_tft_credential()
                    except Exception as e:
                        print(f"[ERROR] TFT credential initialization failed: {e}")
                        raise
            token = self.tft_token
        else:
            # Use UAT credentials (default)
            token = self.uat_token
        
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
    
    def search_uat_items(self, title: str, description: str) -> List[Dict]:
        """
        Fast search UAT Azure DevOps organization for similar work items.
        
        Optimized for submission wizard performance - completes in 2-3 minutes max.
        Uses intelligent search strategies: first finds all items with key terms,
        then ranks by semantic similarity to title and description.
        
        Args:
            title (str): Issue title to search for similarities
            description (str): Issue description for content matching
            
        Returns:
            List[Dict]: List of similar work items with metadata
        """
        print("\n" + "#"*80)
        print("[ADO SEARCHER] 🎯 SEARCH_UAT_ITEMS() EXECUTED 🎯")
        print(f"[ADO SEARCHER] Title: {title[:100]}...")
        print(f"[ADO SEARCHER] Description length: {len(description) if description else 0} chars")
        print("#"*80)
        
        try:
            print("[SEARCH] Starting simple UAT search (date + title keywords)...")
            start_time = time.time()
            
            # SIMPLE QUERY - just like the user's screenshot:
            # Created Date > 6/1/2025, Work Item Type = Actions, Title Contains key terms
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=240)  # ~8 months
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            
            # Extract key terms from title (words 4+ chars, skip common words)
            title_lower = title.lower()
            stop_words = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'where', 'when', 'what', 'how', 'azure', 'microsoft'}
            title_words = [word for word in title_lower.split() if len(word) > 3 and word not in stop_words]
            
            # Use top 3 key terms
            key_terms = title_words[:3]
            
            if key_terms:
                # Build simple CONTAINS query - ALL terms must match
                contains_clause = " AND ".join([f"[System.Title] CONTAINS '{term}'" for term in key_terms])
                
                wiql_query = f"""
                SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.State]
                FROM workitems 
                WHERE [System.TeamProject] = '{self.config.UAT_PROJECT}'
                AND [System.WorkItemType] = 'Actions'
                AND [System.State] <> 'Removed'
                AND [System.CreatedDate] > '{cutoff_date_str}'
                AND ({contains_clause})
                ORDER BY [System.CreatedDate] DESC
                """
            else:
                # Fallback - just date + work item type
                wiql_query = f"""
                SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.State]
                FROM workitems 
                WHERE [System.TeamProject] = '{self.config.UAT_PROJECT}'
                AND [System.WorkItemType] = 'Actions'
                AND [System.State] <> 'Removed'
                AND [System.CreatedDate] > '{cutoff_date_str}'
                ORDER BY [System.CreatedDate] DESC
                """
            
            print(f"[SEARCH] Simple Query: CreatedDate > {cutoff_date_str}, Type=Actions, Title Contains: {key_terms}")
            
            wiql_url = f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_apis/wit/wiql?api-version={self.config.API_VERSION}"
            response = requests.post(wiql_url, headers=self._get_headers('uat'), json={"query": wiql_query})
            
            if response.status_code != 200:
                print(f"[ERROR] UAT search failed: {response.status_code}")
                return []
            
            work_items = response.json().get('workItems', [])
            elapsed = time.time() - start_time
            print(f"✅ Simple UAT search completed in {elapsed:.1f}s - Found {len(work_items)} matches")
            
            if not work_items:
                return []
            
            # Get details for matches (limit to reasonable number)
            print(f"[SEARCH] Fetching details for {min(len(work_items), 100)} work items...")
            return self._get_work_item_details_batch(work_items[:100], title)
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR in UAT search: {str(e)}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            return []
    
    def _get_work_item_details_batch(self, work_items: List[Dict], query_title: str = "") -> List[Dict]:
        """Get work item details in batch with similarity scoring based on title match"""
        try:
            if not work_items:
                return []
            
            results = []
            work_item_ids = [item['id'] for item in work_items if 'id' in item]
            
            # Batch fetch for performance
            batch_size = 50
            for i in range(0, len(work_item_ids), batch_size):
                batch_ids = work_item_ids[i:i + batch_size]
                ids_param = ','.join(map(str, batch_ids))
                
                detail_url = f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_apis/wit/workitems"
                detail_params = {
                    'ids': ids_param,
                    'fields': 'System.Id,System.Title,System.Description,System.State,System.CreatedDate',
                    'api-version': '7.0'
                }
                
                detail_response = requests.get(detail_url, headers=self._get_headers('uat'), params=detail_params)
                
                if detail_response.status_code != 200:
                    continue
                
                batch_work_items = detail_response.json().get('value', [])
                
                for work_item in batch_work_items:
                    fields = work_item.get('fields', {})
                    work_item_id = work_item.get('id')
                    
                    # Extract title and description from work item fields
                    uat_title = fields.get('System.Title', '')
                    uat_description = fields.get('System.Description', '')
                    
                    # Strip HTML tags from description for clean display
                    # Azure DevOps stores descriptions as HTML, which needs cleaning for search results
                    clean_description = re.sub(r'<[^>]+>', '', uat_description)  # Remove HTML tags like <div>, <p>, etc.
                    clean_description = re.sub(r'\s+', ' ', clean_description).strip()  # Normalize whitespace
                    
                    # Calculate actual title similarity using SequenceMatcher (Python's difflib)
                    # This provides accurate similarity scores from 0.0 (no match) to 1.0 (exact match)
                    # SequenceMatcher uses the Ratcliff-Obershelp algorithm for sequence comparison
                    title_similarity = SequenceMatcher(None, query_title.lower(), uat_title.lower()).ratio()
                    
                    # Build result dictionary with all relevant work item information
                    results.append({
                        'id': work_item_id,
                        'title': uat_title,
                        'description': clean_description[:500],  # Truncate long descriptions
                        'similarity': round(title_similarity, 2),  # Actual calculated similarity (not hardcoded)
                        'source': 'UAT',
                        'url': f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_workitems/edit/{work_item_id}",
                        'created_date': fields.get('System.CreatedDate', ''),
                        'work_item_type': 'Actions',
                        'state': fields.get('System.State', ''),
                        'match_reasoning': f'Title match: {int(title_similarity * 100)}%'  # User-friendly percentage
                    })
            
            return results
            
        except Exception as e:
            print(f"[ERROR] Batch work item fetch failed: {e}")
            return []
    
    def _search_by_key_terms(self, title: str, description: str) -> List[Dict]:
        """Search for all items containing key terms from title, then rank by semantic similarity"""
        try:
            # Extract semantic components from title
            title_analysis = self._analyze_title_semantics(title)
            
            # Build search terms from weighted terms and meaningful phrases
            search_terms = []
            
            # Add high-weight Azure product/service terms
            for term_info in title_analysis['weighted_terms']:
                if term_info['weight'] >= 2.5 and term_info['type'] in ['product', 'functional']:
                    search_terms.append(term_info['term'])
            
            # Add multi-word technical phrases (like "AI Foundry Agent Service")
            title_lower = title.lower()
            technical_phrases = [
                'ai foundry agent service', 'foundry agent service', 'agent service',
                'data governance', 'data catalog', 'data map', 'data quality',
                'api management', 'service bus', 'key vault', 'app service',
                'logic apps', 'function app', 'cognitive services',
                'storage account', 'cosmos db', 'sql database'
            ]
            
            for phrase in technical_phrases:
                if phrase in title_lower and phrase not in search_terms:
                    search_terms.append(phrase)
            
            # If no specific terms found, use individual important words
            if not search_terms:
                words = title_lower.split()
                important_words = [w for w in words if len(w) > 3 and w not in ['the', 'and', 'for', 'with', 'from', 'that', 'this', 'where', 'when', 'what', 'how']]
                search_terms.extend(important_words[:5])  # Top 5 words
            
            if not search_terms:
                return []
            
            # Use 240-day (8 month) cutoff to match production query
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=240)
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            
            # Build WIQL query with AND matching (all terms must appear) and date filter
            contains_clauses = []
            for term in search_terms[:5]:  # Use top 5 most important terms with AND
                term_escaped = term.replace("'", "''")
                contains_clauses.append(f"([System.Title] CONTAINS '{term_escaped}' OR [System.Description] CONTAINS '{term_escaped}')")
            
            wiql_query = f"""
            SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType], [System.State]
            FROM workitems 
            WHERE [System.TeamProject] = '{self.config.UAT_PROJECT}'
            AND [System.WorkItemType] = 'Actions'
            AND [System.CreatedDate] >= '{cutoff_date_str}'
            AND ({' AND '.join(contains_clauses)})
            ORDER BY [System.CreatedDate] DESC
            """
            
            print(f"[SEARCH] Key terms search: Using 240-day filter + AND matching for {len(search_terms[:5])} terms")
            
            wiql_url = f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_apis/wit/wiql?api-version={self.config.API_VERSION}"
            response = requests.post(wiql_url, headers=self._get_headers('uat'), json={"query": wiql_query})
            
            if response.status_code == 200:
                work_items = response.json().get('workItems', [])
                if work_items:
                    # ⚡ PERFORMANCE OPTIMIZATION: Limit candidates for fast response
                    max_candidates = min(200, len(work_items))  # Process max 200 for speed
                    print(f"[SEARCH] Fast search: Processing top {max_candidates} of {len(work_items)} candidates...")
                    return self._get_work_item_details_with_semantic_scoring(work_items[:max_candidates], title, title_analysis, description)
            
            return []
            
        except Exception as e:
            print(f"Key terms search failed: {e}")
            return []

    def _search_by_exact_title(self, title: str) -> List[Dict]:
        """Search for exact title matches with semantic understanding (legacy method)"""
        try:
            # Extract semantic components from title
            title_analysis = self._analyze_title_semantics(title)
            
            # Try exact match first for very specific titles
            if title_analysis['is_very_specific']:
                title_escaped = title.replace("'", "''")
                wiql_query = f"""
                SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType], [System.State]
                FROM workitems 
                WHERE [System.TeamProject] = '{self.config.UAT_PROJECT}'
                AND [System.WorkItemType] = 'Actions'
                AND [System.Title] CONTAINS '{title_escaped}'
                ORDER BY [System.CreatedDate] DESC
                """
                
                wiql_url = f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_apis/wit/wiql?api-version={self.config.API_VERSION}"
                response = requests.post(wiql_url, headers=self._get_headers('uat'), json={"query": wiql_query})
                
                if response.status_code == 200:
                    work_items = response.json().get('workItems', [])
                    if work_items and len(work_items) <= 10:  # If few exact matches, return them
                        return self._get_work_item_details(work_items[:50], title, title)
            
            # If too many matches or no exact matches, use semantic search
            return self._semantic_title_search(title_analysis, title)
            
        except Exception as e:
            print(f"Exact title search failed: {e}")
            return []
    
    def _analyze_title_semantics(self, title: str) -> Dict:
        """Analyze title to extract semantic components"""
        title_lower = title.lower()
        
        # Comprehensive Azure services knowledge base from Microsoft Learn
        azure_products = {
            # AI and Machine Learning Services (Highest Priority)
            'ai foundry': 3.5, 'foundry': 3.0, 'agent service': 3.2, 'ai studio': 3.0,
            'openai': 3.5, 'azure openai': 3.5, 'gpt': 3.2, 'copilot': 3.0,
            'machine learning': 3.0, 'ml': 2.8, 'cognitive services': 3.0,
            'ai services': 3.0, 'computer vision': 2.8, 'ai vision': 2.8,
            'speech service': 2.8, 'ai speech': 2.8, 'language service': 2.8,
            'ai language': 2.8, 'translator': 2.8, 'ai translator': 2.8,
            'ai search': 3.0, 'cognitive search': 3.0, 'search service': 2.8,
            'document intelligence': 2.8, 'ai document intelligence': 2.8,
            'content safety': 2.5, 'ai content safety': 2.5, 'immersive reader': 2.5,
            'bot service': 2.5, 'bot framework': 2.5, 'custom vision': 2.5,
            'face': 2.5, 'video indexer': 2.5,
            
            # Data and Analytics Services (High Priority)
            'purview': 3.0, 'microsoft purview': 3.0, 'synapse': 3.0, 'synapse analytics': 3.0,
            'databricks': 3.0, 'azure databricks': 3.0, 'data factory': 3.0,
            'data lake': 2.8, 'data lake storage': 2.8, 'hdinsight': 2.8,
            'stream analytics': 2.8, 'data explorer': 2.8, 'kusto': 2.8,
            'analysis services': 2.5, 'power bi': 2.5, 'power bi embedded': 2.5,
            
            # Compute Services
            'virtual machines': 2.8, 'vm': 2.5, 'app service': 2.8, 'web apps': 2.5,
            'function': 2.8, 'functions': 2.8, 'azure functions': 2.8,
            'container apps': 2.8, 'container instances': 2.5, 'container registry': 2.5,
            'kubernetes': 2.8, 'aks': 2.8, 'service fabric': 2.5,
            'batch': 2.5, 'virtual machine scale sets': 2.5, 'vmss': 2.3,
            
            # Storage Services
            'storage': 2.5, 'blob storage': 2.8, 'blob': 2.5, 'files': 2.5,
            'file storage': 2.5, 'disk storage': 2.5, 'managed disks': 2.5,
            'queue storage': 2.5, 'table storage': 2.5, 'archive storage': 2.3,
            
            # Database Services
            'sql database': 2.8, 'sql': 2.5, 'sql managed instance': 2.8,
            'cosmos db': 2.8, 'cosmosdb': 2.8, 'cosmos': 2.8,
            'redis': 2.5, 'cache for redis': 2.5, 'redis cache': 2.5,
            'mysql': 2.5, 'postgresql': 2.5, 'mariadb': 2.5,
            'database migration service': 2.3,
            
            # Networking Services
            'virtual network': 2.5, 'vnet': 2.3, 'vpn gateway': 2.5,
            'expressroute': 2.5, 'load balancer': 2.5, 'application gateway': 2.5,
            'firewall': 2.5, 'ddos protection': 2.5, 'bastion': 2.5,
            'network watcher': 2.3, 'private link': 2.5, 'dns': 2.3,
            'traffic manager': 2.3, 'cdn': 2.3, 'content delivery network': 2.3,
            
            # Integration and Messaging
            'service bus': 2.8, 'servicebus': 2.8, 'event hubs': 2.8,
            'event hub': 2.8, 'event grid': 2.5, 'logic apps': 2.8,
            'logic app': 2.8, 'api management': 2.8, 'apim': 2.5,
            'signalr': 2.3, 'notification hubs': 2.3,
            
            # Security and Identity
            'key vault': 2.8, 'keyvault': 2.8, 'active directory': 2.8,
            'entra id': 2.8, 'entra': 2.8, 'ad': 2.3, 'managed identity': 2.5,
            'azure ad': 2.8, 'authentication': 2.5, 'authorization': 2.5,
            'rbac': 2.3, 'security center': 2.5, 'sentinel': 2.5,
            'dedicated hsm': 2.3, 'managed hsm': 2.5, 'attestation': 2.3,
            
            # Monitoring and Management
            'monitor': 2.5, 'azure monitor': 2.5, 'log analytics': 2.5,
            'application insights': 2.5, 'alerts': 2.3, 'metrics': 2.3,
            'automation': 2.3, 'resource manager': 2.3, 'policy': 2.3,
            'blueprints': 2.3, 'cost management': 2.3,
            
            # DevOps and Development
            'devops': 2.5, 'azure devops': 2.5, 'pipelines': 2.3,
            'artifacts': 2.3, 'repos': 2.3, 'boards': 2.3, 'test plans': 2.3,
            'github': 2.3, 'visual studio': 2.3, 'app configuration': 2.3,
            
            # IoT and Edge
            'iot hub': 2.5, 'iot central': 2.3, 'iot edge': 2.3,
            'digital twins': 2.3, 'sphere': 2.3, 'time series insights': 2.3,
            
            # Mixed Reality and Media
            'spatial anchors': 2.0, 'remote rendering': 2.0, 'object anchors': 2.0,
            'media services': 2.3, 'video analyzer': 2.3, 'communication services': 2.3,
            
            # Specialized Services
            'vmware solution': 2.3, 'spring apps': 2.3, 'red hat openshift': 2.3,
            'lab services': 2.3, 'managed applications': 2.3, 'lighthouse': 2.3,
            'backup': 2.5, 'site recovery': 2.5, 'import export': 2.3,
            'data box': 2.3, 'netapp files': 2.3, 'hpc cache': 2.3
        }
        
        # Azure regions (high weight) - Critical for capacity and regional issues
        # Complete list from https://learn.microsoft.com/en-us/azure/app-service/environment/overview
        azure_regions = {
            # ===== AZURE PUBLIC REGIONS =====
            
            # US Regions
            'east us': 3.0, 'east us 2': 3.0, 'eastus': 3.0, 'eastus2': 3.0,
            'west us': 3.0, 'west us 2': 3.0, 'west us 3': 3.0, 'westus': 3.0, 'westus2': 3.0, 'westus3': 3.0,
            'central us': 3.0, 'centralus': 3.0, 'south central us': 3.0, 'southcentralus': 3.0,
            'north central us': 3.0, 'northcentralus': 3.0, 'west central us': 3.0, 'westcentralus': 3.0,
            
            # Europe Regions
            'north europe': 3.0, 'northeurope': 3.0, 'west europe': 3.0, 'westeurope': 3.0,
            'uk south': 3.0, 'uksouth': 3.0, 'uk west': 3.0, 'ukwest': 3.0,
            'france central': 3.0, 'francecentral': 3.0, 'france south': 3.0, 'francesouth': 3.0,
            'germany west central': 3.0, 'germanywestcentral': 3.0, 'germany north': 3.0, 'germanynorth': 3.0,
            'norway east': 3.0, 'norwayeast': 3.0, 'norway west': 3.0, 'norwaywest': 3.0,
            'switzerland north': 3.0, 'switzerlandnorth': 3.0, 'switzerland west': 3.0, 'switzerlandwest': 3.0,
            'sweden central': 3.0, 'swedencentral': 3.0, 'sweden south': 3.0, 'swedensouth': 3.0,
            'spain central': 3.0, 'spaincentral': 3.0, 'poland central': 3.0, 'polandcentral': 3.0,
            'italy north': 3.0, 'italynorth': 3.0,
            
            # Asia Pacific Regions
            'southeast asia': 3.0, 'southeastasia': 3.0, 'east asia': 3.0, 'eastasia': 3.0,
            'australia east': 3.0, 'australiaeast': 3.0, 'australia southeast': 3.0, 'australiasoutheast': 3.0,
            'australia central': 3.0, 'australiacentral': 3.0, 'australia central 2': 3.0, 'australiacentral2': 3.0,
            'japan east': 3.0, 'japaneast': 3.0, 'japan west': 3.0, 'japanwest': 3.0,
            'korea central': 3.0, 'koreacentral': 3.0, 'korea south': 3.0, 'koreasouth': 3.0,
            'new zealand north': 3.0, 'newzealandnorth': 3.0,
            'taiwan north': 3.0, 'taiwannorth': 3.0, 'taiwan northwest': 3.0, 'taiwannorthwest': 3.0,
            
            # India Regions
            'central india': 3.0, 'centralindia': 3.0, 'south india': 3.0, 'southindia': 3.0,
            'west india': 3.0, 'westindia': 3.0, 'jio india central': 3.0, 'jioindiacentral': 3.0,
            'jio india west': 3.0, 'jioindiawest': 3.0,
            
            # Americas (Non-US)
            'canada central': 3.0, 'canadacentral': 3.0, 'canada east': 3.0, 'canadaeast': 3.0,
            'brazil south': 3.0, 'brazilsouth': 3.0, 'brazil southeast': 3.0, 'brazilsoutheast': 3.0,
            'mexico central': 3.0, 'mexicocentral': 3.0,
            
            # Middle East & Africa
            'south africa north': 3.0, 'southafricanorth': 3.0, 'south africa west': 3.0, 'southafricawest': 3.0,
            'uae north': 3.0, 'uaenorth': 3.0, 'uae central': 3.0, 'uaecentral': 3.0,
            'qatar central': 3.0, 'qatarcentral': 3.0, 'israel central': 3.0, 'israelcentral': 3.0,
            
            # ===== AZURE GOVERNMENT REGIONS =====
            'us dod central': 3.0, 'usdodcentral': 3.0, 'us dod east': 3.0, 'usdodeast': 3.0,
            'us gov arizona': 3.0, 'usgovarizona': 3.0, 'us gov texas': 3.0, 'usgovtexas': 3.0,
            'us gov virginia': 3.0, 'usgovvirginia': 3.0,
            
            # ===== AZURE OPERATED BY 21VIANET (CHINA) =====
            'china east 3': 3.0, 'chinaeast3': 3.0, 'china north 3': 3.0, 'chinanorth3': 3.0,
            
            # Common region name variations and abbreviations
            'us': 2.8, 'europe': 2.8, 'asia': 2.8, 'apac': 2.8, 'emea': 2.8, 'americas': 2.8,
            'gov': 2.5, 'dod': 2.5, 'government': 2.5, 'china': 2.8
        }
        
        # Capacity and resource management terms (high weight) - Critical for capacity requests
        capacity_terms = {
            'capacity': 3.0, 'quota': 2.8, 'limit': 2.8, 'threshold': 2.5, 'allocation': 2.8,
            'availability': 2.8, 'resource': 2.5, 'scaling': 2.5, 'scale': 2.3, 'usage': 2.3,
            'consumption': 2.3, 'utilization': 2.5, 'bandwidth': 2.3, 'throughput': 2.3,
            'vcpu': 2.8, 'cpu': 2.5, 'memory': 2.5, 'storage': 2.5, 'disk': 2.3,
            'cores': 2.5, 'instances': 2.5, 'nodes': 2.3, 'workers': 2.3,
            'increase': 2.5, 'decrease': 2.0, 'expand': 2.3, 'reduce': 2.0,
            'request': 2.0, 'need': 1.8, 'require': 2.0, 'provision': 2.3
        }
        
        # Regional and location terms (medium-high weight)
        location_terms = {
            'region': 2.8, 'location': 2.5, 'datacenter': 2.5, 'data center': 2.5,
            'geography': 2.3, 'geo': 2.3, 'zone': 2.3, 'availability zone': 2.5,
            'site': 2.0, 'facility': 2.0, 'center': 1.8, 'area': 1.5
        }
        
        # Functional terms (medium-high weight) - Azure-specific concepts
        functional_terms = {
            # Data Management and Governance
            'data catalog': 2.8, 'data governance': 2.8, 'data map': 2.8,
            'data classification': 2.5, 'data lineage': 2.5, 'data quality': 2.5,
            'metadata': 2.3, 'schema': 2.3, 'taxonomy': 2.3,
            
            # Security and Compliance
            'authentication': 2.5, 'authorization': 2.5, 'identity': 2.5,
            'single sign-on': 2.5, 'sso': 2.3, 'multi-factor': 2.3, 'mfa': 2.3,
            'conditional access': 2.5, 'privileged access': 2.3, 'pim': 2.3,
            'security': 2.5, 'compliance': 2.5, 'audit': 2.3, 'governance': 2.5,
            'encryption': 2.5, 'tls': 2.3, 'ssl': 2.3, 'certificates': 2.3,
            'zero trust': 2.3, 'defender': 2.3, 'vulnerability': 2.3,
            
            # Integration and Connectivity
            'integration': 2.5, 'api': 2.5, 'rest api': 2.5, 'webhook': 2.3,
            'connector': 2.5, 'hybrid': 2.5, 'gateway': 2.5, 'endpoint': 2.3,
            'messaging': 2.3, 'queue': 2.3, 'topic': 2.3, 'subscription': 2.3,
            'event-driven': 2.3, 'publisher': 2.3, 'subscriber': 2.3,
            
            # Development and Operations
            'deployment': 2.3, 'ci/cd': 2.5, 'continuous integration': 2.3,
            'continuous deployment': 2.3, 'devops': 2.5, 'infrastructure as code': 2.3,
            'iac': 2.3, 'arm template': 2.3, 'bicep': 2.3, 'terraform': 2.3,
            'containerization': 2.3, 'microservices': 2.3, 'serverless': 2.5,
            
            # Monitoring and Observability
            'monitoring': 2.3, 'logging': 2.3, 'telemetry': 2.3, 'metrics': 2.3,
            'alerts': 2.3, 'diagnostics': 2.3, 'health check': 2.3,
            'performance': 2.3, 'availability': 2.3, 'reliability': 2.3,
            'sla': 2.3, 'slo': 2.3, 'rto': 2.3, 'rpo': 2.3,
            
            # Data Operations
            'etl': 2.5, 'elt': 2.5, 'extract': 2.3, 'transform': 2.3, 'load': 2.3,
            'pipeline': 2.5, 'workflow': 2.3, 'orchestration': 2.3,
            'batch processing': 2.3, 'stream processing': 2.3, 'real-time': 2.3,
            'data lake': 2.5, 'data warehouse': 2.5, 'lakehouse': 2.3,
            
            # Cloud Operations
            'migration': 2.3, 'modernization': 2.3, 'optimization': 2.3,
            'scaling': 2.3, 'auto-scaling': 2.3, 'load balancing': 2.3,
            'failover': 2.3, 'disaster recovery': 2.3, 'backup': 2.3,
            'replication': 2.3, 'geo-redundancy': 2.3, 'high availability': 2.3,
            
            # Configuration and Management
            'configuration': 2.0, 'provisioning': 2.3, 'template': 2.3,
            'policy': 2.3, 'role assignment': 2.3, 'permissions': 2.3,
            'resource group': 2.3, 'subscription': 2.3, 'tenant': 2.3,
            'management group': 2.3, 'cost optimization': 2.3, 'tagging': 2.3
        }
        
        # Technical action terms (medium weight) - Azure operations
        action_terms = {
            # Data Operations
            'search': 1.8, 'query': 1.8, 'filter': 1.8, 'index': 1.8,
            'scan': 1.8, 'crawl': 1.8, 'discover': 1.8, 'catalog': 1.8,
            'classify': 1.8, 'label': 1.5, 'tag': 1.5, 'annotate': 1.5,
            
            # CRUD Operations
            'create': 1.5, 'read': 1.3, 'update': 1.5, 'delete': 1.5,
            'insert': 1.5, 'upsert': 1.5, 'merge': 1.5, 'patch': 1.5,
            'get': 1.3, 'put': 1.3, 'post': 1.3, 'retrieve': 1.5,
            
            # Data Movement
            'import': 1.8, 'export': 1.8, 'sync': 1.8, 'replicate': 1.8,
            'migrate': 1.8, 'copy': 1.5, 'move': 1.5, 'transfer': 1.8,
            'backup': 1.8, 'restore': 1.8, 'archive': 1.5,
            
            # Configuration and Management
            'configure': 1.8, 'setup': 1.5, 'install': 1.5, 'deploy': 1.8,
            'provision': 1.8, 'allocate': 1.5, 'assign': 1.5, 'bind': 1.5,
            'enable': 1.5, 'disable': 1.5, 'activate': 1.5, 'deactivate': 1.5,
            'start': 1.3, 'stop': 1.3, 'restart': 1.5, 'pause': 1.3, 'resume': 1.3,
            
            # Analysis and Processing
            'analyze': 1.8, 'process': 1.8, 'transform': 1.8, 'enrich': 1.8,
            'validate': 1.5, 'verify': 1.5, 'check': 1.3, 'test': 1.5,
            'evaluate': 1.5, 'assess': 1.5, 'review': 1.3, 'audit': 1.5,
            
            # Monitoring and Troubleshooting
            'monitor': 1.5, 'track': 1.5, 'trace': 1.5, 'log': 1.5,
            'debug': 1.5, 'troubleshoot': 1.8, 'diagnose': 1.8, 'resolve': 1.8,
            'fix': 1.5, 'repair': 1.5, 'recover': 1.8, 'restore': 1.8,
            
            # Security Operations
            'authenticate': 1.8, 'authorize': 1.8, 'encrypt': 1.8, 'decrypt': 1.5,
            'sign': 1.5, 'verify': 1.5, 'validate': 1.5, 'attest': 1.5,
            'grant': 1.5, 'revoke': 1.5, 'deny': 1.3, 'allow': 1.3,
            
            # Integration Operations
            'connect': 1.8, 'integrate': 1.8, 'link': 1.5, 'join': 1.5,
            'map': 1.8, 'bind': 1.5, 'associate': 1.5, 'relate': 1.3,
            'publish': 1.5, 'subscribe': 1.5, 'notify': 1.5, 'alert': 1.5
        }
        
        # ===== AZURE SERVICE AVAILABILITY & CATEGORIZATION =====
        # Based on https://learn.microsoft.com/en-us/azure/reliability/availability-service-by-category
        # and https://learn.microsoft.com/en-us/azure/reliability/availability-zones-service-support
        
        # Foundational Services (Available in all regions, highest reliability)
        foundational_services = {
            'application gateway': 3.2, 'app gateway': 3.2, 
            'backup': 3.0, 'azure backup': 3.0,
            'cosmos db': 3.5, 'cosmosdb': 3.5, 'cosmos db for nosql': 3.5,
            'event hubs': 3.2, 'eventhubs': 3.2,
            'expressroute': 3.2, 'express route': 3.2,
            'key vault': 3.2, 'keyvault': 3.2,
            'kubernetes service': 3.5, 'aks': 3.5, 'azure kubernetes service': 3.5,
            'load balancer': 3.2, 'loadbalancer': 3.2,
            'nat gateway': 3.0, 'natgateway': 3.0,
            'public ip': 3.0, 'publicip': 3.0,
            'service bus': 3.2, 'servicebus': 3.2,
            'service fabric': 3.0, 'servicefabric': 3.0,
            'site recovery': 3.0, 'siterecovery': 3.0,
            'sql database': 3.5, 'sqldatabase': 3.5, 'azure sql': 3.5,
            'sql managed instance': 3.5, 'sqlmi': 3.5,
            'storage accounts': 3.5, 'storage account': 3.5,
            'data lake storage': 3.2, 'datalake': 3.2, 'adls': 3.2,
            'blob storage': 3.5, 'blobs': 3.2,
            'disk storage': 3.2, 'managed disks': 3.2,
            'virtual machine scale sets': 3.2, 'vmss': 3.2,
            'virtual machines': 3.5, 'vm': 3.2, 'vms': 3.2,
            'virtual network': 3.5, 'vnet': 3.2, 'vnets': 3.2,
            'vpn gateway': 3.2, 'vpngateway': 3.2
        }
        
        # Mainstream Services (Available in recommended regions within 90 days)
        mainstream_services = {
            'ai search': 3.2, 'cognitive search': 3.2, 'search service': 3.0,
            'api management': 3.2, 'apim': 3.0,
            'app configuration': 3.0, 'appconfig': 3.0,
            'app service': 3.5, 'web apps': 3.2, 'appservice': 3.2,
            'bastion': 3.0, 'azure bastion': 3.0,
            'batch': 3.0, 'azure batch': 3.0,
            'cache for redis': 3.2, 'redis': 3.0, 'redis cache': 3.2,
            'container instances': 3.0, 'aci': 3.0,
            'container registry': 3.2, 'acr': 3.0,
            'data explorer': 3.2, 'kusto': 3.0, 'adx': 3.0,
            'data factory': 3.5, 'adf': 3.2, 'datafactory': 3.2,
            'database for mysql': 3.2, 'mysql': 3.0,
            'database for postgresql': 3.2, 'postgresql': 3.0, 'postgres': 3.0,
            'ddos protection': 3.0, 'ddos': 2.8,
            'dns private resolver': 2.8, 'private dns': 2.8,
            'event grid': 3.0, 'eventgrid': 3.0,
            'firewall': 3.2, 'azure firewall': 3.2,
            'firewall manager': 3.0, 'firewallmanager': 3.0,
            'functions': 3.5, 'azure functions': 3.5, 'function app': 3.2,
            'hdinsight': 3.0, 'hdi': 2.8,
            'iot hub': 3.2, 'iothub': 3.0,
            'logic apps': 3.2, 'logicapps': 3.2,
            'media services': 2.8, 'mediaservices': 2.8,
            'monitor': 3.2, 'azure monitor': 3.2, 'application insights': 3.0,
            'log analytics': 3.2, 'logs': 3.0,
            'network watcher': 3.0, 'networkwatcher': 3.0,
            'private link': 3.2, 'privatelink': 3.2,
            'files storage': 3.0, 'file shares': 3.0, 'azure files': 3.0,
            'premium blob': 3.0, 'premium blob storage': 3.0,
            'virtual wan': 3.0, 'vwan': 2.8,
            'entra domain services': 3.0, 'aad ds': 2.8, 'domain services': 3.0
        }
        
        # Strategic Services (Demand-driven, specialized offerings)
        strategic_services = {
            'ai services': 3.5, 'cognitive services': 3.5,
            'analysis services': 2.8, 'ssas': 2.5,
            'api for fhir': 2.5, 'fhir': 2.5,
            'automation': 3.0, 'azure automation': 3.0,
            'container apps': 3.2, 'containerapps': 3.2,
            'data share': 2.5, 'datashare': 2.5,
            'database for mariadb': 2.5, 'mariadb': 2.5,
            'database migration service': 2.8, 'dms': 2.5,
            'databricks': 3.5, 'azure databricks': 3.5,
            'dedicated hsm': 2.5, 'hsm': 2.5,
            'digital twins': 2.8, 'digitaltwins': 2.8,
            'hpc cache': 2.8, 'hpccache': 2.8,
            'kubernetes fleet manager': 2.5, 'fleet': 2.5,
            'lab services': 2.5, 'labs': 2.5,
            'machine learning': 3.5, 'ml': 3.2, 'aml': 3.2,
            'managed hsm': 2.8, 'managedhsm': 2.8,
            'managed instance for apache cassandra': 2.5, 'cassandra': 2.5,
            'netapp files': 3.0, 'anf': 2.8, 'netappfiles': 3.0,
            'red hat openshift': 3.0, 'openshift': 2.8, 'aro': 2.8,
            'remote rendering': 2.5, 'remoterendering': 2.5,
            'signalr service': 3.0, 'signalr': 2.8,
            'spring apps': 3.2, 'springapps': 3.2, 'spring cloud': 3.0,
            'archive storage': 2.8, 'archive': 2.5,
            'file sync': 2.8, 'filesync': 2.8,
            'synapse analytics': 3.5, 'synapse': 3.5,
            'ultra disk': 3.0, 'ultra ssd': 3.0, 'ultradisk': 3.0,
            'vmware solution': 3.0, 'avs': 2.8, 'azure vmware': 3.0,
            'attestation': 2.5, 'azure attestation': 2.5,
            'purview': 3.5, 'microsoft purview': 3.5,
            'sql on vms': 3.0, 'sql server on vm': 3.0,
            'stretch database': 2.5, 'sql stretch': 2.5
        }
        
        # Availability Zone Support (Critical for high-availability scenarios)
        availability_zone_services = {
            'ai search': 3.2, 'api management': 3.2, 'app configuration': 3.0,
            'app service': 3.2, 'application gateway': 3.5, 'automation': 3.0,
            'backup': 3.2, 'bastion': 3.2, 'batch': 3.0, 'blob storage': 3.2,
            'cache for redis': 3.5, 'compute gallery': 3.0, 'container apps': 3.2,
            'container registry': 3.0, 'cosmos db': 3.5, 'data explorer': 3.2,
            'data factory': 3.2, 'data lake storage': 3.2, 'database for mysql': 3.2,
            'database for postgresql': 3.2, 'databricks': 3.2, 'ddos protection': 3.0,
            'disk encryption': 3.0, 'disk storage': 3.5, 'dns private resolver': 3.0,
            'event grid': 3.0, 'event hubs': 3.2, 'expressroute': 3.2,
            'files': 3.0, 'firewall': 3.5, 'functions': 3.2, 'iot hub': 3.2,
            'key vault': 3.5, 'kubernetes service': 3.5, 'load balancer': 3.5,
            'logic apps': 3.2, 'managed cassandra': 3.0, 'monitor': 3.2,
            'network watcher': 3.0, 'notification hubs': 3.0, 'private link': 3.2,
            'queue storage': 3.0, 'red hat openshift': 3.2, 'service bus': 3.5,
            'service fabric': 3.2, 'signalr': 3.0, 'site recovery': 3.0,
            'spring apps': 3.2, 'sql database': 3.5, 'sql managed instance': 3.5,
            'stream analytics': 3.2, 'table storage': 3.0, 'virtual machines': 3.2,
            'virtual machine scale sets': 3.2, 'virtual network': 3.2, 'vpn gateway': 3.2,
            'web pubsub': 3.0, 'entra domain services': 3.0, 'fabric': 3.2,
            'power bi embedded': 3.0
        }
        
        # Service Reliability Indicators (for capacity and scaling issues)
        reliability_terms = {
            'availability zones': 3.5, 'az': 3.0, 'zones': 2.8,
            'high availability': 3.2, 'ha': 3.0, 'uptime': 2.8,
            'disaster recovery': 3.2, 'dr': 2.8, 'backup': 3.0,
            'failover': 3.0, 'redundancy': 3.0, 'replication': 2.8,
            'sla': 3.0, 'service level': 2.8, 'reliability': 2.8,
            'resilience': 2.8, 'fault tolerance': 3.0, 'durability': 2.8
        }
        
        # Company/customer identifiers (IGNORED for matching)
        company_indicators = [
            'corp', 'ltd', 'inc', 'llc', 'ricoh', 'microsoft', 'banco', 'bradesco',
            'contoso', 'fabrikam', 'northwind', 'adventureworks', 'wideworld',
            # Common customer/company patterns
            'customer', 'client', 'partner', 'vendor', 'supplier'
        ]
        
        # Extract weighted terms
        weighted_terms = []
        company_terms = []
        
        # Check for multi-word terms first
        all_terms = {
            **azure_products, **azure_regions, **capacity_terms, **location_terms, **functional_terms,
            **foundational_services, **mainstream_services, **strategic_services, 
            **availability_zone_services, **reliability_terms
        }
        for term, weight in all_terms.items():
            if term in title_lower:
                term_type = 'product' if term in azure_products else \
                           'region' if term in azure_regions else \
                           'capacity' if term in capacity_terms else \
                           'location' if term in location_terms else \
                           'functional' if term in functional_terms else \
                           'foundational' if term in foundational_services else \
                           'mainstream' if term in mainstream_services else \
                           'strategic' if term in strategic_services else \
                           'availability_zone' if term in availability_zone_services else \
                           'reliability' if term in reliability_terms else 'technical'
                weighted_terms.append({'term': term, 'weight': weight, 'type': term_type})
        
        # Check individual words
        words = title_lower.split()
        for word in words:
            word_clean = re.sub(r'[^\w]', '', word)  # Remove punctuation
            
            if word_clean in company_indicators:
                company_terms.append(word_clean)
            elif word_clean in action_terms:
                weighted_terms.append({'term': word_clean, 'weight': action_terms[word_clean], 'type': 'action'})
            elif len(word_clean) > 4 and word_clean not in ['the', 'and', 'for', 'with', 'from']:
                # Technical terms not in our dictionaries
                weighted_terms.append({'term': word_clean, 'weight': 1.0, 'type': 'technical'})
        
        # Determine if title is very specific
        total_weight = sum(term['weight'] for term in weighted_terms)
        is_very_specific = (
            len(weighted_terms) <= 3 and  # Few terms
            total_weight >= 5.0 and       # High semantic weight
            any(t['weight'] >= 2.5 for t in weighted_terms)  # Has high-value terms
        )
        
        return {
            'weighted_terms': weighted_terms,
            'company_terms': company_terms,
            'total_weight': total_weight,
            'is_very_specific': is_very_specific,
            'primary_terms': [t for t in weighted_terms if t['weight'] >= 2.0]
        }
    
    def _semantic_title_search(self, title_analysis: Dict, original_title: str) -> List[Dict]:
        """Perform semantic search based on title analysis"""
        try:
            # Build search query using primary terms
            primary_terms = title_analysis['primary_terms']
            
            if not primary_terms:
                return []
            
            # Create CONTAINS clauses for primary terms
            contains_clauses = []
            for term_info in primary_terms:
                term_escaped = term_info['term'].replace("'", "''")
                contains_clauses.append(f"[System.Title] CONTAINS '{term_escaped}'")
            
            # Use OR for flexibility but limit results
            wiql_query = f"""
            SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType], [System.State]
            FROM workitems 
            WHERE [System.TeamProject] = '{self.config.UAT_PROJECT}'
            AND [System.WorkItemType] = 'Actions'
            AND ({' OR '.join(contains_clauses)})
            ORDER BY [System.CreatedDate] DESC
            """
            
            wiql_url = f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_apis/wit/wiql?api-version={self.config.API_VERSION}"
            response = requests.post(wiql_url, headers=self._get_headers('uat'), json={"query": wiql_query})
            
            if response.status_code != 200:
                return []
            
            work_items = response.json().get('workItems', [])
            
            if not work_items:
                return []
                
            print(f"Semantic search found {len(work_items)} candidates, analyzing...")
            
            # Limit candidates for performance but include description analysis
            candidates = work_items[:500]  # Process reasonable number
            return self._get_work_item_details_with_semantic_scoring(candidates, original_title, title_analysis)
            
        except Exception as e:
            print(f"Semantic title search failed: {e}")
            return []
    
    def _search_recent_items(self, title: str, description: str, days: int = 240) -> List[Dict]:
        """Search recent items with similarity scoring (last 8 months to match production query)"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            
            # Extract key terms from title for targeted search
            # Use STRICTER matching - require words 4+ chars and filter common words
            title_lower = title.lower()
            title_words = [word for word in title_lower.split() if len(word) > 3 
                          and word not in ['the', 'and', 'for', 'with', 'from', 'that', 'this', 
                                          'where', 'when', 'what', 'how', 'azure', 'support']]
            
            # Extract meaningful phrases (2-3 word combinations that appear together)
            key_phrases = []
            for i in range(len(title_words) - 1):
                phrase = f"{title_words[i]} {title_words[i+1]}"
                if len(phrase) > 8:  # Meaningful phrases only
                    key_phrases.append(phrase)
            
            # Use phrases if available, otherwise use top words
            key_terms = key_phrases[:2] if key_phrases else title_words[:3]
            
            if key_terms:
                # Build CONTAINS clause for key terms - ALL terms must match (AND not OR)
                contains_clause = " AND ".join([f"[System.Title] CONTAINS '{term}'" for term in key_terms])
                
                wiql_query = f"""
                SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType], [System.State]
                FROM workitems 
                WHERE [System.TeamProject] = '{self.config.UAT_PROJECT}'
                AND [System.WorkItemType] = 'Actions'
                AND [System.CreatedDate] >= '{cutoff_date_str}'
                AND ({contains_clause})
                ORDER BY [System.CreatedDate] DESC
                """
            else:
                # Fallback to recent items without keyword filtering
                wiql_query = f"""
                SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType], [System.State]
                FROM workitems 
                WHERE [System.TeamProject] = '{self.config.UAT_PROJECT}'
                AND [System.WorkItemType] = 'Actions'
                AND [System.CreatedDate] >= '{cutoff_date_str}'
                ORDER BY [System.CreatedDate] DESC
                """
            
            print(f"[SEARCH] Using {days}-day filter with key terms: {key_terms}")
            print(f"[SEARCH] WIQL Query Preview: ...WHERE CreatedDate >= '{cutoff_date_str}' AND Title CONTAINS...")
            
            wiql_url = f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_apis/wit/wiql?api-version={self.config.API_VERSION}"
            response = requests.post(wiql_url, headers=self._get_headers('uat'), json={"query": wiql_query})
            
            if response.status_code != 200:
                print(f"Recent search failed: {response.status_code}")
                return []
            
            work_items = response.json().get('workItems', [])
            print(f"[SEARCH] Query returned {len(work_items)} work items (before similarity scoring)")
            if not work_items:
                return []
            
            # Limit to reasonable number for processing
            max_to_process = min(500, len(work_items))
            print(f"[SEARCH] Processing top {max_to_process} of {len(work_items)} items with semantic scoring...")
            return self._get_work_item_details_with_semantic_scoring(work_items[:max_to_process], title, self._analyze_title_semantics(title), description)
            
        except Exception as e:
            print(f"Recent search failed: {e}")
            return []
    
    def _search_by_keywords(self, title: str, description: str) -> List[Dict]:
        """Keyword-based search as final fallback"""
        try:
            # Extract meaningful keywords
            all_text = f"{title} {description}".lower()
            words = [word for word in all_text.split() if len(word) > 4]  # Longer words only
            keywords = list(set(words))[:5]  # Unique keywords, max 5
            
            if not keywords:
                return []
            
            # Build keyword search
            contains_clauses = []
            for keyword in keywords:
                keyword_escaped = keyword.replace("'", "''")
                contains_clauses.append(f"([System.Title] CONTAINS '{keyword_escaped}' OR [System.Description] CONTAINS '{keyword_escaped}')")
            
            wiql_query = f"""
            SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType], [System.State]
            FROM workitems 
            WHERE [System.TeamProject] = '{self.config.UAT_PROJECT}'
            AND [System.WorkItemType] = 'Actions'
            AND ({' OR '.join(contains_clauses)})
            ORDER BY [System.CreatedDate] DESC
            """
            
            wiql_url = f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_apis/wit/wiql?api-version={self.config.API_VERSION}"
            response = requests.post(wiql_url, headers=self._get_headers('uat'), json={"query": wiql_query})
            
            if response.status_code != 200:
                return []
            
            work_items = response.json().get('workItems', [])
            if not work_items:
                return []
            
            # Process limited set for speed
            limited_items = work_items[:1000]  # Max 1000 items
            return self._get_work_item_details(limited_items, title, description)
            
        except Exception as e:
            print(f"Keyword search failed: {e}")
            return []
    
    def _get_work_item_details(self, work_items: List[Dict], title: str, description: str) -> List[Dict]:
        """Get detailed work item info and calculate similarities (legacy method)"""
        # Use semantic scoring for better results
        title_analysis = self._analyze_title_semantics(title)
        return self._get_work_item_details_with_semantic_scoring(work_items, title, title_analysis, description)
    
    def _get_work_item_details_with_semantic_scoring(self, work_items: List[Dict], title: str, title_analysis: Dict, description: str = None) -> List[Dict]:
        """Get detailed work item info with semantic similarity scoring"""
        try:
            if not work_items:
                return []
            
            similar_items = []
            work_item_ids = [item['id'] for item in work_items if 'id' in item]
            
            # ⚡ PERFORMANCE: Faster batch processing
            batch_size = 50  # Smaller batches for faster response
            
            for i in range(0, len(work_item_ids), batch_size):
                batch_ids = work_item_ids[i:i + batch_size]
                ids_param = ','.join(map(str, batch_ids))
                
                detail_url = f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_apis/wit/workitems"
                detail_params = {
                    'ids': ids_param,
                    'fields': 'System.Id,System.Title,System.Description,System.State,System.CreatedDate',
                    'api-version': '7.0'
                }
                
                detail_response = requests.get(detail_url, headers=self._get_headers('uat'), params=detail_params)
                
                if detail_response.status_code != 200:
                    continue
                
                batch_work_items = detail_response.json().get('value', [])
                
                # Semantic similarity calculation
                for work_item in batch_work_items:
                    try:
                        fields = work_item.get('fields', {})
                        work_item_id = work_item.get('id')
                        work_item_title = fields.get('System.Title', '')
                        work_item_description = fields.get('System.Description', '')
                        
                        # Calculate semantic similarity
                        semantic_score = self._calculate_semantic_similarity(
                            title, work_item_title, title_analysis, 
                            description or title, work_item_description
                        )
                        
                        # PERFORMANCE: Use higher threshold and early exit
                        if semantic_score['combined_score'] > 0.6:  # Higher threshold for quality
                            similar_items.append({
                                'id': work_item_id,
                                'title': work_item_title,
                                'description': work_item_description[:500],  # Truncate for performance
                                'similarity': semantic_score['combined_score'],
                                'title_semantic_score': semantic_score['title_score'],
                                'description_match_score': semantic_score['desc_score'],
                                'source': 'UAT',
                                'url': f"{self.config.UAT_BASE_URL}/{quote(self.config.UAT_PROJECT)}/_workitems/edit/{work_item_id}",
                                'created_date': fields.get('System.CreatedDate', ''),
                                'work_item_type': 'Actions',
                                'state': fields.get('System.State', ''),
                                'match_reasoning': semantic_score['reasoning']
                            })
                            
                            # ⚡ PERFORMANCE: Early exit when we have enough quality matches
                            if len(similar_items) >= 30 and semantic_score['combined_score'] > 0.8:
                                print(f"[PERF] Early exit: Found {len(similar_items)} high-quality matches")
                                break
                            
                    except Exception as item_error:
                        continue  # Skip problematic items
                
                # ⚡ Early exit at batch level too
                if len(similar_items) >= 50:
                    print(f"[PERF] Batch early exit: Found {len(similar_items)} matches")
                    break
            
            # Sort by semantic similarity and return top matches
            similar_items.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_items[:50]  # Return top 50 matches to ensure exact matches aren't missed
            
        except Exception as e:
            print(f"Error getting work item details: {e}")
            return []
    
    def _calculate_semantic_similarity(self, user_title: str, item_title: str, title_analysis: Dict, 
                                     user_desc: str, item_desc: str) -> Dict:
        """Calculate semantic similarity between user input and work item"""
        
        # 1. Title semantic matching
        title_score = 0.0
        matched_concepts = []
        
        item_title_lower = item_title.lower()
        user_title_lower = user_title.lower()
        
        # Special boost for very similar titles (exact company + concept matches)
        title_similarity_ratio = SequenceMatcher(None, user_title_lower, item_title_lower).ratio()
        if title_similarity_ratio > 0.8:  # Very similar titles
            title_score += 0.4  # Big boost for near-exact matches
            matched_concepts.append(f"Near-exact: {title_similarity_ratio:.2f}")
        
        # Check for primary term matches (weighted heavily)
        for term_info in title_analysis['primary_terms']:
            term = term_info['term']
            if term in item_title_lower:
                title_score += term_info['weight'] * 0.3  # Each primary term contributes up to 30%
                matched_concepts.append(f"Primary: {term}")
        
        # Company terms are IGNORED for matching - we only care about Azure services and context
        # This prevents customer-specific matches from interfering with functional matching
        
        # Check for other weighted terms
        for term_info in title_analysis['weighted_terms']:
            if term_info not in title_analysis['primary_terms']:
                term = term_info['term']
                if term in item_title_lower:
                    title_score += term_info['weight'] * 0.1  # Secondary terms contribute less
                    matched_concepts.append(f"Secondary: {term}")
        
        # Cap title score at 1.0
        title_score = min(title_score, 1.0)
        
        # 2. Description content analysis (when titles match concepts)
        desc_score = 0.0
        desc_reasoning = []
        
        if title_score > 0.3 and item_desc:  # Only analyze description if title has some relevance
            user_desc_lower = user_desc.lower()
            item_desc_lower = item_desc.lower()
            
            # Check for functional similarity keywords
            functional_keywords = [
                'search', 'query', 'filter', 'column', 'schema', 'catalog', 'data',
                'language', 'mixed', 'english', 'japanese', 'character', 'deployment',
                'schedule', 'accelerate', 'timeline', 'implementation', 'feature'
            ]
            
            common_functional_terms = 0
            for keyword in functional_keywords:
                if keyword in user_desc_lower and keyword in item_desc_lower:
                    common_functional_terms += 1
                    desc_reasoning.append(f"Functional: {keyword}")
            
            # Calculate description similarity
            if len(item_desc_lower) > 0:
                basic_desc_similarity = SequenceMatcher(None, user_desc_lower, item_desc_lower).ratio()
                functional_boost = min(common_functional_terms * 0.15, 0.6)  # Up to 60% boost
                desc_score = min(basic_desc_similarity + functional_boost, 1.0)
        
        # 3. Combined scoring
        # Weight: Title semantic (70%) + Description functional (30%)
        combined_score = (title_score * 0.7) + (desc_score * 0.3)
        
        # 4. Generate reasoning
        reasoning_parts = []
        if matched_concepts:
            reasoning_parts.append(f"Title concepts: {', '.join(matched_concepts[:3])}")
        if desc_reasoning:
            reasoning_parts.append(f"Description match: {', '.join(desc_reasoning[:3])}")
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Basic text similarity"
        
        return {
            'combined_score': combined_score,
            'title_score': title_score,
            'desc_score': desc_score,
            'reasoning': reasoning
        }

    
    def search_tft_items(self, title: str, description: str) -> List[Dict]:
        """
        Search Technical Feedback Azure DevOps organization for similar work items.
        
        Performs a comprehensive search of the Technical Feedback Team (TFT) organization's 
        work items within the configured lookback period. Similar to UAT search but targets
        the TFT organization for technical feedback and feature requests.
        
        Args:
            title (str): Issue title to search for similarities
            description (str): Issue description for content matching
            
        Returns:
            List[Dict]: List of similar work items with metadata including:
                - id: Work item ID
                - title: Work item title
                - description: Work item description
                - similarity: Calculated similarity score (0.0-1.0)
                - source: Organization identifier ('TFT')
                - url: Direct link to work item
                - created_date: When the work item was created
                - work_item_type: Type of work item (Feature, Enhancement, etc.)
                - state: Current state of the work item
        """
        try:
            # Use a shorter time range to avoid hitting the 20k work item limit
            cutoff_date = datetime.now() - timedelta(days=7)  # Reduced to 7 days due to high volume
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            
            # WIQL query to get work items from the last 12 months, filtering for Feature work items
            wiql_query = f"""
            SELECT [System.Id], [System.Title], [System.Description], [System.CreatedDate], [System.WorkItemType], [System.State]
            FROM workitems 
            WHERE [System.TeamProject] = '{self.config.TFT_PROJECT}'
            AND [System.CreatedDate] >= '{cutoff_date_str}'
            AND [System.WorkItemType] = 'Feature'
            ORDER BY [System.CreatedDate] DESC
            """
            
            # Execute WIQL query
            wiql_url = f"{self.config.TFT_BASE_URL}/{quote(self.config.TFT_PROJECT)}/_apis/wit/wiql?api-version={self.config.API_VERSION}"
            wiql_response = requests.post(
                wiql_url,
                headers=self._get_headers('tft'),
                json={"query": wiql_query}
            )
            
            if wiql_response.status_code != 200:
                print(f"TFT WIQL query failed: {wiql_response.status_code}")
                print(f"TFT Response text: {wiql_response.text}")
                print(f"TFT Query URL: {wiql_url}")
                print(f"TFT Query: {wiql_query}")
                return []
            
            work_items = wiql_response.json().get('workItems', [])
            if not work_items:
                return []
            
            # Get detailed work item information
            work_item_ids = [str(item['id']) for item in work_items[:100]]  # Limit to 100 items
            
            if not work_item_ids:
                return []
            
            # Get work item details
            batch_url = f"{self.config.TFT_BASE_URL}/_apis/wit/workitems?ids={','.join(work_item_ids)}&api-version={self.config.API_VERSION}"
            batch_response = requests.get(batch_url, headers=self._get_headers('tft'))
            
            if batch_response.status_code != 200:
                print(f"TFT Batch request failed: {batch_response.status_code}")
                return []
            
            detailed_items = batch_response.json().get('value', [])
            
            # Calculate similarities and filter
            similar_items = []
            for item in detailed_items:
                fields = item.get('fields', {})
                item_title = fields.get('System.Title', '')
                item_description = fields.get('System.Description', '')
                
                # Calculate similarity
                title_similarity = SequenceMatcher(None, title.lower(), item_title.lower()).ratio()
                desc_similarity = SequenceMatcher(None, description.lower(), item_description.lower()).ratio()
                overall_similarity = (title_similarity * 0.6) + (desc_similarity * 0.4)
                
                if overall_similarity >= self.config.SIMILARITY_THRESHOLD:
                    similar_items.append({
                        'id': item['id'],
                        'title': item_title,
                        'description': item_description,
                        'created_date': fields.get('System.CreatedDate', ''),
                        'work_item_type': fields.get('System.WorkItemType', ''),
                        'state': fields.get('System.State', ''),
                        'similarity': overall_similarity,
                        'source': 'Feature',
                        'url': f"{self.config.TFT_BASE_URL}/{quote(self.config.TFT_PROJECT)}/_workitems/edit/{item['id']}"
                    })
            
            # Sort by similarity (highest first)
            similar_items.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_items
            
        except Exception as e:
            print(f"Error searching TFT items: {str(e)}")
            return []


class EnhancedMatcher:
    """
    Main enhanced matching system orchestrator that coordinates all matching operations.
    
    This class serves as the central coordinator for the enhanced matching process,
    integrating AI analysis, local database searching, and Azure DevOps integration
    to provide comprehensive issue matching and resolution suggestions.
    
    Attributes:
        issue_tracker: Local issue database and similarity matching system
        progress_tracker (ProgressTracker): Real-time progress monitoring
        ai_analyzer (AIAnalyzer): AI-powered quality analysis and enhancement
        ado_searcher (AzureDevOpsSearcher): Azure DevOps integration for work item searching
    """
    
    def __init__(self, issue_tracker):
        """
        Initialize the enhanced matcher with all required components.
        
        Args:
            issue_tracker: Instance of the local issue tracking system
        """
        print("[DEBUG MATCHER 1] EnhancedMatcher.__init__() starting...", flush=True)
        self.issue_tracker = issue_tracker
        print("[DEBUG MATCHER 2] issue_tracker assigned.", flush=True)
        self.progress_tracker = ProgressTracker()
        print("[DEBUG MATCHER 3] ProgressTracker created.", flush=True)
        self.ai_analyzer = AIAnalyzer()
        print("[DEBUG MATCHER 4] AIAnalyzer created. About to create AzureDevOpsSearcher...", flush=True)
        self.ado_searcher = AzureDevOpsSearcher()
        print("[DEBUG MATCHER 5] AzureDevOpsSearcher created! About to create HybridContextAnalyzer...", flush=True)
        self.context_analyzer = HybridContextAnalyzer()
        print("[DEBUG MATCHER 6] EnhancedMatcher.__init__() completed successfully!", flush=True)
    
    def start_matching_process(self, wizard_data: Dict) -> Dict:
        """
        Start the enhanced matching process with initial quality analysis.
        
        Performs the first step of enhanced matching by analyzing the completeness
        and quality of the submitted issue data using AI-powered analysis.
        
        Args:
            wizard_data (Dict): Complete wizard submission data including:
                - title: Issue title
                - description: Detailed issue description
                - impact: Business impact statement
                - opportunity_id: Related opportunity ID (optional)
                - milestone_id: Related milestone ID (optional)
                
        Returns:
            Dict: Analysis results including:
                - progress: Current processing step information
                - analysis: Quality analysis results with completeness score
                - needs_more_info: Boolean indicating if more information is required
        """
        # Step 1: Analyze completeness
        progress = self.progress_tracker.start_step("Analyzing submission for completeness")
        
        analysis = self.ai_analyzer.analyze_completeness(
            wizard_data.get('title', ''),
            wizard_data.get('description', ''),
            wizard_data.get('impact', '')
        )
        
        return {
            'progress': progress,
            'analysis': analysis,
            'needs_more_info': not analysis['is_complete']
        }
    
    def enhance_information(self, wizard_data: Dict) -> Dict:
        """
        Enhance the description and impact statements using AI analysis.
        
        Applies AI-powered enhancement to improve the quality and completeness
        of issue descriptions and impact statements, adding context and technical
        categorization to improve matching accuracy.
        
        Args:
            wizard_data (Dict): Wizard submission data to enhance
            
        Returns:
            Dict: Enhancement results including:
                - progress: Current processing step information
                - enhanced: Enhanced descriptions and impact statements
        """
        progress = self.progress_tracker.start_step("Enhancing description and impact statements")
        
        enhanced = self.ai_analyzer.enhance_description(
            wizard_data.get('title', ''),
            wizard_data.get('description', ''),
            wizard_data.get('impact', ''),
            wizard_data.get('opportunity_id', ''),
            wizard_data.get('milestone_id', '')
        )
        
        return {
            'progress': progress,
            'enhanced': enhanced
        }
    
    def analyze_context_for_evaluation(self, title: str, description: str, impact: str = "") -> Dict:
        """
        Perform context analysis and return results for human evaluation.
        
        🆕 v3.1: Fixed blank fields bug by including ALL context analysis fields
        
        This method performs only the context analysis phase without proceeding 
        to search operations. Results are returned for human validation before
        continuing with the intelligent search process.
        
        PREVIOUS BUG:
        The evaluation data was only passing a subset of context analysis fields:
        - category, intent, confidence, business_impact (✓ included)
        - reasoning, pattern_features, source (✓ included)
        - technical_complexity, urgency_level (✗ MISSING - showed "Not Available")
        - key_concepts, semantic_keywords (✗ MISSING - showed "Not available")
        - domain_entities, recommended_search_strategy (✗ MISSING)
        - context_summary (✗ MISSING)
        
        FIX:
        Now includes ALL fields from the ContextAnalysis object, ensuring the UI
        displays complete information in the Final Decision Summary section.
        
        Args:
            title (str): Issue title
            description (str): Issue description  
            impact (str): Business impact statement
            
        Returns:
            Dict: Complete context analysis results for evaluation with structure:
            {
                'original_issue': {
                    'title': str,
                    'description': str,
                    'impact': str
                },
                'context_analysis': {
                    'category': str (enum value),
                    'intent': str (enum value),
                    'confidence': float (0.0-1.0),
                    'business_impact': str (low/medium/high),
                    'technical_complexity': str (low/medium/high),  # 🆕 v3.1
                    'urgency_level': str (low/medium/high),         # 🆕 v3.1
                    'key_concepts': List[str],                      # 🆕 v3.1
                    'semantic_keywords': List[str],                 # 🆕 v3.1
                    'domain_entities': Dict[str, List[str]],        # 🆕 v3.1
                    'recommended_search_strategy': Dict[str, bool], # 🆕 v3.1
                    'context_summary': str,                         # 🆕 v3.1
                    'reasoning': str or Dict,
                    'pattern_features': Dict,
                    'source': str (ai/pattern/hybrid)
                },
                'timestamp': str (ISO format)
            }
        """
        # Perform intelligent context analysis
        context_analysis = self.context_analyzer.analyze(title, description, impact)
        
        # Format context analysis for evaluation - NOW WITH ALL FIELDS
        category_value = context_analysis.category.value if hasattr(context_analysis.category, 'value') else str(context_analysis.category).split('.')[-1].lower()
        intent_value = context_analysis.intent.value if hasattr(context_analysis.intent, 'value') else str(context_analysis.intent).split('.')[-1].lower()
        
        evaluation_data = {
            'original_issue': {
                'title': title,
                'description': description,
                'impact': impact
            },
            'context_analysis': {
                # Core classification
                'category': category_value,
                'intent': intent_value,
                'confidence': context_analysis.confidence,
                
                # Business context
                'business_impact': context_analysis.business_impact,
                
                # 🆕 v3.1: Previously missing fields that caused "Not Available" display
                'technical_complexity': context_analysis.technical_complexity,
                'urgency_level': context_analysis.urgency_level,
                'key_concepts': context_analysis.key_concepts,
                'semantic_keywords': context_analysis.semantic_keywords,
                'domain_entities': context_analysis.domain_entities,
                'recommended_search_strategy': context_analysis.recommended_search_strategy,
                'context_summary': context_analysis.context_summary,
                
                # Analysis details
                'reasoning': context_analysis.reasoning,
                'pattern_features': context_analysis.pattern_features,
                'pattern_reasoning': context_analysis.pattern_reasoning if hasattr(context_analysis, 'pattern_reasoning') else None,
                'source': context_analysis.source,
                
                # AI status tracking (for diagnostic display)
                # These fields enable templates to show success indicators and error messages
                'ai_available': context_analysis.ai_available,
                'ai_error': context_analysis.ai_error,
                
                # Display-friendly field mappings
                'category_display': category_value.replace('_', ' ').title(),
                'intent_display': intent_value.replace('_', ' ').title(),
                'business_impact_display': context_analysis.business_impact.replace('_', ' ').title() if context_analysis.business_impact else 'Not Assessed'
            },
            'timestamp': datetime.now().isoformat()
        }
        
        # Handle reasoning display - could be dict or string
        reasoning_preview = context_analysis.reasoning
        if isinstance(reasoning_preview, dict):
            reasoning_preview = f"Pattern matching only (AI {'disabled' if not hasattr(context_analysis, 'source') else 'unavailable'})"
        elif isinstance(reasoning_preview, str):
            reasoning_preview = reasoning_preview[:100]
        
        print(f"CONTEXT ANALYSIS FOR EVALUATION: {reasoning_preview}...")
        print(f"Category: {context_analysis.category}, Intent: {context_analysis.intent}")
        print(f"Confidence: {context_analysis.confidence:.2f}")
        
        return evaluation_data

    def intelligent_search_all_sources(self, title: str, description: str, impact: str = "", progress_callback=None, skip_evaluation: bool = False) -> Dict:
        """
        Intelligent search using context analysis for smart routing and matching
        
        Performs sophisticated pre-processing to understand the context, intent, and domain
        of the user's issue, then applies intelligent search strategies based on the analysis.
        
        Args:
            title (str): Issue title
            description (str): Issue description  
            impact (str): Business impact statement
            progress_callback (callable): Optional callback for progress updates
            skip_evaluation (bool): If True, skip evaluation and proceed directly with search
            
        Returns:
            Dict: Comprehensive search results with context analysis
        """
        results = {
            'evaluating_retirements': [],
            'uat_items': [],
            'feature_items': [],
            'total_matches': 0,
            'context_analysis': None,
            'search_strategy_used': {}
        }
        
        # Step 1: Intelligent Context Analysis
        if progress_callback:
            progress_callback(1, 6, 15, "Analyzing Context - Understanding issue domain and intent")
        
        context_analysis = self.context_analyzer.analyze(title, description, impact)
        results['context_analysis'] = {
            'category': context_analysis.category,
            'intent': context_analysis.intent,
            'confidence': context_analysis.confidence,
            'business_impact': context_analysis.business_impact,
            'reasoning': context_analysis.reasoning,
            'pattern_features': context_analysis.pattern_features,
            'source': context_analysis.source
        }
        
        print(f"CONTEXT ANALYSIS: Category={context_analysis.category}, Intent={context_analysis.intent}")
        
        # Step 2: Smart Retirement Checking (always check)
        if progress_callback:
            progress_callback(2, 6, 30, "Smart Retirement Analysis - Context-aware retirement checking")
        
        # Use comprehensive search strategy
        strategy = {'search_retirements': True, 'search_ado': True}
        results['search_strategy_used'] = strategy
        
        # Retirement checking is now handled by search_service.py via the /perform_search route
        if strategy.get('search_retirements', False):
            print("SMART ROUTING: Retirement checking available via search service")
        else:
            print("SMART ROUTING: Skipping retirement check (context indicates non-retirement issue)")
        
        # Step 3: Intelligent UAT Search
        if progress_callback:
            progress_callback(3, 6, 50, "Intelligent UAT Search - Context-driven user issue matching")
        
        # Generate intelligent search terms based on context
        enhanced_search_terms = self._generate_intelligent_search_terms(
            title, description, context_analysis
        )
        
        print(f"INTELLIGENT SEARCH TERMS: {enhanced_search_terms[:50]}...")
        
        try:
            if strategy.get('prioritize_uats', True):
                print("SMART ROUTING: Prioritizing UAT search (context indicates user issue similarity)")
                
                uat_items = self.ado_searcher.search_uat_items(title, enhanced_search_terms)
                
                results['uat_items'] = self._apply_context_scoring(uat_items, context_analysis)
            else:
                print("SMART ROUTING: Standard UAT search")
                
                uat_items = self.ado_searcher.search_uat_items(title, description)
                
                results['uat_items'] = uat_items
        except Exception as e:
            print(f"Warning: Error in intelligent UAT search: {e}")
            results['uat_items'] = []
        
        # Step 4: Intelligent Feature Search  
        if progress_callback:
            progress_callback(4, 6, 70, "Intelligent Feature Search - Context-aware feature matching")
        
        try:
            if strategy.get('prioritize_features', False):
                print("SMART ROUTING: Prioritizing feature search (context indicates feature request)")
                feature_items = self.ado_searcher.search_tft_items(title, enhanced_search_terms)
                results['feature_items'] = self._apply_context_scoring(feature_items, context_analysis)
            else:
                print("SMART ROUTING: Standard feature search")
                feature_items = self.ado_searcher.search_tft_items(title, description)
                results['feature_items'] = feature_items
        except Exception as e:
            print(f"Warning: Error in intelligent feature search: {e}")
            results['feature_items'] = []
        
        # Step 5: Intelligent Results Compilation
        if progress_callback:
            progress_callback(5, 6, 85, "Smart Results Compilation - Context-aware ranking and prioritization")
        
        all_items = self._intelligent_results_compilation(results, context_analysis)
        results['all_items'] = all_items
        results['total_matches'] = len(all_items)
        
        print(f"INTELLIGENT RESULTS: {len(results['evaluating_retirements'])} retirements, "
              f"{len(results['uat_items'])} UATs, {len(results['feature_items'])} features, "
              f"{len(all_items)} total intelligent matches")
        
        if progress_callback:
            progress_callback(6, 6, 100, "Context Analysis Complete - Intelligent matching results ready")
        
        return {
            'progress': self.progress_tracker.get_progress() if hasattr(self, 'progress_tracker') else None,
            'results': results
        }
    
    def _generate_intelligent_search_terms(self, title: str, description: str, context_analysis) -> str:
        """Generate context-aware search terms for better matching"""
        
        # Start with original content
        base_terms = f"{title} {description}"
        
        # Add semantic keywords from context analysis
        semantic_terms = " ".join(context_analysis.semantic_keywords)
        
        # Add key concepts
        concept_terms = " ".join(context_analysis.key_concepts)
        
        # Add domain-specific expansions based on category
        category_expansions = {
            IssueCategory.COMPLIANCE_REGULATORY: "audit framework standard requirement control policy governance",
            IssueCategory.TECHNICAL_SUPPORT: "configuration implementation troubleshooting resolution support guide",
            IssueCategory.FEATURE_REQUEST: "functionality capability enhancement improvement feature development",
            IssueCategory.SECURITY_GOVERNANCE: "security protection monitoring detection prevention governance",
            IssueCategory.MIGRATION_MODERNIZATION: "migration modernization upgrade transition replacement alternative"
        }
        
        expansion_terms = category_expansions.get(context_analysis.category, "")
        
        # Combine all terms intelligently
        enhanced_terms = f"{base_terms} {semantic_terms} {concept_terms} {expansion_terms}"
        
        return enhanced_terms.strip()
    
    def _apply_context_scoring(self, items: List[Dict], context_analysis) -> List[Dict]:
        """Apply context-aware scoring to improve relevance"""
        
        if not items:
            return items
        
        # Add context relevance scores to items
        for item in items:
            item_text = f"{item.get('title', '')} {item.get('description', '')}".lower()
            
            # Calculate context relevance
            relevance_score = 0
            
            # Boost items that match key concepts
            for concept in context_analysis.key_concepts:
                if concept.lower() in item_text:
                    relevance_score += 0.2
            
            # Boost items that match semantic keywords  
            for keyword in context_analysis.semantic_keywords:
                if keyword.lower() in item_text:
                    relevance_score += 0.1
            
            # Boost based on business impact alignment
            if context_analysis.business_impact == "high":
                high_impact_terms = ["critical", "production", "urgent", "business"]
                if any(term in item_text for term in high_impact_terms):
                    relevance_score += 0.3
            
            # Add context relevance to existing similarity score
            original_similarity = item.get('similarity', 0)
            enhanced_similarity = min(original_similarity + relevance_score, 1.0)
            item['context_relevance'] = relevance_score
            item['enhanced_similarity'] = enhanced_similarity
        
        # Sort by enhanced similarity
        items.sort(key=lambda x: x.get('enhanced_similarity', x.get('similarity', 0)), reverse=True)
        
        return items
    
    def _intelligent_results_compilation(self, results: Dict, context_analysis) -> List[Dict]:
        """Intelligently compile and prioritize results based on context"""
        
        all_items = []
        
        # Priority 1: Retirement items (if relevant to context)
        retirement_items = results.get('evaluating_retirements', [])
        if retirement_items and context_analysis.category == IssueCategory.SERVICE_RETIREMENT:
            print("INTELLIGENT COMPILATION: Prioritizing retirement items (retirement context detected)")
            all_items.extend(retirement_items)
        
        # Priority 2: Context-appropriate items
        if context_analysis.recommended_search_strategy.get('prioritize_uats', False):
            print("INTELLIGENT COMPILATION: Prioritizing UAT items (technical support context)")
            all_items.extend(results.get('uat_items', []))
            all_items.extend(results.get('feature_items', []))
        elif context_analysis.recommended_search_strategy.get('prioritize_features', False):
            print("INTELLIGENT COMPILATION: Prioritizing feature items (feature request context)")
            all_items.extend(results.get('feature_items', []))
            all_items.extend(results.get('uat_items', []))
        else:
            # Standard prioritization for other contexts
            all_items.extend(results.get('uat_items', []))
            all_items.extend(results.get('feature_items', []))
        
        # Add any retirement items not already included
        if context_analysis.category != IssueCategory.SERVICE_RETIREMENT and retirement_items:
            all_items.extend(retirement_items)
        
        # Apply final intelligent sorting
        def intelligent_sort_key(item):
            # Use context-enhanced scoring if available
            if 'enhanced_similarity' in item:
                return item['enhanced_similarity']
            elif item.get('type') == 'retirement':
                return item.get('match_score', 0)
            else:
                return item.get('similarity', 0)
        
        all_items.sort(key=intelligent_sort_key, reverse=True)
        
        # Limit results based on context urgency
        max_results = 45
        if context_analysis.urgency_level == "high":
            max_results = 20  # Focus on top results for urgent issues
        
        return all_items[:max_results]
    
    def search_all_sources(self, title: str, description: str, enhanced_description: str, progress_callback=None) -> Dict:
        """
        Search all available sources for similar items with comprehensive progress tracking.
        
        Performs a multi-source search across local database, UAT organization,
        and Technical Feedback organization, providing real-time progress updates
        and aggregating results from all sources.
        
        Args:
            title (str): Issue title for similarity matching
            description (str): Original issue description
            enhanced_description (str): AI-enhanced description for improved matching
            progress_callback (callable): Optional callback for progress updates
            
        Returns:
            Dict: Comprehensive search results including:
                - evaluating_retirements: Matches from local database
                - uat_items: Matches from UAT Azure DevOps
                - feature_items: Matches from TFT Azure DevOps
                - total_matches: Total number of matches across all sources
                - progress: Final progress status
        """
        results = {
            'evaluating_retirements': [],
            'uat_items': [],
            'feature_items': [],
            'total_matches': 0
        }
        
        # Update progress if callback provided
        if progress_callback:
            progress_callback(2, 5, 40, "Evaluating Retirements - Searching local issues database")
        
        # Step 2: Check Evaluating Retirements database
        time.sleep(0.5)  # Simulate processing time
        
        # Retirement checking is now handled by search_service.py
        # Fallback to original local database search
        search_text = f"{title} {description}"
        similar_issues = self.issue_tracker.find_similar_issues(search_text)
        if similar_issues:
            for issue_data, similarity in similar_issues:
                results['evaluating_retirements'].append({
                    'id': issue_data['id'],
                        'title': issue_data['issue'],
                        'description': issue_data['description'],
                        'similarity': similarity,
                        'source': 'Evaluating Retirement',
                        'actions': issue_data.get('actions', [])
                    })
        
        # Update progress for UAT search
        if progress_callback:
            progress_callback(3, 5, 60, "Evaluating UATs - Combing through UAT work items (past 12 months)")
        
        # Step 3: Search UAT items
        time.sleep(1.0)  # Simulate processing time
        
        uat_items = self.ado_searcher.search_uat_items(title, enhanced_description)
        results['uat_items'] = uat_items
        
        # Update progress for TFT search
        if progress_callback:
            progress_callback(4, 5, 80, "Examining Existing Features - Combing through Technical Feedback (past 12 months)")
        
        # Step 4: Search Technical Feedback items
        time.sleep(1.0)  # Simulate processing time
        
        feature_items = self.ado_searcher.search_tft_items(title, enhanced_description)
        results['feature_items'] = feature_items
        
        # Update progress for final compilation
        if progress_callback:
            progress_callback(5, 5, 90, "Compiling Results - Sorting and preparing matches for review")
        
        # Step 5: Compile results
        time.sleep(0.5)  # Simulate processing time
        
        # Combine and sort all results with retirement priority
        retirement_items = []
        other_items = []
        
        # Separate retirement issues from other matches
        for item in results['evaluating_retirements']:
            if item.get('type') == 'retirement':
                # Retirement issues get top priority
                retirement_items.append(item)
            else:
                other_items.append(item)
        
        # Add other sources
        other_items.extend(results['uat_items'])
        other_items.extend(results['feature_items'])
        
        # Sort retirement items by match score (highest first)
        retirement_items.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        # Sort other items by similarity score
        other_items.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        # Combine with retirements at the top
        all_items = retirement_items + other_items
        
        # Limit to maximum 45 items as requested
        if len(all_items) > 45:
            all_items = all_items[:45]
        
        results['all_items'] = all_items
        results['total_matches'] = len(all_items)
        
        print(f"DEBUG - Search results summary:")
        print(f"  Evaluating Retirements: {len(results['evaluating_retirements'])}")
        print(f"  UAT items: {len(results['uat_items'])}")
        print(f"  Feature items: {len(results['feature_items'])}")
        print(f"  Total all_items: {len(all_items)}")
        print(f"  Total matches: {results['total_matches']}")
        
        return {
            'progress': self.progress_tracker.get_progress() if hasattr(self, 'progress_tracker') else None,
            'results': results
        }
    
    def paginate_results(self, all_items: List[Dict], page: int = 1) -> Dict:
        """Paginate results for display"""
        items_per_page = EnhancedMatchingConfig.MAX_RESULTS_PER_PAGE
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        
        paginated_items = all_items[start_idx:end_idx]
        total_pages = (len(all_items) + items_per_page - 1) // items_per_page
        
        return {
            'items': paginated_items,
            'current_page': page,
            'total_pages': total_pages,
            'total_items': len(all_items),
            'has_previous': page > 1,
            'has_next': page < total_pages,
            'previous_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None
        }
    
    def continue_intelligent_search_after_approval(self, evaluation_data: Dict, progress_callback=None) -> Dict:
        """
        Continue intelligent search after human evaluation approval
        
        This method takes the approved context analysis and proceeds with the 
        intelligent search using the validated context understanding.
        
        Args:
            evaluation_data (Dict): Original evaluation data with approved context
            progress_callback (callable): Optional callback for progress updates
            
        Returns:
            Dict: Complete search results using approved context
        """
        # Extract original issue data
        original_issue = evaluation_data['original_issue']
        title = original_issue['title']
        description = original_issue['description']
        impact = original_issue.get('impact', '')
        
        # Use approved context analysis
        approved_context = evaluation_data['context_analysis']
        approved_strategy = evaluation_data['recommended_strategy']
        
        print(f"[SEARCH] APPROVED SEARCH METHOD CALLED - continue_intelligent_search_after_approval")
        print(f"CONTINUING SEARCH WITH APPROVED CONTEXT:")
        print(f"Category: {approved_context['category']}, Intent: {approved_context['intent']}")
        print(f"Strategy: {approved_strategy}")
        print(f"[SEARCH] RETIREMENT SEARCH SETTING: {approved_strategy.get('search_retirements', 'NOT_SET')}")
        
        results = {
            'evaluating_retirements': [],
            'uat_items': [],
            'feature_items': [],
            'total_matches': 0,
            'context_analysis': approved_context,
            'search_strategy_used': approved_strategy
        }
        
        # Step 1: Smart Retirement Checking (based on approved strategy)
        if progress_callback:
            progress_callback(1, 4, 25, "Executing Smart Retirement Search - Using approved context analysis")
        
        # Retirement checking is now handled by search_service.py
        if approved_strategy.get('search_retirements', False):
            print("🔄 APPROVED ROUTING: Retirement checking available via search service")
        else:
            print("🚫 APPROVED ROUTING: Skipping retirement check (user confirmed non-retirement issue)")
            print(f"   ✅ Strategy correctly set search_retirements = {approved_strategy.get('search_retirements')}")
        
        # Step 2: UAT Search with approved context
        if progress_callback:
            progress_callback(2, 4, 50, "Executing UAT Search - Using approved context understanding")
        
        # Generate intelligent search terms based on approved context
        enhanced_search_terms = f"{title} {description} {' '.join(approved_context.get('semantic_keywords', []))}"
        
        try:
            if approved_strategy.get('prioritize_uats', True):
                print("[ROUTING] APPROVED ROUTING: Prioritizing UAT search (user confirmed user issue context)")
                print(f"[SEARCH] Searching with enhanced terms: {enhanced_search_terms[:100]}...")
                
                uat_items = self.ado_searcher.search_uat_items(title, enhanced_search_terms)
                
                print(f"✅ UAT search returned {len(uat_items)} items")
                results['uat_items'] = uat_items
            else:
                print("[SEARCH] APPROVED ROUTING: Standard UAT search")
                uat_items = self.ado_searcher.search_uat_items(title, description)
                print(f"✅ UAT search returned {len(uat_items)} items")
                results['uat_items'] = uat_items
        except Exception as e:
            print(f"❌ CRITICAL ERROR in approved UAT search: {e}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            results['uat_items'] = []
        
        # Step 3: Feature Search with approved context
        if progress_callback:
            progress_callback(3, 4, 75, "Executing Feature Search - Using approved context analysis")
        
        try:
            if approved_strategy.get('prioritize_features', False):
                print("APPROVED ROUTING: Prioritizing feature search (user confirmed feature request context)")
                feature_items = self.ado_searcher.search_tft_items(title, enhanced_search_terms)
                results['feature_items'] = feature_items
            else:
                print("APPROVED ROUTING: Standard feature search")
                feature_items = self.ado_searcher.search_tft_items(title, description)
                results['feature_items'] = feature_items
        except Exception as e:
            print(f"Warning: Error in approved feature search: {e}")
            results['feature_items'] = []
        
        # Step 4: Results Compilation
        if progress_callback:
            progress_callback(4, 4, 100, "Compiling Results - Finalizing matches with approved context")
        
        # Combine all results
        all_items = []
        all_items.extend(results['evaluating_retirements'])
        all_items.extend(results['uat_items'])
        all_items.extend(results['feature_items'])
        
        results['all_items'] = all_items
        results['total_matches'] = len(all_items)
        
        print(f"APPROVED SEARCH COMPLETE: {len(results['evaluating_retirements'])} retirements, "
              f"{len(results['uat_items'])} UATs, {len(results['feature_items'])} features, "
              f"{len(all_items)} total matches")
        
        return {
            'progress': self.progress_tracker.get_progress() if hasattr(self, 'progress_tracker') else None,
            'results': results
        }
