from services.crud_services import read_one, update, read_query
from services.inference_service import readiness_classifier
from database.models import PersonalReadinessLevel
from database.enums import AssessmentType
from fastapi import HTTPException
import numpy as np

async def get_student_next_action(user_id: str):
    """
    Determines the next assessment or action for the student.
    Priority:
    1. Diagnostic (If new user OR milestone reached)
    2. Post-Assessment (If a subject is finished)
    3. Quiz (General practice)
    """
    user_profile = await read_one("user_profiles", user_id)
    if not user_profile:
        return None

    student_info = user_profile.get("student_info", {})
    progress_report = student_info.get("progress_report", [])
    
    # 1. CHECK INITIAL DIAGNOSTIC (New User)
    # If no progress at all, they MUST take the Diagnostic
    if not progress_report:
        # Check if they already took it (this flag should be set on submission)
        if not user_profile.get("has_taken_diagnostic"):
            return {
                "type": AssessmentType.DIAGNOSTIC,
                "title": "Diagnostic Examination",
                "reason": "Welcome! Take this diagnostic test to assess your baseline knowledge."
            }

    # 2. CHECK MILESTONE DIAGNOSTIC (Mock Board Exam)
    # Trigger after finishing all 4 core subjects
    completed_subjects_count = len([
        p for p in progress_report 
        if p.get("modules_completeness", 0) >= 90
    ])
    
    last_diag = student_info.get("last_diagnostic_milestone", 0)
    
    if completed_subjects_count >= 4 and last_diag < 4:
        return {
            "type": AssessmentType.DIAGNOSTIC,
            "title": "Mock Board Exam",
            "reason": "You've completed all subjects! It's time for a full simulation."
        }

    # 3. CHECK POST-ASSESSMENT (Subject Completion)
    for subject_report in progress_report:
        if subject_report.get("modules_completeness", 0) >= 100:
            if subject_report.get("assessment_completeness", 0) < 100: 
                return {
                    "type": AssessmentType.POST_ASSESSMENT,
                    "subject_id": subject_report.get("subject_id"),
                    "title": "Subject Post-Test",
                    "reason": "Prove your mastery of this subject to unlock the badge."
                }

    # 4. DEFAULT
    return {
        "type": AssessmentType.QUIZ,
        "title": "Daily Quiz",
        "reason": "Keep your streak alive!"
    }

async def update_student_readiness(user_id: str):
    # (Existing readiness logic from previous turns - preserved)
    user_profile = await read_one("user_profiles", user_id)
    if not user_profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    student_info = user_profile.get("student_info", {})
    progress_report = student_info.get("progress_report", [])
    
    total_subjects = len(progress_report)
    
    if total_subjects == 0:
        avg_module_completion = 0.0
        avg_assessment_score = 0.0
    else:
        sum_mod = sum([float(r.get("modules_completeness", 0)) for r in progress_report])
        avg_module_completion = sum_mod / total_subjects

        sum_assess = sum([float(r.get("assessment_completeness", 0)) for r in progress_report])
        avg_assessment_score = sum_assess / total_subjects

    timeliness_score = student_info.get("timeliness", 80.0) 
    features = [avg_assessment_score, avg_module_completion, float(timeliness_score)]
    
    new_level = PersonalReadinessLevel.VERY_LOW
    try:
        prediction = readiness_classifier.predict(features)
        predicted_val = int(prediction[0][0])
        level_map = {1: PersonalReadinessLevel.VERY_LOW, 2: PersonalReadinessLevel.LOW, 3: PersonalReadinessLevel.MODERATE, 4: PersonalReadinessLevel.HIGH}
        new_level = level_map.get(predicted_val, PersonalReadinessLevel.MODERATE)
    except Exception:
        weighted_score = (avg_module_completion * 0.4) + (avg_assessment_score * 0.6)
        if weighted_score >= 85: new_level = PersonalReadinessLevel.HIGH
        elif weighted_score >= 60: new_level = PersonalReadinessLevel.MODERATE
        elif weighted_score >= 30: new_level = PersonalReadinessLevel.LOW
        else: new_level = PersonalReadinessLevel.VERY_LOW

    if "student_info" not in user_profile: user_profile["student_info"] = {}
    user_profile["student_info"]["personal_readiness"] = new_level
    user_profile["personal_readiness"] = new_level 
    
    await update("user_profiles", user_id, user_profile)
    
    return {
        "user_id": user_id,
        "new_readiness_level": new_level,
        "metrics": {"avg_reading": round(avg_module_completion, 1), "avg_assessment": round(avg_assessment_score, 1)}
    }