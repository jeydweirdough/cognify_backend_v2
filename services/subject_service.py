# services/subject_service.py
"""
Subject management service for viewing and updating subjects/curriculum.
"""
from typing import Dict, List, Optional, Any
from fastapi import HTTPException, status
from services.crud_services import read_one, read_query, update, create, delete
from datetime import datetime
import uuid

async def get_all_subjects(
    requester_role: str,
    skip: int = 0,
    limit: int = 100
) -> List[Dict[str, Any]]:
    subjects = await read_query("subjects", [])
    subjects.sort(key=lambda x: x["data"].get("created_at", datetime.min), reverse=True)
    paginated = subjects[skip:skip + limit]
    
    result = []
    for subj in paginated:
        data = subj["data"]
        result.append({
            "id": subj["id"],
            "title": data.get("title"),
            "description": data.get("description"),
            "pqf_level": data.get("pqf_level"),
            "total_weight_percentage": data.get("total_weight_percentage"),
            "topics_count": len(data.get("topics", [])),
            "created_at": data.get("created_at"),
            "is_verified": data.get("is_verified", False),
            "is_active": data.get("is_active", True),
            "image_url": data.get("image_url"),
            "created_by": data.get("created_by")
        })
    return result

async def get_subject_by_id(subject_id: str, requester_role: str) -> Dict[str, Any]:
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Subject not found")
    
    result = {
        "id": subject_id,
        "title": subject.get("title"),
        "pqf_level": subject.get("pqf_level"),
        "total_weight_percentage": subject.get("total_weight_percentage"),
        "topics": subject.get("topics", []),
        "created_at": subject.get("created_at"),
        "updated_at": subject.get("updated_at"),
        "is_verified": subject.get("is_verified", False),
        "is_active": subject.get("is_active", True),
        "description": subject.get("description"),
        "image_url": subject.get("image_url"),
    }
    
    if requester_role in ["faculty_member", "admin"]:
        topics = subject.get("topics", [])
        topics_with_content = sum(1 for t in topics if t.get("lecture_content"))
        result["statistics"] = {
            "total_topics": len(topics),
            "completion_percentage": (topics_with_content / len(topics) * 100) if topics else 0
        }
    return result

async def create_subject(subject_data: Dict[str, Any], requester_id: str, requester_role: str, is_personal: bool):
    subject_id = str(uuid.uuid4())
    now = datetime.utcnow()
    payload = {
        "id": subject_id,
        "title": subject_data.get("title"),
        "description": subject_data.get("description"),
        "pqf_level": subject_data.get("pqf_level"),
        "topics": [],
        "created_at": now,
        "updated_at": now,
        "created_by": requester_id,
        "personal": is_personal,
        "is_verified": False,
        "is_active": True
    }

    if is_personal:
        await create(f"students/{requester_id}/subjects", payload, doc_id=subject_id)
        return {"message": "Personal subject created", "subject_id": subject_id}

    await create("subjects", payload, doc_id=subject_id)
    return {"message": "Subject created successfully", "subject_id": subject_id}

async def update_subject(subject_id: str, update_data: Dict[str, Any], requester_role: str) -> Dict[str, Any]:
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Subject not found")
    
    update_data["updated_at"] = datetime.utcnow()
    await update("subjects", subject_id, update_data)
    return {"message": "Subject updated", "subject_id": subject_id}

# [FIX] Added Verify Function
async def verify_subject(subject_id: str, verifier_id: str) -> Dict[str, Any]:
    subject = await read_one("subjects", subject_id)
    if not subject:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Subject not found")
    
    update_data = {
        "is_verified": True,
        "verified_at": datetime.utcnow(),
        "verified_by": verifier_id,
        "updated_at": datetime.utcnow()
    }
    
    await update("subjects", subject_id, update_data)
    return {
        "message": "Subject verified successfully",
        "subject_id": subject_id,
        "verified_at": update_data["verified_at"]
    }

async def delete_subject(subject_id: str):
    await delete("subjects", subject_id)
    return {"message": "Subject deleted successfully"}