# services/question_service.py
"""
Question validation service aligned to Philippine Psychometrician Board Exam Standards
Based on PRC requirements and Professional Regulation Commission guidelines
"""
from typing import Any, List, Optional, Union, Set, Dict


# ===== PSYCHOMETRICIAN BOARD EXAM TAXONOMY MAPPING =====
# Aligned to Philippine board exam item construction standards
TYPE_TO_TAXONOMY: Dict[str, Set[str]] = {
    # Multiple Choice - Most common in board exams (60-70% of questions)
    # Can assess all cognitive levels depending on stem construction
    "multiple_choice": {
        "remembering",      # Recall facts, theories, definitions
        "understanding",    # Explain concepts, interpret case studies
        "applying",         # Apply theories to scenarios
        "analyzing",        # Distinguish between approaches
        "evaluating",       # Judge appropriateness of interventions
        "creating"          # Synthesize novel solutions
    },
    
    # Multiple Responses - Used for comprehensive understanding (15-20%)
    "multiple_responses": {
        "understanding",    # Identify multiple correct characteristics
        "applying",         # Select all applicable interventions
        "analyzing",        # Recognize all relevant factors
        "evaluating",       # Assess multiple valid approaches
        "creating"          # Identify all components of a solution
    },
    
    # True/False - Basic recall and comprehension (5-10%)
    "true_false": {
        "remembering",      # Factual statements
        "understanding"     # Conceptual understanding
    },
    
    # Short Answer - Demonstrate understanding (rare in board exams)
    "short_answer": {
        "understanding",    # Define or explain briefly
        "applying",         # Show application steps
        "analyzing"         # Break down concepts
    },
    
    # Fill in the Blank - Terminology and definitions (5%)
    "fill_in_the_blank": {
        "remembering",      # Recall specific terms
        "understanding"     # Complete conceptual statements
    },
    
    # Matching - Connect related concepts (5%)
    "matching": {
        "remembering",      # Match terms to definitions
        "understanding",    # Match theories to theorists
        "applying"          # Match techniques to applications
    },
    
    # Sequence - Procedural knowledge (rare)
    "sequence": {
        "understanding",    # Order of developmental stages
        "applying",         # Steps in assessment process
        "analyzing"         # Logical flow of interventions
    },
    
    # Rationale - Justify clinical decisions (supplementary)
    "rationale": {
        "analyzing",        # Explain reasoning
        "evaluating",       # Justify approach selection
        "creating"          # Design and defend solutions
    }
}


# ===== DIFFICULTY-TAXONOMY ALIGNMENT =====
# Based on board exam difficulty distribution: 30% Easy, 40% Moderate, 30% Difficult
DIFFICULTY_TO_TAXONOMY: Dict[str, Set[str]] = {
    "Easy": {
        "remembering",      # Direct recall
        "understanding"     # Basic comprehension
    },
    "Moderate": {
        "understanding",    # Deep comprehension
        "applying",         # Application to scenarios
        "analyzing"         # Analysis of situations
    },
    "Difficult": {
        "analyzing",        # Complex analysis
        "evaluating",       # Critical evaluation
        "creating"          # Synthesis and creation
    }
}


# ===== BLOOM'S TAXONOMY HIERARCHY =====
BLOOM_HIERARCHY = [
    "remembering",
    "understanding",
    "applying",
    "analyzing",
    "evaluating",
    "creating"
]


# ===== VALIDATION FUNCTIONS =====

def validate_taxonomy(question_type: str, taxonomy: str) -> None:
    """
    Validate that the taxonomy is appropriate for the question type.
    Aligned to Philippine Psychometrician Board Exam standards.
    
    Args:
        question_type: The type of question (from QuestionType enum)
        taxonomy: The Bloom's taxonomy level (from BloomTaxonomy enum)
        
    Raises:
        ValueError: If taxonomy is not valid for the question type
    """
    allowed_taxonomies = TYPE_TO_TAXONOMY.get(question_type, set())
    if taxonomy not in allowed_taxonomies:
        raise ValueError(
            f"Taxonomy '{taxonomy}' is not valid for question type '{question_type}'. "
            f"Allowed taxonomies: {', '.join(sorted(allowed_taxonomies))}"
        )


def validate_difficulty_taxonomy_alignment(
    difficulty: str, 
    taxonomy: str,
    strict: bool = False
) -> None:
    """
    Validate that difficulty level aligns with Bloom's taxonomy.
    Ensures board exam item difficulty standards are met.
    
    Args:
        difficulty: Easy, Moderate, or Difficult
        taxonomy: Bloom's taxonomy level
        strict: If True, enforces strict alignment; if False, provides warning only
        
    Raises:
        ValueError: If strict=True and alignment is invalid
    """
    allowed_taxonomies = DIFFICULTY_TO_TAXONOMY.get(difficulty, set())
    
    if taxonomy not in allowed_taxonomies:
        message = (
            f"Difficulty '{difficulty}' typically requires taxonomy levels: "
            f"{', '.join(sorted(allowed_taxonomies))}. Got '{taxonomy}'. "
            f"This may not align with board exam standards."
        )
        if strict:
            raise ValueError(message)
        # In non-strict mode, this would log a warning in production
        # For now, we'll pass but you should implement logging


def validate_choices_based_question(
    question_type: str,
    choices: Optional[List[str]],
    answers: Optional[Union[str, List[str]]]
) -> None:
    """
    Validate MULTIPLE_CHOICE and MULTIPLE_RESPONSES questions.
    Follows Philippine board exam standards for distractor quality.
    
    Args:
        question_type: Either multiple_choice or multiple_responses
        choices: List of answer choices
        answers: The correct answer(s)
        
    Raises:
        ValueError: If validation fails
    """
    if not choices or len(choices) < 2:
        raise ValueError(f"{question_type} questions must have at least 2 choices.")
    
    # Board exam standard: 4 choices for multiple choice
    if question_type == "multiple_choice" and len(choices) != 4:
        # Warning: Board exams typically use exactly 4 choices
        pass  # Could log warning here
    
    if answers is None:
        raise ValueError(f"{question_type} questions must have correct_answers.")
    
    if question_type == "multiple_choice":
        if isinstance(answers, list):
            raise ValueError("multiple_choice correct_answers must be a single string.")
        if answers not in choices:
            raise ValueError("multiple_choice correct_answers must be one of the choices.")
    
    elif question_type == "multiple_responses":
        if not isinstance(answers, list):
            raise ValueError("multiple_responses correct_answers must be a list of strings.")
        if len(answers) < 2:
            raise ValueError("multiple_responses correct_answers must have at least 2 items.")
        if not all(ans in choices for ans in answers):
            raise ValueError("All correct_answers must be in choices.")
        # Board exam guideline: Not all choices should be correct
        if len(answers) == len(choices):
            raise ValueError("multiple_responses cannot have all choices as correct answers.")


def validate_true_false(answers: Optional[Union[str, bool]]) -> None:
    """
    Validate TRUE_FALSE questions.
    
    Args:
        answers: The correct answer
        
    Raises:
        ValueError: If answer is not a boolean
    """
    if not isinstance(answers, bool):
        raise ValueError("true_false correct_answers must be a boolean.")


def validate_text_answer(
    question_type: str, 
    answers: Optional[Union[str, bool, List[str]]]
) -> None:
    """
    Validate SHORT_ANSWER, FILL_IN_THE_BLANK, and RATIONALE questions.
    
    Args:
        question_type: The type of question
        answers: The correct answer
        
    Raises:
        ValueError: If answer is not a string or is empty
    """
    if not isinstance(answers, str):
        raise ValueError(f"{question_type} correct_answers must be a string.")
    if not answers.strip():
        raise ValueError(f"{question_type} correct_answers cannot be empty.")


def validate_list_answer(
    question_type: str, 
    answers: Optional[Union[str, bool, List[str]]]
) -> None:
    """
    Validate MATCHING and SEQUENCE questions.
    
    Args:
        question_type: The type of question
        answers: The correct answer(s)
        
    Raises:
        ValueError: If answers is not a list with at least 2 items
    """
    if not isinstance(answers, list) or len(answers) < 2:
        raise ValueError(
            f"{question_type} correct_answers must be a list with at least 2 items."
        )
    
    # Ensure no duplicates in answers
    if len(answers) != len(set(answers)):
        raise ValueError(f"{question_type} correct_answers cannot contain duplicates.")


def validate_competency_alignment(
    question_bloom: str,
    competency_bloom: str,
    strict: bool = True
) -> None:
    """
    Ensure question Bloom level aligns with TOS competency requirement.
    Critical for maintaining board exam content validity.
    
    Args:
        question_bloom: Bloom's taxonomy level of the question
        competency_bloom: Target Bloom's level from TOS competency
        strict: If True, must match exactly; if False, allows higher levels
        
    Raises:
        ValueError: If alignment is invalid
    """
    if strict:
        if question_bloom != competency_bloom:
            raise ValueError(
                f"Question Bloom level '{question_bloom}' must match "
                f"competency target '{competency_bloom}' for TOS alignment."
            )
    else:
        # Allow question to assess at higher cognitive level than minimum
        question_index = BLOOM_HIERARCHY.index(question_bloom)
        competency_index = BLOOM_HIERARCHY.index(competency_bloom)
        
        if question_index < competency_index:
            raise ValueError(
                f"Question Bloom level '{question_bloom}' cannot be lower than "
                f"competency requirement '{competency_bloom}'."
            )


def validate_question(
    question_type: str,
    taxonomy: str,
    choices: Optional[List[str]],
    answers: Optional[Union[str, bool, List[str]]],
    difficulty: Optional[str] = None,
    competency_bloom: Optional[str] = None
) -> None:
    """
    Main validation function for Philippine Psychometrician Board Exam questions.
    Orchestrates all validations to ensure item quality and TOS alignment.
    
    Args:
        question_type: The type of question (from QuestionType enum)
        taxonomy: The Bloom's taxonomy level (from BloomTaxonomy enum)
        choices: List of answer choices (if applicable)
        answers: The correct answer(s)
        difficulty: Difficulty level (Easy, Moderate, Difficult)
        competency_bloom: Target Bloom level from TOS competency
        
    Raises:
        ValueError: If any validation fails
    """
    # 1. Validate taxonomy appropriateness for question type
    validate_taxonomy(question_type, taxonomy)
    
    # 2. Validate difficulty-taxonomy alignment
    if difficulty:
        validate_difficulty_taxonomy_alignment(difficulty, taxonomy, strict=False)
    
    # 3. Validate competency alignment
    if competency_bloom:
        validate_competency_alignment(taxonomy, competency_bloom, strict=True)
    
    # 4. Validate answers based on question type
    if question_type in {"multiple_choice", "multiple_responses"}:
        validate_choices_based_question(question_type, choices, answers)
    
    elif question_type == "true_false":
        validate_true_false(answers)
    
    elif question_type in {"short_answer", "fill_in_the_blank", "rationale"}:
        validate_text_answer(question_type, answers)
    
    elif question_type in {"matching", "sequence"}:
        validate_list_answer(question_type, answers)


def validate_assessment_total_items(
    questions: List, 
    total_items: Optional[int]
) -> None:
    """
    Validate that total_items matches the number of questions.
    
    Args:
        questions: List of questions
        total_items: Expected total number of items
        
    Raises:
        ValueError: If total_items doesn't match questions length
    """
    if total_items is not None and len(questions) != total_items:
        raise ValueError(
            f"total_items ({total_items}) must match the number of questions "
            f"provided ({len(questions)})"
        )


def validate_assessment_distribution(
    questions: List[Dict],
    target_easy: float = 30.0,
    target_moderate: float = 40.0,
    target_difficult: float = 30.0,
    tolerance: float = 5.0
) -> Dict[str, Any]:
    """
    Validate that assessment follows board exam difficulty distribution.
    Standard: 30% Easy, 40% Moderate, 30% Difficult
    
    Args:
        questions: List of question objects with 'difficulty_level' field
        target_easy: Target percentage for easy questions
        target_moderate: Target percentage for moderate questions
        target_difficult: Target percentage for difficult questions
        tolerance: Acceptable deviation percentage
        
    Returns:
        Dict with validation results and actual distribution
        
    Raises:
        ValueError: If distribution deviates beyond tolerance
    """
    if not questions:
        raise ValueError("Cannot validate distribution for empty question list")
    
    total = len(questions)
    
    counts = {
        "Easy": sum(1 for q in questions if q.get("difficulty_level") == "Easy"),
        "Moderate": sum(1 for q in questions if q.get("difficulty_level") == "Moderate"),
        "Difficult": sum(1 for q in questions if q.get("difficulty_level") == "Difficult")
    }
    
    actual = {
        "Easy": (counts["Easy"] / total) * 100,
        "Moderate": (counts["Moderate"] / total) * 100,
        "Difficult": (counts["Difficult"] / total) * 100
    }
    
    deviations = {
        "Easy": abs(actual["Easy"] - target_easy),
        "Moderate": abs(actual["Moderate"] - target_moderate),
        "Difficult": abs(actual["Difficult"] - target_difficult)
    }
    
    violations = [
        level for level, dev in deviations.items() 
        if dev > tolerance
    ]
    
    result = {
        "is_valid": len(violations) == 0,
        "actual_distribution": actual,
        "target_distribution": {
            "Easy": target_easy,
            "Moderate": target_moderate,
            "Difficult": target_difficult
        },
        "deviations": deviations,
        "violations": violations
    }
    
    if violations:
        raise ValueError(
            f"Assessment difficulty distribution violates board exam standards. "
            f"Violations: {', '.join(violations)}. "
            f"Actual: Easy={actual['Easy']:.1f}%, Moderate={actual['Moderate']:.1f}%, "
            f"Difficult={actual['Difficult']:.1f}%"
        )
    
    return result