# services/adaptability_service.py
from typing import Dict, List
from services.crud_services import read_query, read_one, update
from datetime import datetime, timedelta
import statistics

async def analyze_study_behavior(user_id: str) -> Dict:
    """
    Deep analysis of student's study behavior patterns.
    Tracks reading speed, focus, interruptions, and time preferences.
    """
    # Get all completed study sessions
    sessions = await read_query("study_logs", [
        ("user_id", "==", user_id),
        ("completion_status", "==", "completed")
    ])
    
    if not sessions:
        return {
            "status": "insufficient_data",
            "message": "Not enough study sessions to analyze behavior",
            "sessions_count": 0
        }
    
    # Categorize by resource type
    module_sessions = [s for s in sessions if s["data"].get("resource_type") == "module"]
    assessment_sessions = [s for s in sessions if s["data"].get("resource_type") == "assessment"]
    
    # Analyze module reading behavior
    module_analysis = analyze_reading_behavior(module_sessions)
    
    # Analyze assessment taking behavior
    assessment_analysis = analyze_assessment_behavior(assessment_sessions)
    
    # Determine study time preferences
    time_preferences = determine_time_preferences(sessions)
    
    # Calculate focus quality
    focus_metrics = calculate_focus_metrics(sessions)
    
    # Determine learning pace
    learning_pace = determine_learning_pace(module_analysis, assessment_analysis)
    
    return {
        "user_id": user_id,
        "total_sessions": len(sessions),
        "module_behavior": module_analysis,
        "assessment_behavior": assessment_analysis,
        "time_preferences": time_preferences,
        "focus_metrics": focus_metrics,
        "learning_pace": learning_pace,
        "recommendations": generate_adaptive_recommendations(
            module_analysis, 
            assessment_analysis, 
            focus_metrics,
            learning_pace
        )
    }


def analyze_reading_behavior(sessions: List[Dict]) -> Dict:
    """
    Analyze how student reads modules.
    """
    if not sessions:
        return {"status": "no_data"}
    
    durations = [s["data"].get("duration_seconds", 0) / 60 for s in sessions]
    interruptions = [s["data"].get("interruptions_count", 0) for s in sessions]
    
    # Detect if student reads in chunks
    reading_pattern = "continuous"
    if statistics.mean(interruptions) > 3:
        reading_pattern = "chunked"  # Frequently interrupted
    elif statistics.mean(durations) < 15:
        reading_pattern = "quick_scanner"  # Short sessions
    
    return {
        "average_reading_time_minutes": round(statistics.mean(durations), 2),
        "median_reading_time_minutes": round(statistics.median(durations), 2),
        "total_reading_time_hours": round(sum(durations) / 60, 2),
        "average_interruptions": round(statistics.mean(interruptions), 2),
        "reading_pattern": reading_pattern,
        "sessions_with_breaks": sum(1 for i in interruptions if i > 2),
        "continuous_sessions": sum(1 for i in interruptions if i <= 1)
    }


def analyze_assessment_behavior(sessions: List[Dict]) -> Dict:
    """
    Analyze how student takes assessments.
    """
    if not sessions:
        return {"status": "no_data"}
    
    durations = [s["data"].get("duration_seconds", 0) / 60 for s in sessions]
    
    # Determine assessment pace
    avg_duration = statistics.mean(durations)
    
    if avg_duration < 15:
        pace = "rushed"
    elif avg_duration > 45:
        pace = "thorough"
    else:
        pace = "moderate"
    
    return {
        "average_assessment_time_minutes": round(statistics.mean(durations), 2),
        "median_assessment_time_minutes": round(statistics.median(durations), 2),
        "shortest_time_minutes": round(min(durations), 2),
        "longest_time_minutes": round(max(durations), 2),
        "assessment_pace": pace,
        "total_assessments_taken": len(sessions)
    }


def determine_time_preferences(sessions: List[Dict]) -> Dict:
    """
    Identify when student prefers to study.
    """
    hour_distribution = {
        "morning": 0,    # 6am - 12pm
        "afternoon": 0,  # 12pm - 6pm
        "evening": 0,    # 6pm - 10pm
        "night": 0       # 10pm - 6am
    }
    
    for session in sessions:
        start_time = session["data"].get("start_time")
        if not start_time:
            continue
        
        hour = start_time.hour if hasattr(start_time, 'hour') else 12
        
        if 6 <= hour < 12:
            hour_distribution["morning"] += 1
        elif 12 <= hour < 18:
            hour_distribution["afternoon"] += 1
        elif 18 <= hour < 22:
            hour_distribution["evening"] += 1
        else:
            hour_distribution["night"] += 1
    
    # Find preferred time
    preferred = max(hour_distribution, key=hour_distribution.get)
    
    return {
        "distribution": hour_distribution,
        "preferred_time": preferred,
        "recommendation": get_time_recommendation(preferred)
    }


def get_time_recommendation(preferred_time: str) -> str:
    """
    Provide recommendation based on study time preference.
    """
    recommendations = {
        "morning": "Morning learner - best retention in AM hours. Schedule important topics early.",
        "afternoon": "Afternoon learner - peak focus after lunch. Good for complex topics.",
        "evening": "Evening learner - studies well after day activities. Consistent schedule recommended.",
        "night": "Night learner - consider earlier study times for better retention."
    }
    return recommendations.get(preferred_time, "Maintain consistent study schedule")


def calculate_focus_metrics(sessions: List[Dict]) -> Dict:
    """
    Calculate focus and attention metrics.
    """
    interruptions = [s["data"].get("interruptions_count", 0) for s in sessions]
    idle_times = [s["data"].get("idle_time_seconds", 0) / 60 for s in sessions]
    
    avg_interruptions = statistics.mean(interruptions) if interruptions else 0
    avg_idle = statistics.mean(idle_times) if idle_times else 0
    
    # Determine focus level
    if avg_interruptions < 2 and avg_idle < 5:
        focus_level = "High"
    elif avg_interruptions < 5 and avg_idle < 15:
        focus_level = "Medium"
    else:
        focus_level = "Low"
    
    return {
        "average_interruptions": round(avg_interruptions, 2),
        "average_idle_minutes": round(avg_idle, 2),
        "focus_level": focus_level,
        "distraction_index": round((avg_interruptions + avg_idle) / 2, 2)
    }


def determine_learning_pace(module_analysis: Dict, assessment_analysis: Dict) -> str:
    """
    Determine if student is a fast, standard, or slow learner.
    """
    if module_analysis.get("status") == "no_data":
        return "Standard"
    
    avg_reading = module_analysis.get("average_reading_time_minutes", 30)
    avg_assessment = assessment_analysis.get("average_assessment_time_minutes", 30)
    
    # Fast learners: quick reading + quick assessments
    if avg_reading < 20 and avg_assessment < 20:
        return "Fast"
    
    # Slow learners: slow reading + thorough assessments
    elif avg_reading > 40 or avg_assessment > 40:
        return "Slow"
    
    return "Standard"


def generate_adaptive_recommendations(
    module_analysis: Dict,
    assessment_analysis: Dict,
    focus_metrics: Dict,
    learning_pace: str
) -> List[str]:
    """
    Generate personalized recommendations based on behavior analysis.
    """
    recommendations = []
    
    # Reading behavior recommendations
    reading_pattern = module_analysis.get("reading_pattern")
    if reading_pattern == "chunked":
        recommendations.append("You study in chunks. Break modules into 15-minute segments.")
    elif reading_pattern == "quick_scanner":
        recommendations.append("You scan quickly. Consider deeper reading for better retention.")
    
    # Assessment behavior recommendations
    assessment_pace = assessment_analysis.get("assessment_pace")
    if assessment_pace == "rushed":
        recommendations.append("You complete assessments quickly. Review answers before submitting.")
    elif assessment_pace == "thorough":
        recommendations.append("You take your time with assessments. Good for accuracy!")
    
    # Focus recommendations
    focus_level = focus_metrics.get("focus_level")
    if focus_level == "Low":
        recommendations.append("High distraction detected. Try 25-minute Pomodoro sessions.")
    elif focus_level == "High":
        recommendations.append("Excellent focus! You can handle longer study sessions.")
    
    # Pace recommendations
    if learning_pace == "Fast":
        recommendations.append("Fast learner. Challenge yourself with difficult topics.")
    elif learning_pace == "Slow":
        recommendations.append("Thorough learner. Allow extra time for complex topics.")
    
    return recommendations


async def update_behavior_profile(user_id: str):
    """
    Update student's behavior profile based on latest analysis.
    Called after each study session ends.
    """
    analysis = await analyze_study_behavior(user_id)
    
    if analysis.get("status") == "insufficient_data":
        return
    
    # Extract key metrics
    module_behavior = analysis.get("module_behavior", {})
    time_prefs = analysis.get("time_preferences", {})
    focus = analysis.get("focus_metrics", {})
    
    behavior_profile = {
        "average_session_length": module_behavior.get("average_reading_time_minutes", 0),
        "preferred_study_time": time_prefs.get("preferred_time", "Any"),
        "interruption_frequency": focus.get("focus_level", "Medium"),
        "learning_pace": analysis.get("learning_pace", "Standard"),
        "last_updated": datetime.utcnow()
    }
    
    # Update in database
    profile = await read_one("user_profiles", user_id)
    if profile:
        student_info = profile.get("student_info", {})
        student_info["behavior_profile"] = behavior_profile
        
        await update("user_profiles", user_id, {"student_info": student_info})
    
    return behavior_profile


async def get_adaptive_content(user_id: str, subject_id: str) -> Dict:
    """
    Return personalized content delivery strategy based on behavior.
    """
    profile = await read_one("user_profiles", user_id)
    behavior = profile.get("student_info", {}).get("behavior_profile", {})
    
    learning_pace = behavior.get("learning_pace", "Standard")
    focus_level = behavior.get("interruption_frequency", "Medium")
    
    # Adapt content delivery
    if learning_pace == "Fast" and focus_level == "High":
        strategy = {
            "module_chunk_size": "full",
            "assessment_difficulty": "increase_gradually",
            "recommended_session_length": "45-60 minutes",
            "break_frequency": "every_60_minutes"
        }
    elif learning_pace == "Slow" or focus_level == "Low":
        strategy = {
            "module_chunk_size": "small_sections",
            "assessment_difficulty": "build_confidence_first",
            "recommended_session_length": "15-25 minutes",
            "break_frequency": "every_25_minutes"
        }
    else:
        strategy = {
            "module_chunk_size": "medium_sections",
            "assessment_difficulty": "standard",
            "recommended_session_length": "30-45 minutes",
            "break_frequency": "every_45_minutes"
        }
    
    return {
        "user_id": user_id,
        "subject_id": subject_id,
        "behavior_profile": behavior,
        "content_strategy": strategy,
        "personalized_tips": generate_adaptive_recommendations(
            {"reading_pattern": "continuous"},
            {"assessment_pace": "moderate"},
            {"focus_level": focus_level},
            learning_pace
        )
    }