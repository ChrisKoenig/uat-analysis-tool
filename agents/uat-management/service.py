"""
UAT Management Service - Microservice Wrapper
v1.0 - Phase 7: Microservices Transformation

Microservice for User Acceptance Testing (UAT) management.
Provides endpoints for:
- Creating UAT work items in Azure DevOps
- Retrieving UAT details
- Listing UATs with filters
- Updating UAT work items
- Managing UAT lifecycle

Port: 8004
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import ADO integration
from services.ado_integration import AzureDevOpsClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="UAT Management Service",
    description="User Acceptance Testing management and Azure DevOps integration",
    version="1.0.0"
)

# Enable CORS for API Gateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],  # API Gateway
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class CreateUATRequest(BaseModel):
    """Request for creating a UAT work item"""
    title: str = Field(..., description="UAT title")
    description: str = Field(..., description="Detailed description")
    impact: Optional[str] = Field("", description="Business impact")
    category: Optional[str] = Field("feature_request", description="Issue category")
    intent: Optional[str] = Field("new_feature", description="User intent")
    classification_reason: Optional[str] = Field("", description="AI classification reasoning")
    selected_features: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Related features")
    selected_uats: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Related UATs")
    opportunity_id: Optional[str] = Field("", description="Opportunity ID")
    milestone_id: Optional[str] = Field("", description="Milestone ID")

class UATResponse(BaseModel):
    """Response with UAT work item details"""
    success: bool
    work_item_id: Optional[int] = None
    url: Optional[str] = None
    title: Optional[str] = None
    state: Optional[str] = None
    assigned_to: Optional[str] = None
    error: Optional[str] = None

class UATListItem(BaseModel):
    """UAT list item"""
    id: int
    title: str
    state: str
    created_date: str
    assigned_to: Optional[str] = None

class UATListResponse(BaseModel):
    """Response with list of UATs"""
    uats: List[UATListItem]
    total: int
    filters: Dict[str, Any]

# Global ADO client (lazy initialization)
ado_client = None

def get_ado_client():
    """Get or create Azure DevOps client (lazy initialization)"""
    global ado_client
    if ado_client is None:
        logger.info("Initializing Azure DevOps client...")
        ado_client = AzureDevOpsClient()
        logger.info("Azure DevOps client authenticated")
    return ado_client

@app.on_event("startup")
async def startup_event():
    """Initialize the UAT management service on startup"""
    logger.info("UAT Management Service starting up...")
    logger.info("Service initialized (authentication will occur on first API call)")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "uat-management",
        "version": "1.0.0",
        "ado_client": ado_client is not None
    }

@app.get("/info")
async def service_info():
    """Get service information and capabilities"""
    return {
        "name": "UAT Management Service",
        "version": "1.0.0",
        "description": "User Acceptance Testing management and Azure DevOps integration",
        "port": 8004,
        "endpoints": {
            "create": "POST /create - Create UAT work item in Azure DevOps",
            "get": "GET /{work_item_id} - Retrieve UAT details",
            "list": "GET /list - List UATs with optional filters",
            "update": "PUT /{work_item_id} - Update UAT work item",
            "health": "GET /health - Health check",
            "info": "GET /info - Service information"
        },
        "capabilities": {
            "azure_devops_integration": True,
            "work_item_creation": True,
            "work_item_updates": True,
            "work_item_queries": True,
            "authentication_cached": True
        }
    }

@app.post("/create", response_model=UATResponse)
async def create_uat(request: CreateUATRequest):
    """
    Create a UAT work item in Azure DevOps.
    
    Creates a new Action work item in the UAT project with complete
    issue information including classification, selected features/UATs,
    and business context (opportunity ID, milestone ID).
    """
    if ado_client is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Creating UAT: {request.title[:50]}...")
        
        # Prepare issue data for ADO client
        full_issue_data = {
            'title': request.title,
            'description': request.description,
            'impact': request.impact or "",
            'category': request.category or "feature_request",
            'intent': request.intent or "new_feature",
            'classification_reason': request.classification_reason or "",
            'selected_features': request.selected_features or [],
            'selected_uats': request.selected_uats or [],
            'opportunity_id': request.opportunity_id or "",
            'milestone_id': request.milestone_id or ""
        }
        
        # Create work item via ADO client
        result = get_ado_client().create_work_item_from_issue(full_issue_data)
        
        if result.get('success'):
            logger.info(f"UAT created: #{result.get('work_item_id')} - {result.get('title')[:50]}")
            return UATResponse(
                success=True,
                work_item_id=result.get('work_item_id'),
                url=result.get('url'),
                title=result.get('title'),
                state=result.get('state'),
                assigned_to=result.get('assigned_to')
            )
        else:
            logger.error(f"[ERROR] UAT creation failed: {result.get('error')}")
            return UATResponse(
                success=False,
                error=result.get('error', 'Failed to create work item')
            )
        
    except Exception as e:
        logger.error(f"[ERROR] Error creating UAT: {e}")
        raise HTTPException(status_code=500, detail=f"UAT creation failed: {str(e)}")

@app.get("/list", response_model=UATListResponse)
async def list_uats(
    state: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List UAT work items with optional filters.
    
    Queries Azure DevOps for Action work items in the UAT project,
    with support for filtering by state, assignee, and result limits.
    """
    if ado_client is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Listing UATs (state={state}, assigned_to={assigned_to}, limit={limit})...")
        
        # Query work items via ADO client
        work_items = get_ado_client().query_work_items(
            work_item_type="Actions",
            state=state,
            assigned_to=assigned_to,
            max_results=limit
        )
        
        # Convert to response format
        uat_list = []
        for wi in work_items:
            uat_list.append(UATListItem(
                id=wi['id'],
                title=wi['fields']['System.Title'],
                state=wi['fields']['System.State'],
                created_date=wi['fields']['System.CreatedDate'],
                assigned_to=wi['fields'].get('System.AssignedTo', {}).get('displayName')
            ))
        
        logger.info(f"Found {len(uat_list)} UATs")
        
        return UATListResponse(
            uats=uat_list,
            total=len(uat_list),
            filters={"state": state, "assigned_to": assigned_to, "limit": limit}
        )
        
    except Exception as e:
        logger.error(f"[ERROR] Error listing UATs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list UATs: {str(e)}")

@app.get("/{work_item_id}")
async def get_uat(work_item_id: int):
    """
    Retrieve UAT work item details by ID.
    
    Fetches complete work item information from Azure DevOps including
    title, description, state, assignments, and custom fields.
    """
    if ado_client is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Retrieving UAT #{work_item_id}...")
        
        # Get work item details via ADO client
        work_item = get_ado_client().get_work_item(work_item_id)
        
        if work_item and not work_item.get('error'):
            logger.info(f"Retrieved UAT #{work_item_id}")
            return work_item
        else:
            logger.warning(f"[WARN] UAT #{work_item_id} not found")
            raise HTTPException(status_code=404, detail=f"Work item {work_item_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Error retrieving UAT: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve UAT: {str(e)}")

@app.put("/{work_item_id}")
async def update_uat(work_item_id: int, updates: Dict[str, Any]):
    """
    Update UAT work item fields.
    
    Updates specified fields in the Azure DevOps work item.
    Supports updating title, description, state, assignments, and custom fields.
    """
    if ado_client is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Updating UAT #{work_item_id}...")
        
        # Update work item via ADO client
        result = get_ado_client().update_work_item(work_item_id, updates)
        
        if result.get('success'):
            logger.info(f"UAT #{work_item_id} updated successfully")
            return {
                "success": True,
                "work_item_id": work_item_id,
                "updated_fields": list(updates.keys())
            }
        else:
            logger.error(f"[ERROR] UAT update failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get('error', 'Failed to update work item')
            }
        
    except Exception as e:
        logger.error(f"[ERROR] Error updating UAT: {e}")
        raise HTTPException(status_code=500, detail=f"UAT update failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("UAT Management Service - Starting")
    print("="*80)
    print(f"Port: 8004")
    print(f"Features: UAT CRUD, Azure DevOps Integration")
    print(f"Operations: Create, Read, Update, List")
    print("="*80)
    
    uvicorn.run(app, host="0.0.0.0", port=8004)
