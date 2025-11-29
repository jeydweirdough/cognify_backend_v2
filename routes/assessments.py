from fastapi import APIRouter, Depends, HTTPException, Query, Body
from database.models import AssessmentBlueprintSchema, AssessmentSchema, AssessmentType
from services.assessment_generator import generate_assessment_from_blueprint
from services.crud_services import read_all, read_one, delete, update, create
from core.security import verify_firebase_token, allowed_users
from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

router = APIRouter(prefix="/assessments", tags=["Assessment Generation"])

# --- Input Models ---
class AssessmentCreateRequest(BaseModel):
    title: str
    subject_id: Optional[str] = "general"
    purpose: Optional[str] = "Quiz" # Matches frontend 'purpose'
    description: Optional[str] = None
    module_id: Optional[str] = None
    questions: List[Dict] = []
    total_items: int = 0
    bloom_levels: List[str] = []
    is_verified: bool = False

class AssessmentUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    purpose: Optional[str] = None
    subject_id: Optional[str] = None
    module_id: Optional[str] = None
    questions: Optional[List[Dict]] = None
    total_items: Optional[int] = None
    bloom_levels: Optional[List[str]] = None
    is_verified: Optional[bool] = None

# --- Routes ---

@router.get("/", summary="Get all assessments")
async def list_assessments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    current_user: dict = Depends(verify_firebase_token)
):
    assessments = await read_all("assessments", limit, skip)
    return {"items": assessments, "total": len(assessments)}

@router.get("/{assessment_id}", summary="Get assessment by ID")
async def get_assessment(
    assessment_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    assessment = await read_one("assessments", assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment

# [FIX] Added Manual Create Route
@router.post("/", summary="Create Assessment Manually")
async def create_assessment_manual(
    assessment_data: AssessmentCreateRequest,
    current_user: dict = Depends(allowed_users(["teacher", "admin", "faculty_member"]))
):
    data = assessment_data.model_dump()
    data["created_by"] = current_user["uid"]
    data["created_at"] = datetime.utcnow()
    # Ensure type exists for DB consistency, default to purpose or 'Quiz'
    if "type" not in data: 
        data["type"] = data.get("purpose", "Quiz")
        
    new_record = await create("assessments", data)
    return new_record

# [FIX] Added Update Route
@router.put("/{assessment_id}", summary="Update Assessment")
async def update_assessment(
    assessment_id: str,
    updates: AssessmentUpdateRequest,
    current_user: dict = Depends(allowed_users(["teacher", "admin", "faculty_member"]))
):
    # Filter out None values
    data = {k: v for k, v in updates.model_dump().items() if v is not None}
    
    if not data:
         raise HTTPException(status_code=400, detail="No fields to update")
         
    data["updated_at"] = datetime.utcnow()
    data["updated_by"] = current_user["uid"]
    
    await update("assessments", assessment_id, data)
    return {"message": "Assessment updated successfully"}

@router.delete("/{assessment_id}")
async def delete_assessment(
    assessment_id: str,
    current_user: dict = Depends(allowed_users(["teacher", "admin", "faculty_member"]))
):
    await delete("assessments", assessment_id)
    return {"status": "success"}

# --- Verification Routes ---
@router.post("/{assessment_id}/verify")
async def verify_assessment(
    assessment_id: str,
    current_user: dict = Depends(allowed_users(["admin"]))
):
    await update("assessments", assessment_id, {
        "is_verified": True,
        "is_rejected": False,
        "verified_at": datetime.utcnow(),
        "verified_by": current_user["uid"]
    })
    return {"message": "Assessment verified"}

@router.post("/{assessment_id}/reject")
async def reject_assessment(
    assessment_id: str,
    reason: str = Query(...),
    current_user: dict = Depends(allowed_users(["admin"]))
):
    await update("assessments", assessment_id, {
        "is_verified": False,
        "is_rejected": True,
        "rejection_reason": reason,
        "rejected_at": datetime.utcnow(),
        "rejected_by": current_user["uid"]
    })
    return {"message": "Assessment rejected"}

@router.post("/generate", response_model=AssessmentSchema)
async def create_assessment_ai(
    blueprint: AssessmentBlueprintSchema, 
    title: str, 
    assessment_type: AssessmentType,
    current_user: dict = Depends(allowed_users(["teacher", "admin", "faculty_member"]))
):
    new_assessment = await generate_assessment_from_blueprint(
        blueprint=blueprint, 
        title=title, 
        assessment_type=assessment_type
    )
    return new_assessment