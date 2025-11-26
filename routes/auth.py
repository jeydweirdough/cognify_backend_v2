# routes/auth.py
from fastapi import APIRouter, HTTPException, Request, status, Depends
from fastapi.responses import JSONResponse
from database.models import SignUpSchema, LoginSchema, UserProfileBase
from services.role_services import get_role_id_by_designation
from services.crud_services import read_query, read_one, update
from firebase_admin import auth
from core.firebase import db
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup_page(auth_data: SignUpSchema):
    """
    Register a new user. Email must be pre-registered by admin.
    """
    # 0. WHITELIST CHECK
    whitelist_entry = await read_query("pre_registered_users", [("email", "==", auth_data.email)])
    
    if not whitelist_entry:
        raise HTTPException(
            status_code=403, 
            detail="Email is not pre-registered by Admin. Please contact your administrator."
        )

    # Get the assigned role from whitelist
    assigned_role = whitelist_entry[0]["data"].get("assigned_role")

    # 1. Create Firebase Auth user
    try:
        fb_user = auth.create_user(
            email=auth_data.email, 
            password=auth_data.password
        )
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail=f"Account with email {auth_data.email} already exists.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Create Firestore profile
    try:
        profile_payload = UserProfileBase(
            email=fb_user.email,
            first_name=auth_data.first_name,
            last_name=auth_data.last_name,
            role_id=await get_role_id_by_designation(assigned_role),
            is_verified=True,  # Auto-verify since whitelisted
            is_registered=True,
            password=""  # Don't store password
        )
        
        await db.collection("user_profiles").document(fb_user.uid).set(
            profile_payload.model_dump(exclude={"password"})
        )
        
        # Update whitelist entry to mark as registered
        await update("pre_registered_users", whitelist_entry[0]["id"], {
            "is_registered": True,
            "registered_at": datetime.utcnow(),
            "user_id": fb_user.uid
        })
        
        return {
            "message": "Successfully created user", 
            "uid": fb_user.uid, 
            "email": fb_user.email,
            "role": assigned_role
        }
    
    except Exception as e:
        # Rollback Firebase Auth user
        try:
            auth.delete_user(fb_user.uid)
        except Exception as rollback_e:
            raise HTTPException(
                status_code=500, 
                detail=f"CRITICAL: Profile creation failed, AND auth user rollback failed. {rollback_e}"
            )
        raise HTTPException(status_code=400, detail=f"Failed to create profile: {e}")


@router.post("/login")
async def login(credentials: LoginSchema):
    """
    Login endpoint. Returns custom token for Firebase authentication.
    """
    try:
        # Verify user exists in Firebase Auth by email
        user = auth.get_user_by_email(credentials.email)
        
        # Check if user profile exists and is verified
        profile = await read_one("user_profiles", user.uid)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        if not profile.get("is_verified"):
            raise HTTPException(status_code=403, detail="Account not verified by admin")
        
        # Create custom token
        custom_token = auth.create_custom_token(user.uid)
        
        # Log login activity
        await db.collection("login_logs").add({
            "user_id": user.uid,
            "email": credentials.email,
            "timestamp": datetime.utcnow(),
            "ip_address": None  # Add if needed
        })
        
        return {
            "message": "Login successful",
            "custom_token": custom_token.decode('utf-8'),
            "uid": user.uid,
            "email": user.email,
            "role_id": profile.get("role_id"),
            "profile": profile
        }
        
    except auth.UserNotFoundError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/logout")
async def logout(user_id: str):
    """
    Logout endpoint. Revokes refresh tokens.
    """
    try:
        auth.revoke_refresh_tokens(user_id)
        
        # Log logout activity
        await db.collection("logout_logs").add({
            "user_id": user_id,
            "timestamp": datetime.utcnow()
        })
        
        return {"message": "Logout successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")


@router.post("/forgot-password")
async def forgot_password(email: str):
    """
    Send password reset email.
    """
    try:
        # Verify email exists
        user = auth.get_user_by_email(email)
        
        # Generate password reset link
        link = auth.generate_password_reset_link(email)
        
        # TODO: Send email with link
        # For now, return the link (in production, send via email service)
        
        return {
            "message": "Password reset link sent to email",
            "reset_link": link  # Remove in production
        }
        
    except auth.UserNotFoundError:
        # Don't reveal if email exists or not for security
        return {"message": "If email exists, password reset link has been sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password reset failed: {str(e)}")


@router.post("/verify-token")
async def verify_token(token: str):
    """
    Verify Firebase ID token.
    """
    try:
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token['uid']
        
        profile = await read_one("user_profiles", user_id)
        
        return {
            "valid": True,
            "uid": user_id,
            "email": decoded_token.get('email'),
            "profile": profile
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")