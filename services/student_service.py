from services.crud_services import read_one, update, read_query
from services.inference_service import readiness_classifier
from database.models import PersonalReadinessLevel
from fastapi import HTTPException

async def update_student_readiness(user_id: str):
    """
    Aggregates student data, runs it through the ONNX model, 
    and updates their PersonalReadinessLevel in Firestore.
    """
    # 1. Fetch Student Profile
    user_profile = await read_one("user_profiles", user_id)
    if not user_profile or not user_profile.get("student_info"):
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    student_info = user_profile["student_info"]
    
    # 2. Extract Features for AI
    # Example features: [avg_score, completion_rate, timeliness_score, total_time_spent]
    # We derive these from the existing data in Firestore
    
    # (Mock calculation - replace with actual aggregation logic later)
    avg_score = 75.0 # Placeholder
    completion_rate = student_info.get("progress_report", [{}])[0].get("overall_completeness", 0)
    timeliness = student_info.get("timeliness", 0)
    
    features = [avg_score, float(completion_rate), float(timeliness)]
    
    # 3. Run Inference (Lightweight ONNX)
    try:
        # Expected output: [1] or [2] or [3] or [4] corresponding to the Enum
        prediction = readiness_classifier.predict(features)
        predicted_level_int = int(prediction[0][0]) # Assuming model returns shape (1,1)
        
        # Map int to Enum
        level_map = {
            1: PersonalReadinessLevel.VERY_LOW,
            2: PersonalReadinessLevel.LOW,
            3: PersonalReadinessLevel.MODERATE,
            4: PersonalReadinessLevel.HIGH
        }
        new_level = level_map.get(predicted_level_int, PersonalReadinessLevel.MODERATE)
        
        # 4. Update Database
        student_info["personal_readiness"] = new_level
        await update("user_profiles", user_id, {"student_info": student_info})
        
        return {
            "user_id": user_id,
            "new_readiness_level": new_level,
            "ai_confidence": "High (ONNX Local)"
        }
        
    except FileNotFoundError:
        # Fallback if model isn't trained yet
        return {"status": "AI Model missing, readiness not updated."}
    except Exception as e:
        print(f"Inference Error: {e}")
        return {"status": "Error calculating readiness"}