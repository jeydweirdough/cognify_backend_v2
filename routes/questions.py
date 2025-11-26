# routes/questions.py
from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.security import allowed_users
from database.models import DistributionAnalysis, QuestionBulkCreateRequest, QuestionCreateRequest, QuestionResponse, QuestionSchema, QuestionUpdateRequest, TimestampSchema
from database.enums import QuestionType, BloomTaxonomy, DifficultyLevel
from services.question_service import (
    validate_question,
    validate_assessment_distribution,
    DIFFICULTY_TO_TAXONOMY,
    TYPE_TO_TAXONOMY
)

# FIX: dependencies=[Depends(...)]
router = APIRouter(prefix="/questions", tags=["Questions"], dependencies=[Depends(allowed_users(["faculty", "teacher", "admin"]))])

# ===== ROUTES =====

@router.post(
    "/", 
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new question",
    description="Create a question aligned to TOS competency and board exam standards"
)
async def create_question(
    request: QuestionCreateRequest,
    # user: User = Depends(get_current_user)  # Uncomment when auth is implemented
) -> QuestionResponse:
    """
    Create a new question with full validation.
    
    Validates:
    - Question type and taxonomy alignment
    - Difficulty and taxonomy alignment
    - TOS competency alignment
    - Answer format correctness
    """
    try:
        # Get competency details to validate alignment
        # competency = await get_competency(request.competency_id)
        competency_bloom = "understanding"  # Placeholder - fetch from DB
        
        # Validate question
        validate_question(
            question_type=request.type.value,
            taxonomy=request.bloom_taxonomy.value,
            choices=request.choices,
            answers=request.correct_answers,
            difficulty=request.difficulty_level.value,
            competency_bloom=competency_bloom
        )
        
        # Create question in database
        question_data = {
            **request.dict(),
            "created_at": datetime.utcnow(),
            "created_by": "user_id",  # Get from auth
            "is_verified": False
        }
        
        # question_id = await db.questions.insert(question_data)
        # created_question = await db.questions.get(question_id)
        
        # Placeholder response
        return QuestionResponse(
            id="q_123",
            **request.dict(),
            created_at=datetime.utcnow()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create question: {str(e)}"
        )


@router.post(
    "/bulk",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create questions",
    description="Create multiple questions and validate distribution"
)
async def bulk_create_questions(
    request: QuestionBulkCreateRequest
) -> Dict[str, Any]:
    """
    Create multiple questions at once.
    Optionally validates board exam difficulty distribution.
    """
    try:
        created_questions = []
        errors = []
        
        for idx, question_req in enumerate(request.questions):
            try:
                # Individual question validation
                validate_question(
                    question_type=question_req.type.value,
                    taxonomy=question_req.bloom_taxonomy.value,
                    choices=question_req.choices,
                    answers=question_req.correct_answers,
                    difficulty=question_req.difficulty_level.value
                )
                
                # Create question
                # question_id = await db.questions.insert(question_req.dict())
                created_questions.append({
                    "index": idx,
                    "id": f"q_{idx}",  # Placeholder
                    "status": "created"
                })
                
            except ValueError as e:
                errors.append({
                    "index": idx,
                    "question_text": question_req.text[:50] + "...",
                    "error": str(e)
                })
        
        # Validate distribution if requested
        distribution_valid = True
        distribution_analysis = None
        
        if request.validate_distribution and created_questions:
            try:
                questions_data = [
                    {"difficulty_level": q.difficulty_level.value}
                    for q in request.questions
                ]
                distribution_analysis = validate_assessment_distribution(
                    questions_data
                )
            except ValueError as e:
                distribution_valid = False
                distribution_analysis = {"error": str(e)}
        
        return {
            "total_submitted": len(request.questions),
            "created": len(created_questions),
            "failed": len(errors),
            "created_questions": created_questions,
            "errors": errors,
            "distribution_analysis": distribution_analysis,
            "distribution_valid": distribution_valid
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk creation failed: {str(e)}"
        )


@router.get(
    "/",
    response_model=List[QuestionResponse],
    summary="Get questions with filters",
    description="Retrieve questions filtered by competency, taxonomy, difficulty, etc.",
    dependencies=Depends(allowed_users(["student"]))
)
async def get_questions(
    competency_id: Optional[str] = Query(None, description="Filter by competency"),
    bloom_taxonomy: Optional[BloomTaxonomy] = Query(None, description="Filter by taxonomy"),
    difficulty_level: Optional[DifficultyLevel] = Query(None, description="Filter by difficulty"),
    question_type: Optional[QuestionType] = Query(None, description="Filter by type"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Items per page")
) -> List[QuestionResponse]:
    """
    Get questions with optional filters.
    Supports pagination.
    """
    try:
        # Build filter query
        filters = {}
        if competency_id:
            filters["competency_id"] = competency_id
        if bloom_taxonomy:
            filters["bloom_taxonomy"] = bloom_taxonomy.value
        if difficulty_level:
            filters["difficulty_level"] = difficulty_level.value
        if question_type:
            filters["type"] = question_type.value
        if is_verified is not None:
            filters["is_verified"] = is_verified
        
        # Query database
        # questions = await db.questions.find(filters, skip=skip, limit=limit)
        
        # Placeholder response
        return [
            QuestionResponse(
                id="q_1",
                text="Sample question",
                type=QuestionType.MULTIPLE_CHOICE,
                choices=["A", "B", "C", "D"],
                correct_answers="A",
                competency_id="comp_1",
                bloom_taxonomy=BloomTaxonomy.REMEMBERING,
                difficulty_level=DifficultyLevel.EASY,
                created_at=datetime.utcnow()
            )
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve questions: {str(e)}"
        )


@router.get(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Get question by ID",
    description="Retrieve a specific question"
)
async def get_question(question_id: str) -> QuestionResponse:
    """Get a single question by ID"""
    try:
        # question = await db.questions.get(question_id)
        # if not question:
        #     raise HTTPException(status_code=404, detail="Question not found")
        
        # Placeholder response
        return QuestionResponse(
            id=question_id,
            text="Sample question",
            type=QuestionType.MULTIPLE_CHOICE,
            choices=["A", "B", "C", "D"],
            correct_answers="A",
            competency_id="comp_1",
            bloom_taxonomy=BloomTaxonomy.REMEMBERING,
            difficulty_level=DifficultyLevel.EASY,
            created_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve question: {str(e)}"
        )


@router.put(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Update question",
    description="Update an existing question"
)
async def update_question(
    question_id: str,
    request: QuestionUpdateRequest
) -> QuestionResponse:
    """
    Update a question. 
    Re-validates after update.
    """
    try:
        # Get existing question
        # existing = await db.questions.get(question_id)
        # if not existing:
        #     raise HTTPException(status_code=404, detail="Question not found")
        
        # Merge updates
        # updated_data = {**existing, **request.dict(exclude_unset=True)}
        
        # Re-validate if key fields changed
        if any([request.bloom_taxonomy, request.difficulty_level, request.correct_answers]):
            # Re-run validation
            pass
        
        # Update in database
        # await db.questions.update(question_id, updated_data)
        
        # Placeholder response
        return QuestionResponse(
            id=question_id,
            text="Updated question",
            type=QuestionType.MULTIPLE_CHOICE,
            choices=["A", "B", "C", "D"],
            correct_answers="A",
            competency_id="comp_1",
            bloom_taxonomy=BloomTaxonomy.UNDERSTANDING,
            difficulty_level=DifficultyLevel.MODERATE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update question: {str(e)}"
        )


@router.delete(
    "/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete question",
    description="Soft delete a question"
)
async def delete_question(question_id: str):
    """
    Soft delete a question (sets deleted_at timestamp).
    Hard delete not allowed to maintain audit trail.
    """
    try:
        # Soft delete
        # await db.questions.update(question_id, {"deleted_at": datetime.utcnow()})
        return None
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete question: {str(e)}"
        )


@router.post(
    "/{question_id}/verify",
    response_model=QuestionResponse,
    summary="Verify question",
    description="Mark question as verified by faculty"
)
async def verify_question(
    question_id: str,
    # user: User = Depends(get_current_faculty)  # Only faculty can verify
) -> QuestionResponse:
    """
    Verify a question for use in assessments.
    Only verified questions can be included in board exam practice tests.
    """
    try:
        # Update verification status
        # await db.questions.update(question_id, {
        #     "is_verified": True,
        #     "verified_at": datetime.utcnow(),
        #     "verified_by": user.id
        # })
        
        # Placeholder response
        return QuestionResponse(
            id=question_id,
            text="Verified question",
            type=QuestionType.MULTIPLE_CHOICE,
            choices=["A", "B", "C", "D"],
            correct_answers="A",
            competency_id="comp_1",
            bloom_taxonomy=BloomTaxonomy.REMEMBERING,
            difficulty_level=DifficultyLevel.EASY,
            created_at=datetime.utcnow(),
            is_verified=True,
            verified_at=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify question: {str(e)}"
        )


@router.get(
    "/competency/{competency_id}/distribution",
    response_model=DistributionAnalysis,
    summary="Analyze question distribution for competency",
    description="Get distribution analysis for questions in a competency"
)
async def get_competency_distribution(competency_id: str) -> DistributionAnalysis:
    """
    Analyze question distribution for a specific TOS competency.
    Useful for ensuring adequate coverage.
    """
    try:
        # Query questions for competency
        # questions = await db.questions.find({"competency_id": competency_id})
        
        # Analyze distribution
        # distribution = analyze_distribution(questions)
        
        # Placeholder response
        return DistributionAnalysis(
            total_questions=20,
            by_difficulty={
                "Easy": 6,
                "Moderate": 8,
                "Difficult": 6
            },
            by_taxonomy={
                "remembering": 5,
                "understanding": 7,
                "applying": 5,
                "analyzing": 3
            },
            by_type={
                "multiple_choice": 15,
                "multiple_responses": 3,
                "true_false": 2
            },
            board_exam_compliance={
                "is_compliant": True,
                "deviations": {}
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze distribution: {str(e)}"
        )


@router.get(
    "/validation-rules",
    response_model=Dict[str, Any],
    summary="Get validation rules",
    description="Get current validation rules for question types and taxonomies"
)
async def get_validation_rules() -> Dict[str, Any]:
    """
    Return the current validation rules.
    Useful for frontend validation and documentation.
    """
    return {
        "type_to_taxonomy": TYPE_TO_TAXONOMY,
        "difficulty_to_taxonomy": DIFFICULTY_TO_TAXONOMY,
        "board_exam_distribution": {
            "easy": 30,
            "moderate": 40,
            "difficult": 30
        },
        "choice_requirements": {
            "multiple_choice": "Exactly 4 choices recommended (board exam standard)",
            "multiple_responses": "2-6 choices, at least 2 correct answers"
        }
    }


# ===== HELPER ROUTES FOR QUESTION CREATION =====

@router.get(
    "/templates/{question_type}",
    response_model=Dict[str, Any],
    summary="Get question template",
    description="Get a template for creating questions of specific type"
)
async def get_question_template(question_type: QuestionType) -> Dict[str, Any]:
    """
    Get a template with examples for creating questions.
    Helps maintain consistency with board exam standards.
    """
    templates = {
        QuestionType.MULTIPLE_CHOICE: {
            "structure": {
                "stem": "Present scenario or question",
                "choices": ["A. First option", "B. Second option", "C. Third option", "D. Fourth option"],
                "correct_answer": "One letter A-D",
                "rationale": "Explain why answer is correct"
            },
            "example": {
                "text": "According to Freud's psychoanalytic theory, the ID operates on the:",
                "choices": [
                    "Reality principle",
                    "Pleasure principle",
                    "Moral principle",
                    "Conscious principle"
                ],
                "correct_answers": "Pleasure principle",
                "bloom_taxonomy": "remembering",
                "difficulty_level": "Easy"
            },
            "tips": [
                "Use 4 plausible distractors",
                "Avoid 'all of the above' or 'none of the above'",
                "Ensure grammatical consistency",
                "Make all choices similar in length"
            ]
        },
        QuestionType.MULTIPLE_RESPONSES: {
            "structure": {
                "stem": "Question requiring multiple correct answers",
                "choices": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
                "correct_answers": ["Two or more letters"],
                "rationale": "Explain each correct answer"
            },
            "example": {
                "text": "Which of the following are defense mechanisms described by Anna Freud? (Select all that apply)",
                "choices": [
                    "Repression",
                    "Classical conditioning",
                    "Projection",
                    "Self-actualization",
                    "Denial"
                ],
                "correct_answers": ["Repression", "Projection", "Denial"],
                "bloom_taxonomy": "understanding",
                "difficulty_level": "Moderate"
            }
        }
        # Add more templates as needed
    }
    
    template = templates.get(question_type)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Template not available for {question_type}"
        )
    
    return template


@router.post(
    "/validate",
    response_model=Dict[str, Any],
    summary="Validate question before creation",
    description="Dry-run validation without creating question"
)
async def validate_question_endpoint(request: QuestionCreateRequest) -> Dict[str, Any]:
    """
    Validate a question without creating it.
    Useful for frontend validation feedback.
    """
    try:
        validate_question(
            question_type=request.type.value,
            taxonomy=request.bloom_taxonomy.value,
            choices=request.choices,
            answers=request.correct_answers,
            difficulty=request.difficulty_level.value
        )
        
        return {
            "is_valid": True,
            "message": "Question passes all validation rules",
            "warnings": []
        }
        
    except ValueError as e:
        return {
            "is_valid": False,
            "message": str(e),
            "errors": [str(e)]
        }