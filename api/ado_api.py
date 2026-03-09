"""
Azure DevOps Search APIs
=========================

Endpoints for searching TFT features and UATs in Azure DevOps.

POST /api/v1/ado/search/features - Search similar TFT features
POST /api/v1/ado/search/uats - Search similar UATs
"""

from flask import request, jsonify
from . import api_bp
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@api_bp.route('/ado/search/features', methods=['POST'])
def search_tft_features():
    """
    Search for similar TFT features in Azure DevOps.
    
    Returns features with similarity scores to help link related work.
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
        limit = data.get('limit', 10)
        
        # Validate required fields
        if not title:
            return jsonify({
                'error': 'Title is required',
                'status': 'error'
            }), 400
        
        # Import ADO integration
        from services.ado_integration import AzureDevOpsClient
        
        # Create ADO client
        ado_client = AzureDevOpsClient()
        
        # Search for features
        features = ado_client.search_tft_features(
            title=title,
            description=description,
            threshold=0.5
        )
        
        # Limit results
        features = features[:limit]
        
        # Return results
        return jsonify({
            'status': 'success',
            'features': features,
            'count': len(features)
        }), 200
        
    except Exception as e:
        print(f"[API ERROR] Feature search failed: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'error': f'Feature search failed: {str(e)}',
            'status': 'error'
        }), 500


@api_bp.route('/ado/search/uats', methods=['POST'])
def search_uats():
    """
    Search for similar UATs in Azure DevOps.
    
    Searches UATs from the last 180 days by default.
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
        days_back = data.get('days_back', 180)
        limit = data.get('limit', 10)
        
        # Validate required fields
        if not title:
            return jsonify({
                'error': 'Title is required',
                'status': 'error'
            }), 400
        
        # Import Azure DevOps searcher for UAT search
        from services.enhanced_matching import AzureDevOpsSearcher
        
        # Create searcher
        searcher = AzureDevOpsSearcher()
        
        # Search for UATs (search_uat_items takes title and description)
        uats = searcher.search_uat_items(title, '')
        
        # Limit results
        limited_uats = uats[:limit]
        
        # Return results
        return jsonify({
            'status': 'success',
            'uats': limited_uats,
            'count': len(limited_uats),
            'total_found': len(uats)
        }), 200
        
    except Exception as e:
        print(f"[API ERROR] UAT search failed: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'error': f'UAT search failed: {str(e)}',
            'status': 'error'
        }), 500
