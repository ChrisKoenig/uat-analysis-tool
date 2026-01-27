"""
Admin Service - Dedicated microservice for administrative functions
Port: 8008
Responsibilities:
- Evaluation data viewer and search
- System configuration (future)
- User management (future)
- Audit logs (future)
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime, timedelta
import os
import json
import requests
import threading
import time
from typing import List, Dict, Any, Optional
from blob_storage_helper import (
    load_context_evaluations, 
    save_context_evaluations, 
    delete_context_evaluation,
    load_corrections,
    save_corrections
)
from keyvault_config import get_keyvault_config

app = Flask(__name__, template_folder='templates/admin')
app.config['SECRET_KEY'] = os.urandom(24)

# Initialize services
kv_config = get_keyvault_config()

# Health history file path
HEALTH_HISTORY_FILE = 'cache/health_history.json'

def load_health_history():
    """Load health check history from file"""
    if os.path.exists(HEALTH_HISTORY_FILE):
        try:
            with open(HEALTH_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_health_history(history):
    """Save health check history to file"""
    os.makedirs('cache', exist_ok=True)
    with open(HEALTH_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def add_health_check(service_name, status, response_time=None):
    """Add a health check entry"""
    history = load_health_history()
    history.append({
        'timestamp': datetime.now().isoformat(),
        'service': service_name,
        'status': status,
        'response_time': response_time
    })
    
    # Keep only last 24 hours of data
    cutoff = datetime.now() - timedelta(hours=24)
    history = [h for h in history if datetime.fromisoformat(h['timestamp']) > cutoff]
    
    save_health_history(history)


# Application Insights Integration
try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    from opencensus.ext.flask.flask_middleware import FlaskMiddleware
    import logging
    
    config = kv_config.get_config()
    app_insights_key = config.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    
    if app_insights_key:
        # Add Azure logging handler
        logger = logging.getLogger(__name__)
        logger.addHandler(AzureLogHandler(connection_string=app_insights_key))
        logger.setLevel(logging.INFO)
        
        # Add request tracking
        middleware = FlaskMiddleware(app, exporter=None)
        
        print("✅ Application Insights telemetry enabled")
        TELEMETRY_ENABLED = True
    else:
        print("⚠️  Application Insights not configured")
        TELEMETRY_ENABLED = False
except ImportError:
    print("⚠️  opencensus-ext-azure not installed - telemetry disabled")
    TELEMETRY_ENABLED = False
except Exception as e:
    print(f"⚠️  Application Insights setup failed: {e}")
    TELEMETRY_ENABLED = False

# TODO: Add authentication middleware here
# @app.before_request
# def check_authentication():
#     if not session.get('admin_authenticated'):
#         return redirect(url_for('login'))


# Background health checker
def background_health_checker():
    """Background thread that checks service health every 5 minutes"""
    services = {
        'api-gateway': 'http://localhost:8000/health',
        'context-analyzer': 'http://localhost:8001/health',
        'search-service': 'http://localhost:8002/health',
        'enhanced-matching': 'http://localhost:8003/health',
        'uat-management': 'http://localhost:8004/health',
        'llm-classifier': 'http://localhost:8005/health',
        'embedding-service': 'http://localhost:8006/health',
        'vector-search': 'http://localhost:8007/health'
    }
    
    while True:
        for service_name, url in services.items():
            try:
                response = requests.get(url, timeout=2)
                status = 'up' if response.status_code == 200 else 'down'
                response_time = response.elapsed.total_seconds() * 1000
                add_health_check(service_name, status, response_time)
            except:
                add_health_check(service_name, 'down', None)
        
        # Sleep for 5 minutes
        time.sleep(300)

# Start background health checker
health_checker_thread = threading.Thread(target=background_health_checker, daemon=True)
health_checker_thread.start()


@app.route('/')
def index():
    """Admin home page - Dashboard"""
    stats = get_evaluation_statistics()
    return render_template('dashboard.html', stats=stats)


@app.route('/evaluations')
def evaluations_list():
    """List all evaluations with search"""
    # Get filter parameters
    search_query = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Load all evaluations
    evaluations = load_context_evaluations()
    
    # DEBUG: Log evaluation data structure
    if evaluations:
        print(f"\n🔍 DEBUG: Found {len(evaluations)} evaluations")
        print(f"🔍 DEBUG: First evaluation keys: {list(evaluations[0].keys())}")
        print(f"🔍 DEBUG: First evaluation data:")
        for key, value in evaluations[0].items():
            if isinstance(value, dict):
                print(f"  {key}: {type(value).__name__} with keys {list(value.keys())}")
            elif isinstance(value, list):
                print(f"  {key}: {type(value).__name__} with {len(value)} items")
            else:
                print(f"  {key}: {repr(value)[:100]}")
    else:
        print("\n⚠️ DEBUG: No evaluations found!")
    
    # Apply search filter
    filtered = filter_evaluations(
        evaluations, 
        search_query=search_query
    )
    
    # Pagination
    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered[start:end]
    
    # Calculate pagination info
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        'evaluations_list.html',
        evaluations=paginated,
        search_query=search_query,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages
    )


@app.route('/evaluations/viewer')
def evaluation_viewer():
    """Interactive evaluation viewer with navigation"""
    eval_id = request.args.get('id')
    search_query = request.args.get('search', '').strip()
    
    # Load all evaluations
    evaluations = load_context_evaluations()
    
    # Apply filters to get the working set
    filtered = filter_evaluations(
        evaluations,
        search_query=search_query
    )
    
    if not filtered:
        return render_template('evaluation_viewer.html', 
                             evaluation=None, 
                             error="No evaluations found")
    
    # Find current evaluation
    current_idx = 0
    current_eval = None
    
    if eval_id:
        for idx, evaluation in enumerate(filtered):
            eval_key = evaluation.get('evaluation_id') or evaluation.get('id')
            if eval_key == eval_id:
                current_idx = idx
                current_eval = evaluation
                break
    
    # If not found or no ID provided, show first
    if current_eval is None:
        current_eval = filtered[0]
        current_idx = 0
    
    # Get prev/next evaluation IDs
    prev_id = filtered[current_idx - 1].get('evaluation_id') or filtered[current_idx - 1].get('id') if current_idx > 0 else None
    next_id = filtered[current_idx + 1].get('evaluation_id') or filtered[current_idx + 1].get('id') if current_idx < len(filtered) - 1 else None
    
    return render_template(
        'evaluation_viewer.html',
        evaluation=current_eval,
        current_index=current_idx + 1,
        total_count=len(filtered),
        prev_id=prev_id,
        next_id=next_id,
        search_query=search_query
    )


@app.route('/evaluations/<eval_id>/detail')
def evaluation_detail_view(eval_id: str):
    """View single evaluation details (old route for backwards compatibility)"""
    evaluations = load_context_evaluations()
    
    evaluation = next(
        (e for e in evaluations if e.get('evaluation_id') == eval_id),
        None
    )
    
    if not evaluation:
        return render_template('evaluation_viewer.html', 
                             evaluation=None,
                             error=f"Evaluation {eval_id} not found")
    
    # Extract data for display
    context = evaluation.get('context_analysis', {})
    user_input = evaluation.get('user_input', {})
    search_results = evaluation.get('search_results', {})
    
    return render_template(
        'evaluation_detail.html',
        evaluation_id=eval_id,
        evaluation=evaluation,
        context=context,
        user_input=user_input,
        search_results=search_results,
        original_title=user_input.get('issue_title', ''),
        original_description=user_input.get('issue_description', ''),
        original_impact=user_input.get('impact', ''),
        detected_category=evaluation.get('detected_category', context.get('category', 'Unknown')),
        user_approved=evaluation.get('user_approved', False)
    )



@app.route('/evaluations/<eval_id>/delete', methods=['POST'])
def delete_evaluation(eval_id):
    """Delete an evaluation"""
    from blob_storage_helper import delete_context_evaluation
    
    success = delete_context_evaluation(eval_id)
    
    if success:
        return jsonify({'success': True, 'message': f'Evaluation {eval_id} deleted successfully'})
    else:
        return jsonify({'success': False, 'message': f'Failed to delete evaluation {eval_id}'}), 404


@app.route('/api/evaluations/search')
def api_search_evaluations():
    """API endpoint for searching evaluations"""
    query = request.args.get('q', '').strip()
    status = request.args.get('status', 'all')
    
    evaluations = load_context_evaluations()
    filtered = filter_evaluations(evaluations, search_query=query, status_filter=status)
    
    # Return simplified list for API
    results = [
        {
            'evaluation_id': e.get('evaluation_id'),
            'timestamp': e.get('timestamp'),
            'user_approved': e.get('user_approved'),
            'category': e.get('detected_category'),
            'uat_numbers': e.get('suggested_uats', [])[:3],  # First 3
            'title': e.get('user_input', {}).get('issue_title', '')[:100]
        }
        for e in filtered
    ]
    
    return jsonify({'results': results, 'count': len(results)})


@app.route('/api/evaluations/export')
def api_export_evaluations():
    """Export evaluations as JSON"""
    search_query = request.args.get('search', '').strip()
    status = request.args.get('status', 'all')
    
    evaluations = load_context_evaluations()
    filtered = filter_evaluations(evaluations, search_query=query, status_filter=status)
    
    return jsonify({
        'export_date': datetime.now().isoformat(),
        'count': len(filtered),
        'evaluations': filtered
    })


def filter_evaluations(
    evaluations: List[Dict[str, Any]], 
    search_query: str = ''
) -> List[Dict[str, Any]]:
    """Filter evaluations based on search query"""
    filtered = evaluations
    
    # Filter by search query
    if search_query:
        query_lower = search_query.lower()
        filtered = [
            e for e in filtered
            if matches_search_query(e, query_lower)
        ]
    
    # Sort by timestamp (newest first)
    filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return filtered


def matches_search_query(evaluation: Dict[str, Any], query: str) -> bool:
    """Check if evaluation matches search query"""
    # Search in UAT numbers
    suggested_uats = evaluation.get('suggested_uats', [])
    for uat in suggested_uats:
        if query in uat.lower():
            return True
    
    # Search in user input
    user_input = evaluation.get('user_input', {})
    if query in user_input.get('issue_title', '').lower():
        return True
    if query in user_input.get('issue_description', '').lower():
        return True
    if query in user_input.get('expected_behavior', '').lower():
        return True
    
    # Search in category
    if query in evaluation.get('detected_category', '').lower():
        return True
    
    # Search in feature
    if query in evaluation.get('detected_feature', '').lower():
        return True
    
    # Search in evaluation ID
    if query in evaluation.get('evaluation_id', '').lower():
        return True
    
    return False


def get_evaluation_statistics() -> Dict[str, Any]:
    """Calculate statistics from evaluations"""
    evaluations = load_context_evaluations()
    
    total = len(evaluations)
    
    # Category breakdown
    category_counts = {}
    for e in evaluations:
        cat = e.get('detected_category', 'Unknown')
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Recent activity (last 7 days)
    from datetime import timedelta
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent = [e for e in evaluations if e.get('timestamp', '') > seven_days_ago]
    
    # Get corrections count
    try:
        corrections_data = load_corrections()
        corrections_count = len(corrections_data.get('corrections', []))
    except:
        corrections_count = 0
    
    # Check service health
    service_health = check_services_health()
    
    return {
        'total': total,
        'corrections_count': corrections_count,
        'category_breakdown': category_counts,
        'recent_count': len(recent),
        'service_health': service_health,
        'services_healthy': service_health.get('all_healthy', False),
        'healthy_services_count': service_health.get('healthy_count', 0),
        'total_services_count': service_health.get('total_count', 0)
    }


def check_services_health() -> Dict[str, Any]:
    """Check health of all microservices"""
    services = {
        'main-app': 'http://localhost:5003/health',
        'api-gateway': 'http://localhost:8000/health',
        'context-analyzer': 'http://localhost:8001/health',
        'search-service': 'http://localhost:8002/health',
        'enhanced-matching': 'http://localhost:8003/health',
        'uat-management': 'http://localhost:8004/health',
        'llm-classifier': 'http://localhost:8005/health',
        'embedding-service': 'http://localhost:8006/health',
        'vector-search': 'http://localhost:8007/health',
    }
    
    results = {}
    healthy_count = 0
    
    for name, url in services.items():
        try:
            response = requests.get(url, timeout=2)
            is_healthy = response.status_code == 200
            results[name] = {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'response_time': int(response.elapsed.total_seconds() * 1000)  # Convert to ms as int
            }
            if is_healthy:
                healthy_count += 1
        except Exception as e:
            results[name] = {
                'status': 'down',
                'error': str(e)
            }
    
    return {
        'services': results,
        'healthy_count': healthy_count,
        'total_count': len(services),
        'all_healthy': healthy_count == len(services)
    }


@app.route('/corrections')
def corrections_list():
    """View all corrections"""
    corrections_data = load_corrections()
    corrections = corrections_data.get('corrections', [])
    
    # Calculate stats
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent_count = sum(1 for c in corrections if c.get('timestamp', '') > seven_days_ago)
    
    categories = set()
    for c in corrections:
        if c.get('correct_category'):
            categories.add(c.get('correct_category'))
    
    return render_template(
        'corrections_list.html',
        corrections=corrections,
        recent_count=recent_count,
        categories_count=len(categories)
    )


@app.route('/corrections/<int:index>/delete', methods=['POST'])
def delete_correction(index):
    """Delete a correction"""
    try:
        corrections_data = load_corrections()
        corrections = corrections_data.get('corrections', [])
        
        if 0 <= index < len(corrections):
            deleted = corrections.pop(index)
            corrections_data['corrections'] = corrections
            
            success = save_corrections(corrections_data)
            if success:
                return jsonify({'success': True, 'message': f'Correction deleted successfully'})
            else:
                return jsonify({'success': False, 'message': 'Failed to save changes'}), 500
        else:
            return jsonify({'success': False, 'message': 'Invalid index'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/health-dashboard')
def health_dashboard():
    """Service health monitoring dashboard"""
    return render_template('health.html')


@app.route('/api/services/health')
def get_services_health():
    """Get current health status of all services"""
    health_status = check_services_health()
    return jsonify(health_status)


@app.route('/api/services/<service_name>/restart', methods=['POST'])
def restart_service(service_name):
    """Restart a specific microservice using PowerShell"""
    import subprocess
    import os
    
    # Map service names to their startup scripts
    service_scripts = {
        'main-app': 'start_main_app.ps1',
        'api-gateway': 'start_gateway.ps1',
        'context-analyzer': 'agents/context-analyzer/start.ps1',
        'search-service': 'agents/search-service/start.ps1',
        'enhanced-matching': 'agents/enhanced-matching/start.ps1',
        'uat-management': 'agents/uat-management/start.ps1',
        'llm-classifier': 'agents/llm-classifier/start.ps1',
        'embedding-service': 'agents/embedding-service/start.ps1',
        'vector-search': 'agents/vector-search/start.ps1'
    }
    
    if service_name not in service_scripts:
        return jsonify({'success': False, 'error': 'Unknown service'}), 400
    
    try:
        # Get the project root directory
        project_root = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(project_root, service_scripts[service_name])
        
        if not os.path.exists(script_path):
            return jsonify({'success': False, 'error': f'Script not found: {script_path}'}), 404
        
        # Kill existing process on the service port
        ports = {
            'main-app': 5003,
            'api-gateway': 8000,
            'context-analyzer': 8001,
            'search-service': 8002,
            'enhanced-matching': 8003,
            'uat-management': 8004,
            'llm-classifier': 8005,
            'embedding-service': 8006,
            'vector-search': 8007
        }
        
        port = ports.get(service_name)
        if port:
            # Kill process using the port
            kill_cmd = f'Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }}'
            subprocess.run(['powershell', '-Command', kill_cmd], capture_output=True)
        
        # Start the service in a new PowerShell window
        start_cmd = f'Start-Process powershell -ArgumentList "-NoExit", "-File", "{script_path}"'
        result = subprocess.run(['powershell', '-Command', start_cmd], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': f'{service_name} restart initiated'})
        else:
            return jsonify({'success': False, 'error': result.stderr}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'success': True, 'message': f'{service_name} restart initiated (async)'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# AZURE KEY VAULT STATUS MONITORING
# =============================================================================

@app.route('/api/keyvault/status')
def get_keyvault_status():
    """
    AZURE KEY VAULT CONNECTION STATUS ENDPOINT
    
    Purpose:
        - Monitors Azure Key Vault connection health
        - Displays authentication method and status
        - Tracks cached secrets count
        - Provides visibility into secrets source
    
    Status Indicators:
        enabled:    Key Vault client initialized
        connected:  Successfully verified Key Vault access
        
    Authentication Methods:
        1. Managed Identity - Production deployments
           Uses AZURE_CLIENT_ID environment variable
           Automatically authenticated via Azure resources
           
        2. DefaultAzureCredential - Local development
           Interactive browser authentication
           Falls back to Azure CLI, VS Code, etc.
           
        3. Environment Variables - Fallback mode
           Reading from .env files directly
           No Key Vault connection active
    
    Response Format:
        {
            "enabled": bool,           # Key Vault client exists
            "connected": bool,         # Connection verified
            "vault_uri": string,       # Key Vault URL
            "auth_method": string,     # Authentication type
            "cached_secrets": int,     # Number of cached values
            "last_checked": timestamp  # Check time
        }
    
    Dashboard Integration:
        - Status card on Admin Dashboard (main page)
        - Status card on Service Health Dashboard
        - Auto-refreshes every 60 seconds
        - Color-coded: Green (connected), Red (disconnected)
    
    Implementation Notes:
        - Always returns HTTP 200 (even on errors)
        - Non-blocking verification check
        - Tests actual secret retrieval for verification
        - Safe to call frequently (uses cached values)
    
    Error Handling:
        - Catches all exceptions gracefully
        - Returns error message in response
        - Never throws exceptions to frontend
    
    Added: 2026-01-26 - Key Vault visibility enhancement
    Related: KEYVAULT_MIGRATION_COMPLETE.md
    """
    try:
        kv = get_keyvault_config()
        
        # Check if Key Vault client is initialized
        is_connected = kv._client is not None
        
        # Try to get the client (which will attempt connection)
        if not is_connected:
            client = kv._get_client()
            is_connected = client is not None
        
        # Determine authentication method
        auth_method = "Not Connected"
        if is_connected:
            managed_identity_client_id = os.environ.get('AZURE_CLIENT_ID')
            if managed_identity_client_id:
                auth_method = f"Managed Identity (Client ID: {managed_identity_client_id[:8]}...)"
            else:
                auth_method = "DefaultAzureCredential (Interactive)"
        
        # Count cached secrets
        cached_secrets = len(kv._cache)
        
        # Try to get a test secret to verify connection
        connection_verified = False
        if is_connected:
            try:
                # Try to get storage account name as test
                test_secret = kv.get_secret("AZURE_STORAGE_ACCOUNT_NAME", fallback_to_env=False)
                connection_verified = test_secret is not None
            except:
                connection_verified = False
        
        return jsonify({
            'enabled': is_connected,
            'connected': connection_verified,
            'vault_uri': kv_config._client.vault_url if kv_config._client else "https://kv-gcs-dev-gg4a6y.vault.azure.net/",
            'auth_method': auth_method,
            'cached_secrets': cached_secrets,
            'last_checked': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'enabled': False,
            'connected': False,
            'error': str(e),
            'last_checked': datetime.now().isoformat()
        }), 200  # Return 200 to avoid errors on frontend


@app.route('/api/services/uptime')
def get_services_uptime():
    """Get uptime statistics for all services over the last 24 hours"""
    history = load_health_history()
    
    if not history:
        return jsonify({'services': {}, 'message': 'No health data available yet'})
    
    # Calculate uptime for each service
    services_stats = {}
    service_names = set(entry['service'] for entry in history)
    
    for service_name in service_names:
        service_history = [h for h in history if h['service'] == service_name]
        
        if not service_history:
            continue
        
        # Count up vs down
        up_count = sum(1 for h in service_history if h['status'] == 'up')
        down_count = sum(1 for h in service_history if h['status'] == 'down')
        total_checks = up_count + down_count
        
        # Calculate uptime percentage
        uptime_percentage = (up_count / total_checks * 100) if total_checks > 0 else 0
        
        # Calculate average response time
        response_times = [h['response_time'] for h in service_history if h.get('response_time') is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else None
        
        # Calculate downtime minutes (assuming 5-minute check intervals)
        downtime_minutes = down_count * 5
        
        services_stats[service_name] = {
            'uptime_percentage': round(uptime_percentage, 2),
            'downtime_minutes': downtime_minutes,
            'total_checks': total_checks,
            'up_count': up_count,
            'down_count': down_count,
            'avg_response_time': round(avg_response_time, 2) if avg_response_time else None
        }
    
    return jsonify({
        'services': services_stats,
        'period_hours': 24,
        'last_updated': datetime.now().isoformat()
    })


@app.route('/logs')
def logs_viewer():
    """View application logs from Azure Log Analytics"""
    config = kv_config.get_config()
    logs_enabled = bool(config.get('AZURE_LOG_ANALYTICS_WORKSPACE_ID'))
    return render_template('logs.html', logs_enabled=logs_enabled)


if __name__ == '__main__':
    print("=" * 80)
    print("🔧 Admin Service Starting")
    print("=" * 80)
    print(f"Port: 8008")
    config = kv_config.get_config()
    print(f"Environment: {config.get('AZURE_OPENAI_ENDPOINT', 'Not configured')}")
    print(f"Storage: Azure Blob Storage (stgcsdevgg4a6y)")
    print("=" * 80)
    print("\nAdmin Routes:")
    print("  http://localhost:8008/                    - Admin Dashboard")
    print("  http://localhost:8008/evaluations         - Evaluations List")
    print("  http://localhost:8008/evaluations/viewer  - Interactive Viewer")
    print("  http://localhost:8008/corrections         - Corrections Database")
    print("  http://localhost:8008/health-dashboard    - Service Health Monitor")
    print("  http://localhost:8008/logs                - Application Logs Viewer")
    print("=" * 80)
    
    if TELEMETRY_ENABLED:
        print("\n✅ Telemetry & Monitoring:")
        print("  • Application Insights - Request tracking enabled")
        print("  • Azure Log Analytics - Log viewing available")
    else:
        print("\n⚠️  Telemetry disabled - install opencensus-ext-azure for full monitoring")
    
    print("=" * 80)
    
    app.run(host='0.0.0.0', port=8008, debug=True)
