from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from core.security import allowed_users
from services.tos_processor import process_tos_document
# [FIX] Added read_query and update to imports
from services.crud_services import create, read_query, update
from database.models import SubjectSchema

router = APIRouter(prefix="/tos", tags=["Curriculum Management"], dependencies=[Depends(allowed_users(["admin"]))])

@router.post("/upload-tos", response_model=SubjectSchema)
async def upload_tos_file(file: UploadFile = File(...)):
    """
    Uploads a TOS PDF, extracts data using AI, and saves the Subject to Firestore.
    [FIX] If the subject exists (by Title), it updates the existing record instead of creating a duplicate.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Read file into memory
        content = await file.read()
        
        # 1. Run the AI Pipeline to get the structured data
        subject_data: SubjectSchema = await process_tos_document(content, file.filename)
        
        # 2. Check if Subject Exists (by Title)
        # This prevents duplicates if the same TOS is uploaded again
        existing_subjects = await read_query("subjects", [("title", "==", subject_data.title)])
        
        if existing_subjects:
            # [UPDATE LOGIC]
            existing_id = existing_subjects[0]["id"]
            
            # Prepare data for update
            update_payload = subject_data.model_dump()
            
            # Perform Update
            await update("subjects", existing_id, update_payload)
            
            # Set the ID on the response object so the frontend knows which ID was updated
            # (SubjectSchema might define 'id' as optional or string, we ensure it's set)
            if hasattr(subject_data, "id"):
                subject_data.id = existing_id
                
            return subject_data
            
        else:
            # [CREATE LOGIC]
            saved_record = await create(
                collection_name="subjects", 
                model_data=subject_data.model_dump(),
                doc_id=None # Auto-generate ID
            )
            
            # Set the new ID on the response
            if isinstance(saved_record, dict) and "id" in saved_record:
                 if hasattr(subject_data, "id"):
                    subject_data.id = saved_record["id"]
                 
            return subject_data
        
    except Exception as e:
        # Catch any errors from AI processing or DB operations
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"TOS Processing Failed: {str(e)}"
        )