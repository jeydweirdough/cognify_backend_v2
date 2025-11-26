# routes/admin.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from database.models import (
    PreRegisteredUserSchema, AnnouncementSchema
)
from database.enums import UserRole
from services.crud_services import create, read_query, update, read_one
from core.security import allowed_users
from core.firebase import db
from datetime import datetime

# FIX: dependencies=[Depends(...)]
router = APIRouter(prefix="/admin", tags=["Admin Dashboard"], dependencies=[Depends(allowed_users(["admin"]))])

# =======================
# USER MANAGEMENT (Whitelist)
# =======================

@router.post("/whitelist-user", summary="Pre-register a user email")
async def whitelist_user(email: str, role: UserRole, current_user: dict = Depends(allowed_users(["admin"]))):
    """
    Admins register emails here. Only these emails can sign up.
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
    
    await create("pre_registered_users", payload.model_dump())
    return {"message": f"User {email} whitelisted as {role}"}

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
    Create an announcement. If is_global is True, it targets everyone.
    """
    payload = AnnouncementSchema(
        title=title,
        content=content,
        target_audience=target_roles,
        is_global=is_global,
        author_id=current_user["uid"]
    )
    
    res = await create("announcements", payload.model_dump())
    # Adjust response to match schema if necessary
    return payload

# =======================
# MATERIAL VERIFICATION
# =======================

@router.get("/pending-questions", response_model=List[dict])
async def get_unverified_questions():
    """Fetch questions waiting for Admin/Faculty verification"""
    questions = await read_query("questions", [("is_verified", "==", False)])
    return questions

@router.post("/verify-question/{question_id}")
async def verify_question_admin(question_id: str, current_user: dict = Depends(allowed_users(["admin", "teacher"]))):
    """Approve a question for use in assessments"""
    await update("questions", question_id, {
        "is_verified": True,
        "verified_at": datetime.utcnow(),
        "verified_by": current_user["uid"]
    })
    return {"message": "Question verified"}