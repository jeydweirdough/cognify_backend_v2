# services/subject_service.py
"""
Subject management service for viewing and updating subjects/curriculum.
"""
from typing import Dict, List, Optional, Any
from fastapi import HTTPException, status
from services.crud_services import read_one, read_query, update, create, delete
from services.role_service import get_user_role_designation
from datetime import datetime


async def get_all_subjects(
    requester_role: str,
    skip: int = 0,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get all subjects with pagination.
    All roles can view subjects, but with different detail levels.
    """
    subjects = await read_query("subjects", [])
    
    # Sort by created_at or title
    subjects.sort(key=lambda x: x["data"].get("created_at", datetime.min), reverse=True)
    
    # Apply pagination
    paginated = subjects[skip:skip + limit]
    
    # Format based on role
    result = []
    for subj in paginated:
        data = subj["data"]
        
        subject_info = {
            "id": subj["id"],
            "title": data.get("title"),
            "pqf_level": data.get("pqf_level"),
            "total_weight_percentage": data.get("total_weight_percentage"),
            "topics_count": len(data.get("topics", [])),
            "created_at": data.get("created_at")
        }
        
        # Include full details for faculty and admin
        if requester_role in ["faculty_member", "admin"]:
            subject_info["topics"] = data.get("topics", [])
            subject_info["description"] = data.get("description")
        
        result.append(subject_info)
    
    return result


async def get_subject_by_id(
    subject_id: str,
    requester_role: str
) -> Dict[str, Any]:
    """
    Get detailed subject information including topics and competencies.
    """
    subject = await read_one("subjects", subject_id)
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # All roles can view basic info
    result = {
        "id": subject_id,
        "title": subject.get("title"),
        "pqf_level": subject.get("pqf_level"),
        "total_weight_percentage": subject.get("total_weight_percentage"),
        "topics": subject.get("topics", []),
        "created_at": subject.get("created_at"),
        "updated_at": subject.get("updated_at")
    }
    
    # Add extra details for faculty/admin
    if requester_role in ["faculty_member", "admin"]:
        result["description"] = subject.get("description")
        
        # Calculate statistics
        topics = subject.get("topics", [])
        total_competencies = sum(len(t.get("competencies", [])) for t in topics)
        topics_with_content = sum(1 for t in topics if t.get("lecture_content"))
        
        result["statistics"] = {
            "total_topics": len(topics),
            "total_competencies": total_competencies,
            "topics_with_modules": topics_with_content,
            "completion_percentage": (topics_with_content / len(topics) * 100) if topics else 0
        }
    
    return result


async def get_subject_topics(
    subject_id: str,
    topic_id: Optional[str] = None
) -> List[Dict[str, Any]] | Dict[str, Any]:
    """
    Get topics for a subject, or a specific topic if topic_id provided.
    """
    subject = await read_one("subjects", subject_id)
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    topics = subject.get("topics", [])
    
    # Return specific topic if requested
    if topic_id:
        topic = next((t for t in topics if t.get("id") == topic_id), None)
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found"
            )
        return topic
    
    return topics


async def get_topic_competencies(
    subject_id: str,
    topic_id: str
) -> List[Dict[str, Any]]:
    """
    Get competencies for a specific topic.
    """
    subject = await read_one("subjects", subject_id)
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    topics = subject.get("topics", [])
    topic = next((t for t in topics if t.get("id") == topic_id), None)
    
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found"
        )
    
    return topic.get("competencies", [])


async def update_subject(
    subject_id: str,
    update_data: Dict[str, Any],
    requester_role: str
) -> Dict[str, Any]:
    """
    Update subject information.
    Only faculty and admin can update.
    """
    if requester_role not in ["faculty_member", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admin can update subjects"
        )
    
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Add update timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update in database
    await update("subjects", subject_id, update_data)
    
    return {
        "message": "Subject updated successfully",
        "subject_id": subject_id,
        "updated_fields": list(update_data.keys())
    }


async def update_topic(
    subject_id: str,
    topic_id: str,
    topic_updates: Dict[str, Any],
    requester_role: str
) -> Dict[str, Any]:
    """
    Update a specific topic within a subject.
    """
    if requester_role not in ["faculty_member", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admin can update topics"
        )
    
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    topics = subject.get("topics", [])
    topic_index = next((i for i, t in enumerate(topics) if t.get("id") == topic_id), None)
    
    if topic_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found"
        )
    
    # Update topic fields
    for key, value in topic_updates.items():
        if key != "id":  # Don't allow ID changes
            topics[topic_index][key] = value
    
    # Save back to database
    await update("subjects", subject_id, {
        "topics": topics,
        "updated_at": datetime.utcnow()
    })
    
    return {
        "message": "Topic updated successfully",
        "subject_id": subject_id,
        "topic_id": topic_id,
        "updated_fields": list(topic_updates.keys())
    }


async def update_competency(
    subject_id: str,
    topic_id: str,
    competency_id: str,
    competency_updates: Dict[str, Any],
    requester_role: str
) -> Dict[str, Any]:
    """
    Update a specific competency within a topic.
    """
    if requester_role not in ["faculty_member", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admin can update competencies"
        )
    
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    topics = subject.get("topics", [])
    topic_index = next((i for i, t in enumerate(topics) if t.get("id") == topic_id), None)
    
    if topic_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found"
        )
    
    competencies = topics[topic_index].get("competencies", [])
    comp_index = next((i for i, c in enumerate(competencies) if c.get("id") == competency_id), None)
    
    if comp_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competency not found"
        )
    
    # Update competency fields
    for key, value in competency_updates.items():
        if key != "id":
            competencies[comp_index][key] = value
    
    topics[topic_index]["competencies"] = competencies
    
    # Save back to database
    await update("subjects", subject_id, {
        "topics": topics,
        "updated_at": datetime.utcnow()
    })
    
    return {
        "message": "Competency updated successfully",
        "subject_id": subject_id,
        "topic_id": topic_id,
        "competency_id": competency_id,
        "updated_fields": list(competency_updates.keys())
    }


async def add_topic_to_subject(
    subject_id: str,
    topic_data: Dict[str, Any],
    requester_role: str
) -> Dict[str, Any]:
    """
    Add a new topic to a subject.
    """
    if requester_role not in ["faculty_member", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty and admin can add topics"
        )
    
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    topics = subject.get("topics", [])
    
    # Generate ID if not provided
    if "id" not in topic_data:
        import uuid
        topic_data["id"] = str(uuid.uuid4())
    
    topics.append(topic_data)
    
    await update("subjects", subject_id, {
        "topics": topics,
        "updated_at": datetime.utcnow()
    })
    
    return {
        "message": "Topic added successfully",
        "subject_id": subject_id,
        "topic_id": topic_data["id"]
    }


async def delete_topic_from_subject(
    subject_id: str,
    topic_id: str,
    requester_role: str
) -> Dict[str, Any]:
    """
    Remove a topic from a subject.
    Only admin can delete topics.
    """
    if requester_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can delete topics"
        )
    
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    topics = subject.get("topics", [])
    updated_topics = [t for t in topics if t.get("id") != topic_id]
    
    if len(updated_topics) == len(topics):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found"
        )
    
    await update("subjects", subject_id, {
        "topics": updated_topics,
        "updated_at": datetime.utcnow()
    })
    
    return {
        "message": "Topic deleted successfully",
        "subject_id": subject_id,
        "deleted_topic_id": topic_id
    }


async def get_subject_statistics(subject_id: str) -> Dict[str, Any]:
    """
    Get statistics for a subject (questions, assessments, student progress).
    """
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Count related questions
    questions = await read_query("questions", [("subject_id", "==", subject_id)])
    verified_questions = [q for q in questions if q["data"].get("is_verified")]
    
    # Count assessments
    assessments = await read_query("assessments", [("subject_id", "==", subject_id)])
    
    # Count submissions
    submissions = await read_query("assessment_submissions", [("subject_id", "==", subject_id)])
    
    # Calculate average score
    scores = [s["data"].get("score", 0) for s in submissions]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    return {
        "subject_id": subject_id,
        "title": subject.get("title"),
        "questions": {
            "total": len(questions),
            "verified": len(verified_questions),
            "unverified": len(questions) - len(verified_questions)
        },
        "assessments": {
            "total": len(assessments)
        },
        "student_activity": {
            "total_submissions": len(submissions),
            "average_score": round(avg_score, 2)
        }
    }