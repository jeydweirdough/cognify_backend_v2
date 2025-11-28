# routes/auth.py
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends, Body
from firebase_admin import auth
from pydantic import BaseModel
from database.models import LoginSchema, SignUpSchema, UserProfileBase
from services.crud_services import create, read_query, update
from services.role_service import get_role_id_by_designation, decode_user, get_user_role_designation, get_user_role_id
from utils.firebase_utils import firebase_login_with_email, refresh_firebase_token
from core.security import verify_firebase_token
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Schema for Refresh Token Request
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
async def login(credentials: LoginSchema):
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
        
        return {
            "message": "Login successful",
            "token": auth_data["idToken"], 
            "refresh_token": auth_data["refreshToken"],
            "uid": auth_data["localId"]
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_token(request: RefreshTokenSchema):
    """
    Called by frontend axios interceptor when 401 occurs.
    Returns new access token and refresh token.
    """
    try:
        new_tokens = refresh_firebase_token(request.refresh_token)
        return {
            "token": new_tokens["token"],
            "refresh_token": new_tokens["refresh_token"]
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/logout")
async def logout(current_user: dict = Depends(verify_firebase_token)):
    """
    Revokes the user's refresh tokens on Firebase to invalidate the session.
    Requires a valid access token in the Authorization header.
    """
    try:
        uid = current_user['uid']
        auth.revoke_refresh_tokens(uid)
        return {"message": "Logged out successfully"}
    except Exception as e:
        # Even if revocation fails, the frontend clears cookies, so we just log warning
        print(f"Logout revocation failed: {e}")
        return {"message": "Logged out locally"}

@router.post("/permission")
async def check_permission(current_user: dict = Depends(verify_firebase_token), request: dict = Body(...)):
    try:
        uid = current_user['uid']
        role_id = await get_user_role_id(uid)
        role_designation = await get_user_role_designation(role_id)

        print(f"User Role Designation: {uid}")
        
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