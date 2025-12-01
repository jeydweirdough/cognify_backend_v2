# services/admin_service.py
from typing import List, Dict, Any
from services.crud_services import read_query, read_one
from database.enums import UserRole
from database.models import MaterialVerificationQueue

async def get_verification_queue() -> List[Dict[str, Any]]:
    """
    Aggregates unverified content from Subjects, Modules, and Assessments.
    """
    queue = []

    # 1. Fetch Pending Subjects
    subjects = await read_query("subjects", [("is_verified", "==", False)])
    for s in subjects:
        data = s["data"]
        # Get creator name
        creator_name = "Unknown"
        if data.get("created_by"):
            user = await read_one("user_profiles", data["created_by"])
            if user:
                creator_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

        queue.append({
            "item_id": s["id"],
            "type": "subject",
            "title": data.get("title", "Untitled Subject"),
            "submitted_by": creator_name,
            "submitted_at": data.get("created_at"),
            "details": data.get("description", "")[:100] + "..."
        })

    # 2. Fetch Pending Modules
    modules = await read_query("modules", [("is_verified", "==", False)])
    for m in modules:
        data = m["data"]
        creator_name = "Unknown"
        if data.get("created_by"):
            user = await read_one("user_profiles", data["created_by"])
            if user:
                creator_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

        queue.append({
            "item_id": m["id"],
            "type": "module",
            "title": data.get("title", "Untitled Module"),
            "submitted_by": creator_name,
            "submitted_at": data.get("created_at"),
            "details": data.get("purpose", "")[:100] + "..."
        })

    # 3. Fetch Pending Assessments
    assessments = await read_query("assessments", [("is_verified", "==", False)])
    for a in assessments:
        data = a["data"]
        creator_name = "Unknown"
        if data.get("created_by"):
            user = await read_one("user_profiles", data["created_by"])
            if user:
                creator_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

        queue.append({
            "item_id": a["id"],
            "type": "assessment",
            "title": data.get("title", "Untitled Assessment"),
            "submitted_by": creator_name,
            "submitted_at": data.get("created_at"),
            "details": f"{data.get('total_items', 0)} items - {data.get('description', '')}"[:100]
        })

    # Sort by date descending (newest first)
    # Handle cases where submitted_at might be None string/isoformat issues
    queue.sort(key=lambda x: str(x["submitted_at"]), reverse=True)

    return queue

async def get_system_statistics() -> Dict[str, Any]:
    """
    Aggregates counts for the Admin Dashboard.
    """
    # Users
    all_users = await read_query("user_profiles", [])
    role_counts = {"student": 0, "faculty_member": 0, "admin": 0}
    
    # Whitelist
    whitelist = await read_query("whitelist", [])
    whitelist_student = sum(1 for w in whitelist if w["data"].get("assigned_role") == "student")
    whitelist_faculty = sum(1 for w in whitelist if w["data"].get("assigned_role") == "faculty_member")

    # Content
    subjects = await read_query("subjects", [])
    modules = await read_query("modules", [])
    assessments = await read_query("assessments", [])
    questions = await read_query("questions", [])

    # Process Users
    # We need to fetch roles to map ID -> Designation
    all_roles = await read_query("roles", [])
    role_map = {r["id"]: r["data"]["designation"] for r in all_roles}

    verified_users = 0
    pending_users = 0

    for u in all_users:
        data = u["data"]
        role_id = data.get("role_id")
        designation = role_map.get(role_id, "student")
        
        if designation in role_counts:
            role_counts[designation] += 1
            
        if data.get("is_verified"):
            verified_users += 1
        else:
            pending_users += 1

    return {
        "total_users": len(all_users),
        "by_role": role_counts,
        "whitelist_students": whitelist_student,
        "whitelist_faculty": whitelist_faculty,
        "verified_users": verified_users,
        "pending_verification": pending_users, # User verification
        
        "total_subjects": len(subjects),
        "total_modules": len(modules),
        "pending_modules": sum(1 for m in modules if not m["data"].get("is_verified")),
        
        "total_assessments": len(assessments),
        "pending_assessments": sum(1 for a in assessments if not a["data"].get("is_verified")),
        
        "pending_questions": sum(1 for q in questions if not q["data"].get("is_verified"))
    }