from fastapi import Request, HTTPException, status, Header
from typing import List
from firebase_admin import auth
from core.firebase import db
from services.role_service import decode_user, get_user_role_id, get_user_role_designation

def verify_firebase_token(request: Request):
    # 1. Get header (Case Insensitive)
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")

    # 2. Check if missing
    if not auth_header:
        print("❌ [Auth Debug] Missing Authorization Header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing authorization header"
        )
    
    # 3. Parse Token (Handle "Bearer <token>" or just "<token>")
    try:
        if "Bearer " in auth_header:
            token = auth_header.split("Bearer ")[1].strip()
        else:
            token = auth_header.strip()

        # 4. Verify
        # check_revoked=False helps avoid issues with Emulator restarts
        return auth.verify_id_token(token, check_revoked=False)
        
    except Exception as e:
        print(f"❌ [Auth Debug] Verification Failed: {e}")
        # Print the first few chars of token to verify it was received
        if 'token' in locals():
            print(f"   Token received (start): {token[:10]}...")
            
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