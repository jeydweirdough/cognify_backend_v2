# routes/auth.py
from fastapi import APIRouter, HTTPException, status, Depends
from firebase_admin import auth
from database.models import LoginSchema, SignUpSchema, UserProfileBase
from services.crud_services import create, read_query
from services.role_services import get_role_id_by_designation
from utils.firebase_utils import firebase_login_with_email
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(auth_data: SignUpSchema):
    """
    1. Validates email is in pre-registered whitelist.
    2. Creates Firebase Auth User.
    3. Creates Firestore User Profile.
    """
    # 1. Check Whitelist (Logic from your provided files)
    # Note: Ensure 'pre_registered_users' collection exists in Firestore
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
            display_name=f"{auth_data.first_name} {auth_data.last_name}"
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
            # Do not save password to Firestore
        )
        
        # Convert to dict and remove password if present in model
        data_dict = profile_data.model_dump(exclude={"password"})
        
        # Save to 'user_profiles' using UID as document ID
        await create("user_profiles", data_dict, doc_id=fb_user.uid)
        
        return {"message": "User created successfully", "uid": fb_user.uid}

    except Exception as e:
        # Rollback: Delete the Auth user if DB save fails to prevent "ghost" accounts
        try:
            auth.delete_user(fb_user.uid)
        except:
            pass # Critical error logging should happen here
        raise HTTPException(status_code=500, detail=f"Profile creation failed: {str(e)}")


@router.post("/login")
async def login(credentials: LoginSchema):
    """
    Exchanges Email/Password for a Firebase ID Token.
    """
    try:
        # 1. Login via REST API
        auth_data = firebase_login_with_email(credentials.email, credentials.password)
        
        # 2. (Optional) Check Firestore profile status (e.g., is_deleted, is_active)
        # This ensures disabled users in DB cannot access API even if they have a token
        # profile = await read_one("user_profiles", auth_data["localId"])
        
        return {
            "message": "Login successful",
            "token": auth_data["idToken"], # Send this as "Bearer <token>"
            "refresh_token": auth_data["refreshToken"],
            "uid": auth_data["localId"]
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))