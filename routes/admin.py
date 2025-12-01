# routes/admin.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from typing import List
from services.crud_services import create, read_query, delete, update, read_one
from services.admin_service import get_verification_queue, get_system_statistics
from core.security import allowed_users
from database.enums import UserRole
from database.models import PreRegisteredUserSchema
from datetime import datetime
import csv
import io

# Ensure only admins can access these routes
router = APIRouter(prefix="/admin", tags=["Admin Management"], dependencies=[Depends(allowed_users(["admin"]))])

@router.get("/verification-queue")
async def verification_queue():
    """Get list of all items needing verification"""
    return await get_verification_queue()

@router.get("/users/statistics")
async def user_statistics():
    """Get dashboard statistics"""
    return await get_system_statistics()

@router.get("/whitelist")
async def get_whitelist():
    """Get all whitelisted emails"""
    whitelist = await read_query("whitelist", [])
    # Flatten for frontend
    return {"users": whitelist}

@router.post("/whitelist-user")
async def add_whitelist_user(email: str, role: str):
    """Manually add a user to whitelist"""
    # Check for duplicates
    existing = await read_query("whitelist", [("email", "==", email)])
    if existing:
        raise HTTPException(status_code=400, detail="Email already whitelisted")
        
    entry = {
        "email": email,
        "assigned_role": role,
        "is_registered": False,
        "added_by": "admin_manual",
        "created_at": datetime.utcnow()
    }
    await create("whitelist", entry)
    return {"message": "User added to whitelist"}

@router.delete("/whitelist/{email}")
async def remove_whitelist_user(email: str):
    """Remove a user from whitelist"""
    existing = await read_query("whitelist", [("email", "==", email)])
    if not existing:
        raise HTTPException(status_code=404, detail="User not found in whitelist")
    
    await delete("whitelist", existing[0]['id'])
    return {"message": "User removed from whitelist"}

@router.post("/whitelist/bulk")
async def bulk_whitelist_users(file: UploadFile = File(...)):
    """Upload CSV for bulk whitelisting"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    content = await file.read()
    decoded_content = content.decode('utf-8')
    csv_reader = csv.reader(io.StringIO(decoded_content))
    
    rows = list(csv_reader)
    # Skip header if present
    if rows and "email" in rows[0][0].lower():
        rows = rows[1:]
        
    added = 0
    skipped = 0
    errors = []
    
    existing_list = await read_query("whitelist", [])
    existing_emails = {u['data'].get('email') for u in existing_list}

    for i, row in enumerate(rows):
        try:
            if len(row) < 2: continue
            email = row[0].strip().lower()
            role_str = row[1].strip().lower()
            
            if email in existing_emails:
                skipped += 1
                continue
                
            # Normalize Role
            if "admin" in role_str: role = UserRole.ADMIN
            elif "faculty" in role_str: role = UserRole.FACULTY
            else: role = UserRole.STUDENT
            
            entry = {
                "email": email,
                "assigned_role": role,
                "is_registered": False,
                "added_by": "bulk_upload",
                "created_at": datetime.utcnow()
            }
            await create("whitelist", entry)
            added += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")
            skipped += 1
            
    return {"message": "Processed", "added": added, "skipped": skipped, "errors": errors}