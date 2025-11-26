from fastapi import APIRouter, Depends, HTTPException
from database.models import AssessmentBlueprintSchema, AssessmentSchema, AssessmentType
from services.assessment_generator import generate_assessment_from_blueprint
from core.security import allowed_users

router = APIRouter(prefix="/assessments", tags=["Assessment Generation"])

@router.post("/generate", response_model=AssessmentSchema)
async def create_assessment(
    blueprint: AssessmentBlueprintSchema, 
    title: str, 
    assessment_type: AssessmentType,
    current_user: dict = Depends(allowed_users(["teacher", "admin"]))
):
    """
    Generates a new Assessment (Quiz/Exam) based on the TOS Blueprint.
    - Selects questions based on difficulty distribution.
    - Shuffles them.
    - Saves the Exam to the database.
    """
    
    new_assessment = await generate_assessment_from_blueprint(
        blueprint=blueprint, 
        title=title, 
        assessment_type=assessment_type
    )
    
    return new_assessment