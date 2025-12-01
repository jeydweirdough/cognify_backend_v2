from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from services.authentication_service import cvsu_email_verification, validate_password_rules
from services.role_service import get_role_id_by_designation
from services.question_service import validate_question
from typing import Dict, List, Optional, Union, Any
from enum import Enum
from database.enums import (
    UserRole, AssessmentType, QuestionType, ProgressStatus, 
    BloomTaxonomy, PersonalReadinessLevel, DifficultyLevel
)

# --- BASE ---
class TimestampSchema(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

class VerificationSchema(BaseModel):
    is_verified: bool = False
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None

# --- NEW: ADMIN & ANNOUNCEMENTS ---
class PreRegisteredUserSchema(TimestampSchema):
    email: str = Field(..., description="Must be a @cvsu.edu.ph email")
    assigned_role: UserRole
    added_by: str 

class AnnouncementSchema(TimestampSchema):
    title: str
    content: str
    target_audience: List[UserRole] = [] 
    is_global: bool = False
    author_id: str
    
class MaterialVerificationQueue(VerificationSchema):
    item_id: str
    type: str 
    title: str
    submitted_by: str
    submitted_at: datetime
    details: Optional[str] = None

# --- NEW: ADAPTABILITY & BEHAVIOR TRACKING ---
class StudySessionLog(TimestampSchema):
    user_id: str
    resource_id: str 
    resource_type: str 
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    interruptions_count: int = 0 
    idle_time_seconds: float = 0.0 
    completion_status: ProgressStatus = ProgressStatus.IN_PROGRESS

class StudentBehaviorProfile(BaseModel):
    average_session_length: float = 0.0 
    preferred_study_time: str = "Any" 
    interruption_frequency: str = "Low" 
    learning_pace: str = "Standard" 

# --- AUTHENTICATION ---
class LoginSchema(BaseModel):
    email: str
    password: str

    @field_validator("email")
    def validate_cvsu_email(cls, value):
        try:
            if not cvsu_email_verification(value):
                raise ValueError("Email must belong to the CVSU domain (@cvsu.edu.ph)")
        except NameError:
            pass 
        return value

class SignUpSchema(LoginSchema):
    first_name: str
    last_name: str
    username: Optional[str]
    role_id: Optional[str] = None  # Will be set by backend based on whitelist
    
    @field_validator("first_name")
    def validate_first_name(cls, value):
        if not value or not value.strip():
            raise ValueError("First name is required")
        if len(value.strip()) < 2:
            raise ValueError("First name must be at least 2 characters")
        return value.strip()
    
    @field_validator("last_name")
    def validate_last_name(cls, value):
        if not value or not value.strip():
            raise ValueError("Last name is required")
        if len(value.strip()) < 2:
            raise ValueError("Last name must be at least 2 characters")
        return value.strip()
    
    @field_validator("username")
    def validate_username(cls, value):
        if not value or not value.strip():
            raise ValueError("Username is required")
        if len(value.strip()) < 4:
            raise ValueError("Username must be at least 4 characters")
        # Remove spaces and convert to lowercase
        clean_username = value.strip().lower().replace(" ", "")
        if len(clean_username) < 4:
            raise ValueError("Username must be at least 4 characters (excluding spaces)")
        return clean_username
    
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


# --- CURATED TOS HIERARCHY ---
class CompetencySchema(TimestampSchema):
    code: str  
    description: str
    target_bloom_level: BloomTaxonomy 
    target_difficulty: DifficultyLevel 
    allocated_items: int = 0 

class TopicSchema(TimestampSchema):
    title: str
    weight_percentage: float
    competencies: List[CompetencySchema]
    lecture_content: Optional[str]
    image: Optional[str]

# --- SUBJECT SCHEMA ---
class SubjectSchema(TimestampSchema, VerificationSchema):
    title: str
    pqf_level: int = 6
    description: Optional[str] = None
    total_weight_percentage: float = 100.0
    content: Optional[str] = None 
    material_url: Optional[str] = None
    image_url: Optional[str] = None
    icon_name: Optional[str] = "book"
    icon_color: Optional[str] = "#000000"
    icon_bg_color: Optional[str] = "#ffffff"
    created_by: Optional[str] = None 
    is_active: bool = True
    deleted: bool = False

# --- QUESTION BANK ---
class QuestionSchema(TimestampSchema, VerificationSchema):
    text: str = Field(..., description="The text of the question")
    type: QuestionType
    choices: Optional[List[str]] = []
    correct_answers: Optional[Union[str, bool, List[str]]] = None
    
    # [FIX] Made Optional for easier frontend creation (Ad-hoc quizzes)
    competency_id: Optional[str] = None 
    bloom_taxonomy: Optional[BloomTaxonomy] = BloomTaxonomy.REMEMBERING
    difficulty_level: Optional[DifficultyLevel] = DifficultyLevel.EASY

    # Removed Strict Validation for now to allow partial saves
    # @model_validator(mode="after") ... 

# --- ASSESSMENT GENERATION ---
class AssessmentBlueprintSchema(BaseModel):
    subject_id: str
    target_topics: List[str] 
    total_items: int = 0
    easy_percentage: float = 0     
    moderate_percentage: float = 0 
    difficult_percentage: float = 0 

class AssessmentSchema(TimestampSchema, VerificationSchema):
    title: str
    type: AssessmentType
    subject_id: str
    
    # [FIX] Added missing fields to match Frontend Editor
    module_id: Optional[str] = None
    description: Optional[str] = None
    bloom_levels: Optional[List[str]] = []

    blueprint: Optional[AssessmentBlueprintSchema] = None
    questions: List[QuestionSchema] = []
    total_items: int = 0

    @model_validator(mode="after")
    def validate_total_items(cls, values):
        # Auto-calculate if not provided
        if values.questions and values.total_items == 0:
            values.total_items = len(values.questions)
        return values

# --- STUDENT PROGRESS ---
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
    competency_id: str
    mastery_percentage: float

class StudentProgressReport(TimestampSchema):
    subject_id: str
    modules_completeness: int
    assessment_completeness: int
    overall_completeness: int
    weakest_competencies: List[str] 

class StudentSchema(BaseModel):
    user_id: str
    personal_readiness: Optional[PersonalReadinessLevel] = None
    confident_subject: Optional[List[str]] = None
    timeliness: int
    behavior_profile: StudentBehaviorProfile = Field(default_factory=StudentBehaviorProfile)
    progress_report: Optional[List[StudentProgressReport]] = None
    competency_performance: Optional[List[StudentCompetencyPerformance]] = None
    recommended_study_modules: Optional[List[str]] = None

class UserProfileBase(SignUpSchema, VerificationSchema):
    profile_image: Optional[str] = None
    middle_name: Optional[str] = None
    username: Optional[str] = None
    student_info: Optional[StudentSchema] = None
    is_registered: bool = False
    profile_picture: Optional[str] = None
    
class QuestionCreateRequest(BaseModel):
    text: str = Field(..., description="The question text", min_length=10)
    type: QuestionType
    choices: Optional[List[str]] = Field(None, description="Answer choices for MCQ")
    correct_answers: Optional[str | bool | List[str]] = Field(..., description="Correct answer(s)")
    competency_id: str = Field(..., description="Must link to specific TOS competency")
    bloom_taxonomy: BloomTaxonomy
    difficulty_level: DifficultyLevel
    rationale: Optional[str] = Field(None, description="Explanation for correct answer")
    references: Optional[List[str]] = Field(None, description="Source references")
    tags: Optional[List[str]] = Field(None, description="Topic tags for filtering")

class QuestionUpdateRequest(BaseModel):
    text: Optional[str] = Field(None, min_length=10)
    choices: Optional[List[str]] = None
    correct_answers: Optional[str | bool | List[str]] = None
    bloom_taxonomy: Optional[BloomTaxonomy] = None
    difficulty_level: Optional[DifficultyLevel] = None
    rationale: Optional[str] = None
    references: Optional[List[str]] = None
    tags: Optional[List[str]] = None

class QuestionBulkCreateRequest(BaseModel):
    questions: List[QuestionCreateRequest]
    validate_distribution: bool = Field(True, description="Validate board exam difficulty distribution")

class QuestionResponse(QuestionSchema):
    id: str
    created_by: Optional[str] = None
    question_number: Optional[int] = None

class QuestionFilterParams(BaseModel):
    competency_id: Optional[str] = None
    bloom_taxonomy: Optional[BloomTaxonomy] = None
    difficulty_level: Optional[DifficultyLevel] = None
    question_type: Optional[QuestionType] = None
    is_verified: Optional[bool] = None
    tags: Optional[List[str]] = None

class DistributionAnalysis(BaseModel):
    total_questions: int
    by_difficulty: Dict[str, int]
    by_taxonomy: Dict[str, int]
    by_type: Dict[str, int]
    board_exam_compliance: Dict[str, Any]

# [FIX] Added AssessmentSubmission
class AssessmentSubmission(BaseModel):
    """
    Stores student's assessment submissions for analytics.
    """
    user_id: str
    assessment_id: str
    subject_id: str
    
    answers: List[Dict] = []  # [{"question_id": "q1", "answer": "A", "is_correct": True, "competency_id": "c1"}]
    
    score: float
    total_items: int
    time_taken_seconds: float
    
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class NotificationSchema(BaseModel):
    """
    In-app notifications for users.
    """
    user_id: str
    title: str
    message: str
    type: str  # announcement, verification, reminder, alert
    is_read: bool = False
    related_id: Optional[str] = None  # ID of related announcement, question, etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SystemLog(BaseModel):
    """
    System activity logs for admin monitoring.
    """
    action: str  # user_created, question_verified, assessment_submitted, etc.
    actor_id: str
    target_id: Optional[str] = None
    details: Dict = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ========================================
# REQUEST MODELS
# ========================================

class SubjectCreateRequest(BaseModel):
    title: str = Field(..., description="The title of the subject")
    pqf_level: int = 6
    description: Optional[str] = None
    
    # [NEW]
    content: Optional[str] = None
    material_url: Optional[str] = None
    
    image_url: Optional[str] = None
    icon_name: Optional[str] = "book"
    icon_color: Optional[str] = "#000000"
    icon_bg_color: Optional[str] = "#ffffff"

class SubjectUpdateRequest(BaseModel):
    title: Optional[str] = None
    pqf_level: Optional[int] = None
    description: Optional[str] = None
    
    # [NEW]
    content: Optional[str] = None
    material_url: Optional[str] = None
    
    image_url: Optional[str] = None
    icon_name: Optional[str] = None
    icon_color: Optional[str] = None
    icon_bg_color: Optional[str] = None


class TopicUpdateRequest(BaseModel):
    title: Optional[str] = None
    weight_percentage: Optional[float] = None
    lecture_content: Optional[str] = None
    image: Optional[str] = None


class CompetencyUpdateRequest(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    target_bloom_level: Optional[str] = None
    target_difficulty: Optional[str] = None
    allocated_items: Optional[int] = None


class TopicCreateRequest(BaseModel):
    title: str = Field(..., min_length=3)
    weight_percentage: float = Field(..., ge=0, le=100)
    competencies: List[Dict[str, Any]] = []
    lecture_content: Optional[str] = None
    image: Optional[str] = None