# routes/auth.py
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response, status, Depends, Body, Cookie
from firebase_admin import auth
from pydantic import BaseModel
from database.models import LoginSchema, SignUpSchema, UserProfileBase
from services.crud_services import create, read_query, update
from services.role_service import get_role_id_by_designation, decode_user, get_user_role_designation, get_user_role_id
from utils.firebase_utils import firebase_login_with_email, refresh_firebase_token
from core.security import verify_firebase_token
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Schema for Refresh Token Request - REMOVED or kept unused if needed elsewhere
class RefreshTokenSchema(BaseModel):
    refresh_token: str

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(auth_data: SignUpSchema):
    """
    1. Validates email is in pre-registered whitelist.
    2. Creates Firebase Auth User.
    3. Creates Firestore User Profile.
    """
    # 1. Check Whitelist
    whitelist_entry = await read_query("pre_registered_users", [("email", "==", auth_data.email)])
    
    if not whitelist_entry:
        raise HTTPException(
            status_code=403, 
            detail="Email is not pre-registered. Contact admin."
        )
    
    assigned_role_name = whitelist_entry[0]["data"].get("assigned_role", "student")
    
    # 2. Get Role ID
    role_id = await get_role_id_by_designation(assigned_role_name)
    if not role_id:
        raise HTTPException(status_code=500, detail=f"Role configuration error: '{assigned_role_name}' not found.")

    # 3. Create Firebase Auth User
    try:
        fb_user = auth.create_user(
            email=auth_data.email,
            password=auth_data.password,
        )
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Email already registered.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth creation failed: {str(e)}")

    # 4. Create Firestore Profile
    try:
        profile_data = UserProfileBase(
            email=auth_data.email,
            first_name=auth_data.first_name,
            last_name=auth_data.last_name,
            role_id=role_id,
            is_verified=True,
            is_registered=True,
        )
        
        data_dict = profile_data.model_dump(exclude={"password"})
        
        # Save to 'user_profiles' using UID as document ID
        await create("user_profiles", data_dict, doc_id=fb_user.uid)

        try:
            await update(
                "pre_registered_users",
                whitelist_entry[0]["id"],
                {
                    "is_registered": True,
                    "registered_at": datetime.utcnow(),
                    "user_id": fb_user.uid
                }
            )
        except Exception:
            pass
        
        return {"message": "User created successfully", "uid": fb_user.uid}

    except Exception as e:
        # Rollback
        try:
            auth.delete_user(fb_user.uid)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Profile creation failed: {str(e)}")


@router.post("/login")
async def login(credentials: LoginSchema, response: Response):
    """
    Exchanges Email/Password for a Firebase ID Token.
    Frontend expects: { token, refresh_token, uid, message }
    """
    try:
        existing_profiles = await read_query("user_profiles", [("email", "==", credentials.email)])
        if not existing_profiles:
            raise HTTPException(status_code=403, detail="Account not registered")
        profile = existing_profiles[0]["data"]
        if not (profile.get("is_registered") and profile.get("is_verified")):
            raise HTTPException(status_code=403, detail="Account not verified or not registered")

        auth_data = firebase_login_with_email(credentials.email, credentials.password)
        
        # Set HTTP-only cookies
        response.set_cookie(
            key="access_token",
            value=auth_data["idToken"],
            httponly=True,
            secure=True,  # HTTPS only
            samesite="lax",
            max_age=3600  # 1 hour
        )
        
        response.set_cookie(
            key="refresh_token",
            value=auth_data["refreshToken"],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=2592000  # 30 days
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
    refresh_token: Optional[str] = Cookie(None)
):
    """
    Called by frontend axios interceptor when 401 occurs.
    1. Reads 'refresh_token' from HttpOnly cookie (NOT body).
    2. Refreshes token with Firebase.
    3. Sets NEW cookies in response.
    """
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing in cookies")

    try:
        new_tokens = refresh_firebase_token(refresh_token)
        
        # [FIX] Set the new tokens as cookies so the browser updates them
        response.set_cookie(
            key="access_token",
            value=new_tokens["token"], # Typically 'id_token' or 'access_token' from Firebase response
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600 # 1 hour
        )
        
        response.set_cookie(
            key="refresh_token",
            value=new_tokens["refresh_token"],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=2592000 # 30 days
        )

        return {"message": "Token refreshed successfully"}
        
    except Exception as e:
        print(f"Refresh failed: {e}")
        # Clear cookies if refresh fails so frontend redirects to login cleanly
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.post("/logout")
async def logout(response: Response, current_user: dict = Depends(verify_firebase_token)):
    """
    Revokes the user's refresh tokens on Firebase to invalidate the session.
    Requires a valid access token in the Authorization header.
    """
    try:
        uid = current_user['uid']
        auth.revoke_refresh_tokens(uid)
        
        # Clear cookies on logout
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        
        return {"message": "Logged out successfully"}
    except Exception as e:
        print(f"Logout revocation failed: {e}")
        # Force clear cookies even if revocation fails
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return {"message": "Logged out locally"}

@router.post("/permission")
async def check_permission(current_user: dict = Depends(verify_firebase_token), request: dict = Body(...)):
    try:
        uid = current_user['uid']
        role_id = await get_user_role_id(uid)
        role_designation = await get_user_role_designation(role_id)

        print(f"User Role Designation: {role_designation}")
        
        if "designation" in request:
            requested = request["designation"]
            # Accept a single designation string or a list/tuple of designations
            if isinstance(requested, (list, tuple)):
                has_permission = role_designation in requested
            else:
                has_permission = role_designation == requested
            return {"has_permission": has_permission}
        
        return {"role_designation": role_designation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))