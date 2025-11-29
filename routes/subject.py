from fastapi import APIRouter, Depends, HTTPException, status, Query
from database.models import SubjectCreateRequest, SubjectUpdateRequest, TopicCreateRequest, TopicUpdateRequest, CompetencyUpdateRequest
from services.subject_service import (
    get_all_subjects, get_subject_by_id, get_subject_topics,
    get_topic_competencies, update_subject, create_subject,
    update_topic, update_competency, add_topic_to_subject,
    delete_topic_from_subject, get_subject_statistics
)
# [FIX] Import direct DB update as 'db_update' to avoid conflict with 'update_subject' service
from services.crud_services import update as db_update 
from services.profile_service import get_user_profile_with_role
from core.security import verify_firebase_token, allowed_users
from datetime import datetime

router = APIRouter(prefix="/subjects", tags=["Subjects & Curriculum"])

# ========================================
# VIEW SUBJECTS
# ========================================

@router.get("/", summary="Get all subjects")
async def list_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: dict = Depends(verify_firebase_token)
):
    _, role = await get_user_profile_with_role(current_user["uid"])
    subjects = await get_all_subjects(role, skip, limit)
    return {"total": len(subjects), "skip": skip, "limit": limit, "subjects": subjects}


@router.get("/{subject_id}", summary="Get subject by ID")
async def get_subject(
    subject_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    _, role = await get_user_profile_with_role(current_user["uid"])
    subject = await get_subject_by_id(subject_id, role)
    return subject

# ... (Existing topic/competency routes can remain as is) ...

# ========================================
# CREATE & UPDATE SUBJECTS
# ========================================

@router.post("/", summary="Create a new subject", status_code=status.HTTP_201_CREATED)
async def create_new_subject(
    subject_data: SubjectCreateRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    user_id, role = await get_user_profile_with_role(current_user["uid"])
    is_personal = role == "student"
    result = await create_subject(
        subject_data=subject_data.model_dump(), 
        requester_id=user_id, 
        requester_role=role,
        is_personal=is_personal
    )
    return result


@router.put("/{subject_id}", summary="Update subject")
async def update_subject_route(
    subject_id: str,
    updates: SubjectUpdateRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    _, role = await get_user_profile_with_role(current_user["uid"])
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    result = await update_subject(subject_id, update_data, role)
    return result

# ========================================
# VERIFICATION ENDPOINTS (NEW)
# ========================================

@router.post("/{subject_id}/verify")
async def verify_subject(
    subject_id: str,
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Approve a pending subject.
    """
    await db_update("subjects", subject_id, {
        "is_verified": True,
        "is_rejected": False,
        "verified_at": datetime.utcnow(),
        "verified_by": current_user["uid"]
    })
    return {"message": "Subject verified"}


@router.post("/{subject_id}/reject")
async def reject_subject(
    subject_id: str,
    reason: str = Query(...),
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Reject a pending subject with a reason.
    """
    await db_update("subjects", subject_id, {
        "is_verified": False,
        "is_rejected": True,
        "rejection_reason": reason,
        "rejected_at": datetime.utcnow(),
        "rejected_by": current_user["uid"]
    })
    return {"message": "Subject rejected"}