# routes/auth.py
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response, status, Depends, Body, Cookie, Header
from firebase_admin import auth
from pydantic import BaseModel
from database.models import LoginSchema, SignUpSchema, UserProfileBase
from services.crud_services import create, read_query, update
from services.role_service import get_role_id_by_designation, get_user_role_designation, get_user_role_id
from utils.firebase_utils import firebase_login_with_email, refresh_firebase_token
from core.security import verify_firebase_token
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

class ClientTypeHeader(BaseModel):
    """Used to detect if request is from mobile or web"""
    client_type: Optional[str] = None

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(auth_data: SignUpSchema):
    """Signup logic remains the same"""
    # ... (keep existing signup code)
    pass

@router.post("/login")
async def login(
    credentials: LoginSchema, 
    response: Response,
    client_type: Optional[str] = Header(None)  # NEW: Detect client type
):
    """
    Login with support for both web (cookies) and mobile (tokens).
    Mobile apps should send 'Client-Type: mobile' header.
    """
    try:
        existing_profiles = await read_query("user_profiles", [("email", "==", credentials.email)])
        if not existing_profiles:
            raise HTTPException(status_code=403, detail="Account not registered")
        
        profile = existing_profiles[0]["data"]
        if not (profile.get("is_registered") and profile.get("is_verified")):
            raise HTTPException(status_code=403, detail="Account not verified or not registered")
        
        auth_data = firebase_login_with_email(credentials.email, credentials.password)
        
        # Determine response format based on client type
        is_mobile = client_type and client_type.lower() == "mobile"
        
        if is_mobile:
            # MOBILE: Return tokens in response body
            return {
                "message": "Login successful",
                "uid": auth_data["localId"],
                "token": auth_data["idToken"],
                "refresh_token": auth_data["refreshToken"],
            }
        else:
            # WEB: Set HTTP-only cookies
            response.set_cookie(
                key="access_token",
                value=auth_data["idToken"],
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=3600
            )
            response.set_cookie(
                key="refresh_token",
                value=auth_data["refreshToken"],
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=2592000
            )
            return {
                "message": "Login successful",
                "uid": auth_data["localId"],
            }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    refresh_token_body: Optional[str] = Body(None, embed=True, alias="refresh_token"),
    client_type: Optional[str] = Header(None)
):
    """
    Refresh token with support for both cookies (web) and body (mobile).
    Mobile apps should send refresh_token in request body.
    """
    # Try to get refresh token from cookie first, then body
    refresh_token = refresh_token_cookie or refresh_token_body
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    try:
        new_tokens = refresh_firebase_token(refresh_token)
        
        is_mobile = client_type and client_type.lower() == "mobile"
        
        if is_mobile:
            # MOBILE: Return tokens in response body
            return {
                "message": "Token refreshed successfully",
                "token": new_tokens["token"],
                "refresh_token": new_tokens["refresh_token"]
            }
        else:
            # WEB: Update cookies
            response.set_cookie(
                key="access_token",
                value=new_tokens["token"],
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=3600
            )
            response.set_cookie(
                key="refresh_token",
                value=new_tokens["refresh_token"],
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=2592000
            )
            return {"message": "Token refreshed successfully"}
    
    except Exception as e:
        print(f"Refresh failed: {e}")
        if not (client_type and client_type.lower() == "mobile"):
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/logout")
async def logout(
    response: Response, 
    current_user: dict = Depends(verify_firebase_token),
    client_type: Optional[str] = Header(None)
):
    """Logout with support for both web and mobile"""
    try:
        uid = current_user['uid']
        auth.revoke_refresh_tokens(uid)
        
        # Only clear cookies for web clients
        if not (client_type and client_type.lower() == "mobile"):
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
        
        return {"message": "Logged out successfully"}
    
    except Exception as e:
        print(f"Logout revocation failed: {e}")
        if not (client_type and client_type.lower() == "mobile"):
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
        return {"message": "Logged out locally"}

# Keep existing /permission endpoint unchanged
@router.post("/permission")
async def check_permission(
    current_user: dict = Depends(verify_firebase_token),
    request: dict = Body(default={})
):
    uid = current_user['uid']
    role_id = await get_user_role_id(uid)
    role_designation = await get_user_role_designation(role_id)
    
    if "designation" in request:
        requested = request["designation"]
        if isinstance(requested, (list, tuple)):
            has_permission = role_designation in requested
        else:
            has_permission = role_designation == requested
        return {"has_permission": has_permission}
    
    return {"role_designation": role_designation}