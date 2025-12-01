from fastapi import APIRouter, HTTPException, Query, Body, Depends
# [FIX] Added 'Dict' to the imports below
from typing import List, Dict, Any, Optional
from services.crud_services import read_query, read_one, create, update, delete
from services.module_service import verify_module, reject_module
from datetime import datetime
import uuid

router = APIRouter(prefix="/modules")

@router.get("/", response_model=List[Dict[str, Any]])
async def get_modules(subject_id: Optional[str] = None):
    filters = []
    if subject_id:
        filters.append(("subject_id", "==", subject_id))
    
    # Simple fetch
    modules = await read_query("modules", filters)
    
    # Flatten ID
    results = []
    for m in modules:
        data = m["data"]
        data["id"] = m["id"]
        results.append(data)
    return results

@router.get("/{module_id}", response_model=Dict[str, Any])
async def get_module(module_id: str):
    mod = await read_one("modules", module_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found")
    mod["id"] = module_id
    return mod

@router.post("/")
async def create_module(payload: Dict[str, Any] = Body(...)):
    doc_id = str(uuid.uuid4())
    payload["created_at"] = datetime.utcnow()
    payload["is_verified"] = False # Default to pending
    await create("modules", payload, doc_id=doc_id)
    return {"id": doc_id, "message": "Module created"}

@router.put("/{module_id}")
async def update_module(module_id: str, payload: Dict[str, Any] = Body(...)):
    payload["updated_at"] = datetime.utcnow()
    await update("modules", module_id, payload)
    return {"message": "Module updated"}

@router.post("/{module_id}/verify")
async def verify_module_endpoint(module_id: str):
    # In a real app, get verifier_id from current_user
    verifier_id = "admin" 
    return await verify_module(module_id, verifier_id)

@router.post("/{module_id}/reject")
async def reject_module_endpoint(module_id: str, reason: str = Query(...)):
    return await reject_module(module_id, reason)

@router.delete("/{module_id}")
async def delete_module_endpoint(module_id: str):
    await delete("modules", module_id)
    return {"message": "Module deleted"}