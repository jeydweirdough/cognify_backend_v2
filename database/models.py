from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from services.authentication_service import cvsu_email_verification, validate_password_rules
from services.role_services import get_role_id_by_designation
from services.question_service import validate_assessment_total_items, validate_question
from typing import Dict, List, Optional, Union
from enums import UserRole, AssessmentType, QuestionType, ProgressStatus, BloomTaxonomy, PersonalReadinessLevel, Timeliness

class TimestampSchema(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

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

class SubjectSchema(TimestampSchema):
    id: str
    title: str
    image: Optional[str]
    description: Optional[str]

class TopicAndCompentencySchema(TimestampSchema):
    topic: str
    competency: str

class ModuleSchema(TimestampSchema):
    title: str
    description: Optional[str]
    subject_id: str
    source: str
    image: Optional[str]
    topics_and_competencies: List[TopicAndCompentencySchema]
    bloom_taxonomy: BloomTaxonomy

class QuestionSchema(TimestampSchema):
    text: str = Field(..., description="The text of the question")
    type: QuestionType = Field(..., description="Type of the question")
    choices: Optional[List[str]] = Field(None, description="List of options if applicable")
    correct_answers: Optional[Union[str, bool, List[str]]] = Field(
        None, description="The correct answer(s) depending on question type"
    )
    module_basis: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_all(cls, values):
        validate_question(
            question_type=values.type.value,  # Assuming QuestionType is an Enum
            taxonomy=values.bloom_taxonomy.value,  # Assuming BloomTaxonomy is an Enum
            choices=values.choices,
            answers=values.correct_answers
        )
        return values

class AssessmentSchema(TimestampSchema):
    type: AssessmentType
    subject_id: Optional[str] = None
    title: Optional[str] = None
    questions: List[QuestionSchema]
    total_items: Optional[int] = None

    @model_validator(mode="after")
    def validate_total_items(cls, values):
        validate_assessment_total_items(values.questions, values.total_items)
        return values

class ProgressSchema(TimestampSchema):
    time_spent: float = Field(0.0, description="Time spent in minutes")
    times_taken: int = Field(0, description="Number of times the module has been taken")
    completion: int
    status: ProgressStatus = Field(ProgressStatus.IN_PROGRESS, description="Progress status of the module")
    
    @field_validator("completion")
    def validate_completion(cls, value: int) -> int:
        if not (0 <= value <= 100):
            raise ValueError("Completion must be between 0 and 100")
        return value
    
class CompletedModules(ProgressSchema):
    module_id: str
    student_id: str

class CompletedAssessment(ProgressSchema):
    assessment_id: str
    student_id: str
    overall_items: Optional[int] = None
    score: Optional[int] = None
    percentage: Optional[int] = None

class StudentProgressReport(TimestampSchema):
    subject_id: str
    modules_completeness: int
    assessment_completeness: int
    overall_completeness: int

class NotificationsSchema(TimestampSchema):
    title: str
    message: str
    is_read: bool = False
    student_id: str

class StudentSchema(TimestampSchema):
    personal_readiness: Optional[PersonalReadinessLevel] = None
    confident_subject: Optional[List[str]] = None
    timeliness: Timeliness = Timeliness.FLEXIBLE
    progress_report: Optional[List[StudentProgressReport]] = None
    recommended_modules: Optional[List[str]] = None

class UserProfileBase(SignUpSchema):
    profile_image: Optional[str] = None
    middle_name: Optional[str] = None
    username: Optional[str] = None
    student_info: Optional[StudentSchema] = None

    class Config:
        fields = {"password": {"exclude": True}}
