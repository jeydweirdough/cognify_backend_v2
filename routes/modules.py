from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from services.module_matcher import auto_categorize_module
from services.crud_services import update, read_one, create, read_all, delete
from services.upload_service import upload_file
from core.security import allowed_users, verify_firebase_token
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

# Ensure 'admin' and 'faculty_member' can manage modules
router = APIRouter(prefix="/modules", tags=["Module Management"], dependencies=[Depends(verify_firebase_token)])

# ... (Keep existing Pydantic Models: ModuleUpdateModel, ModuleCreateModel) ...
class ModuleUpdateModel(BaseModel):
    title: Optional[str] = None
    purpose: Optional[str] = None
    bloom_levels: Optional[List[str]] = None 
    subject_id: Optional[str] = None
    is_verified: Optional[bool] = None

class ModuleCreateModel(BaseModel):
    title: str
    subject_id: str
    purpose: Optional[str] = None
    bloom_levels: Optional[List[str]] = []
    material_url: Optional[str] = None
    material_type: Optional[str] = None
    is_verified: Optional[bool] = False

@router.get("/", summary="Get all modules")
async def list_modules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    subject_id: Optional[str] = None
):
    modules = await read_all("modules", limit, skip)
    if subject_id:
        modules = [m for m in modules if m.get("subject_id") == subject_id]
    return {"items": modules, "total": len(modules)}

@router.get("/{module_id}", summary="Get module by ID")
async def get_module(module_id: str):
    module = await read_one("modules", module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module

@router.post("/", summary="Create Module Metadata")
async def create_module(module_data: ModuleCreateModel):
    new_module = await create("modules", module_data.model_dump())
    return new_module

@router.put("/{module_id}")
async def update_module_route(module_id: str, updates: ModuleUpdateModel):
    data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await update("modules", module_id, data)
    return result

@router.delete("/{module_id}")
async def delete_module_route(module_id: str):
    await delete("modules", module_id)
    return {"status": "success", "message": "Module deleted"}

# [FIX] Added Verification Endpoints
@router.post("/{module_id}/verify")
async def verify_module(
    module_id: str,
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
):
    await update("modules", module_id, {
        "is_verified": True,
        "is_rejected": False,
        "verified_at": datetime.utcnow(),
        "verified_by": current_user["uid"]
    })
    return {"message": "Module verified successfully"}

@router.post("/{module_id}/reject")
async def reject_module(
    module_id: str,
    reason: str = Query(...),
    current_user: dict = Depends(allowed_users(["admin", "faculty_member"]))
):
    await update("modules", module_id, {
        "is_verified": False,
        "is_rejected": True,
        "rejection_reason": reason,
        "rejected_at": datetime.utcnow(),
        "rejected_by": current_user["uid"]
    })
    return {"message": "Module rejected"}

@router.post("/upload-smart", summary="Upload Module with AI Auto-Categorization")
async def upload_module_smart(
    subject_id: str = Form(...),
    file: UploadFile = File(...)
):
    content = await file.read()
    ai_decision = await auto_categorize_module(content, subject_id)
    
    target_topic_id = ai_decision.get("matched_topic_id")
    
    await file.seek(0)
    file_url = await upload_file(file)
    
    module_data = {
        "subject_id": subject_id,
        "title": file.filename,
        "purpose": ai_decision.get("reasoning", "Uploaded via Smart Match"),
        "bloom_levels": ["Applying"], 
        "material_url": file_url,
        "is_verified": False,
        "created_at": datetime.utcnow()
    }
    
    await create("modules", module_data)
    
    if target_topic_id:
        subject_data = await read_one("subjects", subject_id)
        if subject_data:
            topics = subject_data.get("topics", [])
            for topic in topics:
                if topic["id"] == target_topic_id:
                    topic["lecture_content"] = file_url
                    break
            await update("subjects", subject_id, {"topics": topics})

    return {
        "message": "Module successfully uploaded",
        "file_url": file_url,
        "ai_decision": ai_decision
    }