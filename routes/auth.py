# routes/auth.py
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response, status, Depends, Body, Cookie, Header
from firebase_admin import auth
from pydantic import BaseModel
from database.models import LoginSchema, SignUpSchema, UserProfileBase
# [FIX] Added read_one to imports
from services.crud_services import create, read_query, update, read_one
from services.role_service import get_role_id_by_designation, get_user_role_designation, get_user_role_id
from utils.firebase_utils import firebase_login_with_email, refresh_firebase_token
from core.security import verify_firebase_token
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

class ClientTypeHeader(BaseModel):
    """Used to detect if request is from mobile or web"""
    client_type: Optional[str] = None
    
@router.post("/admin/whitelist", status_code=status.HTTP_201_CREATED)
async def whitelist_email(
    email: str = Body(...),
    assigned_role: str = Body(default="Student"),
    current_user: dict = Depends(verify_firebase_token)
):
    """Admin endpoint to whitelist an email for registration"""
    # Verify admin role
    user_role = await get_user_role_designation(await get_user_role_id(current_user['uid']))
    if user_role not in ["admin", "faculty_member"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Check if already exists
    existing = await read_query("whitelist", [("email", "==", email)])
    if existing:
        raise HTTPException(status_code=409, detail="Email already whitelisted")
    
    # Create whitelist entry
    whitelist_data = {
        "email": email,
        "assigned_role": assigned_role,
        "is_registered": False,
        "created_at": datetime.utcnow(),
        "created_by": current_user['uid']
    }
    
    await create("whitelist", whitelist_data)
    return {"message": "Email whitelisted successfully", "email": email}

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(auth_data: SignUpSchema):
    """
    Registers a new user with Self-Healing for broken accounts.
    """
    try:
        # 1. Verify Whitelist / Pre-registration
        whitelist_entries = await read_query("whitelist", [("email", "==", auth_data.email)])
        
        if not whitelist_entries:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="This email is not authorized for registration. Please contact the administrator."
            )
        
        whitelist_doc = whitelist_entries[0]
        whitelist_data = whitelist_doc["data"]
        
        # [FIX] Check if already registered AND if profile actually exists (Handle Stale Whitelist)
        if whitelist_data.get("is_registered", False):
            is_valid_registration = False
            # Check by ID if available
            if whitelist_data.get("user_id"):
                 if await read_one("user_profiles", whitelist_data["user_id"]):
                     is_valid_registration = True
            # Fallback check by email
            elif await read_query("user_profiles", [("email", "==", auth_data.email)]):
                 is_valid_registration = True
            
            if is_valid_registration:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This email is already registered."
                )
            # If we get here, the whitelist says "registered" but no profile exists. 
            # We allow the process to continue to fix this state.

        # 2. Check if username already exists (if provided)
        if auth_data.username:
            existing_username = await read_query("user_profiles", [("username", "==", auth_data.username)])
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username is already taken."
                )

        # 3. Create User in Firebase Authentication (With Self-Healing)
        user = None
        try:
            user = auth.create_user(
                email=auth_data.email,
                password=auth_data.password,
                display_name=f"{auth_data.first_name} {auth_data.last_name}"
            )
        except auth.EmailAlreadyExistsError:
            # [FIX] Logic to handle "Zombie Accounts" (Auth exists, DB missing)
            try:
                # Fetch existing auth record
                user = auth.get_user_by_email(auth_data.email)
                
                # Check DB one last time to ensure we don't overwrite a valid user
                if await read_one("user_profiles", user.uid):
                     raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Account already exists and is active."
                    )
                
                # REPAIR: Update the stale Auth record with new details
                user = auth.update_user(
                    user.uid,
                    password=auth_data.password,
                    display_name=f"{auth_data.first_name} {auth_data.last_name}"
                )
                print(f"Self-healed zombie account for {auth_data.email}")
                
            except Exception as inner_e:
                print(f"Self-healing failed: {inner_e}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Account exists but could not be reset. Contact support."
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Authentication provider error: {str(e)}"
            )

        # 4. Determine Role from Whitelist
        assigned_role_name = whitelist_data.get("assigned_role")
        role_id = None
        
        if assigned_role_name is not None:
            s = str(assigned_role_name).strip().lower()
            if "faculty" in s:
                designation = "faculty_member"
            elif "admin" in s:
                designation = "admin"
            else:
                designation = "student"
            role_id = await get_role_id_by_designation(designation)
        
        if not role_id:
            role_id = await get_role_id_by_designation("student")

        # 5. Create User Profile in Firestore
        new_profile = {
            "uid": user.uid,
            "email": auth_data.email,
            "first_name": auth_data.first_name,
            "last_name": auth_data.last_name,
            "username": auth_data.username,
            "role_id": role_id,
            "is_registered": True,
            "is_verified": True, 
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "profile_image": None,
            # Init empty student info to prevent mobile crashes
            "student_info": {
                "personal_readiness": "VERY_LOW",
                "progress_report": [],
                "timeliness": 100,
                "behavior_profile": {"learning_pace": "Standard"}
            }
        }
        
        # Force write to ensure profile exists
        await create("user_profiles", new_profile, doc_id=user.uid)
        
        # 6. Update Whitelist Entry
        await update("whitelist", whitelist_doc["id"], {
            "is_registered": True,
            "registered_at": datetime.utcnow(),
            "user_id": user.uid
        })

        return {
            "message": "Account created successfully", 
            "uid": user.uid,
            "email": auth_data.email,
            "username": auth_data.username
        }
    
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected signup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during signup: {str(e)}"
        )

@router.post("/login")
async def login(
    credentials: LoginSchema, 
    response: Response,
    client_type: Optional[str] = Header(None)
):
    """Login with support for both web and mobile."""
    try:
        # Check if profile exists and is active
        existing_profiles = await read_query("user_profiles", [("email", "==", credentials.email)])
        if not existing_profiles:
            raise HTTPException(status_code=403, detail="Account not registered. Please sign up first.")
        
        profile = existing_profiles[0]["data"]
        
        # Enforce verification
        if not (profile.get("is_registered") and profile.get("is_verified")):
            raise HTTPException(status_code=403, detail="Account not verified or not registered")
        
        # Perform Firebase Login
        auth_data = firebase_login_with_email(credentials.email, credentials.password)
        
        is_mobile = client_type and client_type.lower() == "mobile"
        
        if is_mobile:
            return {
                "message": "Login successful",
                "uid": auth_data["localId"],
                "token": auth_data["idToken"],
                "refresh_token": auth_data["refreshToken"],
            }
        else:
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
    refresh_token = refresh_token_cookie or refresh_token_body
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    try:
        new_tokens = refresh_firebase_token(refresh_token)
        is_mobile = client_type and client_type.lower() == "mobile"
        
        if is_mobile:
            return {
                "message": "Token refreshed successfully",
                "token": new_tokens["token"],
                "refresh_token": new_tokens["refresh_token"]
            }
        else:
            response.set_cookie(key="access_token", value=new_tokens["token"], httponly=True, secure=True, samesite="lax", max_age=3600)
            response.set_cookie(key="refresh_token", value=new_tokens["refresh_token"], httponly=True, secure=True, samesite="lax", max_age=2592000)
            return {"message": "Token refreshed successfully"}
    
    except Exception as e:
        if not (client_type and client_type.lower() == "mobile"):
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/logout")
async def logout(
    response: Response, 
    client_type: Optional[str] = Header(None)
):
    try:
        if not (client_type and client_type.lower() == "mobile"):
            response.delete_cookie(key="access_token", httponly=True, secure=True, samesite="lax")
            response.delete_cookie(key="refresh_token", httponly=True, secure=True, samesite="lax")
        return {"message": "Logged out successfully"}
    except Exception:
        return {"message": "Logged out locally"}

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

@router.put("/password", summary="Update User Password")
async def update_password(
    data: LoginSchema,
    current_user: dict = Depends(verify_firebase_token)
):
    uid = current_user['uid']
    new_password = data.password.strip()
    
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password too short")

    try:
        auth.update_user(uid, password=new_password)
        return {"message": "Password updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update password")