# routes/assessments.py
from fastapi import APIRouter, HTTPException, status, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from database.models import AssessmentSchema
from services.crud_services import create, read_one, update, delete, read_query

router = APIRouter(prefix="/assessments")

@router.get("/", response_model=List[Dict[str, Any]])
async def get_assessments(subject_id: Optional[str] = None):
    filters = []
    if subject_id:
        filters.append(("subject_id", "==", subject_id))
    assessments = await read_query("assessments", filters)
    results = []
    for a in assessments:
        data = a["data"]
        data["id"] = a["id"]
        results.append(data)
    return results

@router.get("/{assessment_id}", response_model=Dict[str, Any])
async def get_assessment(assessment_id: str):
    doc = await read_one("assessments", assessment_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")
    doc["id"] = assessment_id
    return doc

@router.post("/", response_model=Dict[str, Any])
async def create_assessment(payload: Dict[str, Any] = Body(...)):
    try:
        if "purpose" in payload and "type" not in payload:
            payload["type"] = payload["purpose"]
            
        doc_id = str(uuid.uuid4())
        payload["is_verified"] = False
        payload["created_at"] = datetime.utcnow()
        
        await create("assessments", payload, doc_id=doc_id)
        return {"id": doc_id, "message": "Assessment created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{assessment_id}")
async def update_assessment(assessment_id: str, payload: Dict[str, Any] = Body(...)):
    payload["updated_at"] = datetime.utcnow()
    await update("assessments", assessment_id, payload)
    return {"id": assessment_id, "message": "Updated successfully"}

# [FIX] Verify Endpoint
@router.post("/{assessment_id}/verify")
async def verify_assessment(assessment_id: str):
    doc = await read_one("assessments", assessment_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")

    update_data = {
        "is_verified": True,
        "verified_at": datetime.utcnow(),
        "verified_by": "admin",
        "updated_at": datetime.utcnow()
    }
    await update("assessments", assessment_id, update_data)
    return {"message": "Assessment verified", "id": assessment_id}

@router.delete("/{assessment_id}")
async def delete_assessment(assessment_id: str):
    await delete("assessments", assessment_id)
    return {"message": "Deleted successfully"}