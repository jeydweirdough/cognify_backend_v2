from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from services.authentication_service import cvsu_email_verification, validate_password_rules
from services.question_service import validate_assessment_total_items, validate_question
from typing import Dict, List, Optional, Union
from enum import Enum
from enums import (
    UserRole, AssessmentType, QuestionType, ProgressStatus, 
    BloomTaxonomy, PersonalReadinessLevel, DifficultyLevel
)

# --- BASE ---
class TimestampSchema(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

# --- AUTHENTICATION (Kept mostly the same) ---
class LoginSchema(TimestampSchema):
    email: str
    password: str

    @field_validator("email")
    def validate_cvsu_email(cls, value):
        if not cvsu_email_verification(value):
            raise ValueError("Email must belong to the CVSU domain (@cvsu.edu.ph)")
        return value
    
    @field_validator("password")
    def validate_password(cls, value):
        rules = {
            "at least one uppercase letter": r"[A-Z]",
            "at least one lowercase letter": r"[a-z]",
            "at least one digit": r"\d",
            "at least one special character": r"[!@#$%^&*(),.?\":{}|<>]",
            "minimum length of 8 characters": r".{8,}"
        }
        return validate_password_rules(value, rules)

class SignUpSchema(LoginSchema):
    first_name: Optional[str]
    last_name: Optional[str]
    role_id: UserRole = UserRole.STUDENT

# --- CURATED TOS HIERARCHY ---

class CompetencySchema(TimestampSchema):
    """
    Represents the specific row in the TOS (e.g., '1.1 Cite major tenets...') [cite: 9]
    """
    id: str
    code: str  # e.g., "1.1"
    description: str
    
    # TOS Specifics
    target_bloom_level: BloomTaxonomy # The primary cognitive level required
    target_difficulty: DifficultyLevel # Easy, Moderate, Difficult
    
    # Derived from TOS columns for Item Analysis
    allocated_items: int = 0  # e.g., "8" items [cite: 9]

class TopicSchema(TimestampSchema):
    """
    Represents the grouping in TOS (e.g., '1. Theories of Personality') [cite: 9]
    Acts as the 'Module' container.
    """
    id: str
    title: str
    weight_percentage: float
    competencies: List[CompetencySchema]
    
    # Educational Content
    lecture_content: Optional[str]
    image: Optional[str]

class SubjectSchema(TimestampSchema):
    """
    Represents the Board Subject (e.g., 'Advanced Theories of Personality') 
    """
    id: str
    title: str
    pqf_level: int
    total_weight_percentage: float = 100.0
    topics: List[TopicSchema]

# --- QUESTION BANK ---

class QuestionSchema(TimestampSchema):
    id: str
    text: str = Field(..., description="The text of the question")
    type: QuestionType
    choices: Optional[List[str]]
    correct_answers: Optional[Union[str, bool, List[str]]]
    
    # STRICT ALIGNMENT TO TOS
    competency_id: str = Field(..., description="Links question to specific TOS competency")
    bloom_taxonomy: BloomTaxonomy
    difficulty_level: DifficultyLevel

    @model_validator(mode="after")
    def validate_all(cls, values):
        validate_question(
            question_type=values.type.value,
            taxonomy=values.bloom_taxonomy.value,
            choices=values.choices,
            answers=values.correct_answers
        )
        return values

# --- ASSESSMENT GENERATION ---

class AssessmentBlueprintSchema(BaseModel):
    """
    Defines the rules for generating a quiz/exam based on TOS weights.
    """
    subject_id: str
    target_topics: List[str] # List of Topic IDs to include
    total_items: int = 100
    
    # Distribution override (defaults to Board Standards)
    easy_percentage: float = 0.30     # 30% [cite: 12]
    moderate_percentage: float = 0.40 # 40% [cite: 9]
    difficult_percentage: float = 0.30 # 30% [cite: 9]

class AssessmentSchema(TimestampSchema):
    id: str
    title: str
    type: AssessmentType
    subject_id: str
    
    # The blueprint used to generate this assessment
    blueprint: Optional[AssessmentBlueprintSchema] = None
    
    questions: List[QuestionSchema]
    total_items: int

    @model_validator(mode="after")
    def validate_total_items(cls, values):
        if values.questions and values.total_items:
             if len(values.questions) != values.total_items:
                 raise ValueError("Question count does not match total_items")
        return values

# --- STUDENT PROGRESS (Enhanced for Analytics) ---

class ProgressSchema(TimestampSchema):
    time_spent: float
    times_taken: int
    completion: int
    status: ProgressStatus
    
    @field_validator("completion")
    def validate_completion(cls, value: int) -> int:
        if not (0 <= value <= 100):
            raise ValueError("Completion must be between 0 and 100")
        return value

class StudentCompetencyPerformance(BaseModel):
    """Tracks how well a student knows a specific TOS Competency"""
    competency_id: str
    mastery_percentage: float # derived from quiz answers linked to this competency

class StudentProgressReport(TimestampSchema):
    subject_id: str
    modules_completeness: int
    assessment_completeness: int
    overall_completeness: int
    
    # New: Detailed breakdown for 'Weakness Identification'
    weakest_competencies: List[str] 

class StudentSchema(TimestampSchema):
    user_id: str
    personal_readiness: Optional[PersonalReadinessLevel] = None
    confident_subject: Optional[List[str]] = None
    timeliness: int
    progress_report: Optional[List[StudentProgressReport]] = None
    competency_performance: Optional[List[StudentCompetencyPerformance]] = None

class UserProfileBase(SignUpSchema):
    profile_image: Optional[str] = None
    middle_name: Optional[str] = None
    username: Optional[str] = None
    student_info: Optional[StudentSchema] = None

    class Config:
        fields = {"password": {"exclude": True}}