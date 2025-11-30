# core/security.py
from fastapi import Cookie, Request, HTTPException, status, Header, Depends
from typing import List, Optional
from firebase_admin import auth
from core.firebase import db
from services.role_service import decode_user, get_user_role_id, get_user_role_designation

async def verify_firebase_token(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None)
) -> dict:
    """
    Verify Firebase token from either:
    1. Authorization header (for mobile apps)
    2. Cookie (for web apps)
    
    Returns decoded token with user info.
    """
    token = None
    
    # 1. Try Authorization header first (Mobile / API Clients)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]
    
    # 2. Fall back to cookie (Web Admin / Faculty)
    elif access_token:
        token = access_token
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided"
        )
    
    try:
        # [IMPROVEMENT] check_revoked=True checks if the user's session was invalidated 
        # (e.g. password change, logout, or admin ban)
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        return decoded_token
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )

def allowed_users(allowed_roles: List[str]):
    """
    Dependency to restrict access based on user roles.
    Usage: @router.get("/", dependencies=[Depends(allowed_users(["admin"]))])
    """
    async def dependency(user: dict = Depends(verify_firebase_token)):
        # Check roles
        uid = user["uid"]
        
        # Fetch role details from Firestore
        try:
            role_id = await get_user_role_id(uid)
            designation = await get_user_role_designation(role_id)
            
            # Normalize to lowercase for comparison
            if not designation or designation.lower() not in [r.lower() for r in allowed_roles]:
                print(f"❌ [Auth] Access Denied. User: {designation}, Allowed: {allowed_roles}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="You do not have permission to perform this action"
                )
        except Exception as e:
            # Fallback if role service fails
            print(f"❌ [Auth] Role Verification Failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Could not verify user permissions"
            )
            
        return user
    return dependency