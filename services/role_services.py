from core.firebase import db
import asyncio
from google.cloud.firestore_v1.base_query import FieldFilter
from fastapi import HTTPException, status
from firebase_admin import auth  # Direct import to avoid circular dependency

async def decode_user(token: str) -> dict:
    """
    Decodes the Firebase ID token directly using firebase_admin.auth
    to avoid circular imports with core.security.
    """
    try:
        decoded = auth.verify_id_token(token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User UID not found in token")
    
    return decoded

async def get_user_role_id(uid: str):
    user_doc = db.collection("user_profiles").document(uid).get()
    
    if not user_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    
    user_data = user_doc.to_dict()
    role_id = user_data.get("role_id")
    if not role_id:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="User role not assigned")

    role_doc = db.collection("roles").document(role_id).get()
    if not role_doc.exists:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role designation missing")

    designation = role_doc.to_dict().get("designation")

    return designation.lower()

async def get_user_role_designation(role_id: str):
    role_doc = db.collection("roles").document(role_id).get()
    if not role_doc.exists:
        return None
    
    designation = role_doc.to_dict().get("designation")
    return designation

async def get_role_id_by_designation(designation: str):
    roles_ref = db.collection("roles")
    query = roles_ref.where(
        filter=FieldFilter("designation", "==", designation)
    )
    results = query.stream()
    role_doc = None
    for doc in results:
        role_doc = doc
        break

    if role_doc:
        return role_doc.id
    return None