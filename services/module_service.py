from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import HTTPException, status
from services.crud_services import read_one, update, create, read_query, delete
import uuid

async def verify_module(module_id: str, verifier_id: str) -> Dict[str, Any]:
    """
    Sets a module as verified.
    """
    module = await read_one("modules", module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    update_data = {
        "is_verified": True,
        "verified_at": datetime.utcnow(),
        "verified_by": verifier_id,
        "updated_at": datetime.utcnow()
    }
    
    await update("modules", module_id, update_data)
    
    return {
        "message": "Module verified successfully",
        "id": module_id,
        "verified_at": update_data["verified_at"]
    }

async def reject_module(module_id: str, reason: str) -> Dict[str, Any]:
    """
    Reject a module (optional: soft delete or flag).
    """
    module = await read_one("modules", module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
        
    update_data = {
        "is_verified": False,
        "is_rejected": True,
        "rejection_reason": reason,
        "updated_at": datetime.utcnow()
    }
    
    await update("modules", module_id, update_data)
    return {"message": "Module rejected", "id": module_id}