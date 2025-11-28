from fastapi import Request, HTTPException, status, Header
from typing import List
from firebase_admin import auth
from core.firebase import db
from services.role_service import decode_user, get_user_role_id, get_user_role_designation

def verify_firebase_token(request: Request):
    # Read from cookie instead of header
    token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token"
        )
    
    try:
        return auth.verify_id_token(token, check_revoked=False)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

def allowed_users(allowed_roles: List[str]):
    async def dependency(request: Request):
        # Re-use the robust verification above
        user = verify_firebase_token(request)
        
        # Check roles
        uid = user["uid"]
        role_id = await get_user_role_id(uid)
        designation = await get_user_role_designation(role_id)

        if designation not in [role.lower() for role in allowed_roles]:
            print(f"❌ [Auth Debug] Access Denied. User Role: {designation}, Allowed: {allowed_roles}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return user
    return dependency