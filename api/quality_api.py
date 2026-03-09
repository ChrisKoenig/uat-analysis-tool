"""
Quality Analysis API
====================

Endpoint for analyzing input quality and completeness.
Used by Teams bot to validate user input before proceeding.

POST /api/v1/analyze/quality
Request: {title: str, description: str, impact: str}
Response: {score: int, suggestions: list, completeness: dict}
"""

from flask import request, jsonify
from . import api_bp
import sys
import os

# Add parent directory to path to import app modules
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, 'apps'))

@api_bp.route('/analyze/quality', methods=['POST'])
def analyze_quality():
    """
    Analyze input quality and provide improvement suggestions.
    
    This uses the AIAnalyzer.analyze_completeness logic to validate
    that the user has provided sufficient information for accurate analysis.
    """
    print("[QUALITY API] ==================== RECEIVED REQUEST ====================")
    try:
        # Get request data
        print("[QUALITY API] Getting JSON data from request...")
        data = request.get_json()
        print(f"[QUALITY API] Received data: {data}")
        
        if not data:
            print("[QUALITY API] ERROR: No JSON data provided")
            return jsonify({
                'error': 'No JSON data provided',
                'status': 'error'
            }), 400
        
        # Extract fields
        print("[QUALITY API] Extracting fields...")
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        impact = data.get('impact', '').strip()
        print(f"[QUALITY API] Title length: {len(title)}, Description length: {len(description)}, Impact length: {len(impact)}")
        
        # Validate required fields
        if not title:
            print("[QUALITY API] ERROR: Title is required")
            return jsonify({
                'error': 'Title is required',
                'status': 'error'
            }), 400
        
        if not description:
            print("[QUALITY API] ERROR: Description is required")
            return jsonify({
                'error': 'Description is required',
                'status': 'error'
            }), 400
        
        # Import AIAnalyzer
        print("[QUALITY API] Importing AIAnalyzer...")
        from shared.enhanced_matching import AIAnalyzer
        
        # Create analyzer instance
        print("[QUALITY API] Creating AIAnalyzer instance...")
        analyzer = AIAnalyzer()
        
        # Perform quality analysis
        print("[QUALITY API] Performing quality analysis...")
        quality_result = analyzer.analyze_completeness(title, description, impact)
        print(f"[QUALITY API] Analysis complete! Score: {quality_result.get('completeness_score', 'N/A')}")
        
        # Return structured response
        print("[QUALITY API] Returning response...")
        return jsonify({
            'status': 'success',
            'score': quality_result['completeness_score'],
            'is_complete': quality_result['is_complete'],
            'needs_improvement': quality_result['needs_improvement'],
            'suggestions': quality_result['suggestions'],
            'issues': quality_result['issues'],
            'garbage_detected': quality_result['garbage_detected'],
            'garbage_details': quality_result['garbage_details']
        }), 200
        
    except Exception as e:
        print(f"[QUALITY API] ❌ EXCEPTION OCCURRED: {type(e).__name__}")
        print(f"[QUALITY API] ❌ ERROR MESSAGE: {str(e)}")
        import traceback
        print(f"[QUALITY API] ❌ FULL TRACEBACK:")
        traceback.print_exc()
        
        return jsonify({
            'error': f'Quality analysis failed: {str(e)}',
            'status': 'error',
            'error_type': type(e).__name__
        }), 500
