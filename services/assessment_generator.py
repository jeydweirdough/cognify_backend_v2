import random
from typing import List
from database.models import AssessmentBlueprintSchema, QuestionSchema, AssessmentSchema, AssessmentType
from services.crud_services import read_query, create
from fastapi import HTTPException

async def generate_assessment_from_blueprint(blueprint: AssessmentBlueprintSchema, title: str, assessment_type: AssessmentType) -> AssessmentSchema:
    """
    Core Logic:
    1. Fetches questions from the Bank matching the Subject + Topics.
    2. Filters and Shuffles them based on Difficulty Distribution (30/40/30).
    3. Creates the Assessment record.
    """
    
    # 1. Fetch Pool of Questions for these Topics
    # We use the 'in' operator for Firestore (requires an index usually, or client-side filter if small)
    # Ideally, loop topics if 'in' query limit is hit.
    
    all_questions_raw = await read_query(
        collection_name="questions",
        filters=[
            ("subject_id", "==", blueprint.subject_id),
            # In a real app, you might need a more complex query or multiple queries for "topic_id in [...]"
        ]
    )
    
    # Filter by Topic in memory (for simplicity/robustness)
    topic_set = set(blueprint.target_topics)
    eligible_questions = [
        q for q in all_questions_raw 
        if q["data"].get("topic_id") in topic_set or q["data"].get("competency_id") in topic_set
    ]

    # 2. Categorize by Difficulty
    easy_pool = [q for q in eligible_questions if q["data"].get("difficulty_level") == "Easy"]
    mod_pool = [q for q in eligible_questions if q["data"].get("difficulty_level") == "Moderate"]
    diff_pool = [q for q in eligible_questions if q["data"].get("difficulty_level") == "Difficult"]

    # 3. Calculate Allocations
    total = blueprint.total_items
    n_easy = int(total * blueprint.easy_percentage)
    n_mod = int(total * blueprint.moderate_percentage)
    n_diff = total - (n_easy + n_mod) # Remainder goes to difficult or easy

    # 4. Select Questions (Random Sampling)
    selected_data = []
    
    if len(easy_pool) < n_easy or len(mod_pool) < n_mod or len(diff_pool) < n_diff:
        # Fallback: Not enough questions in bank. 
        # Strategy: Fill what we can, or throw error. Here we throw error to alert teacher.
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient questions in bank. Need: E:{n_easy}/M:{n_mod}/D:{n_diff}. Available: E:{len(easy_pool)}/M:{len(mod_pool)}/D:{len(diff_pool)}"
        )

    selected_data.extend(random.sample(easy_pool, n_easy))
    selected_data.extend(random.sample(mod_pool, n_mod))
    selected_data.extend(random.sample(diff_pool, n_diff))

    # Convert back to Schema (and flatten the ID)
    final_questions = []
    for item in selected_data:
        q_data = item["data"]
        q_data["id"] = item["id"]
        final_questions.append(QuestionSchema(**q_data))

    # 5. Create the Assessment Object
    assessment_payload = AssessmentSchema(
        id="", # Placeholder, will be set by DB
        title=title,
        type=assessment_type,
        subject_id=blueprint.subject_id,
        blueprint=blueprint,
        questions=final_questions,
        total_items=len(final_questions)
    )
    
    # 6. Save to DB
    saved = await create("assessments", assessment_payload.model_dump(exclude={"id"}))
    assessment_payload.id = saved["id"]
    
    return assessment_payload