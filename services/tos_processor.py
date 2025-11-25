from fastapi import APIRouter, UploadFile, File, HTTPException, status
from services.tos_processor import process_tos_document
from services.crud_services import create, read_query # <--- Added read_query
from database.models import SubjectSchema

router = APIRouter(prefix="/curriculum", tags=["Curriculum Management"])

@router.post("/upload-tos", response_model=SubjectSchema)
async def upload_tos_file(file: UploadFile = File(...)):
    """
    Uploads a TOS PDF.
    - If Subject DOES NOT exist: Extracts data using AI -> Saves to DB.
    - If Subject ALREADY exists: Returns the existing DB record (Ignores creation).
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # 1. Read file into memory
        content = await file.read()
        
        # 2. Run the AI Pipeline (Gemini + Llama)
        # This extracts the Title and Structure from the PDF
        subject_data: SubjectSchema = await process_tos_document(content, file.filename)
        
        # ---------------------------------------------------------
        # NEW: FALLBACK CHECKER (Duplicate Prevention)
        # ---------------------------------------------------------
        # Check if a subject with this EXACT Title already exists in Firestore
        existing_subjects = await read_query(
            collection_name="subjects", 
            filters=[("title", "==", subject_data.title)],
            limit=1
        )

        if existing_subjects:
            # FALLBACK TRIGGERED: Subject exists.
            # We return the existing database record instead of creating a new one.
            print(f"Duplicate detected: '{subject_data.title}'. Skipping creation.")
            
            # Map the raw DB dict back to SubjectSchema for the response
            existing_record = existing_subjects[0]["data"]
            existing_record["id"] = existing_subjects[0]["id"] # Ensure ID is included
            return existing_record
        
        # ---------------------------------------------------------
        # END CHECKER
        # ---------------------------------------------------------

        # 3. If No Duplicate, Save to Firestore
        saved_record = await create(
            collection_name="subjects", 
            model_data=subject_data.model_dump(),
            doc_id=None # Auto-generate ID
        )
        
        # Add the generated ID to the response
        response_data = saved_record["data"]
        response_data["id"] = saved_record["id"]
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Processing Failed: {str(e)}"
        )