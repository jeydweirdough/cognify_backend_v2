from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    STUDENT = "student"
    FACULTY = "faculty_member" # Updated from TEACHER

class AssessmentType(str, Enum):
    PRE_ASSESSMENT = "pre-assessment"
    QUIZ = "quiz"
    POST_ASSESSMENT = "post-assessment"
    DIAGNOSTIC = "diagnostic"

class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    MUTIPLE_RESPONSES = "multiple_responses"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    FILL_IN_THE_BLANK = "fill_in_the_blank"
    MATCHING = "matching"
    SEQUENCE = "sequence"
    RATIONALE = "rationale"

class ProgressStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class BloomTaxonomy(str, Enum):
    REMEMBERING = "remembering"
    UNDERSTANDING = "understanding"
    APPLYING = "applying"
    ANALYZING = "analyzing"
    EVALUATING = "evaluating"
    CREATING = "creating"

class PersonalReadinessLevel(str, Enum):
    VERY_LOW = "1"
    LOW = "2"
    MODERATE = "3"
    HIGH = "4"

class DifficultyLevel(str, Enum):
    EASY = "Easy"
    MODERATE = "Moderate"
    DIFFICULT = "Difficult"