"""
Context Analysis API
====================

Endpoint for intelligent context analysis of issues.
Uses IntelligentContextAnalyzer to understand category, intent, and domain.

POST /api/v1/analyze/context
Request: {title: str, description: str, impact: str}
Response: {category, intent, confidence, domain_entities, detected_products, reasoning, analysis_steps}
"""

from flask import request, jsonify, current_app
from . import api_bp
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@api_bp.route('/analyze/context', methods=['POST'])
def analyze_context():
    """
    Perform comprehensive intelligent context analysis.
    
    Returns complete analysis including category classification, intent detection,
    entity extraction, product detection, and step-by-step reasoning.
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No JSON data provided',
                'status': 'error'
            }), 400
        
        # Extract fields
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        impact = data.get('impact', '').strip()
        
        # Validate required fields
        if not title or not description:
            return jsonify({
                'error': 'Title and description are required',
                'status': 'error'
            }), 400
        
        # Write debug to file since terminal output isn't showing
        try:
            with open('C:/Projects/Hack/debug_context.log', 'a', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write(f"[DEBUG CONTEXT API] REQUEST RECEIVED\n")
                f.write(f"[DEBUG CONTEXT API] Title: {title}\n")
                f.write(f"[DEBUG CONTEXT API] Description: {description[:200]}\n")
                f.write("="*80 + "\n")
                f.flush()
        except OSError:
            pass
        
        import sys
        sys.stdout.flush()
        print("="*80, flush=True)
        print(f"[DEBUG CONTEXT API] REQUEST RECEIVED", flush=True)
        print(f"[DEBUG CONTEXT API] Title: {title}", flush=True)
        print(f"[DEBUG CONTEXT API] Description: {description[:100]}...", flush=True)
        print("="*80, flush=True)
        sys.stdout.flush()
        
        # Import context analyzer
        from services.enhanced_matching import EnhancedMatcher, ProgressTracker
        
        print("[DEBUG 1] About to create ProgressTracker...", flush=True)
        # Create tracker for progress (but we won't use it for API)
        tracker = ProgressTracker()
        print("[DEBUG 2] ProgressTracker created. About to create EnhancedMatcher...", flush=True)
        
        # Create matcher instance
        matcher = EnhancedMatcher(tracker)
        print("[DEBUG 3] EnhancedMatcher created successfully. About to call analyze_context_for_evaluation...", flush=True)
        
        # Perform context analysis
        evaluation_data = matcher.analyze_context_for_evaluation(title, description, impact)
        print("[DEBUG 4] analyze_context_for_evaluation completed successfully!", flush=True)
        
        # =====================================================================
        # PRODUCT DETECTION EXTRACTION
        # =====================================================================
        # Extract detected Microsoft products from the context analysis response.
        # Products can come from multiple sources:
        # 1. pattern_reasoning.microsoft_products - Regex-based pattern matching
        #    (most specific, includes variants like "Defender for Databases")
        # 2. domain_entities.technologies - General tech keywords
        # 3. domain_entities.azure_services - Azure service names
        # =====================================================================
        
        # Extract context analysis from evaluation_data
        context_analysis = evaluation_data.get('context_analysis', {})
        
        # Extract detected products from multiple sources
        domain_entities = context_analysis.get('domain_entities', {})
        # pattern_reasoning is inside context_analysis and contains the regex-matched products
        pattern_reasoning = context_analysis.get('pattern_reasoning', {})
        detected_products = []
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[DEBUG API {timestamp}] NEW CODE LOADED - domain_entities received: {domain_entities}")
        print(f"[DEBUG API {timestamp}] pattern_reasoning keys: {pattern_reasoning.keys() if pattern_reasoning else 'None'}")
        
        # =====================================================================
        # SMART PRODUCT FILTERING
        # =====================================================================
        # Problem: Pattern matching detects both generic products ("Microsoft Defender")
        #          and specific variants ("Defender for Databases"). We want to show
        #          only the most specific products to avoid confusion.
        # 
        # Solution: Filter products based on specificity:
        #   - SPECIFIC: Contains " for " (e.g., "Defender for Endpoint")
        #               or special suffixes (" Studio", " Apps")
        #   - GENERIC: Base product names (e.g., "Microsoft Defender", "Azure")
        # 
        # If specific variants exist, return ONLY those (user cares about the variant).
        # If no specific variants, return generic products (better than nothing).
        # =====================================================================
        
        # =====================================================================
        # INTELLIGENT PRODUCT DETECTION WITH SMART FILTERING
        # =====================================================================
        # Products come from TWO sources:
        # 1. pattern_reasoning.microsoft_products - AI-detected Microsoft products
        #    (includes full names like "Defender for Databases", "Azure Route Server")
        # 2. domain_entities.azure_services - Dynamically extracted Azure services
        #    (fallback when AI detection is empty)
        #
        # CRITICAL: We filter OUT action verbs that aren't real services:
        # - "migrate" (action verb) → EXCLUDED
        # - "Azure Migrate" (actual service) → INCLUDED
        # - "route server" / "Azure Route Server" (actual service) → INCLUDED
        #
        # This ensures detected products show ONLY real Azure/Microsoft services,
        # not keywords or action verbs from the issue description.
        # =====================================================================
        
        # First, get Microsoft products from pattern_reasoning (these are the official detected products)
        microsoft_products = pattern_reasoning.get('microsoft_products', [])
        print(f"[DEBUG API] microsoft_products from pattern_reasoning: {microsoft_products}")
        
        # ⚠️ BUG FIX (Jan 16 2026): Also check step_by_step for microsoft_products_detected
        # The intelligent analyzer stores products in step_by_step_reasoning["microsoft_products_detected"]
        # but the comprehensive_reasoning dict puts them under "microsoft_products"
        if not microsoft_products and isinstance(pattern_reasoning, dict):
            # Try alternative locations where products might be stored
            if 'step_by_step' in pattern_reasoning:
                # Pattern reasoning is the comprehensive reasoning format
                microsoft_products = pattern_reasoning.get('microsoft_products', [])
            elif 'microsoft_products_detected' in pattern_reasoning:
                # Direct access to step_by_step format
                microsoft_products = pattern_reasoning.get('microsoft_products_detected', [])
            
            print(f"[DEBUG API] After fallback check, microsoft_products: {microsoft_products}")
        
        if microsoft_products:
            # Smart filtering: Prioritize specific variants over generic base products
            # E.g., "Defender for Databases" is more specific than "Microsoft Defender"
            specific_products = []
            generic_products = []
            
            for product in microsoft_products:
                if isinstance(product, dict):
                    # ⚠️ BUG FIX (Jan 16 2026): Use 'title' field for proper product names
                    # The 'name' field contains lowercase matched terms like "migrate", "vpn gateway"
                    # The 'title' field contains proper capitalized names like "Azure Route Server"
                    product_name = product.get('title', product.get('name', ''))
                    if product_name:
                        # Check if this is a specific variant (contains "for" or has multiple words)
                        name_lower = product_name.lower()
                        if ' for ' in name_lower or ' studio' in name_lower or ' apps' in name_lower:
                            specific_products.append(product_name)
                        else:
                            generic_products.append(product_name)
                elif isinstance(product, str):
                    if ' for ' in product.lower():
                        specific_products.append(product)
                    else:
                        generic_products.append(product)
            
            # If we have specific variants, only use those
            # Otherwise use all products (generic ones)
            if specific_products:
                detected_products.extend(specific_products)
                print(f"[DEBUG API] Using {len(specific_products)} specific product variants")
            else:
                detected_products.extend(generic_products)
                print(f"[DEBUG API] No specific variants, using {len(generic_products)} generic products")
        
        # If no Microsoft products found, use domain_entities with smart filtering
        # ⚠️ CRITICAL FILTERING LOGIC (Jan 16 2026):
        # Domain entities contains correctly detected Azure services BUT also has action verbs
        # Example from domain_entities.azure_services:
        #   ✅ "route server", "azure route server" (real services)
        #   ❌ "migrate", "import", "export" (action verbs, not services)
        #
        # Solution: Filter out single-word action verbs while keeping multi-word services
        # This allows dynamic detection of ANY Azure service without hardcoding
        if not detected_products:
            print(f"[DEBUG API] No Microsoft products, checking domain_entities for Azure services")
            
            # Common verbs and actions to exclude (NOT product names)
            excluded_terms = {
                'migrate', 'create', 'deploy', 'configure', 'setup', 'install',
                'update', 'upgrade', 'delete', 'remove', 'scale', 'monitor',
                'import', 'export', 'recovery', 'backup'
            }
            
            # Combine azure_services from domain_entities with filtering
            if 'azure_services' in domain_entities and isinstance(domain_entities['azure_services'], list):
                print(f"[DEBUG API] azure_services contains: {domain_entities['azure_services']}")
                for item in domain_entities['azure_services']:
                    item_lower = str(item).lower().strip()
                    
                    # Skip single-word action verbs
                    if item_lower in excluded_terms:
                        print(f"[DEBUG API] Skipping excluded term: {item}")
                        continue
                    
                    # Skip if it's ONLY an action verb with no service name
                    # e.g., skip "migrate" but allow "azure migrate" or "migration service"
                    if item_lower in excluded_terms and 'azure' not in item_lower:
                        print(f"[DEBUG API] Skipping action verb: {item}")
                        continue
                    
                    # Valid Azure service - add it with proper capitalization
                    # Convert to title case for display
                    detected_products.append(item.title() if isinstance(item, str) else item)
                    print(f"[DEBUG API] Added Azure service: {item}")
        
        print(f"[DEBUG API] Combined detected_products: {detected_products}")
        
        # =====================================================================
        # DEDUPLICATION WITH PLURAL NORMALIZATION
        # =====================================================================
        # Problem: Pattern matching can detect both singular and plural forms
        #          of the same product, causing duplicates in the results.
        # 
        # Examples:
        #   - "Defender for Databases" and "Defender for Database" (plural vs singular)
        #   - "azure databases" and "azure database"
        # 
        # Solution: Normalize by:
        #   1. Convert to lowercase (case insensitive comparison)
        #   2. Strip whitespace (remove leading/trailing spaces)
        #   3. Remove trailing 's' (normalize plurals)
        #   4. Track in set to prevent duplicates
        # 
        # Example Flow:
        #   Input: ["Defender for Databases", "Defender for Database", "Azure SQL"]
        #   Normalized: ["defender for database", "defender for database", "azure sql"]
        #   Deduplicated: ["Defender for Databases", "Azure SQL"]
        #   (First occurrence kept, subsequent duplicates skipped)
        # 
        # Result: Teams Bot shows clean product list without duplicates
        # =====================================================================
        
        def normalize_product_name(name):
            """
            Normalize product name for deduplication.
            
            Handles:
            - Case insensitivity ("Defender" == "defender")
            - Plural variations ("Databases" == "Database")
            
            Returns:
                Normalized lowercase string without trailing 's'
            """
            normalized = str(name).lower().strip()
            # Normalize common plural variations
            normalized = normalized.rstrip('s')  # Remove trailing 's' for plural forms
            return normalized
        
        seen = {}  # Map normalized name -> original name
        unique_products = []
        for product in detected_products:
            normalized = normalize_product_name(product)
            if normalized not in seen:
                seen[normalized] = product
                unique_products.append(product)
            else:
                # Keep the longer/more specific version
                existing = seen[normalized]
                if len(str(product)) > len(str(existing)):
                    # Replace with longer version
                    idx = unique_products.index(existing)
                    unique_products[idx] = product
                    seen[normalized] = product
        
        # ⚠️ DEMO FIX (Jan 16 2026): Removed get_category_guidance import
        # Was causing ImportError - function doesn't exist in app.py
        # TODO POST-DEMO: Restore category guidance functionality if needed
        category = context_analysis.get('category')
        category_guidance = None
        
        # Return structured response
        return jsonify({
            'status': 'success',
            'category': context_analysis.get('category'),
            'category_guidance': category_guidance,
            'category_display': context_analysis.get('category_display'),
            'intent': context_analysis.get('intent'),
            'intent_display': context_analysis.get('intent_display'),
            'confidence': context_analysis.get('confidence'),
            'business_impact': context_analysis.get('business_impact'),
            'business_impact_display': context_analysis.get('business_impact_display'),
            'domain_entities': domain_entities,
            'detected_products': unique_products,  # Now populated from domain_entities
            'key_concepts': context_analysis.get('key_concepts', []),
            'technical_complexity': context_analysis.get('technical_complexity'),
            'urgency_level': context_analysis.get('urgency_level'),
            'reasoning': context_analysis.get('reasoning'),
            'pattern_features': context_analysis.get('pattern_features', {}),
            'pattern_reasoning': context_analysis.get('pattern_reasoning'),
            'source': context_analysis.get('source', 'pattern_matching'),
            'ai_available': context_analysis.get('ai_available', False),
            'ai_error': context_analysis.get('ai_error'),
            'timestamp': evaluation_data.get('timestamp')
        }), 200
        
    except Exception as e:
        print(f"[API ERROR] Context analysis failed: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'error': f'Context analysis failed: {str(e)}',
            'status': 'error'
        }), 500
