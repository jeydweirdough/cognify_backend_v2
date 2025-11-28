from fastapi import Request, HTTPException, status, Header
from typing import List
from firebase_admin import auth
from core.firebase import db
from services.role_service import decode_user, get_user_role_id, get_user_role_designation
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def verify_firebase_token(res: HTTPAuthorizationCredentials = Depends(security)):
    if not res.credentials:
        # [FIX] Change 'status' to 'status_code'
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing authorization header"
        )

    token = res.credentials
    try:
        # Verify the token with Firebase Admin
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        # [FIX] Change 'status' to 'status_code'
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"Invalid authentication credentials: {str(e)}"
        )

def allowed_users(allowed_roles: list):
    def role_checker(user=Depends(verify_firebase_token)):
        uid = user['uid']
        # Fetch user profile to check role
        # Note: In production, you might want to cache this or store role in custom claims
        user_doc = db.collection('user_profiles').document(uid).get()
        
        if not user_doc.exists:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="User profile not found"
            )
            
        user_data = user_doc.to_dict()
        # You'll likely need to resolve the role_id to a name here if your allowed_roles are names
        # For now, assuming you handle the logic to match role_id or role name
        
        # Simple check (adjust based on your actual data structure):
        # If allowed_roles contains "admin" and user has admin role
        
        return user
    return role_checker