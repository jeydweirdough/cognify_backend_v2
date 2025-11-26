from fastapi import APIRouter, Depends, HTTPException, status
from services.student_service import update_student_readiness
from services.crud_services import read_one
from core.security import allowed_users

router = APIRouter(prefix="/student", tags=["Student Analytics"])

@router.get("/profile/{user_id}")
async def get_student_profile(user_id: str, current_user: dict = Depends(allowed_users(["student", "teacher", "admin"]))):
    """
    Fetches the full student profile including AI-generated insights.
    """
    # Security check: Students can only view their own profile
    if current_user["role"] == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    profile = await read_one("user_profiles", user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
        
    return profile

@router.post("/analyze-readiness/{user_id}")
async def analyze_readiness(user_id: str, current_user: dict = Depends(allowed_users(["student", "teacher"]))):
    """
    Triggers the ONNX AI Model to re-calculate the student's 'Personal Readiness Level'
    based on their latest progress and timeliness data.
    """
    if current_user["role"] == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Call the service that uses the joblib/onnx model
    result = await update_student_readiness(user_id)
    
    return result