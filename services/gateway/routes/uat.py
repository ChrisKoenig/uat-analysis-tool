"""
UAT (Unified Action Tracker) API Routes
Phase 7: Routes requests to UAT Management microservice (port 8004)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# UAT Management service URL
UAT_SERVICE_URL = "http://localhost:8004"

# Request/Response Models
class CreateUATRequest(BaseModel):
    """Request for creating a UAT"""
    title: str
    description: str
    impact: Optional[str] = ""
    category: Optional[str] = "feature_request"
    intent: Optional[str] = "new_feature"
    classification_reason: Optional[str] = ""
    selected_features: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    selected_uats: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    opportunity_id: Optional[str] = ""
    milestone_id: Optional[str] = ""

@router.post("/create")
async def create_uat(request: CreateUATRequest):
    """
    Create a new UAT work item in Azure DevOps.
    Routes to UAT Management service.
    """
    try:
        logger.info(f"🔄 Routing UAT creation to UAT Management service...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{UAT_SERVICE_URL}/create",
                json=request.dict()
            )
            response.raise_for_status()
            result = response.json()
            
        work_item_id = result.get('work_item_id', 'N/A')
        logger.info(f"✅ UAT created: #{work_item_id}")
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"❌ UAT Management service error: {e}")
        raise HTTPException(status_code=503, detail=f"UAT Management service unavailable: {str(e)}")

@router.get("/list")
async def list_uats(
    state: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List UAT work items with optional filters.
    Routes to UAT Management service.
    """
    try:
        logger.info(f"🔄 Routing UAT list to UAT Management service...")
        
        params = {"limit": limit}
        if state:
            params["state"] = state
        if assigned_to:
            params["assigned_to"] = assigned_to
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{UAT_SERVICE_URL}/list",
                params=params
            )
            response.raise_for_status()
            result = response.json()
            
        total = result.get('total', 0)
        logger.info(f"✅ Listed {total} UATs")
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"❌ UAT Management service error: {e}")
        raise HTTPException(status_code=503, detail=f"UAT Management service unavailable: {str(e)}")

@router.get("/{work_item_id}")
async def get_uat(work_item_id: int):
    """
    Retrieve UAT work item by ID.
    Routes to UAT Management service.
    """
    try:
        logger.info(f"🔄 Routing UAT retrieval to UAT Management service...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{UAT_SERVICE_URL}/{work_item_id}"
            )
            response.raise_for_status()
            result = response.json()
            
        logger.info(f"✅ Retrieved UAT #{work_item_id}")
        return result
        
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ UAT Management service error: {e}")
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Work item {work_item_id} not found")
        raise HTTPException(status_code=503, detail=f"UAT Management service unavailable: {str(e)}")

@router.put("/{work_item_id}")
async def update_uat(work_item_id: int, updates: Dict[str, Any]):
    """
    Update existing UAT work item.
    Routes to UAT Management service.
    """
    try:
        logger.info(f"🔄 Routing UAT update to UAT Management service...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{UAT_SERVICE_URL}/{work_item_id}",
                json=updates
            )
            response.raise_for_status()
            result = response.json()
            
        logger.info(f"✅ Updated UAT #{work_item_id}")
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"❌ UAT Management service error: {e}")
        raise HTTPException(status_code=503, detail=f"UAT Management service unavailable: {str(e)}")
