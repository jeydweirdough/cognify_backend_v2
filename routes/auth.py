from fastapi import APIRouter, HTTPException, Request, status, Depends
from fastapi.responses import JSONResponse
from database.models import SignUpSchema, LoginSchema, UserProfileBase
from services.role_services import get_role_id_by_designation
from services.crud_services import read_query # Added import
from firebase_admin import auth
from core.firebase import db

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup_page(auth_data: SignUpSchema):
    # 0. WHITELIST CHECK
    # Check if the email exists in 'pre_registered_users' collection
    whitelist_entry = await read_query("pre_registered_users", [("email", "==", auth_data.email)])
    
    if not whitelist_entry:
        raise HTTPException(
            status_code=403, 
            detail="Email is not pre-registered by Admin. Please contact your administrator."
        )

    # 1. Create Firebase Auth user first
    try:
        fb_user = auth.create_user(
            email=auth_data.email, 
            password=auth_data.password
        )
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail=f"Account with email {auth_data.email} already exists.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. If Auth user succeeds, create the Firestore profile
    try:
        profile_payload = UserProfileBase(
            email=fb_user.email,
            first_name=auth_data.first_name,
            last_name=auth_data.last_name,
            role_id=get_role_id_by_designation(auth_data.role),
            is_verified=True, # Auto-verify since they are whitelisted
            is_registered=True
        )
        
        await db.collection("user_profiles").document(fb_user.uid).set(profile_payload.dict(exclude={"password"}))
        
        return {"message": "Successfully created user", "uid": fb_user.uid, "email": fb_user.email}
    
    except Exception as e:
        # --- ROLLBACK ---
        try:
            auth.delete_user(fb_user.uid)
        except Exception as rollback_e:
            raise HTTPException(status_code=500, detail=f"CRITICAL: Profile creation failed, AND auth user rollback failed. {rollback_e}")
        raise HTTPException(status_code=400, detail=f"Failed to create profile: {e}")