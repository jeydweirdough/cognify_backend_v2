# routes/analytics.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from core.security import allowed_users
from services.analytics_service import (
    calculate_passing_rate,
    predict_student_passing_probability,
    analyze_student_weaknesses,
    get_subject_analytics,
    recommend_study_modules
)

router = APIRouter(prefix="/analytics", tags=["Analytics & Insights"])

@router.get("/passing-rate")
async def get_passing_rate(
    subject_id: Optional[str] = Query(None),
    assessment_id: Optional[str] = Query(None),
    current_user: dict = Depends(allowed_users(["admin", "teacher"]))
):
    """
    Get passing rate statistics for assessments.
    Can filter by subject or specific assessment.
    """
    return await calculate_passing_rate(subject_id, assessment_id)


@router.get("/student/{user_id}/passing-probability")
async def get_passing_probability(
    user_id: str,
    subject_id: str,
    current_user: dict = Depends(allowed_users(["admin", "teacher", "student"]))
):
    """
    Predict probability of student passing based on ML model.
    Uses student behavior, performance history, and engagement metrics.
    """
    # Students can only view their own predictions
    if current_user.get("role") == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await predict_student_passing_probability(user_id, subject_id)


@router.get("/student/{user_id}/weaknesses")
async def get_student_weaknesses(
    user_id: str,
    subject_id: str,
    current_user: dict = Depends(allowed_users(["admin", "teacher", "student"]))
):
    """
    Analyze student's weak competencies and get study recommendations.
    """
    if current_user.get("role") == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await analyze_student_weaknesses(user_id, subject_id)


@router.get("/student/{user_id}/recommendations")
async def get_study_recommendations(
    user_id: str,
    subject_id: str,
    current_user: dict = Depends(allowed_users(["admin", "teacher", "student"]))
):
    """
    Get personalized module recommendations based on:
    - Weak competencies
    - Learning behavior
    - Study patterns
    """
    if current_user.get("role") == "student" and current_user["uid"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get weaknesses first
    analysis = await analyze_student_weaknesses(user_id, subject_id)
    
    return {
        "user_id": user_id,
        "subject_id": subject_id,
        "recommendations": analysis.get("recommendations", []),
        "based_on_weaknesses": analysis.get("weaknesses", [])
    }


@router.get("/subject/{subject_id}/overview")
async def get_subject_overview(
    subject_id: str,
    current_user: dict = Depends(allowed_users(["admin", "teacher"]))
):
    """
    Comprehensive analytics dashboard for a subject:
    - Passing rates
    - Completion rates
    - Difficult topics
    - Engagement metrics
    """
    return await get_subject_analytics(subject_id)


@router.get("/dashboard/teacher")
async def get_teacher_dashboard(
    current_user: dict = Depends(allowed_users(["teacher"]))
):
    """
    Teacher dashboard with all their subjects' analytics.
    """
    # TODO: Get subjects taught by this teacher
    # For now, return placeholder
    return {
        "teacher_id": current_user["uid"],
        "message": "Teacher dashboard - implement subject filtering",
        "subjects": []
    }


@router.get("/dashboard/admin")
async def get_admin_dashboard(
    current_user: dict = Depends(allowed_users(["admin"]))
):
    """
    Admin dashboard with system-wide analytics.
    """
    # TODO: Implement system-wide statistics
    return {
        "total_students": 0,
        "total_teachers": 0,
        "total_subjects": 0,
        "overall_passing_rate": 0.0,
        "message": "Admin dashboard - implement system-wide stats"
    }