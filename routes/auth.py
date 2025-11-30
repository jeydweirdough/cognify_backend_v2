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
    """
    Registers a new user. 
    Requires the email to be pre-registered (whitelisted) by an admin in 'pre_registered_users'.
    """
    # 1. Verify Whitelist / Pre-registration
    # Check if the email exists in the whitelist
    whitelist_entries = await read_query("pre_registered_users", [("email", "==", auth_data.email)])
    
    if not whitelist_entries:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="This email is not authorized for registration. Please contact the administrator."
        )
    
    whitelist_doc = whitelist_entries[0]
    whitelist_data = whitelist_doc["data"]
    
    # Check if already registered
    if whitelist_data.get("is_registered", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered."
        )

    # 2. Create User in Firebase Authentication
    try:
        user = auth.create_user(
            email=auth_data.email,
            password=auth_data.password,
            display_name=f"{auth_data.first_name} {auth_data.last_name}"
        )
    except auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Authentication provider error: {str(e)}"
        )

    # 3. Determine Role from Whitelist
    # The whitelist is the source of truth for the role (e.g., 'Student', 'Faculty').
    assigned_role_name = whitelist_data.get("assigned_role")
    role_id = None
    
    if assigned_role_name:
        role_id = await get_role_id_by_designation(assigned_role_name)
    
    # Fallback to Student if resolution fails (safety net)
    if not role_id:
        role_id = await get_role_id_by_designation("Student")

    # 4. Create User Profile in Firestore
    new_profile = {
        "uid": user.uid,
        "email": auth_data.email,
        "first_name": auth_data.first_name,
        "last_name": auth_data.last_name,
        "username": auth_data.username,
        "role_id": role_id,
        "is_registered": True,
        "is_verified": True, # Whitelisted users are implicitly verified
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "profile_image": None
    }
    
    # Save to 'user_profiles'
    await create("user_profiles", new_profile, doc_id=user.uid)
    
    # 5. Update Whitelist Entry
    await update("pre_registered_users", whitelist_doc["id"], {
        "is_registered": True,
        "registered_at": datetime.utcnow(),
        "user_id": user.uid
    })

    return {"message": "Account created successfully", "uid": user.uid}

@router.post("/login")
async def login(
    credentials: LoginSchema, 
    response: Response,
    client_type: Optional[str] = Header(None)
):
    """
    Login with support for both web (cookies) and mobile (tokens).
    Mobile apps should send 'Client-Type: mobile' header.
    """
    try:
        # Check if profile exists and is active
        existing_profiles = await read_query("user_profiles", [("email", "==", credentials.email)])
        if not existing_profiles:
            raise HTTPException(status_code=403, detail="Account not registered")
        
        profile = existing_profiles[0]["data"]
        
        # Enforce verification
        if not (profile.get("is_registered") and profile.get("is_verified")):
            raise HTTPException(status_code=403, detail="Account not verified or not registered")
        
        # Perform Firebase Login
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