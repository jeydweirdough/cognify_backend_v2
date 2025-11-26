from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from services.module_matcher import auto_categorize_module
from services.crud_services import update, read_one
from core.security import allowed_users
# Note: You need a helper to upload to Firebase Storage. 
# For this example, we'll simulate the URL generation.

router = APIRouter(prefix="/modules", tags=["Module Management"], dependencies=Depends(allowed_users(["faculty"])))

@router.post("/upload-smart", summary="Upload Module with AI Auto-Categorization")
async def upload_module_smart(
    subject_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Faculty uploads a PDF. 
    AI reads it, finds the correct Topic in the TOS, and attaches it automatically.
    """
    
    # 1. Read File Content
    content = await file.read()
    
    # 2. Run AI Categorization
    # Returns: { "matched_topic_id": "topic_123", "reasoning": "..." }
    ai_decision = await auto_categorize_module(content, subject_id)
    
    target_topic_id = ai_decision.get("matched_topic_id")
    
    if not target_topic_id:
         raise HTTPException(status_code=400, detail="AI could not match this module to any topic in the TOS.")

    # 3. (Mock) Upload File to Cloud Storage -> Get URL
    # file_url = await upload_to_firebase(file, f"modules/{subject_id}/{target_topic_id}")
    file_url = f"https://storage.googleapis.com/simulated-bucket/{file.filename}" 
    
    # 4. Update the Database
    # We need to find the specific topic inside the subject and update its 'lecture_content'
    
    subject_data = await read_one("subjects", subject_id)
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
        return {
            "message": "Module successfully categorized and uploaded",
            "matched_topic": target_topic_id,
            "ai_reasoning": ai_decision.get("reasoning"),
            "file_url": file_url
        }
    else:
        raise HTTPException(status_code=500, detail="Matched topic ID not found in database structure.")