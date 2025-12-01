# routes/profiles.py
"""
Profile viewing routes with role-based access control.
Implements strict permission checks for data access.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
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
from services.role_service import get_role_id_by_designation
from services.crud_services import read_one, update
from pydantic import BaseModel
from datetime import datetime
from services.upload_service import upload_file

router = APIRouter(prefix="/profiles", tags=["User Profiles"])

# --- SCHEMAS ---

class ProfileUpdateRequest(BaseModel):
    """Schema for updating OWN profile (Safe fields only)."""
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    username: str | None = None
    profile_picture: str | None = None

class AdminUserUpdateRequest(ProfileUpdateRequest):
    """
    Schema for admins updating OTHER users.
    Includes sensitive fields like role.
    """
    role: str | None = None
    is_verified: bool | None = None

# ========================================
# SELF PROFILE ACCESS
# ========================================

@router.get("/me", summary="Get current user's profile")
async def get_my_profile(current_user: dict = Depends(verify_firebase_token)):
    user_id = current_user["uid"]
    profile, role = await get_user_profile_with_role(user_id)
    
    if role == "student":
        data = await get_student_related_data(user_id)
    elif role == "faculty_member":
        data = await get_faculty_profile_data(user_id)
    elif role == "admin":
        data = await get_admin_profile_data(user_id)
    else:
        data = {"profile": profile}
        
    return {"role": role, "data": data}


@router.put("/me", summary="Update own profile")
async def update_my_profile(
    updates: ProfileUpdateRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    user_id = current_user["uid"]
    
    # Filter out None values
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    update_data["updated_at"] = datetime.utcnow()
    await update("user_profiles", user_id, update_data)
    
    return {"message": "Profile updated successfully", "updated_fields": list(update_data.keys())}


@router.get("/me/permissions", summary="Get my access permissions")
async def get_my_permissions(current_user: dict = Depends(verify_firebase_token)):
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
    requester_id = current_user["uid"]
    _, requester_role = await get_user_profile_with_role(requester_id)
    
    await validate_profile_access(requester_id, requester_role, target_id)
    
    target_profile, target_role = await get_user_profile_with_role(target_id)
    
    if target_role == "student":
        data = await get_student_related_data(target_id)
    elif target_role == "faculty_member":
        data = await get_faculty_profile_data(target_id)
    elif target_role == "admin":
        data = await get_admin_profile_data(target_id)
    else:
        data = {"profile": target_profile}

    return {"user_id": target_id, "role": target_role, "data": data}


# ========================================
# ADMIN-SPECIFIC UPDATE (THE FIX)
# ========================================

@router.put("/user/{target_id}", summary="Update another user's profile")
async def update_target_user_profile(
    target_id: str,
    updates: AdminUserUpdateRequest, # <--- MUST USE THIS SCHEMA
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Update another user's profile information. ADMIN ONLY.
    """
    requester_id = current_user["uid"]
    _, requester_role = await get_user_profile_with_role(requester_id)
    
    if requester_role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update other profiles.")
    
    # Debugging print to see what backend receives
    print(f"DEBUG: Updating user {target_id} with data: {updates.model_dump()}")

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    
    # Handle Role Change
    if "role" in update_data:
        raw_role = update_data["role"].lower().strip()
        # Map common terms to correct Enum values
        role_map = {
            "admin": "admin",
            "student": "student",
            "teacher": "faculty_member",
            "faculty": "faculty_member",
            "faculty_member": "faculty_member"
        }
        normalized_role = role_map.get(raw_role, raw_role)
        
        # Look up the ID
        role_id = await get_role_id_by_designation(normalized_role)
        if not role_id:
             # Try capitalizing
            role_id = await get_role_id_by_designation(normalized_role.capitalize())
            
        if not role_id:
            raise HTTPException(status_code=400, detail=f"Invalid role designation: {update_data['role']}")
            
        update_data["role_id"] = role_id
        del update_data["role"] # Clean up

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update. Check your payload keys.")
    
    update_data["updated_at"] = datetime.utcnow()
    await update("user_profiles", target_id, update_data)
    
    return {
        "message": f"User {target_id} updated successfully",
        "updated_fields": list(update_data.keys())
    }


# ========================================
# LISTS & SEARCH
# ========================================

@router.get("/students", summary="List all students")
async def list_all_students(
    current_user: dict = Depends(verify_firebase_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    _, requester_role = await get_user_profile_with_role(current_user["uid"])
    if requester_role not in ["faculty_member", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    students = await get_all_students_summary(requester_role)
    return {"total": len(students), "students": students[skip:skip + limit]}

@router.get("/faculty", summary="List all faculty")
async def list_all_faculty(
    current_user: dict = Depends(verify_firebase_token),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    _, requester_role = await get_user_profile_with_role(current_user["uid"])
    if requester_role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    faculty = await get_all_faculty_summary()
    return {"total": len(faculty), "faculty": faculty[skip:skip + limit]}

@router.get("/search", summary="Search users")
async def search_users(
    query: str = Query(..., min_length=2),
    role_filter: str | None = Query(None),
    current_user: dict = Depends(verify_firebase_token)
):
    requester_id = current_user["uid"]
    _, requester_role = await get_user_profile_with_role(requester_id)
    
    if requester_role == "student":
        raise HTTPException(status_code=403, detail="Forbidden")
        
    if requester_role == "faculty_member":
        role_filter = "student" # Faculty can only search students
        
    # Logic to fetch users based on role
    if requester_role == "admin" and role_filter != "student":
        if role_filter == "faculty_member":
            users = await get_all_faculty_summary()
        else:
            s = await get_all_students_summary("admin")
            f = await get_all_faculty_summary()
            users = s + f
    else:
        users = await get_all_students_summary(requester_role)
        
    q = query.lower()
    results = [
        u for u in users 
        if q in u.get("email", "").lower() or 
           q in u.get("first_name", "").lower() or 
           q in u.get("last_name", "").lower()
    ]
    return {"results": results[:50]}

# ========================================
# EXTRAS
# ========================================

@router.get("/student/{student_id}/performance")
async def get_student_performance(student_id: str, current_user: dict = Depends(verify_firebase_token)):
    requester_id = current_user["uid"]
    _, role = await get_user_profile_with_role(requester_id)
    await validate_profile_access(requester_id, role, student_id)
    data = await get_student_related_data(student_id)
    return {
        "readiness": data["student_info"]["personal_readiness"],
        "progress": data["student_info"]["progress_report"]
    }

@router.get("/student/{student_id}/activity")
async def get_student_activity(student_id: str, current_user: dict = Depends(verify_firebase_token)):
    requester_id = current_user["uid"]
    _, role = await get_user_profile_with_role(requester_id)
    await validate_profile_access(requester_id, role, student_id)
    data = await get_student_related_data(student_id)
    return {"activity": data["activity"]["study_logs"][:10]}

@router.get("/admin/system-overview")
async def get_system_overview(current_user: dict = Depends(verify_firebase_token)):
    _, role = await get_user_profile_with_role(current_user["uid"])
    if role != "admin": raise HTTPException(403, "Forbidden")
    data = await get_admin_profile_data(current_user["uid"])
    return {"statistics": data["system_statistics"]}

@router.post("/upload-avatar")
async def upload_profile_picture(file: UploadFile = File(...), current_user: dict = Depends(verify_firebase_token)):
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(400, "Invalid image")
    url = await upload_file(file)
    return {"file_url": url}