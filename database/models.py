from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from services.authentication_service import cvsu_email_verification, validate_password_rules
from services.role_services import get_role_id_by_designation
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
    """
    Whitelist table. Admins add emails here. 
    Users can only sign up if their email exists here.
    """
    email: str = Field(..., description="Must be a @cvsu.edu.ph email")
    assigned_role: UserRole
    added_by: str # Admin ID

class AnnouncementSchema(TimestampSchema):
    """
    Announcements created by Admin or Faculty.
    """
    title: str
    content: str
    target_audience: List[UserRole] = [] # Empty list = All
    is_global: bool = False
    author_id: str
    
class MaterialVerificationQueue(BaseModel):
    """
    Response model for Admins to see pending materials
    """
    item_id: str
    type: str # 'question', 'assessment', 'module'
    title: str
    submitted_by: str
    submitted_at: datetime

# --- NEW: ADAPTABILITY & BEHAVIOR TRACKING ---
class StudySessionLog(TimestampSchema):
    """
    Logs a single study session to track behavior.
    """
    user_id: str
    resource_id: str # ID of the Module or Assessment
    resource_type: str # 'module' or 'assessment'
    
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Behavioral Metrics
    interruptions_count: int = 0 # How many times they tabbed out or paused
    idle_time_seconds: float = 0.0 # Detected idle time
    
    completion_status: ProgressStatus = ProgressStatus.IN_PROGRESS

class StudentBehaviorProfile(BaseModel):
    """
    Aggregated metrics used for AI Adaptability.
    Stored inside StudentSchema.
    """
    average_session_length: float = 0.0 # in minutes
    preferred_study_time: str = "Any" # Morning, Afternoon, Evening
    interruption_frequency: str = "Low" # Low, Medium, High
    learning_pace: str = "Standard" # Fast, Standard, Slow

# --- AUTHENTICATION ---
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
    role_id: str = Field(get_role_id_by_designation(UserRole.STUDENT))

# --- CURATED TOS HIERARCHY ---
class CompetencySchema(TimestampSchema):
    code: str  # e.g., "1.1"
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

class SubjectSchema(TimestampSchema):
    title: str
    pqf_level: int
    total_weight_percentage: float = 100.0
    topics: List[TopicSchema]

# --- QUESTION BANK ---
class QuestionSchema(TimestampSchema, VerificationSchema):
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
    subject_id: str
    target_topics: List[str] # List of Topic IDs to include
    total_items: int = 0
    easy_percentage: float = 0     
    moderate_percentage: float = 0 
    difficult_percentage: float = 0 

class AssessmentSchema(TimestampSchema, VerificationSchema):
    title: str
    type: AssessmentType
    subject_id: str
    blueprint: Optional[AssessmentBlueprintSchema] = None
    questions: List[QuestionSchema]
    total_items: int

    @model_validator(mode="after")
    def validate_total_items(cls, values):
        if values.questions and values.total_items:
             if len(values.questions) != values.total_items:
                 raise ValueError("Question count does not match total_items")
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
    
    # New Behavioral Data
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

class PreRegisteredUserSchema(BaseModel):
    """
    Whitelist table. Admins add emails here.
    Users can only sign up if their email exists here.
    """
    email: str = Field(..., description="Must be a @cvsu.edu.ph email")
    assigned_role: str  # UserRole enum value
    added_by: str  # Admin ID
    is_registered: bool = False  # NEW FIELD
    registered_at: Optional[datetime] = None  # NEW FIELD
    user_id: Optional[str] = None  # NEW FIELD
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class AnnouncementSchema(BaseModel):
    """
    Announcements created by Admin or Faculty.
    """
    title: str
    content: str
    target_audience: List[str] = []  # List of role names
    is_global: bool = False
    author_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class StudySessionLog(BaseModel):
    """
    Logs a single study session to track behavior.
    Enhanced with more tracking fields.
    """
    user_id: str
    resource_id: str  # ID of the Module or Assessment
    resource_type: str  # 'module' or 'assessment'
    
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Behavioral Metrics
    interruptions_count: int = 0  # How many times they tabbed out or paused
    idle_time_seconds: float = 0.0  # Detected idle time
    
    completion_status: str = "in_progress"  # or "completed"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class AssessmentSubmission(BaseModel):
    """
    Stores student's assessment submissions for analytics.
    """
    user_id: str
    assessment_id: str
    subject_id: str
    
    answers: List[Dict]  # [{"question_id": "q1", "answer": "A", "is_correct": True, "competency_id": "c1"}]
    
    score: float
    total_items: int
    time_taken_seconds: float
    
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StudentBehaviorProfile(BaseModel):
    """
    Aggregated metrics used for AI Adaptability.
    Stored inside StudentSchema.
    Enhanced with more fields.
    """
    average_session_length: float = 0.0  # in minutes
    preferred_study_time: str = "Any"  # Morning, Afternoon, Evening, Night
    interruption_frequency: str = "Medium"  # Low, Medium, High
    learning_pace: str = "Standard"  # Fast, Standard, Slow
    
    # NEW FIELDS
    reading_pattern: str = "continuous"  # continuous, chunked, quick_scanner
    assessment_pace: str = "moderate"  # rushed, moderate, thorough
    focus_level: str = "Medium"  # High, Medium, Low
    last_updated: Optional[datetime] = None


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