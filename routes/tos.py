# routes/tos.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from core.security import allowed_users
from services.tos_processor import process_tos_document
from services.crud_services import create
from database.models import SubjectSchema

# FIX: dependencies=[Depends(...)] (Added brackets)
router = APIRouter(prefix="/tos", tags=["Curriculum Management"], dependencies=[Depends(allowed_users(["admin"]))])

@router.post("/upload-tos", response_model=SubjectSchema)
async def upload_tos_file(file: UploadFile = File(...)):
    """
    Uploads a TOS PDF, extracts data using AI, and saves the Subject to Firestore.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Read file into memory
        content = await file.read()
        
        # 1. Run the AI Pipeline
        subject_data: SubjectSchema = await process_tos_document(content, file.filename)
        
        # 2. Save to Firestore (Subject Collection)
        saved_record = await create(
            collection_name="subjects", 
            model_data=subject_data.model_dump(),
            doc_id=None # Auto-generate ID
        )
        
        return subject_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"AI Processing Failed: {str(e)}"
        )