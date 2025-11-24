# services/question_validator.py
from typing import List, Optional, Union, Set, Dict


# Taxonomy mapping configuration
TYPE_TO_TAXONOMY: Dict[str, Set[str]] = {
    "MULTIPLE_CHOICE": {"REMEMBERING", "UNDERSTANDING", "APPLYING"},
    "MULTIPLE_RESPONSES": {"ANALYZING", "EVALUATING", "CREATING"},
    "TRUE_FALSE": {"REMEMBERING", "UNDERSTANDING"},
    "SHORT_ANSWER": {"UNDERSTANDING", "APPLYING", "ANALYZING"},
    "FILL_IN_THE_BLANK": {"REMEMBERING", "UNDERSTANDING"},
    "MATCHING": {"REMEMBERING", "UNDERSTANDING"},
    "SEQUENCE": {"APPLYING", "ANALYZING"},
    "RATIONALE": {"EVALUATING", "CREATING"},
}


def validate_taxonomy(question_type: str, taxonomy: str) -> None:
    """
    Validate that the taxonomy is appropriate for the question type.
    
    Args:
        question_type: The type of question
        taxonomy: The Bloom's taxonomy level
        
    Raises:
        ValueError: If taxonomy is not valid for the question type
    """
    allowed_taxonomies = TYPE_TO_TAXONOMY.get(question_type, set())
    if taxonomy not in allowed_taxonomies:
        raise ValueError(
            f"Taxonomy '{taxonomy}' is not valid for question type '{question_type}'"
        )


def validate_choices_based_question(
    question_type: str,
    choices: Optional[List[str]],
    answers: Optional[Union[str, List[str]]]
) -> None:
    """
    Validate MULTIPLE_CHOICE and MULTIPLE_RESPONSES questions.
    
    Args:
        question_type: Either MULTIPLE_CHOICE or MULTIPLE_RESPONSES
        choices: List of answer choices
        answers: The correct answer(s)
        
    Raises:
        ValueError: If validation fails
    """
    if not choices or len(choices) < 2:
        raise ValueError(f"{question_type} questions must have at least 2 choices.")
    
    if answers is None:
        raise ValueError(f"{question_type} questions must have correct_answers.")
    
    if question_type == "MULTIPLE_CHOICE":
        if isinstance(answers, list):
            raise ValueError("MULTIPLE_CHOICE correct_answers must be a single string.")
        if answers not in choices:
            raise ValueError("MULTIPLE_CHOICE correct_answers must be one of the choices.")
    
    elif question_type == "MULTIPLE_RESPONSES":
        if not isinstance(answers, list):
            raise ValueError("MULTIPLE_RESPONSES correct_answers must be a list of strings.")
        if len(answers) < 2:
            raise ValueError("MULTIPLE_RESPONSES correct_answers must have at least 2 items.")
        if not all(ans in choices for ans in answers):
            raise ValueError("All correct_answers must be in choices.")


def validate_true_false(answers: Optional[Union[str, bool]]) -> None:
    """
    Validate TRUE_FALSE questions.
    
    Args:
        answers: The correct answer
        
    Raises:
        ValueError: If answer is not a boolean
    """
    if not isinstance(answers, bool):
        raise ValueError("TRUE_FALSE correct_answers must be a boolean.")


def validate_text_answer(question_type: str, answers: Optional[Union[str, bool, List[str]]]) -> None:
    """
    Validate SHORT_ANSWER, FILL_IN_THE_BLANK, and RATIONALE questions.
    
    Args:
        question_type: The type of question
        answers: The correct answer
        
    Raises:
        ValueError: If answer is not a string
    """
    if not isinstance(answers, str):
        raise ValueError(f"{question_type} correct_answers must be a string.")


def validate_list_answer(question_type: str, answers: Optional[Union[str, bool, List[str]]]) -> None:
    """
    Validate MATCHING and SEQUENCE questions.
    
    Args:
        question_type: The type of question
        answers: The correct answer(s)
        
    Raises:
        ValueError: If answers is not a list with at least 2 items
    """
    if not isinstance(answers, list) or len(answers) < 2:
        raise ValueError(f"{question_type} correct_answers must be a list with at least 2 items.")


def validate_question(
    question_type: str,
    taxonomy: str,
    choices: Optional[List[str]],
    answers: Optional[Union[str, bool, List[str]]]
) -> None:
    """
    Main validation function that orchestrates all validations.
    
    Args:
        question_type: The type of question
        taxonomy: The Bloom's taxonomy level
        choices: List of answer choices (if applicable)
        answers: The correct answer(s)
        
    Raises:
        ValueError: If any validation fails
    """
    # Validate taxonomy
    validate_taxonomy(question_type, taxonomy)
    
    # Validate answers based on question type
    if question_type in {"MULTIPLE_CHOICE", "MULTIPLE_RESPONSES"}:
        validate_choices_based_question(question_type, choices, answers)
    
    elif question_type == "TRUE_FALSE":
        validate_true_false(answers)
    
    elif question_type in {"SHORT_ANSWER", "FILL_IN_THE_BLANK", "RATIONALE"}:
        validate_text_answer(question_type, answers)
    
    elif question_type in {"MATCHING", "SEQUENCE"}:
        validate_list_answer(question_type, answers)

def validate_assessment_total_items(questions: List, total_items: Optional[int]) -> None:
    """
    Validate that total_items matches the number of questions.
    
    Args:
        questions: List of questions
        total_items: Expected total number of items
        
    Raises:
        ValueError: If total_items doesn't match questions length
    """
    if total_items is not None and len(questions) != total_items:
        raise ValueError("total_items must match the number of questions provided")