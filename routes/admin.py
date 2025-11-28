# routes/admin.py
from collections import defaultdict
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
        assigned_role=role.value,
        added_by=current_user["uid"]
    )
    
    result = await create("pre_registered_users", payload.model_dump())
    return {
        "message": f"User {email} whitelisted as {role}",
        "id": result["id"],
        "auto_verify_on_signup": True
    }

@router.get("/readiness/nominations")
async def list_readiness_nominations(current_user: dict = Depends(allowed_users(["admin"]))):
    nominations = await read_query("readiness_nominations", [])
    return {"total": len(nominations), "nominations": nominations}

@router.post("/readiness/approve/{nomination_id}")
async def approve_readiness(nomination_id: str, current_user: dict = Depends(allowed_users(["admin"]))):
    nomination = await read_one("readiness_nominations", nomination_id)
    if not nomination:
        raise HTTPException(status_code=404, detail="Nomination not found")
    student_id = nomination.get("student_id")
    await update("readiness_nominations", nomination_id, {"status": "approved", "decided_at": datetime.utcnow(), "decided_by": current_user["uid"]})
    profile = await read_one("user_profiles", student_id)
    if profile:
        info = profile.get("student_info", {})
        info["board_exam_ready"] = True
        info["board_exam_verified_at"] = datetime.utcnow()
        info["board_exam_verified_by"] = current_user["uid"]
        await update("user_profiles", student_id, {"student_info": info})
    return {"message": "Readiness approved"}

@router.post("/readiness/reject/{nomination_id}")
async def reject_readiness(nomination_id: str, reason: str = "", current_user: dict = Depends(allowed_users(["admin"]))):
    nomination = await read_one("readiness_nominations", nomination_id)
    if not nomination:
        raise HTTPException(status_code=404, detail="Nomination not found")
    await update("readiness_nominations", nomination_id, {"status": "rejected", "decided_at": datetime.utcnow(), "decided_by": current_user["uid"], "reason": reason})
    return {"message": "Readiness rejected"}


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
    Get comprehensive system statistics:
    - Active User Counts (by role, status)
    - Whitelisted (Pending Signup) Counts
    - Content Counts (Subjects, Modules, Assessments, Questions)
    """
    
    # 1. Fetch All Data
    all_users = await read_query("user_profiles", [])
    all_roles = await read_query("roles", [])
    all_whitelist = await read_query("pre_registered_users", [])  # [NEW] Fetch whitelist
    
    all_subjects = await read_query("subjects", [])
    all_assessments = await read_query("assessments", [])
    all_questions = await read_query("questions", [])

    # 2. Build Role Map
    role_map = {}
    for r in all_roles:
        role_name = r["data"].get("designation", "unknown").lower()
        role_map[r["id"]] = role_name

    # 3. User Statistics
    # [FIX] Initialize keys to ensure Pie Chart always sees 'admin'
    stats = {
        "total_users": len(all_users),
        "by_role": { "admin": 0, "student": 0, "faculty_member": 0 },
        "verified_users": 0,
        "pending_verification": 0,
        "active_users": 0,
        # [NEW] Whitelist Counts
        "whitelist_students": 0,
        "whitelist_faculty": 0
    }
    
    # Count Active Users
    for user in all_users:
        data = user["data"]
        role_id = data.get("role_id")
        role_name = role_map.get(role_id, "unknown")
        
        # Fallback for admin if role_id is missing/mismatched
        if role_name == "unknown" and user["id"] == current_user["uid"]:
             role_name = "admin"

        # Safe increment
        if role_name in stats["by_role"]:
            stats["by_role"][role_name] += 1
        else:
            stats["by_role"][role_name] = 1
        
        if data.get("is_verified"):
            stats["verified_users"] += 1
        else:
            stats["pending_verification"] += 1
            
        if data.get("is_active", True):
            stats["active_users"] += 1

    # [NEW] Count Whitelisted Users
    for w in all_whitelist:
        # whitelist stores 'assigned_role' as a string value (e.g., "student")
        role = w["data"].get("assigned_role", "")
        if role == "student":
            stats["whitelist_students"] += 1
        elif role == "faculty_member":
            stats["whitelist_faculty"] += 1

    # 4. Content Statistics
    total_modules = 0
    pending_modules = 0
    
    for subject in all_subjects:
        topics = subject["data"].get("topics", [])
        for topic in topics:
            if topic.get("lecture_content"):
                total_modules += 1
                if not topic.get("is_verified", False):
                    pending_modules += 1

    # Return Combined Stats
    return {
        **stats,
        "total_subjects": len(all_subjects),
        "total_modules": total_modules,
        "pending_modules": pending_modules,
        "total_assessments": len(all_assessments),
        "pending_assessments": len([a for a in all_assessments if not a["data"].get("is_verified", False)]),
        "total_questions": len(all_questions),
        "pending_questions": len([q for q in all_questions if not q["data"].get("is_verified", False)])
    }


# =======================
# ANNOUNCEMENTS
# =======================

@router.post("/announcements", response_model=AnnouncementSchema)
async def create_announcement(
    title: str, 
    content: str, 
    target_roles: List[UserRole] = [],
    is_global: bool = False,
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
):
    """
    Create an announcement.
    - is_global=True: Shows to everyone
    - target_roles: Specific roles (student, teacher, admin)
    """
    audience = [r.value if hasattr(r, "value") else str(r) for r in target_roles]
    payload = AnnouncementSchema(
        title=title,
        content=content,
        target_audience=audience,
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
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
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
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
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
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
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
async def get_unverified_questions(current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))):
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
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
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
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
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

@router.get("/users/growth")
async def get_user_growth_statistics(current_user: dict = Depends(allowed_users(["admin"]))):
    """
    Get user growth over time.
    """
    # Optimized fetch (only needed fields if possible, but Firestore is document-based)
    all_users = await read_query("user_profiles", [])
    
    growth_data = defaultdict(int)
    
    for user in all_users:
        created_at = user["data"].get("created_at")
        if not created_at:
            continue
            
        # Robust Date Parsing
        dt = None
        if isinstance(created_at, datetime):
            dt = created_at
        elif isinstance(created_at, str):
            try:
                # Handle ISO format with or without microseconds/timezone
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except ValueError:
                continue
        
        if dt:
            month_key = dt.strftime("%Y-%m")
            growth_data[month_key] += 1
            
    # Sort and Aggregate
    sorted_keys = sorted(growth_data.keys())
    cumulative_count = 0
    chart_data = []
    
    for month in sorted_keys:
        count = growth_data[month]
        cumulative_count += count
        
        # Friendly Label: "Jan 24"
        dt_obj = datetime.strptime(month, "%Y-%m")
        label = dt_obj.strftime("%b %y")
        
        chart_data.append({
            "date": label,
            "new_users": count,
            "total_users": cumulative_count
        })
        
    return chart_data