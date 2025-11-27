# services/profile_service.py
"""
Profile viewing service with role-based access control.
Handles data retrieval and filtering based on user permissions.
"""
from typing import Dict, List, Optional, Any
from fastapi import HTTPException, status
from services.crud_services import read_one, read_query
from services.role_service import get_user_role_designation


async def get_user_profile_with_role(user_id: str) -> tuple[Dict, str]:
    """
    Get user profile and their role designation.
    
    Returns:
        Tuple of (profile_data, role_designation)
    """
    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    role_id = profile.get("role_id")
    if not role_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User role not assigned"
        )
    
    role_designation = await get_user_role_designation(role_id)
    if not role_designation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role designation not found"
        )
    
    return profile, role_designation.lower()


async def get_student_related_data(user_id: str) -> Dict[str, Any]:
    """
    Fetch all data related to a specific student.
    Used for student self-view and faculty/admin viewing student profiles.
    """
    # Get base profile
    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Study logs
    study_logs = await read_query("study_logs", [("user_id", "==", user_id)])
    
    # Assessment submissions
    assessments = await read_query("assessment_submissions", [("user_id", "==", user_id)])
    
    # Notifications
    notifications = await read_query("notifications", [("user_id", "==", user_id)])
    
    # Announcement reads
    announcement_reads = await read_query("announcement_reads", [("user_id", "==", user_id)])
    
    # Progress data (if stored separately)
    # This might be embedded in student_info, so we extract it
    student_info = profile.get("student_info", {})
    progress_report = student_info.get("progress_report", [])
    competency_performance = student_info.get("competency_performance", [])
    behavior_profile = student_info.get("behavior_profile", {})
    
    return {
        "profile": profile,
        "student_info": {
            "personal_readiness": student_info.get("personal_readiness"),
            "confident_subject": student_info.get("confident_subject", []),
            "timeliness": student_info.get("timeliness", 0),
            "behavior_profile": behavior_profile,
            "progress_report": progress_report,
            "competency_performance": competency_performance,
            "recommended_study_modules": student_info.get("recommended_study_modules", [])
        },
        "activity": {
            "study_logs": study_logs,
            "total_sessions": len(study_logs),
            "completed_sessions": len([log for log in study_logs if log["data"].get("completion_status") == "completed"])
        },
        "assessments": {
            "submissions": assessments,
            "total_assessments": len(assessments),
            "average_score": calculate_average_score(assessments)
        },
        "notifications": {
            "all": notifications,
            "unread_count": len([n for n in notifications if not n["data"].get("is_read", False)])
        },
        "engagement": {
            "announcements_read": len(announcement_reads)
        }
    }


async def get_faculty_profile_data(user_id: str) -> Dict[str, Any]:
    """
    Fetch faculty member's own profile data.
    Faculty can only see their own information, not other faculty members.
    """
    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty profile not found"
        )
    
    # Notifications for this faculty member
    notifications = await read_query("notifications", [("user_id", "==", user_id)])
    
    # Announcements created by this faculty
    announcements = await read_query("announcements", [("author_id", "==", user_id)])
    
    # Questions created by this faculty
    questions = await read_query("questions", [("created_by", "==", user_id)])
    
    # Assessments created by this faculty
    assessments = await read_query("assessments", [("created_by", "==", user_id)])
    
    return {
        "profile": profile,
        "activity": {
            "announcements_created": len(announcements),
            "questions_created": len(questions),
            "verified_questions": len([q for q in questions if q["data"].get("is_verified", False)]),
            "assessments_created": len(assessments)
        },
        "notifications": {
            "all": notifications,
            "unread_count": len([n for n in notifications if not n["data"].get("is_read", False)])
        },
        "created_content": {
            "recent_announcements": announcements[:5],
            "recent_questions": questions[:10]
        }
    }


async def get_all_students_summary(requester_role: str) -> List[Dict[str, Any]]:
    """
    Get summary of all students.
    Only accessible by faculty and admin.
    """
    if requester_role not in ["faculty_member", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only faculty and admin can view all students"
        )
    
    # Get all users with student role
    all_users = await read_query("user_profiles", [])
    
    # Filter for students
    students = []
    for user in all_users:
        user_data = user["data"]
        role_id = user_data.get("role_id")
        if role_id:
            role_designation = await get_user_role_designation(role_id)
            if role_designation and role_designation.lower() == "student":
                students.append({
                    "id": user["id"],
                    "email": user_data.get("email"),
                    "first_name": user_data.get("first_name"),
                    "last_name": user_data.get("last_name"),
                    "is_verified": user_data.get("is_verified", False),
                    "profile_picture": user_data.get("profile_picture"),
                    "student_info": {
                        "personal_readiness": user_data.get("student_info", {}).get("personal_readiness"),
                        "timeliness": user_data.get("student_info", {}).get("timeliness", 0)
                    }
                })
    
    return students


async def get_all_faculty_summary() -> List[Dict[str, Any]]:
    """
    Get summary of all faculty members.
    Only accessible by admin.
    """
    all_users = await read_query("user_profiles", [])
    
    # Filter for faculty
    faculty = []
    for user in all_users:
        user_data = user["data"]
        role_id = user_data.get("role_id")
        if role_id:
            role_designation = await get_user_role_designation(role_id)
            if role_designation and role_designation.lower() == "faculty_member":
                # Get their contribution stats
                questions_count = len(await read_query("questions", [("created_by", "==", user["id"])]))
                announcements_count = len(await read_query("announcements", [("author_id", "==", user["id"])]))
                
                faculty.append({
                    "id": user["id"],
                    "email": user_data.get("email"),
                    "first_name": user_data.get("first_name"),
                    "last_name": user_data.get("last_name"),
                    "is_verified": user_data.get("is_verified", False),
                    "profile_picture": user_data.get("profile_picture"),
                    "contributions": {
                        "questions_created": questions_count,
                        "announcements_created": announcements_count
                    }
                })
    
    return faculty


async def get_admin_profile_data(user_id: str) -> Dict[str, Any]:
    """
    Fetch admin's own profile data with system statistics.
    """
    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin profile not found"
        )
    
    # System statistics
    all_users = await read_query("user_profiles", [])
    all_subjects = await read_query("subjects", [])
    all_questions = await read_query("questions", [])
    all_assessments = await read_query("assessments", [])
    
    # Count by role
    role_counts = {"student": 0, "faculty_member": 0, "admin": 0}
    for user in all_users:
        role_id = user["data"].get("role_id")
        if role_id:
            role_designation = await get_user_role_designation(role_id)
            if role_designation:
                role_key = role_designation.lower()
                role_counts[role_key] = role_counts.get(role_key, 0) + 1
    
    # Pending verifications
    pending_questions = len([q for q in all_questions if not q["data"].get("is_verified", False)])
    pending_assessments = len([a for a in all_assessments if not a["data"].get("is_verified", False)])
    
    return {
        "profile": profile,
        "system_statistics": {
            "total_users": len(all_users),
            "students": role_counts.get("student", 0),
            "faculty": role_counts.get("faculty_member", 0),
            "admins": role_counts.get("admin", 0),
            "total_subjects": len(all_subjects),
            "total_questions": len(all_questions),
            "total_assessments": len(all_assessments),
            "pending_verifications": {
                "questions": pending_questions,
                "assessments": pending_assessments
            }
        }
    }


async def validate_profile_access(
    requester_id: str,
    requester_role: str,
    target_id: str
) -> bool:
    """
    Validate if requester has permission to view target profile.
    
    Rules:
    - Students: Can only view their own profile
    - Faculty: Can view their own profile + all student profiles
    - Admin: Can view all profiles
    
    Args:
        requester_id: ID of user making the request
        requester_role: Role of requester (student, faculty_member, admin)
        target_id: ID of profile being accessed
        
    Returns:
        True if access is allowed
        
    Raises:
        HTTPException if access is denied
    """
    # Self-access is always allowed
    if requester_id == target_id:
        return True
    
    # Admin can access all profiles
    if requester_role == "admin":
        return True
    
    # Faculty can access student profiles
    if requester_role == "faculty_member":
        target_profile, target_role = await get_user_profile_with_role(target_id)
        if target_role == "student":
            return True
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Faculty members cannot view other faculty profiles"
            )
    
    # Students can only view their own profile
    if requester_role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only view their own profile"
        )
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied"
    )


def calculate_average_score(assessments: List[Dict]) -> float:
    """Helper function to calculate average assessment score."""
    if not assessments:
        return 0.0
    
    scores = [a["data"].get("score", 0) for a in assessments]
    return sum(scores) / len(scores) if scores else 0.0


async def get_profile_view_permissions(role: str) -> Dict[str, bool]:
    """
    Get what data sections a role can view.
    Useful for frontend to know what to display.
    """
    permissions = {
        "student": {
            "can_view_own_profile": True,
            "can_view_other_students": False,
            "can_view_faculty": False,
            "can_view_admin": False,
            "can_view_system_stats": False,
            "can_view_all_users_list": False
        },
        "faculty_member": {
            "can_view_own_profile": True,
            "can_view_other_students": True,
            "can_view_faculty": False,
            "can_view_admin": False,
            "can_view_system_stats": False,
            "can_view_all_users_list": True  # But filtered to students only
        },
        "admin": {
            "can_view_own_profile": True,
            "can_view_other_students": True,
            "can_view_faculty": True,
            "can_view_admin": True,
            "can_view_system_stats": True,
            "can_view_all_users_list": True
        }
    }
    
    return permissions.get(role, permissions["student"])