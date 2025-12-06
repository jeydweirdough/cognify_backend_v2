from fastapi import APIRouter, HTTPException, Query, Body, Depends, UploadFile, File, status
from typing import List, Dict, Any, Optional
from services.crud_services import read_query, read_one, create, update, delete
from services.module_service import verify_module, reject_module
from services.upload_service import upload_file 
from datetime import datetime
import uuid
import traceback

# Create the router
router = APIRouter(prefix="/modules")


@router.post("/upload", response_model=Dict[str, str])
async def upload_module_material(file: UploadFile = File(...)):
    """
    Uploads a PDF to Google Drive via the V2 Upload Service.
    """
    print(f"DEBUG: Upload request received for file: {file.filename}")
    
    # 1. Validation
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
        
    try:
        # 2. Upload to Drive
        file_url = await upload_file(file)
        print(f"DEBUG: Upload success! URL: {file_url}")
        return {"file_url": file_url}
        
    except Exception as e:
        print("DEBUG: Upload failed")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# =================================================================
# NOW it is safe to define generic routes like /{module_id}
# =================================================================

@router.get("/", response_model=List[Dict[str, Any]])
async def get_modules(subject_id: Optional[str] = None):
    filters = []
    if subject_id:
        filters.append(("subject_id", "==", subject_id))
    
    modules = await read_query("modules", filters)
    
    results = []
    for m in modules:
        data = m["data"]
        data["id"] = m["id"]
        results.append(data)
    return results

# This generic route catches EVERYTHING else. It must be AFTER /upload.
@router.get("/{module_id}", response_model=Dict[str, Any])
async def get_module(module_id: str):
    mod = await read_one("modules", module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    mod["id"] = module_id
    return mod

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_module(payload: Dict[str, Any] = Body(...)):
    doc_id = str(uuid.uuid4())
    payload["created_at"] = datetime.utcnow()
    if "is_verified" not in payload:
        payload["is_verified"] = False 
        
    await create("modules", payload, doc_id=doc_id)
    return {"id": doc_id, "message": "Module created"}

@router.put("/{module_id}")
async def update_module(module_id: str, payload: Dict[str, Any] = Body(...)):
    payload["updated_at"] = datetime.utcnow()
    await update("modules", module_id, payload)
    return {"message": "Module updated"}

@router.post("/{module_id}/verify")
async def verify_module_endpoint(module_id: str):
    verifier_id = "admin" 
    return await verify_module(module_id, verifier_id)

@router.post("/{module_id}/reject")
async def reject_module_endpoint(module_id: str, reason: str = Query(...)):
    return await reject_module(module_id, reason)

@router.delete("/{module_id}")
async def delete_module_endpoint(module_id: str):
    await delete("modules", module_id)
    return {"message": "Module deleted"}