"""
UAT Creation API
================

Endpoint for creating UAT work items in Azure DevOps.

POST /api/v1/uat/create
Request: Complete issue data with selected features/UATs and IDs
Response: {success, work_item_id, url, title, state}
"""

from flask import request, jsonify
from . import api_bp
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@api_bp.route('/uat/create', methods=['POST'])
def create_uat():
    """
    Create a UAT work item in Azure DevOps.
    
    Requires complete issue information including selected features, UATs,
    opportunity ID, and milestone ID.
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No JSON data provided',
                'status': 'error'
            }), 400
        
        # Extract required fields
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        impact = data.get('impact', '').strip()
        
        # Validate required fields
        if not title or not description:
            return jsonify({
                'error': 'Title and description are required',
                'status': 'error'
            }), 400
        
        # Extract context analysis (optional but helpful)
        # ⚠️ DEMO FIX (Jan 16 2026): Added classification_reason extraction
        # Passes Classification Reason from bot to ADO integration for UAT work items
        category = data.get('category', 'feature_request')
        intent = data.get('intent', 'new_feature')
        classification_reason = data.get('classification_reason', '')
        
        # Extract selections
        selected_features = data.get('selected_features', [])
        selected_uats = data.get('selected_uats', [])
        
        # Extract IDs
        opportunity_id = data.get('opportunity_id', '').strip()
        milestone_id = data.get('milestone_id', '').strip()
        
        # Import ADO integration
        from services.ado_integration import AzureDevOpsClient
        
        # Create ADO client
        ado_client = AzureDevOpsClient()
        
        # Prepare issue data in expected format
        issue_data = {
            'title': title,
            'description': description,
            'impact': impact,
            'category': category,
            'intent': intent
        }
        
        # Prepare issue data with all required fields
        full_issue_data = {
            'title': title,
            'description': description,
            'impact': impact,
            'category': category,
            'intent': intent,
            'classification_reason': classification_reason,
            'selected_features': selected_features,
            'selected_uats': selected_uats,
            'opportunity_id': opportunity_id,
            'milestone_id': milestone_id
        }
        
        # Create UAT work item
        result = ado_client.create_work_item_from_issue(full_issue_data)
        
        # Check if creation was successful
        if result.get('success'):
            return jsonify({
                'status': 'success',
                'success': True,
                'work_item_id': result.get('work_item_id'),
                'url': result.get('url'),
                'title': result.get('title'),
                'state': result.get('state'),
                'assigned_to': result.get('assigned_to')
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'success': False,
                'error': result.get('error', 'Failed to create work item')
            }), 500
        
    except Exception as e:
        print(f"[API ERROR] UAT creation failed: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'error': f'UAT creation failed: {str(e)}',
            'status': 'error',
            'success': False
        }), 500
