from fastapi import APIRouter, Depends, HTTPException, status
from services.student_service import update_student_readiness
from services.crud_services import read_one, create, update, read_query
from core.security import allowed_users
from database.models import StudySessionLog, ProgressStatus, AnnouncementSchema
from datetime import datetime
from typing import List

router = APIRouter(prefix="/student", tags=["Student Analytics"])

@router.get("/profile/{user_id}")
async def get_student_profile(user_id: str, current_user: dict = Depends(allowed_users(["student", "teacher", "admin"]))):
    """
    Fetches the full student profile including AI-generated insights.
    """
    if current_user["role"] == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
        
    return profile

@router.post("/analyze-readiness/{user_id}")
async def analyze_readiness(user_id: str, current_user: dict = Depends(allowed_users(["student", "teacher"]))):
    """
    Triggers the ONNX AI Model to re-calculate the student's 'Personal Readiness Level'.
    """
    if current_user["role"] == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await update_student_readiness(user_id)
    return result

# =======================
# BEHAVIOR TRACKING (ADAPTABILITY)
# =======================

@router.post("/session/start")
async def start_study_session(
    log_data: dict, # resource_id, resource_type
    current_user: dict = Depends(allowed_users(["student"]))
):
    """
    Call this when a student opens a module or starts a quiz.
    """
    log_entry = StudySessionLog(
        user_id=current_user["uid"],
        resource_id=log_data.get("resource_id"),
        resource_type=log_data.get("resource_type"),
        start_time=datetime.utcnow(),
        completion_status=ProgressStatus.IN_PROGRESS
    )
    
    result = await create("study_logs", log_entry.model_dump())
    return {"session_id": result["id"], "message": "Tracking started"}

@router.post("/session/update/{session_id}")
async def update_study_session(
    session_id: str, 
    update_payload: dict, # interruptions, is_finished
    current_user: dict = Depends(allowed_users(["student"]))
):
    """
    Call this periodically or when finished.
    """
    updates = {
        "interruptions_count": update_payload.get("interruptions", 0),
        "updated_at": datetime.utcnow()
    }
    
    if update_payload.get("is_finished"):
        session_data = await read_one("study_logs", session_id)
        if session_data:
            start_time = session_data.get("start_time")
            # Ensure start_time is datetime object (Firestore returns it as such usually)
            # If it's a string/timestamp, convert it. Simplified here:
            if start_time:
                # Firestore returns datetime with timezone info usually
                start_dt = start_time.replace(tzinfo=None) if hasattr(start_time, 'replace') else start_time
                duration = (datetime.utcnow() - start_dt).total_seconds()
                updates["end_time"] = datetime.utcnow()
                updates["duration_seconds"] = duration
                updates["completion_status"] = ProgressStatus.COMPLETED
            
            # TRIGGER ADAPTABILITY UPDATE HERE
            # await update_student_readiness(current_user["uid"])
    
    await update("study_logs", session_id, updates)
    return {"message": "Session updated"}

# =======================
# ANNOUNCEMENTS
# =======================

@router.get("/announcements", response_model=List[AnnouncementSchema])
async def get_my_announcements(current_user: dict = Depends(allowed_users(["student", "teacher", "admin"]))):
    """
    Fetch announcements. For now, returns global announcements.
    """
    # Ideally filter by role target_audience here
    global_anns = await read_query("announcements", [("is_global", "==", True)])
    return global_anns