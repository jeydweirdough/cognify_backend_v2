# routes/subject.py
from fastapi import APIRouter, Body, HTTPException, Query, UploadFile, File, Depends, status
from typing import Dict, Any, List, Optional
from services.subject_service import (
    get_all_subjects, 
    create_subject, 
    update_subject, 
    get_subject_by_id,
    verify_subject,
    delete_subject
)
from services.upload_service import upload_file
from core.security import allowed_users

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

# [NEW] Image Upload Endpoint for Subjects
@router.post("/upload-image", summary="Upload subject cover image")
async def upload_subject_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
):
    """
    Uploads an image (JPEG/PNG/WEBP) to Google Drive and returns the public URL.
    This URL should be passed to the 'image_url' field in create/update subject.
    """
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid image format. Supported: JPEG, PNG, WEBP"
        )
    
    try:
        # Re-using the centralized upload service (saves to Google Drive)
        url = await upload_file(file)
        return {"image_url": url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image upload failed: {str(e)}"
        )

# [FIX] Verification Endpoint
@router.post("/{subject_id}/verify")
async def verify_subject_endpoint(subject_id: str):
    verifier_id = "admin" # Replace with actual user ID from auth
    return await verify_subject(subject_id, verifier_id)

@router.delete("/{subject_id}")
async def delete_subject_endpoint(subject_id: str):
    return await delete_subject(subject_id)