from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from services.module_matcher import auto_categorize_module
from services.crud_services import update, read_one, create
from services.upload_service import upload_file # Import our new local uploader
from core.security import allowed_users
from database.models import SubjectSchema
from datetime import datetime

router = APIRouter(prefix="/modules", tags=["Module Management"], dependencies=[Depends(allowed_users(["faculty_member", "admin"]))])

@router.post("/upload-smart", summary="Upload Module with AI Auto-Categorization")
async def upload_module_smart(
    subject_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Faculty uploads a PDF. 
    1. AI reads it for categorization.
    2. File is saved locally.
    3. Database is updated.
    """
    
    # 1. Read File Content for AI
    content = await file.read()
    
    # 2. Run AI Categorization
    ai_decision = await auto_categorize_module(content, subject_id)
    
    target_topic_id = ai_decision.get("matched_topic_id")
    if not target_topic_id:
         raise HTTPException(status_code=400, detail="AI could not match this module to any topic in the TOS.")

    # 3. Save File Locally
    # IMPORTANT: Reset file cursor to 0 because .read() moved it to the end
    await file.seek(0)
    file_url = await upload_file(file)
    
    # 4. Update the Database
    subject_data = await read_one("subjects", subject_id)
    if not subject_data:
        raise HTTPException(status_code=404, detail="Subject not found")

    topics = subject_data.get("topics", [])
    
    # Find and Update the specific topic
    topic_found = False
    for topic in topics:
        if topic["id"] == target_topic_id:
            topic["lecture_content"] = file_url
            topic_found = True
            break
            
    if topic_found:
        await update("subjects", subject_id, {"topics": topics})
        
        # Optional: Save a separate record for the Module if you have a 'modules' collection
        # await create("modules", { ... })

        return {
            "message": "Module successfully categorized and uploaded",
            "matched_topic": target_topic_id,
            "ai_reasoning": ai_decision.get("reasoning"),
            "file_url": file_url
        }
    else:
        raise HTTPException(status_code=500, detail="Matched topic ID not found in database structure.")
