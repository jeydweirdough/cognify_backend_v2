# routes/student.py
from fastapi import APIRouter, Depends, HTTPException, status
from services.student_service import update_student_readiness
from services.adaptability_service import (
    analyze_study_behavior,
    update_behavior_profile,
    get_adaptive_content
)
from services.crud_services import read_one, create, update, read_query
from services.profile_service import get_user_profile_with_role
from core.security import allowed_users
from database.models import StudySessionLog, AnnouncementSchema
from datetime import datetime
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/student", tags=["Student Analytics"])

@router.get("/profile/{user_id}")
async def get_student_profile(
    user_id: str, 
    current_user: dict = Depends(allowed_users(["student", "faculty_member", "admin"]))
):
    """
    Fetches the full student profile including AI-generated insights.
    """
    if current_user.get("role") == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
        
    return profile


@router.post("/analyze-readiness/{user_id}")
async def analyze_readiness(
    user_id: str, 
    current_user: dict = Depends(allowed_users(["student", "faculty_member"]))
):
    """
    Triggers the ONNX AI Model to re-calculate the student's 'Personal Readiness Level'.
    """
    if current_user.get("role") == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await update_student_readiness(user_id)
    return result


# =======================
# BEHAVIOR TRACKING (ADAPTABILITY)
# =======================

@router.post("/session/start")
async def start_study_session(
    resource_id: str,
    resource_type: str,
    current_user: dict = Depends(allowed_users(["student"]))
):
    """
    Call this when a student opens a module or starts a quiz.
    Tracks start time and initializes session.
    """
    log_entry = StudySessionLog(
        user_id=current_user["uid"],
        resource_id=resource_id,
        resource_type=resource_type,
        start_time=datetime.utcnow(),
        completion_status="in_progress"
    )
    
    result = await create("study_logs", log_entry.model_dump())
    return {
        "session_id": result["id"], 
        "message": "Tracking started",
        "start_time": log_entry.start_time
    }


@router.post("/session/update/{session_id}")
async def update_study_session(
    session_id: str, 
    interruptions: int = 0,
    idle_time_seconds: float = 0.0,
    is_finished: bool = False,
    current_user: dict = Depends(allowed_users(["student"]))
):
    """
    Update session with interruptions and idle time.
    Call periodically (every 5 min) or when finished.
    """
    updates = {
        "interruptions_count": interruptions,
        "idle_time_seconds": idle_time_seconds,
        "updated_at": datetime.utcnow()
    }
    
    if is_finished:
        session_data = await read_one("study_logs", session_id)
        if session_data:
            start_time = session_data.get("start_time")
            
            # Calculate duration
            if start_time:
                if hasattr(start_time, 'replace'):
                    start_dt = start_time.replace(tzinfo=None)
                else:
                    start_dt = start_time
                    
                duration = (datetime.utcnow() - start_dt).total_seconds()
                updates["end_time"] = datetime.utcnow()
                updates["duration_seconds"] = duration
                updates["completion_status"] = "completed"
            
            # Update behavior profile after session ends
            await update_behavior_profile(current_user["uid"])
    
    await update("study_logs", session_id, updates)
    return {"message": "Session updated", "finished": is_finished}


@router.get("/session/history/{user_id}")
async def get_session_history(
    user_id: str,
    limit: int = 50,
    current_user: dict = Depends(allowed_users(["student", "faculty_member", "admin"]))
):
    """
    Get student's study session history.
    """
    if current_user.get("role") == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    sessions = await read_query("study_logs", [
        ("user_id", "==", user_id)
    ])
    
    # Sort by most recent
    sessions.sort(key=lambda x: x["data"].get("start_time", datetime.min), reverse=True)
    
    return {
        "total_sessions": len(sessions),
        "sessions": sessions[:limit]
    }


@router.get("/behavior-analysis/{user_id}")
async def get_behavior_analysis(
    user_id: str,
    current_user: dict = Depends(allowed_users(["student", "faculty_member", "admin"]))
):
    """
    Get comprehensive behavior analysis:
    - Reading patterns
    - Study time preferences
    - Focus metrics
    - Learning pace
    """
    if current_user.get("role") == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    analysis = await analyze_study_behavior(user_id)
    return analysis


@router.get("/adaptive-content/{user_id}")
async def get_adaptive_content_strategy(
    user_id: str,
    subject_id: str,
    current_user: dict = Depends(allowed_users(["student"]))
):
    """
    Get personalized content delivery strategy based on behavior.
    Returns:
    - Recommended session length
    - Module chunk size
    - Break frequency
    - Difficulty progression
    """
    if current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await get_adaptive_content(user_id, subject_id)


# =======================
# ANNOUNCEMENTS
# =======================

@router.get("/announcements", response_model=List[dict])
async def get_my_announcements(
    current_user: dict = Depends(allowed_users(["student", "faculty_member", "admin"]))
):
    """
    Fetch announcements relevant to the current user.
    - Global announcements
    - Role-specific announcements
    """
    # Get user's role designation (student, faculty_member, admin)
    _, user_role = await get_user_profile_with_role(current_user["uid"])
    
    # Get global announcements
    global_anns = await read_query("announcements", [("is_global", "==", True)])
    
    # Get role-specific announcements
    role_anns = await read_query("announcements", [])
    role_specific = [
        ann for ann in role_anns 
        if user_role in ann["data"].get("target_audience", [])
    ]
    
    # Combine and deduplicate
    all_announcements = global_anns + role_specific
    seen_ids = set()
    unique_announcements = []
    
    for ann in all_announcements:
        if ann["id"] not in seen_ids:
            seen_ids.add(ann["id"])
            unique_announcements.append(ann)
    
    # Sort by most recent
    unique_announcements.sort(
        key=lambda x: x["data"].get("created_at", datetime.min), 
        reverse=True
    )
    
    return unique_announcements


@router.post("/announcements/{announcement_id}/read")
async def mark_announcement_read(
    announcement_id: str,
    current_user: dict = Depends(allowed_users(["student", "faculty_member", "admin"]))
):
    """
    Mark an announcement as read by the user.
    """
    # Create read receipt
    await create("announcement_reads", {
        "announcement_id": announcement_id,
        "user_id": current_user["uid"],
        "read_at": datetime.utcnow()
    })
    
    return {"message": "Announcement marked as read"}


# =======================
# NOTIFICATIONS
# =======================

@router.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    current_user: dict = Depends(allowed_users(["student", "faculty_member", "admin"]))
):
    """
    Get user's notifications.
    """
    filters = [("user_id", "==", current_user["uid"])]
    
    if unread_only:
        filters.append(("is_read", "==", False))
    
    notifications = await read_query("notifications", filters)
    
    # Sort by most recent
    notifications.sort(
        key=lambda x: x["data"].get("created_at", datetime.min), 
        reverse=True
    )
    
    return {
        "total": len(notifications),
        "notifications": notifications
    }


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(allowed_users(["student", "faculty_member", "admin"]))
):
    """
    Mark a notification as read.
    """
    await update("notifications", notification_id, {
        "is_read": True,
        "read_at": datetime.utcnow()
    })
    
    return {"message": "Notification marked as read"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: dict = Depends(allowed_users(["student", "faculty_member", "admin"]))
):
    """
    Mark all user's notifications as read.
    """
    notifications = await read_query("notifications", [
        ("user_id", "==", current_user["uid"]),
        ("is_read", "==", False)
    ])
    
    for notif in notifications:
        await update("notifications", notif["id"], {
            "is_read": True,
            "read_at": datetime.utcnow()
        })
    
    return {
        "message": f"Marked {len(notifications)} notifications as read"
    }

class ReadinessNomination(BaseModel):
    student_id: str
    subject_id: str | None = None
    notes: str | None = None

@router.post("/readiness/nominate")
async def nominate_readiness(payload: ReadinessNomination, current_user: dict = Depends(allowed_users(["faculty_member"]))):
    doc = {
        "student_id": payload.student_id,
        "subject_id": payload.subject_id,
        "notes": payload.notes,
        "nominated_by": current_user["uid"],
        "status": "pending",
        "created_at": datetime.utcnow()
    }
    res = await create("readiness_nominations", doc)
    return {"message": "Nomination submitted", "id": res["id"]}

@router.get("/readiness/nominations")
async def my_nominations(current_user: dict = Depends(allowed_users(["faculty_member", "admin"]))):
    _, role = await get_user_profile_with_role(current_user["uid"])
    filters = []
    if role == "faculty_member":
        filters = [("nominated_by", "==", current_user["uid"])]
    nominations = await read_query("readiness_nominations", filters)
    return {"total": len(nominations), "nominations": nominations}

@router.get("/next-action/{user_id}")
async def get_student_recommendation(
    user_id: str,
    current_user: dict = Depends(allowed_users(["student"]))
):
    """
    Returns the next recommended assessment based on the algorithm:
    Pre-Assessment -> Diagnostic -> Post-Assessment
    """
    if current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
        
    return await get_student_next_action(user_id)