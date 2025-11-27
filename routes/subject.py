# routes/subjects.py
"""
Subject/Curriculum management routes.
View and update subjects, topics, and competencies.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from core.security import verify_firebase_token
from database.models import CompetencyUpdateRequest, SubjectUpdateRequest, TopicCreateRequest, TopicUpdateRequest
from services.subject_service import (
    get_all_subjects,
    get_subject_by_id,
    get_subject_topics,
    get_topic_competencies,
    update_subject,
    update_topic,
    update_competency,
    add_topic_to_subject,
    delete_topic_from_subject,
    get_subject_statistics
)
from services.profile_service import get_user_profile_with_role


router = APIRouter(prefix="/subjects", tags=["Subjects & Curriculum"])

# ========================================
# VIEW SUBJECTS
# ========================================

@router.get("/", summary="Get all subjects")
async def list_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Get list of all subjects with pagination.
    All roles can view subjects.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    
    subjects = await get_all_subjects(role, skip, limit)
    
    return {
        "total": len(subjects),
        "skip": skip,
        "limit": limit,
        "subjects": subjects
    }


@router.get("/{subject_id}", summary="Get subject by ID")
async def get_subject(
    subject_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Get detailed subject information including topics and competencies.
    All roles can view.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    
    subject = await get_subject_by_id(subject_id, role)
    
    return subject


@router.get("/{subject_id}/topics", summary="Get all topics for subject")
async def get_topics(
    subject_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Get all topics for a specific subject.
    """
    topics = await get_subject_topics(subject_id)
    
    return {
        "subject_id": subject_id,
        "total_topics": len(topics),
        "topics": topics
    }


@router.get("/{subject_id}/topics/{topic_id}", summary="Get specific topic")
async def get_topic(
    subject_id: str,
    topic_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Get details of a specific topic.
    """
    topic = await get_subject_topics(subject_id, topic_id)
    
    return {
        "subject_id": subject_id,
        "topic": topic
    }


@router.get("/{subject_id}/topics/{topic_id}/competencies", summary="Get topic competencies")
async def get_competencies(
    subject_id: str,
    topic_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Get all competencies for a specific topic.
    """
    competencies = await get_topic_competencies(subject_id, topic_id)
    
    return {
        "subject_id": subject_id,
        "topic_id": topic_id,
        "total_competencies": len(competencies),
        "competencies": competencies
    }


@router.get("/{subject_id}/statistics", summary="Get subject statistics")
async def get_statistics(
    subject_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Get statistics for a subject (questions, assessments, performance).
    Faculty and admin only.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    
    if role not in ["faculty_member", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admin can view statistics"
        )
    
    statistics = await get_subject_statistics(subject_id)
    
    return statistics


# ========================================
# UPDATE SUBJECTS
# ========================================

@router.put("/{subject_id}", summary="Update subject")
async def update_subject_route(
    subject_id: str,
    updates: SubjectUpdateRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Update subject information.
    Faculty and admin only.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    
    # Convert to dict and remove None values
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    result = await update_subject(subject_id, update_data, role)
    
    return result


@router.put("/{subject_id}/topics/{topic_id}", summary="Update topic")
async def update_topic_route(
    subject_id: str,
    topic_id: str,
    updates: TopicUpdateRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Update a specific topic within a subject.
    Faculty and admin only.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    result = await update_topic(subject_id, topic_id, update_data, role)
    
    return result


@router.put("/{subject_id}/topics/{topic_id}/competencies/{competency_id}", 
    summary="Update competency")
async def update_competency_route(
    subject_id: str,
    topic_id: str,
    competency_id: str,
    updates: CompetencyUpdateRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Update a specific competency within a topic.
    Faculty and admin only.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    result = await update_competency(subject_id, topic_id, competency_id, update_data, role)
    
    return result


# ========================================
# ADD/DELETE TOPICS
# ========================================

@router.post("/{subject_id}/topics", summary="Add topic to subject")
async def add_topic(
    subject_id: str,
    topic: TopicCreateRequest,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Add a new topic to a subject.
    Faculty and admin only.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    
    result = await add_topic_to_subject(subject_id, topic.model_dump(), role)
    
    return result


@router.delete("/{subject_id}/topics/{topic_id}", summary="Delete topic")
async def delete_topic(
    subject_id: str,
    topic_id: str,
    current_user: dict = Depends(verify_firebase_token)
):
    """
    Delete a topic from a subject.
    Admin only.
    """
    _, role = await get_user_profile_with_role(current_user["uid"])
    
    result = await delete_topic_from_subject(subject_id, topic_id, role)
    
    return result