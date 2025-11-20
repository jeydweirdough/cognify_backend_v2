from core.firebase import db
import asyncio
from google.cloud.firestore_v1.base_query import FieldFilter
from fastapi import HTTPException, status
from core.security import verify_firebase_token

async def decode_user(token: str) -> dict:
    decoded = await verify_firebase_token(token)
    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User UID not found in token")
    
    return decoded

async def get_user_role_id(uid: str):
    user_doc = db.collection("user_profiles").document(uid).get()
    
    if not user_doc.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    
    role_id = user_doc.to_dict().get("role_id")
    if not role_id:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="User role not assigned")

    role_doc = db.collection("roles").document(role_id).get()
    if not role_doc.exists:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role designation missing")

    designation = role_doc.to_dict().get("designation")

    return designation.lower()

async def get_user_role_designation(role_id: str):
    roles = db.collection("roles").document(role_id).get()

    designation = roles["designation"]

    return designation