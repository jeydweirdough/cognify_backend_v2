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
    
# Add to routes/auth.py
@router.post("/admin/whitelist", status_code=status.HTTP_201_CREATED)
async def whitelist_email(
    email: str = Body(...),
    assigned_role: str = Body(default="Student"),
    current_user: dict = Depends(verify_firebase_token)
):
    """Admin endpoint to whitelist an email for registration"""
    # Verify admin role
    user_role = await get_user_role_designation(await get_user_role_id(current_user['uid']))
    if user_role not in ["admin", "faculty_member"]:  # Adjust to stored designations
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
    Registers a new user. 
    Requires the email to be pre-registered (whitelisted) by an admin in 'pre_registered_users'.
    """
    try:
        # 1. Verify Whitelist / Pre-registration
        # Check if the email exists in the whitelist
        whitelist_entries = await read_query("whitelist", [("email", "==", auth_data.email)])
        
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

        # 2. Check if username already exists (if provided)
        if auth_data.username:
            existing_username = await read_query("user_profiles", [("username", "==", auth_data.username)])
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username is already taken."
                )

        # 3. Create User in Firebase Authentication
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

        # 4. Determine Role from Whitelist
        # The whitelist is the source of truth for the role (e.g., 'Student', 'Faculty').
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
        
        # Fallback to Student if resolution fails (safety net)
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
            "is_verified": True, # Whitelisted users are implicitly verified
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "profile_image": None
        }
        
        # Save to 'user_profiles'
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
        # Re-raise HTTP exceptions as-is
        raise he
    except Exception as e:
        # Log unexpected errors and return generic message
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
    # [FIX] Removed 'current_user' dependency to allow logout even if token is expired
    client_type: Optional[str] = Header(None)
):
    """
    Logout with support for both web and mobile.
    Does not require authentication to ensure cookies are always cleared.
    """
    try:
        # If you wanted to revoke tokens, you would need the uid here.
        # Since we removed the dependency to fix the loop, we focus on clearing cookies.
        
        # Only clear cookies for web clients
        if not (client_type and client_type.lower() == "mobile"):
            # [FIX] Explicitly delete with same attributes to ensure removal
            response.delete_cookie(key="access_token", httponly=True, secure=True, samesite="lax")
            response.delete_cookie(key="refresh_token", httponly=True, secure=True, samesite="lax")
        
        return {"message": "Logged out successfully"}
    
    except Exception as e:
        print(f"Logout error: {e}")
        # Even if error, try to clear cookies
        if not (client_type and client_type.lower() == "mobile"):
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
        return {"message": "Logged out locally"}
    
    except Exception as e:
        print(f"Logout revocation failed: {e}")
        if not (client_type and client_type.lower() == "mobile"):
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
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

# [FIX] Added Password Update Route reusing LoginSchema
@router.put("/password", summary="Update User Password")
async def update_password(
    data: LoginSchema, # Reuses email + password schema
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Updates the password for the currently authenticated user.
    """
    uid = current_user['uid']
    new_password = data.password.strip()
    
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Password must be at least 8 characters long."
        )

    try:
        # Use Firebase Admin SDK to update the password
        auth.update_user(uid, password=new_password)
        return {"message": "Password updated successfully"}
        
    except Exception as e:
        print(f"Password update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password."
        )