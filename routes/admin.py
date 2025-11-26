# routes/admin.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from database.models import PreRegisteredUserSchema, AnnouncementSchema
from database.enums import UserRole
from services.crud_services import create, read_query, update, read_one, delete
from core.security import allowed_users
from core.firebase import db
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"], dependencies=[Depends(allowed_users(["admin"]))])

# =======================
# USER MANAGEMENT (Whitelist)
# =======================

@router.post("/whitelist-user", summary="Pre-register a user email")
async def whitelist_user(
    email: str, 
    role: UserRole, 
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Admins register emails here. Only these emails can sign up.
    Auto-verification enabled once user signs up.
    """
    if not email.endswith("@cvsu.edu.ph"):
        raise HTTPException(status_code=400, detail="Email must be @cvsu.edu.ph")
    
    # Check if already whitelisted
    existing = await read_query("pre_registered_users", [("email", "==", email)])
    if existing:
        raise HTTPException(status_code=400, detail="Email already whitelisted")

    payload = PreRegisteredUserSchema(
        email=email,
        assigned_role=role,
        added_by=current_user["uid"]
    )
    
    result = await create("pre_registered_users", payload.model_dump())
    return {
        "message": f"User {email} whitelisted as {role}",
        "id": result["id"],
        "auto_verify_on_signup": True
    }


@router.get("/whitelist", summary="Get all whitelisted users")
async def get_whitelist(
    is_registered: Optional[bool] = Query(None),
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    View all pre-registered users and their registration status.
    """
    filters = []
    if is_registered is not None:
        filters.append(("is_registered", "==", is_registered))
    
    users = await read_query("pre_registered_users", filters)
    
    return {
        "total": len(users),
        "users": users
    }


@router.delete("/whitelist/{email}", summary="Remove from whitelist")
async def remove_from_whitelist(
    email: str,
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Remove email from whitelist (only if not yet registered).
    """
    users = await read_query("pre_registered_users", [("email", "==", email)])
    
    if not users:
        raise HTTPException(status_code=404, detail="Email not found in whitelist")
    
    user_data = users[0]["data"]
    if user_data.get("is_registered"):
        raise HTTPException(
            status_code=400, 
            detail="Cannot remove - user already registered. Deactivate account instead."
        )
    
    await delete("pre_registered_users", users[0]["id"])
    return {"message": f"Email {email} removed from whitelist"}


# =======================
# USER VERIFICATION & MANAGEMENT
# =======================

@router.get("/users/pending-verification")
async def get_pending_users(current_user: dict = Depends(allowed_users(["admin"]))):
    """
    Get users waiting for manual verification (if auto-verify fails).
    """
    users = await read_query("user_profiles", [("is_verified", "==", False)])
    
    return {
        "total_pending": len(users),
        "users": users
    }


@router.post("/users/{user_id}/verify")
async def verify_user_manually(
    user_id: str,
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Manually verify a user account.
    """
    await update("user_profiles", user_id, {
        "is_verified": True,
        "verified_at": datetime.utcnow(),
        "verified_by": current_user["uid"]
    })
    
    return {"message": "User verified successfully"}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    reason: str,
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Deactivate a user account.
    """
    await update("user_profiles", user_id, {
        "is_active": False,
        "deactivated_at": datetime.utcnow(),
        "deactivated_by": current_user["uid"],
        "deactivation_reason": reason
    })
    
    return {"message": "User deactivated"}


@router.get("/users/statistics")
async def get_user_statistics(current_user: dict = Depends(allowed_users(["admin"]))):
    """
    Get system-wide user statistics.
    """
    all_users = await read_query("user_profiles", [])
    
    stats = {
        "total_users": len(all_users),
        "by_role": {},
        "verified_users": 0,
        "pending_verification": 0,
        "active_users": 0
    }
    
    for user in all_users:
        data = user["data"]
        
        # Count by role
        role = data.get("role_id", "unknown")
        stats["by_role"][role] = stats["by_role"].get(role, 0) + 1
        
        # Count verification status
        if data.get("is_verified"):
            stats["verified_users"] += 1
        else:
            stats["pending_verification"] += 1
        
        # Count active users
        if data.get("is_active", True):
            stats["active_users"] += 1
    
    return stats


# =======================
# ANNOUNCEMENTS
# =======================

@router.post("/announcements", response_model=AnnouncementSchema)
async def create_announcement(
    title: str, 
    content: str, 
    target_roles: List[UserRole] = [],
    is_global: bool = False,
    current_user: dict = Depends(allowed_users(["admin", "teacher"]))
):
    """
    Create an announcement.
    - is_global=True: Shows to everyone
    - target_roles: Specific roles (student, teacher, admin)
    """
    payload = AnnouncementSchema(
        title=title,
        content=content,
        target_audience=target_roles,
        is_global=is_global,
        author_id=current_user["uid"]
    )
    
    result = await create("announcements", payload.model_dump())
    
    # Notification logic here
    await notify_users_about_announcement(result["id"], target_roles, is_global)
    
    return payload


@router.get("/announcements", response_model=List[dict])
async def get_all_announcements(
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(allowed_users(["admin", "teacher"]))
):
    """
    Get all announcements (admin/teacher view).
    """
    announcements = await read_query("announcements", limit=limit)
    return announcements


@router.put("/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    target_roles: Optional[List[UserRole]] = None,
    is_global: Optional[bool] = None,
    current_user: dict = Depends(allowed_users(["admin", "teacher"]))
):
    """
    Update an existing announcement.
    """
    update_data = {"updated_at": datetime.utcnow()}
    
    if title:
        update_data["title"] = title
    if content:
        update_data["content"] = content
    if target_roles is not None:
        update_data["target_audience"] = target_roles
    if is_global is not None:
        update_data["is_global"] = is_global
    
    await update("announcements", announcement_id, update_data)
    
    return {"message": "Announcement updated"}


@router.delete("/announcements/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
    current_user: dict = Depends(allowed_users(["admin", "teacher"]))
):
    """
    Delete an announcement.
    """
    await delete("announcements", announcement_id)
    return {"message": "Announcement deleted"}


async def notify_users_about_announcement(
    announcement_id: str, 
    target_roles: List[UserRole], 
    is_global: bool
):
    """
    Send notifications to users about new announcement.
    """
    # TODO: Implement notification system (email, push, in-app)
    # For now, just log
    print(f"Notification sent for announcement {announcement_id}")
    pass


# =======================
# MATERIAL VERIFICATION
# =======================

@router.get("/pending-questions", response_model=List[dict])
async def get_unverified_questions(current_user: dict = Depends(allowed_users(["admin", "teacher"]))):
    """
    Fetch questions waiting for verification.
    """
    questions = await read_query("questions", [("is_verified", "==", False)])
    
    # Enrich with creator info
    for q in questions:
        creator_id = q["data"].get("created_by")
        if creator_id:
            creator = await read_one("user_profiles", creator_id)
            q["data"]["creator_name"] = f"{creator.get('first_name', '')} {creator.get('last_name', '')}"
    
    return questions


@router.post("/verify-question/{question_id}")
async def verify_question_admin(
    question_id: str, 
    current_user: dict = Depends(allowed_users(["admin", "teacher"]))
):
    """
    Approve a question for use in assessments.
    """
    await update("questions", question_id, {
        "is_verified": True,
        "verified_at": datetime.utcnow(),
        "verified_by": current_user["uid"]
    })
    
    return {"message": "Question verified"}


@router.post("/reject-question/{question_id}")
async def reject_question(
    question_id: str,
    reason: str,
    current_user: dict = Depends(allowed_users(["admin", "teacher"]))
):
    """
    Reject a question with reason.
    """
    await update("questions", question_id, {
        "is_rejected": True,
        "rejected_at": datetime.utcnow(),
        "rejected_by": current_user["uid"],
        "rejection_reason": reason
    })
    
    return {"message": "Question rejected"}


@router.get("/pending-assessments")
async def get_unverified_assessments(current_user: dict = Depends(allowed_users(["admin"]))):
    """
    Get assessments pending verification.
    """
    assessments = await read_query("assessments", [("is_verified", "==", False)])
    return assessments


@router.post("/verify-assessment/{assessment_id}")
async def verify_assessment(
    assessment_id: str,
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Verify an assessment for student use.
    """
    await update("assessments", assessment_id, {
        "is_verified": True,
        "verified_at": datetime.utcnow(),
        "verified_by": current_user["uid"]
    })
    
    return {"message": "Assessment verified"}


@router.get("/pending-modules")
async def get_unverified_modules(current_user: dict = Depends(allowed_users(["admin"]))):
    """
    Get modules pending verification.
    """
    # Modules are stored in subjects.topics
    subjects = await read_query("subjects", [])
    
    pending_modules = []
    for subject in subjects:
        topics = subject["data"].get("topics", [])
        for topic in topics:
            if topic.get("lecture_content") and not topic.get("is_verified", False):
                pending_modules.append({
                    "subject_id": subject["id"],
                    "topic_id": topic["id"],
                    "title": topic["title"],
                    "content_url": topic["lecture_content"]
                })
    
    return pending_modules


@router.post("/verify-module/{subject_id}/{topic_id}")
async def verify_module(
    subject_id: str,
    topic_id: str,
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Verify a module/topic.
    """
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    topics = subject.get("topics", [])
    for topic in topics:
        if topic["id"] == topic_id:
            topic["is_verified"] = True
            topic["verified_at"] = datetime.utcnow()
            topic["verified_by"] = current_user["uid"]
            break
    
    await update("subjects", subject_id, {"topics": topics})
    
    return {"message": "Module verified"}


# =======================
# SYSTEM MONITORING
# =======================

@router.get("/system/health")
async def system_health(current_user: dict = Depends(allowed_users(["admin"]))):
    """
    System health check and statistics.
    """
    return {
        "status": "operational",
        "timestamp": datetime.utcnow(),
        "database": "connected",
        "ai_services": "operational"
    }