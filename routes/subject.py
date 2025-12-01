# routes/subject.py
from fastapi import APIRouter, Body, HTTPException, Query
from typing import Dict, Any, List, Optional
from services.subject_service import (
    get_all_subjects, 
    create_subject, 
    update_subject, 
    get_subject_by_id,
    verify_subject,
    delete_subject
)

router = APIRouter(prefix="/subjects")

@router.get("/", response_model=List[Dict[str, Any]])
async def get_subjects_endpoint(
    role: str = "student", 
    skip: int = 0, 
    limit: int = 100
):
    return await get_all_subjects(role, skip, limit)

@router.get("/{subject_id}", response_model=Dict[str, Any])
async def get_subject_endpoint(subject_id: str, role: str = "student"):
    return await get_subject_by_id(subject_id, role)

@router.post("/", response_model=Dict[str, Any])
async def create_subject_endpoint(
    payload: Dict[str, Any] = Body(...),
    requester_id: str = "admin", # Replace with auth dependency
    role: str = "admin"
):
    return await create_subject(payload, requester_id, role, is_personal=False)

@router.put("/{subject_id}")
async def update_subject_endpoint(subject_id: str, payload: Dict[str, Any] = Body(...)):
    return await update_subject(subject_id, payload, requester_role="admin")

# [FIX] Verification Endpoint
@router.post("/{subject_id}/verify")
async def verify_subject_endpoint(subject_id: str):
    verifier_id = "admin" # Replace with actual user ID from auth
    return await verify_subject(subject_id, verifier_id)

@router.delete("/{subject_id}")
async def delete_subject_endpoint(subject_id: str):
    return await delete_subject(subject_id)