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
    
    # [FIX] Force unverified status on update
    payload["is_verified"] = False
    payload["verified_at"] = None
    payload["verified_by"] = None

    await update("assessments", assessment_id, payload)
    return {"id": assessment_id, "message": "Updated successfully and marked for re-verification"}

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

# --- Submissions ---
@router.get("/submissions", response_model=List[Dict[str, Any]])
async def list_submissions(
    user_id: Optional[str] = None,
    assessment_id: Optional[str] = None,
    module_id: Optional[str] = None,
    subject_id: Optional[str] = None,
):
    filters = []
    if user_id:
        filters.append(("user_id", "==", user_id))
    if assessment_id:
        filters.append(("assessment_id", "==", assessment_id))
    if module_id:
        filters.append(("module_id", "==", module_id))
    if subject_id:
        filters.append(("subject_id", "==", subject_id))

    items = await read_query("assessment_submissions", filters)
    results: List[Dict[str, Any]] = []
    for s in items:
        data = s["data"]
        data["id"] = s["id"]
        results.append(data)
    return results

def _normalize_submission_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    answers = data.get("answers") or []
    if isinstance(answers, list) and "score" not in data:
        try:
            data["score"] = sum(1 for a in answers if a.get("is_correct"))
        except Exception:
            data["score"] = 0
    data["created_at"] = datetime.utcnow()
    return data

@router.post("/submit", response_model=Dict[str, Any])
async def submit_assessment(payload: Dict[str, Any] = Body(...)):
    data = _normalize_submission_payload(payload)
    doc_id = str(uuid.uuid4())
    await create("assessment_submissions", data, doc_id=doc_id)
    return {"id": doc_id, "message": "Submission recorded"}

@router.post("/submissions", response_model=Dict[str, Any])
async def create_submission(payload: Dict[str, Any] = Body(...)):
    data = _normalize_submission_payload(payload)
    doc_id = str(uuid.uuid4())
    await create("assessment_submissions", data, doc_id=doc_id)
    return {"id": doc_id, "message": "Submission recorded"}
