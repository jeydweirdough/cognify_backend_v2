# routes/profiles.py
"""
Profile viewing routes with role-based access control.
Implements strict permission checks for data access.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any
from core.security import verify_firebase_token
from services.profile_service import (
    get_user_profile_with_role,
    get_student_related_data,
    get_faculty_profile_data,
    get_admin_profile_data,
    get_all_students_summary,
    get_all_faculty_summary,
    validate_profile_access,
    get_profile_view_permissions
)
from services.crud_services import read_one, update
from pydantic import BaseModel
from datetime import datetime


router = APIRouter(prefix="/profiles", tags=["User Profiles"])


class ProfileUpdateRequest(BaseModel):
    """Schema for updating profile information."""
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    username: str | None = None
    profile_picture: str | None = None


# ========================================
# SELF PROFILE ACCESS
# ========================================

@router.get("/me", summary="Get current user's profile")
async def get_my_profile(current_user: dict = Depends(verify_firebase_token)):
    """
    Get the authenticated user's own profile with all related data.
    Works for all roles - returns appropriate data based on role.
    """
    user_id = current_user["uid"]
    profile, role = await get_user_profile_with_role(user_id)
    
    # Return role-specific data
    if role == "student":
        return {
            "role": role,
            "data": await get_student_related_data(user_id)
        }
    elif role == "faculty_member":
        return {
            "role": role,
            "data": await get_faculty_profile_data(user_id)
        }
    elif role == "admin":
        return {
            "role": role,
            "data": await get_admin_profile_data(user_id)
        }
    else:
        return {
            "role": role,
            "data": {"profile": profile}
        }


@router.put("/me", summary="Update own profile")
async def update_my_profile(
    updates: ProfileUpdateRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Update the authenticated user's profile information.
    """
    user_id = current_user["uid"]
    
    # Prepare update data (only include non-None fields)
    update_data = {
        k: v for k, v in updates.model_dump().items() 
        if v is not None
    }
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Add update timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update profile
    await update("user_profiles", user_id, update_data)
    
    return {
        "message": "Profile updated successfully",
        "updated_fields": list(update_data.keys())
    }


@router.get("/me/permissions", summary="Get my access permissions")
async def get_my_permissions(current_user: dict = Depends(verify_firebase_token)):
    """
    Get what the current user is allowed to view/access.
    Useful for frontend to conditionally render UI elements.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    permissions = await get_profile_view_permissions(role)
    
    return {
        "user_id": current_user["uid"],
        "role": role,
        "permissions": permissions
    }


# ========================================
# VIEW OTHER USER PROFILES
# ========================================

@router.get("/user/{target_id}", summary="View specific user profile")
async def get_user_profile(
    target_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    View another user's profile.
    
    Access Rules:
    - Students: Can only view their own profile (will be denied)
    - Faculty: Can view student profiles only
    - Admin: Can view all profiles
    """
    requester_id = current_user["uid"]
    _, requester_role = await get_user_profile_with_role(requester_id)
    
    # Validate access permission
    await validate_profile_access(requester_id, requester_role, target_id)
    
    # Get target user's role
    target_profile, target_role = await get_user_profile_with_role(target_id)
    
    # Return appropriate data based on target's role
    if target_role == "student":
        return {
            "user_id": target_id,
            "role": target_role,
            "data": await get_student_related_data(target_id)
        }
    elif target_role == "faculty_member":
        # Only admin can see this (validation already done above)
        return {
            "user_id": target_id,
            "role": target_role,
            "data": await get_faculty_profile_data(target_id)
        }
    elif target_role == "admin":
        # Only admin can see this
        return {
            "user_id": target_id,
            "role": target_role,
            "data": await get_admin_profile_data(target_id)
        }
    else:
        return {
            "user_id": target_id,
            "role": target_role,
            "data": {"profile": target_profile}
        }


# ========================================
# LIST USERS (FACULTY & ADMIN ONLY)
# ========================================

@router.get("/students", summary="List all students")
async def list_all_students(
    current_user: dict = Depends(verify_firebase_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get list of all students.
    
    Access:
    - Faculty: Can view all students
    - Admin: Can view all students
    - Students: Denied
    """
    _, requester_role = await get_user_profile_with_role(current_user["uid"])
    
    if requester_role not in ["faculty_member", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admin can view student list"
        )
    
    students = await get_all_students_summary(requester_role)
    
    # Apply pagination
    total = len(students)
    paginated = students[skip:skip + limit]
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "students": paginated
    }


@router.get("/faculty", summary="List all faculty members")
async def list_all_faculty(
    current_user: dict = Depends(verify_firebase_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get list of all faculty members.
    
    Access:
    - Admin only
    - Faculty cannot view other faculty
    - Students cannot view faculty list
    """
    _, requester_role = await get_user_profile_with_role(current_user["uid"])
    
    if requester_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can view faculty list"
        )
    
    faculty = await get_all_faculty_summary()
    
    # Apply pagination
    total = len(faculty)
    paginated = faculty[skip:skip + limit]
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "faculty": paginated
    }


# ========================================
# SEARCH FUNCTIONALITY
# ========================================

@router.get("/search", summary="Search users by name or email")
async def search_users(
    query: str = Query(..., min_length=2),
    role_filter: str | None = Query(None, regex="^(student|faculty_member|admin)$"),
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Search for users by name or email.
    
    Access restrictions apply:
    - Students: Cannot search (will be denied)
    - Faculty: Can search students only
    - Admin: Can search all users
    """
    requester_id = current_user["uid"]
    _, requester_role = await get_user_profile_with_role(requester_id)
    
    # Students cannot search
    if requester_role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot search for other users"
        )
    
    # Faculty can only search students
    if requester_role == "faculty_member":
        if role_filter and role_filter != "student":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Faculty can only search for students"
            )
        # Force student filter for faculty
        role_filter = "student"
    
    # Get all students (or all users if admin)
    if requester_role == "admin" and role_filter != "student":
        # Admin searching for non-students
        if role_filter == "faculty_member":
            users = await get_all_faculty_summary()
        else:
            # Search all users
            students = await get_all_students_summary("admin")
            faculty = await get_all_faculty_summary()
            users = students + faculty
    else:
        # Search students only
        users = await get_all_students_summary(requester_role)
    
    # Filter by query
    query_lower = query.lower()
    results = [
        user for user in users
        if query_lower in user.get("email", "").lower()
        or query_lower in user.get("first_name", "").lower()
        or query_lower in user.get("last_name", "").lower()
    ]
    
    return {
        "query": query,
        "role_filter": role_filter,
        "results_count": len(results),
        "results": results[:50]  # Limit to 50 results
    }


# ========================================
# STUDENT-SPECIFIC ENDPOINTS
# ========================================

@router.get("/student/{student_id}/performance", summary="Get student performance summary")
async def get_student_performance(
    student_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Get detailed performance summary for a student.
    
    Access:
    - Student can view their own performance
    - Faculty can view any student's performance
    - Admin can view any student's performance
    """
    requester_id = current_user["uid"]
    _, requester_role = await get_user_profile_with_role(requester_id)
    
    # Validate access
    await validate_profile_access(requester_id, requester_role, student_id)
    
    # Get student data
    student_data = await get_student_related_data(student_id)
    
    # Extract and return performance metrics
    return {
        "student_id": student_id,
        "readiness": student_data["student_info"]["personal_readiness"],
        "timeliness": student_data["student_info"]["timeliness"],
        "behavior_profile": student_data["student_info"]["behavior_profile"],
        "progress_reports": student_data["student_info"]["progress_report"],
        "competency_performance": student_data["student_info"]["competency_performance"],
        "assessment_statistics": student_data["assessments"],
        "activity_statistics": student_data["activity"]
    }


@router.get("/student/{student_id}/activity", summary="Get student activity logs")
async def get_student_activity(
    student_id: str,
    current_user: dict = Depends(verify_firebase_token),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get student's recent activity (study sessions, assessments).
    
    Access:
    - Student can view their own activity
    - Faculty can view any student's activity
    - Admin can view any student's activity
    """
    requester_id = current_user["uid"]
    _, requester_role = await get_user_profile_with_role(requester_id)
    
    # Validate access
    await validate_profile_access(requester_id, requester_role, student_id)
    
    # Get student data
    student_data = await get_student_related_data(student_id)
    
    # Sort and limit activity
    study_logs = student_data["activity"]["study_logs"][:limit]
    assessments = student_data["assessments"]["submissions"][:limit]
    
    return {
        "student_id": student_id,
        "recent_study_sessions": study_logs,
        "recent_assessments": assessments,
        "summary": {
            "total_sessions": student_data["activity"]["total_sessions"],
            "completed_sessions": student_data["activity"]["completed_sessions"],
            "total_assessments": student_data["assessments"]["total_assessments"],
            "average_score": student_data["assessments"]["average_score"]
        }
    }


# ========================================
# ADMIN-SPECIFIC ENDPOINTS
# ========================================

@router.get("/admin/system-overview", summary="Get system overview")
async def get_system_overview(current_user: dict = Depends(verify_firebase_token)):
    """
    Get comprehensive system statistics.
    Admin only.
    """
    _, requester_role = await get_user_profile_with_role(current_user["uid"])
    
    if requester_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can view system overview"
        )
    
    admin_data = await get_admin_profile_data(current_user["uid"])
    
    return {
        "statistics": admin_data["system_statistics"],
        "timestamp": datetime.utcnow()
    }